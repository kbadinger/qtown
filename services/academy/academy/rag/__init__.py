"""
academy.rag — public RAG package interface.

Exposes the RAGStore facade used by:
  - Kafka consumer (embed events on ingestion)
  - gRPC QueryTownHistory RPC
  - Tests (test_rag.py)

Also re-exports EMBEDDING_DIM for test assertions.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("academy.rag")

EMBEDDING_DIM = 768  # nomic-embed-text output dimension


# ---------------------------------------------------------------------------
# RAGStore — thin facade that wires embedder + retriever
# ---------------------------------------------------------------------------


class RAGStore:
    """
    Unified RAG interface used by the Kafka consumer and gRPC server.

    Attributes:
        engine:       SQLAlchemy async engine (set after init_db is called)
        SessionLocal: async session factory
    """

    def __init__(self) -> None:
        import os

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        db_url = os.environ.get(
            "DATABASE_URL", "postgresql+asyncpg://qtown:qtown@localhost:5432/qtown"
        )
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

        self.engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        # Use a client without a base_url so that full URLs (including port 11434)
        # appear in mock call_args, enabling test assertions.
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._ollama_url = ollama_url.rstrip("/")

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    async def embed_event(self, text: str) -> list[float]:
        """
        Embed a piece of text via Ollama nomic-embed-text.

        Returns a list[float] of length EMBEDDING_DIM.
        """
        ollama_url = getattr(self, "_ollama_url", "http://localhost:11434")
        resp = await self._http_client.post(
            f"{ollama_url}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data["embedding"]

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def store_event(
        self,
        event_id: int,
        text: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Upsert a town event (with pre-computed embedding) into the store.

        Maps to the academy.embeddings table via the embedder pipeline.
        """
        import json

        from sqlalchemy import text as sa_text

        sql = """
            INSERT INTO academy.embeddings (doc_type, doc_id, content, embedding, metadata)
            VALUES ('event', :doc_id, :content, :embedding::vector, :metadata::jsonb)
            ON CONFLICT (doc_id) DO UPDATE
              SET content    = EXCLUDED.content,
                  embedding  = EXCLUDED.embedding,
                  metadata   = EXCLUDED.metadata
        """
        async with self.SessionLocal() as session:
            await session.execute(
                sa_text(sql),
                {
                    "doc_id": str(event_id),
                    "content": text,
                    "embedding": str(embedding),
                    "metadata": json.dumps(metadata or {}),
                },
            )
            await session.commit()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def search_similar(
        self, query: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        Semantic search returning up to ``top_k`` results.

        Each result dict contains:
          ``event_id``, ``text``, ``distance``, ``source``
        """
        embedding = await self.embed_event(query)

        from sqlalchemy import text as sa_text

        sql = """
            SELECT
                doc_id::bigint              AS event_id,
                content                     AS text,
                embedding <=> :vec::vector  AS distance
            FROM academy.embeddings
            WHERE doc_type = 'event'
            ORDER BY embedding <=> :vec::vector
            LIMIT :top_k
        """
        async with self.SessionLocal() as session:
            result = await session.execute(
                sa_text(sql),
                {"vec": str(embedding), "top_k": top_k},
            )
            rows = result.all()

        return [
            {
                "event_id": row.event_id,
                "text": row.text,
                "distance": float(row.distance),
                "source": "town_events",
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the HTTP client and database engine."""
        await self._http_client.aclose()
        await self.engine.dispose()


__all__ = ["RAGStore", "EMBEDDING_DIM"]
