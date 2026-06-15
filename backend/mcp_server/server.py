"""Mater Fast-MCP server — the 13-tool layer bridging the LLM to the data stores.

Tools 1-8 serve the Mater (driver) agent; tools 9-13 serve the Host (owner)
agent. Run with: ``python -m mcp_server.server`` (streamable-HTTP transport).
"""
from __future__ import annotations

from fastmcp import FastMCP

from common import knowledge
from common.config import settings

from . import queries
from .dtc import DTC_CODES

mcp = FastMCP("mater")


# =============================================================================
# Mater (driver) tools
# =============================================================================
@mcp.tool
async def get_latest_snapshot(car_id: str) -> dict:
    """Current full vehicle state from the Redis hot path (<1ms)."""
    snap = await queries.latest_snapshot(car_id)
    return snap or {"error": "no live data", "car_id": car_id}


@mcp.tool
async def get_signal_latest(car_id: str, signal_name: str) -> dict:
    """Latest value for a single signal (e.g. engine_speed) from Redis."""
    val = await queries.signal_latest(car_id, signal_name)
    return val or {"error": "no data", "car_id": car_id, "signal_name": signal_name}


@mcp.tool
async def get_signal_timeline(car_id: str, signal_name: str, minutes: int = 60) -> list[dict]:
    """Historical trend for a signal over the last N minutes (TimescaleDB aggregates)."""
    return await queries.signal_timeline(car_id, signal_name, minutes)


@mcp.tool
async def get_trip_summary(car_id: str, trip_id: str) -> dict:
    """Per-signal min/avg/max summary for one trip (TimescaleDB)."""
    res = await queries.trip_summary(car_id, trip_id)
    return res or {"error": "trip not found", "trip_id": trip_id}


@mcp.tool
async def search_knowledge(query: str, car_id: str, system: str | None = None,
                           limit: int = 5) -> list[dict]:
    """Semantic search over this vehicle's manuals, TSBs and mechanic logs (Qdrant)."""
    return knowledge.search(query, car_id, system=system, limit=limit)


@mcp.tool
async def check_active_alerts(car_id: str) -> list[dict]:
    """Currently active fault alerts from Redis (<1ms)."""
    return await queries.active_alerts(car_id)


@mcp.tool
async def predict_anomalies(car_id: str, signal_name: str, minutes: int = 60) -> dict:
    """Linear-trend extrapolation flagging an emerging anomaly for a signal."""
    res = await queries.linear_forecast(car_id, signal_name, minutes)
    return res or {"error": "insufficient history", "signal_name": signal_name}


@mcp.tool
async def get_dtc_info(code: str, car_id: str | None = None) -> dict:
    """Explain a diagnostic trouble code (DTC), preferring vehicle-specific docs."""
    if car_id:
        hits = knowledge.search(code, car_id, source="manual", limit=3)
        if hits:
            return {"code": code, "source": "knowledge", "results": hits}
    desc = DTC_CODES.get(code.upper())
    return {"code": code, "source": "builtin",
            "description": desc or "Unknown code; no documentation found."}


# =============================================================================
# Host (owner) tools
# =============================================================================
@mcp.tool
async def get_cars(owner_email: str | None = None) -> list[dict]:
    """Fleet management — list cars, optionally filtered by owner email (PostgreSQL)."""
    return await queries.list_cars(owner_email)


@mcp.tool
async def get_trip_history(car_id: str, limit: int = 20) -> list[dict]:
    """Recent trips for a vehicle (TimescaleDB)."""
    return await queries.trip_history(car_id, limit)


@mcp.tool
async def get_weekly_report(car_id: str) -> dict:
    """Weekly health report combining telemetry aggregates + knowledge context."""
    coolant = await queries.signal_timeline(car_id, "coolant_temp", 7 * 24 * 60)
    rpm = await queries.signal_timeline(car_id, "engine_speed", 7 * 24 * 60)
    alerts = await queries.active_alerts(car_id)
    notes = knowledge.search("recent maintenance and recurring issues", car_id, limit=3)
    return {
        "car_id": car_id,
        "coolant_temp_buckets": len(coolant),
        "peak_coolant": max((r["max_value"] for r in coolant), default=None),
        "peak_rpm": max((r["max_value"] for r in rpm), default=None),
        "active_alerts": alerts,
        "knowledge_notes": notes,
    }


@mcp.tool
async def get_maintenance_schedule(car_id: str) -> dict:
    """Service planning heuristics derived from accumulated runtime (TimescaleDB)."""
    pool_rows = await queries.signal_timeline(car_id, "vehicle_speed", 30 * 24 * 60)
    active_buckets = sum(1 for r in pool_rows if (r["value"] or 0) > 0)
    return {
        "car_id": car_id,
        "active_minutes_30d_estimate": active_buckets,
        "recommendations": [
            {"item": "Oil change", "due": "every 10,000 km or 6 months"},
            {"item": "Air filter", "due": "every 20,000 km"},
            {"item": "Brake inspection", "due": "every 20,000 km"},
        ],
    }


@mcp.tool
async def acknowledge_alert(car_id: str, code: str | None = None) -> dict:
    """Clear one alert by code, or all alerts when code is omitted (Redis)."""
    remaining = await queries.clear_alert(car_id, code)
    return {"car_id": car_id, "cleared": code or "all", "remaining": remaining}


def main() -> None:
    mcp.run(transport="http", host=settings.MCP_HOST, port=settings.MCP_PORT)


if __name__ == "__main__":
    main()
