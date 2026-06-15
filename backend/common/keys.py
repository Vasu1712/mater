"""Redis key-schema helpers — single source of truth for the hot-path layout.

Mirrors the key schema documented in plan.md §2.1.
"""
from __future__ import annotations


def live(car_id: str) -> str:
    """Full telemetry JSON snapshot (TTL 300s)."""
    return f"car:{car_id}:live"


def signal(car_id: str, name: str) -> str:
    """Per-signal latest value `{"v","u","t"}` (TTL 300s)."""
    return f"car:{car_id}:sig:{name}"


def mil(car_id: str) -> str:
    """\"1\" if the check-engine light (MIL) is active (manual clear)."""
    return f"car:{car_id}:mil"


def alerts(car_id: str) -> str:
    """JSON array of active alerts (until acknowledged)."""
    return f"car:{car_id}:alerts"


def ingest_queue(car_id: str) -> str:
    """Write-behind list buffering rows for TimescaleDB."""
    return f"car:{car_id}:ingest:queue"
