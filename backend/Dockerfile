# Single image, multiple entrypoints (ingestion / mcp / agent / tools).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps for asyncpg / sentence-transformers wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Default command runs the ingestion API; override per service in compose.
CMD ["uvicorn", "ingestion.app:app", "--host", "0.0.0.0", "--port", "8000"]
