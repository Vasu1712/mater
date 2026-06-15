"""Knowledge ingestion pipeline (plan.md §2.3).

Splits a document into overlapping chunks, embeds them with all-MiniLM-L6-v2,
and upserts into the per-car-isolated ``car_knowledge`` collection.

Usage:
    python -m tools.ingest_knowledge --car-id acc001 --model Accord \\
        --source manual --system engine path/to/manual.txt
"""
from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from qdrant_client import models

from common import knowledge
from common.config import settings


def _split(text: str, chunk_tokens: int = 512, overlap: int = 128) -> list[str]:
    """Recursive-ish character split approximated at ~4 chars/token."""
    size = chunk_tokens * 4
    step = (chunk_tokens - overlap) * 4
    return [text[i:i + size] for i in range(0, max(len(text), 1), step) if text[i:i + size].strip()]


def ingest(path: Path, car_id: str, car_model: str, source: str, system: str) -> int:
    knowledge.ensure_collection()
    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks = _split(text)

    points = [
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=knowledge.embed(chunk),
            payload={
                "car_id": car_id, "car_model": car_model,
                "source": source, "system": system, "text": chunk,
            },
        )
        for chunk in chunks
    ]
    knowledge.get_qdrant().upsert(settings.QDRANT_COLLECTION, points=points)
    return len(points)


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest a knowledge document into Qdrant.")
    p.add_argument("file", type=Path)
    p.add_argument("--car-id", required=True)
    p.add_argument("--model", dest="car_model", required=True)
    p.add_argument("--source", default="manual",
                   choices=["manual", "tsb", "mechanic_log", "diagnosis_history"])
    p.add_argument("--system", default="engine",
                   choices=["engine", "transmission", "brakes", "electrical"])
    args = p.parse_args()
    n = ingest(args.file, args.car_id, args.car_model, args.source, args.system)
    print(f"Ingested {n} chunks from {args.file} for car {args.car_id}.")


if __name__ == "__main__":
    main()
