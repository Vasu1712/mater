"""FastAPI ingestion service — the `/live-car-data` API.

Receives telemetry frames, fans them out to the Redis hot path, and runs the
background write-behind flusher to TimescaleDB.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.clients import close_pg_pool
from common.models import TelemetryFrame

from .flusher import run_flusher
from .writer import write_frame

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = asyncio.create_task(run_flusher(stop))
    try:
        yield
    finally:
        stop.set()
        await task
        await close_pg_pool()


app = FastAPI(title="Mater Ingestion", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/live-car-data")
async def live_car_data(frame: TelemetryFrame) -> dict:
    """Ingest one telemetry frame (~every 200ms per vehicle)."""
    alerts = await write_frame(frame)
    return {"ok": True, "signals": len(frame.signals), "alerts": alerts}
