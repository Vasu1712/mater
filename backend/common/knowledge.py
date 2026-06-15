"""Qdrant knowledge-path helpers: collection bootstrap, embedding, search.

Implements plan.md §2.3 — per-car tenant isolation (global HNSW disabled,
per-tenant graphs via the ``car_id`` payload index).
"""
from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient, models

from .config import settings


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    return QdrantClient(url=settings.QDRANT_URL)


@lru_cache(maxsize=1)
def get_embedder():
    """Load the sentence-transformers model lazily (heavy import)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBED_MODEL)


def embed(text: str) -> list[float]:
    return get_embedder().encode(text, normalize_embeddings=True).tolist()


def ensure_collection() -> None:
    """Create the car_knowledge collection with tenant isolation if absent."""
    client = get_qdrant()
    if client.collection_exists(settings.QDRANT_COLLECTION):
        return

    client.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=models.VectorParams(
            size=settings.EMBED_DIM, distance=models.Distance.COSINE
        ),
        # Global graph disabled (m=0); per-tenant graphs built via payload_m.
        hnsw_config=models.HnswConfigDiff(
            m=0, payload_m=16, ef_construct=100, full_scan_threshold=10000
        ),
    )

    # Tenant key — drives per-car HNSW subgraphs.
    client.create_payload_index(
        collection_name=settings.QDRANT_COLLECTION,
        field_name="car_id",
        field_schema=models.KeywordIndexParams(type="keyword", is_tenant=True),
    )
    for field in ("car_model", "source", "system"):
        client.create_payload_index(
            collection_name=settings.QDRANT_COLLECTION,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def search(
    query: str,
    car_id: str,
    *,
    source: str | None = None,
    system: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Tenant-scoped semantic search over a car's knowledge."""
    client = get_qdrant()
    must = [models.FieldCondition(key="car_id", match=models.MatchValue(value=car_id))]
    if source:
        must.append(models.FieldCondition(key="source", match=models.MatchValue(value=source)))
    if system:
        must.append(models.FieldCondition(key="system", match=models.MatchValue(value=system)))

    hits = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=embed(query),
        query_filter=models.Filter(must=must),
        limit=limit,
        with_payload=True,
    ).points

    return [
        {"score": h.score, "text": h.payload.get("text"), "source": h.payload.get("source"),
         "system": h.payload.get("system")}
        for h in hits
    ]
