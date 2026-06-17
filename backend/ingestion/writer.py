"""Hot-path write logic: a telemetry frame -> Redis (snapshot, signals,
alerts, MIL) and a write-behind buffer for TimescaleDB.

Implements plan.md §2.1 "Write Path (Every 200ms)".
"""
from __future__ import annotations

import json

from common import keys, rules
from common.clients import get_redis
from common.config import settings
from common.models import TelemetryFrame


async def write_frame(frame: TelemetryFrame) -> list[dict]:
    """Persist one frame to the hot path. Returns the active alert list."""
    r = get_redis()
    ts_iso = frame.timestamp.isoformat()

    snapshot = {
        "car_id": frame.car_id,
        "car_name": frame.car_name,
        "trip_id": frame.trip_id,
        "timestamp": ts_iso,
        "mil": frame.mil,
        "geospatial": frame.geospatial,
        "signals": {
            s.name: {"v": s.value, "u": s.unit, "t": ts_iso} for s in frame.signals
        },
    }

    alerts = [a.model_dump(mode="json") for a in rules.evaluate(frame.signals)]

    pipe = r.pipeline(transaction=False)

    # [1] full snapshot (overwrite)
    pipe.set(keys.live(frame.car_id), json.dumps(snapshot), ex=settings.LIVE_TTL_SECONDS)

    # [2] per-signal latest values
    for s in frame.signals:
        pipe.set(
            keys.signal(frame.car_id, s.name),
            json.dumps({"v": s.value, "u": s.unit, "t": ts_iso}),
            ex=settings.LIVE_TTL_SECONDS,
        )

    # MIL state (manual clear -> no TTL)
    if frame.mil:
        pipe.set(keys.mil(frame.car_id), "1")

    # Live threshold alerts: reconcile with this frame so they self-clear once
    # the signal returns to normal (latched DTC faults use the `mil` key instead).
    if alerts:
        pipe.set(keys.alerts(frame.car_id), json.dumps(alerts))
    else:
        pipe.delete(keys.alerts(frame.car_id))

    # Service metadata (slowly-changing -> no TTL). Carry car_name so the host
    # agent can name the vehicle in maintenance answers.
    if frame.maintenance:
        maint = {**frame.maintenance, "car_name": frame.car_name}
        pipe.set(keys.maintenance(frame.car_id), json.dumps(maint))

    # [3] write-behind buffer for TimescaleDB (one JSON row per signal)
    for s in frame.signals:
        row = {
            "time": ts_iso,
            "car_id": frame.car_id,
            "signal_name": s.name,
            "value": s.value,
            "unit": s.unit,
            "pid": s.pid,
            "trip_id": frame.trip_id,
            "quality": s.quality,
        }
        pipe.lpush(keys.ingest_queue(frame.car_id), json.dumps(row))

    await pipe.execute()
    return alerts
