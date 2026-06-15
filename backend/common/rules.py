"""Lightweight threshold rules evaluated on each ingestion frame.

Real systems would source these from the signal_registry + DTC tables; this
keeps a small, explicit set so proactive alerts work end-to-end out of the box.
"""
from __future__ import annotations

from collections.abc import Iterable

from .models import Alert, SignalReading

# signal_name -> (critical_above, warning_above, human label)
_THRESHOLDS: dict[str, tuple[float | None, float | None, str]] = {
    "coolant_temp": (110.0, 100.0, "Coolant temperature high"),
    "engine_speed": (6500.0, 5500.0, "Engine RPM high"),
    "vehicle_speed": (160.0, 120.0, "Vehicle speed high"),
}


def evaluate(signals: Iterable[SignalReading]) -> list[Alert]:
    """Return alerts triggered by the given signal readings."""
    out: list[Alert] = []
    for s in signals:
        rule = _THRESHOLDS.get(s.name)
        if not rule:
            continue
        crit, warn, label = rule
        if crit is not None and s.value >= crit:
            out.append(Alert(code=f"THRESH_{s.name}", severity="critical",
                             message=f"{label} ({s.value}{s.unit or ''})",
                             signal_name=s.name, value=s.value))
        elif warn is not None and s.value >= warn:
            out.append(Alert(code=f"THRESH_{s.name}", severity="warning",
                             message=f"{label} ({s.value}{s.unit or ''})",
                             signal_name=s.name, value=s.value))
    return out
