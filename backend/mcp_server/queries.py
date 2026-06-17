"""Data-access helpers backing the MCP tools.

Keeps SQL/Redis access out of the tool definitions so the tool layer stays a
thin, well-documented surface for the LLM.
"""
from __future__ import annotations

import json
from datetime import date

import httpx

from common import keys
from common.clients import get_pg_pool, get_redis

_COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _compass(deg: float) -> str:
    return _COMPASS[round(deg / 45) % 8]


async def _reverse_geocode(lat: float, lon: float) -> str | None:
    """Best-effort human-readable place via OpenStreetMap Nominatim."""
    try:
        async with httpx.AsyncClient(
            timeout=3.0, headers={"User-Agent": "mater-fleet/0.1"}
        ) as c:
            r = await c.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json", "zoom": 14},
            )
            if r.status_code == 200:
                return r.json().get("display_name")
    except Exception:  # network/geocoder hiccup -> fall back to raw coords
        return None
    return None

# Service intervals: item -> (km interval, day interval or None).
_SERVICE_INTERVALS: list[tuple[str, int, int | None]] = [
    ("Oil change", 10000, 180),
    ("Air filter", 20000, None),
    ("Brake inspection", 20000, None),
]


# ----------------------------------------------------------------------------
# Redis (hot path)
# ----------------------------------------------------------------------------
async def latest_snapshot(car_id: str) -> dict | None:
    raw = await get_redis().get(keys.live(car_id))
    return json.loads(raw) if raw else None


async def signal_latest(car_id: str, signal_name: str) -> dict | None:
    raw = await get_redis().get(keys.signal(car_id, signal_name))
    return json.loads(raw) if raw else None


async def location(car_id: str) -> dict | None:
    """Current GPS position, heading (with compass), and an approximate place."""
    snap = await latest_snapshot(car_id)
    geo = (snap or {}).get("geospatial")
    if not geo:
        return None
    lat, lon = geo.get("latitude"), geo.get("longitude")
    heading = geo.get("heading_deg")
    place = await _reverse_geocode(lat, lon) if lat is not None and lon is not None else None
    return {
        "car_name": (snap or {}).get("car_name"),
        "latitude": lat,
        "longitude": lon,
        "heading_deg": heading,
        "heading_compass": _compass(heading) if heading is not None else None,
        "approximate_location": place,
        "timestamp": (snap or {}).get("timestamp"),
    }


async def maintenance_status(car_id: str) -> dict | None:
    """Read the feed's service metadata and compute per-item due/overdue status."""
    raw = await get_redis().get(keys.maintenance(car_id))
    if not raw:
        return None
    m = json.loads(raw)

    total = m.get("total_kms")
    last_odo = m.get("last_serviced_odometer_km")
    last_date = m.get("last_serviced_date")

    km_since = round(total - last_odo, 1) if total is not None and last_odo is not None else None
    days_since = None
    if last_date:
        try:
            days_since = (date.today() - date.fromisoformat(last_date)).days
        except ValueError:
            days_since = None

    items = []
    for name, km_int, day_int in _SERVICE_INTERVALS:
        due_in_km = round(km_int - km_since, 1) if km_since is not None else None
        due_in_days = (day_int - days_since) if (day_int and days_since is not None) else None
        overdue = (due_in_km is not None and due_in_km <= 0) or (
            due_in_days is not None and due_in_days <= 0
        )
        items.append({
            "item": name,
            "interval_km": km_int,
            "interval_days": day_int,
            "due_in_km": due_in_km,
            "due_in_days": due_in_days,
            "status": "overdue" if overdue else "ok",
        })

    return {
        "car_name": m.get("car_name"),
        "last_serviced_date": last_date,
        "last_serviced_odometer_km": last_odo,
        "current_odometer_km": total,
        "km_since_service": km_since,
        "days_since_service": days_since,
        "items": items,
    }


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
