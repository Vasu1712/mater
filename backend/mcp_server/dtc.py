"""Minimal built-in DTC dictionary used as a fallback for get_dtc_info().

The primary source is Qdrant (manuals/TSBs); this guarantees common codes
resolve even before any documents are ingested.
"""
from __future__ import annotations

DTC_CODES: dict[str, str] = {
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1). Often a failing "
             "catalytic converter or a downstream O2 sensor.",
    "P0300": "Random/Multiple Cylinder Misfire Detected.",
    "P0171": "System Too Lean (Bank 1).",
    "P0128": "Coolant Thermostat below regulating temperature.",
    "P0455": "Evaporative Emission System leak detected (large leak).",
}
