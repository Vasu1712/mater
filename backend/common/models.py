"""Pydantic models shared across ingestion and tooling."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SignalReading(BaseModel):
    """A single decoded OBD/VSS signal value."""

    name: str
    value: float
    unit: str | None = None
    pid: str | None = None
    quality: str = "normal"


class TelemetryFrame(BaseModel):
    """One ingestion frame from the vehicle (~every 200ms)."""

    car_id: str
    car_name: str | None = None
    trip_id: str | None = None
    timestamp: datetime = Field(default_factory=_now)
    signals: list[SignalReading]
    mil: bool = False
    # Live GPS block from the feed (latitude, longitude, heading_deg).
    geospatial: dict | None = None
    # Slowly-changing service metadata from the feed (last service, odometer…).
    maintenance: dict | None = None


class Alert(BaseModel):
    code: str                      # e.g. DTC "P0420" or rule id
    severity: str = "warning"      # info | warning | critical
    message: str
    signal_name: str | None = None
    value: float | None = None
    raised_at: datetime = Field(default_factory=_now)
