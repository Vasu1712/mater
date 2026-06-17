"""Central runtime configuration, sourced from environment variables.

Defaults target the docker-compose network; override via the environment
when running services locally on the host.
"""
from __future__ import annotations

import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Settings:
    # --- Redis (hot path) ---
    REDIS_URL: str = _env("REDIS_URL", "redis://localhost:6379/0")
    LIVE_TTL_SECONDS: int = int(_env("LIVE_TTL_SECONDS", "300"))
    INGEST_QUEUE_KEY_FMT: str = "car:{car_id}:ingest:queue"

    # --- TimescaleDB / Postgres (cold path) ---
    PG_DSN: str = _env(
        "PG_DSN",
        "postgresql://mater_admin:mater_secure_password@localhost:5432/mater_fleet",
    )

    # --- Qdrant (knowledge path) ---
    QDRANT_URL: str = _env("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION: str = _env("QDRANT_COLLECTION", "car_knowledge")
    EMBED_MODEL: str = _env("EMBED_MODEL", "all-MiniLM-L6-v2")
    EMBED_DIM: int = 384

    # --- Ollama (LLM engine) ---
    OLLAMA_URL: str = _env("OLLAMA_URL", "http://localhost:11434")
    LLM_MODEL: str = _env("LLM_MODEL", "gemma4:e4b")

    # --- MCP server ---
    MCP_HOST: str = _env("MCP_HOST", "0.0.0.0")
    MCP_PORT: int = int(_env("MCP_PORT", "8765"))
    MCP_URL: str = _env("MCP_URL", "http://localhost:8765/mcp")

    # --- Flusher ---
    FLUSH_INTERVAL_SECONDS: float = float(_env("FLUSH_INTERVAL_SECONDS", "1.0"))
    FLUSH_BATCH_SIZE: int = int(_env("FLUSH_BATCH_SIZE", "500"))

    # --- Telemetry source bridge (live-car-api WebSocket -> ingestion) ---
    # Vercel is TLS-only, so the scheme must be wss:// (not ws://).
    TELEMETRY_WS_URL: str = _env(
        "TELEMETRY_WS_URL",
        "wss://live-car-api.vercel.app/ws/v1/telemetry/stream?hz=2",
    )
    INGEST_URL: str = _env("INGEST_URL", "http://ingestion:8000/live-car-data")
    # Override the upstream car_id so it matches the seeded car / dashboard.
    # Set to "" to pass the feed's own car_id through unchanged.
    TELEMETRY_CAR_ID: str = _env("TELEMETRY_CAR_ID", "acc001")


settings = Settings()
