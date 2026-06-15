"""Telemetry simulator — drives the ingestion API at ~5 Hz with plausible OBD data.

Usage:
    python -m tools.simulator --car-id acc001 --rate 5 --duration 60
"""
from __future__ import annotations

import argparse
import asyncio
import math
import random
import uuid
from datetime import datetime, timezone

import httpx

INGEST_URL_DEFAULT = "http://localhost:8000/live-car-data"

# signal_name -> (pid, unit)
_SIGNALS = {
    "engine_speed": ("0C", "rpm"),
    "vehicle_speed": ("0D", "km/h"),
    "coolant_temp": ("05", "degC"),
    "throttle_position": ("11", "%"),
    "intake_temp": ("0F", "degC"),
    "maf": ("10", "g/s"),
    "fuel_level": ("2F", "%"),
}


def _frame(car_id: str, trip_id: str, t: float, spike: bool) -> dict:
    speed = max(0.0, 60 + 40 * math.sin(t / 20) + random.uniform(-5, 5))
    rpm = 800 + speed * 35 + random.uniform(-100, 100)
    coolant = 88 + 4 * math.sin(t / 40) + random.uniform(-1, 1)
    if spike:                       # occasionally push coolant into alert range
        coolant = 112 + random.uniform(0, 5)
    throttle = min(100.0, max(0.0, speed / 1.2 + random.uniform(-5, 5)))

    values = {
        "engine_speed": rpm,
        "vehicle_speed": speed,
        "coolant_temp": coolant,
        "throttle_position": throttle,
        "intake_temp": 30 + random.uniform(-2, 2),
        "maf": 5 + throttle / 5 + random.uniform(-1, 1),
        "fuel_level": max(0.0, 70 - t / 120),
    }
    signals = [
        {"name": n, "value": round(values[n], 2), "unit": u, "pid": pid}
        for n, (pid, u) in _SIGNALS.items()
    ]
    return {
        "car_id": car_id,
        "trip_id": trip_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "mil": spike,
    }


async def run(url: str, car_id: str, rate: float, duration: float) -> None:
    trip_id = str(uuid.uuid4())
    interval = 1.0 / rate
    n = int(duration * rate) if duration else None
    sent = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        t = 0.0
        while n is None or sent < n:
            spike = random.random() < 0.02
            try:
                resp = await client.post(url, json=_frame(car_id, trip_id, t, spike))
                if sent % 25 == 0:
                    print(f"[{sent}] -> {resp.status_code} {resp.json()}")
            except Exception as e:  # noqa: BLE001
                print("post failed:", e)
            sent += 1
            t += interval
            await asyncio.sleep(interval)


def main() -> None:
    p = argparse.ArgumentParser(description="Mater telemetry simulator")
    p.add_argument("--url", default=INGEST_URL_DEFAULT)
    p.add_argument("--car-id", default="acc001")
    p.add_argument("--rate", type=float, default=5.0, help="frames per second")
    p.add_argument("--duration", type=float, default=0, help="seconds (0 = forever)")
    args = p.parse_args()
    asyncio.run(run(args.url, args.car_id, args.rate, args.duration))


if __name__ == "__main__":
    main()
