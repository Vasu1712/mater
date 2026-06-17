"""WebSocket bridge: live-car-api stream -> Mater ingestion.

Subscribes to the connected-car WebSocket feed (``TELEMETRY_WS_URL``), which
emits a *grouped* telemetry payload, flattens each frame into the flat
``TelemetryFrame`` shape (registry signal names) and POSTs it to the ingestion
``/live-car-data`` endpoint. Reconnects with capped exponential backoff.

Usage:
    python -m tools.ws_adapter                # run forever (compose service)
    python -m tools.ws_adapter --once         # forward a single frame and exit
    python -m tools.ws_adapter --frames 50    # forward N frames and exit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

import httpx
import websockets

from common.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mater.ws_adapter")

# Grouped WS field -> (block, key, signal_name, pid, unit).
# Mirrors the signal_registry seed and the dashboard gauges.
_MAP: list[tuple[str, str, str, str, str]] = [
    ("powertrain",     "rpm",            "engine_speed",      "0C", "rpm"),
    ("powertrain",     "speed_kmh",      "vehicle_speed",     "0D", "km/h"),
    ("thermal_fluids", "coolant_temp_c", "coolant_temp",      "05", "degC"),
    ("powertrain",     "throttle_pct",   "throttle_position", "11", "%"),
    ("thermal_fluids", "intake_temp_c",  "intake_temp",       "0F", "degC"),
    ("powertrain",     "maf_gps",        "maf",               "10", "g/s"),
    ("thermal_fluids", "fuel_level_pct", "fuel_level",        "2F", "%"),
]


def _to_frame(grouped: dict) -> dict:
    """Flatten a grouped WS payload into the ingestion TelemetryFrame shape."""
    signals = []
    for block, key, name, pid, unit in _MAP:
        section = grouped.get(block) or {}
        if key in section and section[key] is not None:
            signals.append(
                {"name": name, "value": float(section[key]), "unit": unit, "pid": pid}
            )

    dtc = (grouped.get("safety_behavior") or {}).get("dtc")
    frame = {
        "car_id": settings.TELEMETRY_CAR_ID or grouped["car_id"],
        "car_name": grouped.get("car_name"),
        "timestamp": grouped.get("timestamp"),
        "signals": signals,
        "mil": dtc is not None,
    }
    if grouped.get("trip_id"):
        frame["trip_id"] = grouped["trip_id"]
    if grouped.get("geospatial"):
        frame["geospatial"] = grouped["geospatial"]
    if grouped.get("maintenance"):
        frame["maintenance"] = grouped["maintenance"]
    return frame


async def _stream(client: httpx.AsyncClient, max_frames: int | None) -> int:
    """Consume one WS connection until it closes. Returns frames forwarded."""
    sent = 0
    async with websockets.connect(settings.TELEMETRY_WS_URL, max_queue=8) as ws:
        log.info("connected to %s", settings.TELEMETRY_WS_URL)
        async for message in ws:
            try:
                frame = _to_frame(json.loads(message))
                resp = await client.post(settings.INGEST_URL, json=frame)
                resp.raise_for_status()
            except Exception:  # noqa: BLE001 - skip a bad frame, keep streaming
                log.exception("failed to forward frame")
            else:
                sent += 1
                if sent % 25 == 0:
                    log.info("forwarded %d frames", sent)
            if max_frames is not None and sent >= max_frames:
                return sent
    return sent


async def run(max_frames: int | None) -> None:
    backoff = 1.0
    total = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                total += await _stream(client, None if max_frames is None else max_frames - total)
            except Exception:  # noqa: BLE001 - connection error -> reconnect
                log.exception("stream error; reconnecting in %.0fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            else:
                backoff = 1.0  # clean close (e.g. server cycled) -> reconnect promptly
            if max_frames is not None and total >= max_frames:
                log.info("done: forwarded %d frames", total)
                return


def main() -> None:
    p = argparse.ArgumentParser(description="live-car-api WebSocket -> ingestion bridge")
    p.add_argument("--once", action="store_true", help="forward a single frame and exit")
    p.add_argument("--frames", type=int, default=0, help="forward N frames and exit (0 = forever)")
    args = p.parse_args()
    max_frames = 1 if args.once else (args.frames or None)
    asyncio.run(run(max_frames))


if __name__ == "__main__":
    main()
