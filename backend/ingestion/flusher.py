"""Background write-behind flush: Redis ingest queues -> car_telemetry.

Implements plan.md §2.1 "Background Flush (Every 1 Second)". Runs as part of
the ingestion service lifespan; pops batches off each car's queue and bulk
inserts into the hypertable via COPY.
"""
from __future__ import annotations

import asyncio
import json
import logging

from common import keys
from common.clients import get_pg_pool, get_redis
from common.config import settings

log = logging.getLogger("mater.flusher")

_COLUMNS = ("time", "car_id", "signal_name", "value", "unit", "pid", "trip_id", "quality")


async def _discover_queues() -> list[str]:
    r = get_redis()
    return [k async for k in r.scan_iter(match="car:*:ingest:queue")]


async def _flush_queue(queue_key: str) -> int:
    """Pop up to FLUSH_BATCH_SIZE rows from one queue and insert them."""
    r = get_redis()
    raw = await r.rpop(queue_key, settings.FLUSH_BATCH_SIZE)
    if not raw:
        return 0
    if isinstance(raw, str):  # redis returns a str when count is 1
        raw = [raw]

    records = []
    for item in raw:
        d = json.loads(item)
        records.append((
            d["time"], d["car_id"], d["signal_name"], float(d["value"]),
            d.get("unit"), d.get("pid"), d.get("trip_id"), d.get("quality", "normal"),
        ))

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        # asyncpg parses the ISO timestamp/uuid strings against the column types.
        await conn.copy_records_to_table(
            "car_telemetry", records=records, columns=_COLUMNS
        )
    return len(records)


async def flush_once() -> int:
    total = 0
    for q in await _discover_queues():
        try:
            total += await _flush_queue(q)
        except Exception:  # one bad queue shouldn't stall the rest
            log.exception("flush failed for %s", q)
    return total


async def run_flusher(stop: asyncio.Event) -> None:
    log.info("flusher started (interval=%.1fs)", settings.FLUSH_INTERVAL_SECONDS)
    while not stop.is_set():
        try:
            n = await flush_once()
            if n:
                log.debug("flushed %d rows", n)
        except Exception:
            log.exception("flush cycle error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.FLUSH_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
    log.info("flusher stopped")
