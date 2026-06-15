"""Data-access helpers backing the MCP tools.

Keeps SQL/Redis access out of the tool definitions so the tool layer stays a
thin, well-documented surface for the LLM.
"""
from __future__ import annotations

import json

from common import keys
from common.clients import get_pg_pool, get_redis


# ----------------------------------------------------------------------------
# Redis (hot path)
# ----------------------------------------------------------------------------
async def latest_snapshot(car_id: str) -> dict | None:
    raw = await get_redis().get(keys.live(car_id))
    return json.loads(raw) if raw else None


async def signal_latest(car_id: str, signal_name: str) -> dict | None:
    raw = await get_redis().get(keys.signal(car_id, signal_name))
    return json.loads(raw) if raw else None


async def active_alerts(car_id: str) -> list[dict]:
    raw = await get_redis().get(keys.alerts(car_id))
    return json.loads(raw) if raw else []


async def clear_alert(car_id: str, code: str | None) -> int:
    """Acknowledge one alert (by code) or all alerts. Returns remaining count."""
    r = get_redis()
    raw = await r.get(keys.alerts(car_id))
    alerts = json.loads(raw) if raw else []
    if code is None:
        remaining: list[dict] = []
    else:
        remaining = [a for a in alerts if a.get("code") != code]
    if remaining:
        await r.set(keys.alerts(car_id), json.dumps(remaining))
    else:
        await r.delete(keys.alerts(car_id))
    return len(remaining)


# ----------------------------------------------------------------------------
# TimescaleDB (cold path)
# ----------------------------------------------------------------------------
# Choose the cheapest continuous aggregate that satisfies the window.
def _agg_view(window_minutes: float) -> tuple[str, str]:
    if window_minutes > 24 * 60:
        return "telemetry_1hour", "avg_value"
    if window_minutes > 3 * 60:
        return "telemetry_5min", "avg_value"
    return "telemetry_1min", "avg_value"


async def signal_timeline(car_id: str, signal_name: str, minutes: int) -> list[dict]:
    view, col = _agg_view(minutes)
    sql = f"""
        SELECT bucket AS time, {col} AS value, min_value, max_value
        FROM {view}
        WHERE car_id = $1 AND signal_name = $2
          AND bucket >= now() - ($3 || ' minutes')::interval
        ORDER BY bucket
    """
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, car_id, signal_name, str(minutes))
    return [dict(r) for r in rows]


async def trip_summary(car_id: str, trip_id: str) -> dict | None:
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        trip = await conn.fetchrow(
            "SELECT trip_id, car_id, started_at, ended_at FROM trips WHERE trip_id = $1",
            trip_id,
        )
        if not trip:
            return None
        stats = await conn.fetch(
            """
            SELECT signal_name, avg(value) AS avg, min(value) AS min, max(value) AS max
            FROM car_telemetry
            WHERE car_id = $1 AND trip_id = $2
            GROUP BY signal_name
            """,
            car_id, trip_id,
        )
    return {
        "trip": dict(trip),
        "signals": {r["signal_name"]: {"avg": r["avg"], "min": r["min"], "max": r["max"]}
                    for r in stats},
    }


async def list_cars(owner_email: str | None = None) -> list[dict]:
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        if owner_email:
            rows = await conn.fetch(
                """
                SELECT c.* FROM cars c JOIN users u ON u.user_id = c.owner_id
                WHERE u.email = $1
                """,
                owner_email,
            )
        else:
            rows = await conn.fetch("SELECT * FROM cars")
    return [dict(r) for r in rows]


async def trip_history(car_id: str, limit: int = 20) -> list[dict]:
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT trip_id, started_at, ended_at FROM trips
            WHERE car_id = $1 ORDER BY started_at DESC LIMIT $2
            """,
            car_id, limit,
        )
    return [dict(r) for r in rows]


async def linear_forecast(car_id: str, signal_name: str, minutes: int) -> dict | None:
    """Cheap linear-trend extrapolation over recent 1-min aggregates."""
    series = await signal_timeline(car_id, signal_name, minutes)
    pts = [(i, float(r["value"])) for i, r in enumerate(series) if r["value"] is not None]
    if len(pts) < 3:
        return None
    n = len(pts)
    sx = sum(x for x, _ in pts)
    sy = sum(y for _, y in pts)
    sxx = sum(x * x for x, _ in pts)
    sxy = sum(x * y for x, y in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    last_x = pts[-1][0]
    projected = slope * (last_x + n) + intercept  # ~one window ahead
    return {
        "signal_name": signal_name,
        "slope_per_bucket": slope,
        "current": pts[-1][1],
        "projected": projected,
        "samples": n,
    }
