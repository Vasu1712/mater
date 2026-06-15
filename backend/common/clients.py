"""Lazily-constructed, shared async clients for the three data stores."""
from __future__ import annotations

from functools import lru_cache

import asyncpg
import redis.asyncio as aioredis

from .config import settings

_pg_pool: asyncpg.Pool | None = None


@lru_cache(maxsize=1)
def get_redis() -> aioredis.Redis:
    """Process-wide Redis client (decoded strings)."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_pg_pool() -> asyncpg.Pool:
    """Process-wide asyncpg pool, created on first use."""
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            dsn=settings.PG_DSN, min_size=1, max_size=10
        )
    return _pg_pool


async def close_pg_pool() -> None:
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
