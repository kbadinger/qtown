"""
TownHistoryRetriever — semantic search over Qtown's historical records.

Backed by pgvector for vector storage and a local embedding model
(via Ollama or a configurable endpoint).

Document types indexed:
  - Events    (e.g. NPC trades, battles, discoveries)
  - Dialogues (NPC conversations)
  - Newspapers (in-world news articles)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("academy.rag.retriever")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://qtown:qtown@localhost:5432/qtown"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Document:
    """A retrieved document with its similarity score."""

    doc_id: str
    doc_type: str  # "event" | "dialogue" | "newspaper"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    similarity: float = 0.0


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class TownHistoryRetriever:
    """
    Semantic retrieval from the Qtown history corpus stored in pgvector.

    Usage::

        retriever = TownHistoryRetriever()
        docs = await retriever.search("wheat shortage near market district", k=5)
    """

    def __init__(self) -> None:
        self._db_url = DATABASE_URL
        self._engine: Any = None  # SQLAlchemy async engine, lazily initialised

    async def _get_engine(self) -> Any:
        """Lazily create the SQLAlchemy async engine."""
        if self._engine is not None:
            return self._engine

        from sqlalchemy.ext.asyncio import create_async_engine

        self._engine = create_async_engine(self._db_url, echo=False, pool_pre_ping=True)
        logger.info("pgvector engine initialised — %s", self._db_url)
        return self._engine

    async def embed_text(self, text: str) -> list[float]:
        """
        Return a float vector for ``text`` using the configured embedding model.

        Calls the Ollama /api/embeddings endpoint.  Replace with a direct
        call to a pgvector-compatible embedding service if needed.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            embedding: list[float] = data["embedding"]
            return embedding

    async def search(self, query: str, k: int = 5) -> list[Document]:
        """
        Return the top-``k`` most similar documents to ``query``.

        Uses cosine similarity via pgvector's <=> operator.
        """
        query_vec = await self.embed_text(query)
        engine = await self._get_engine()

        # Placeholder SQL — replace with the actual table schema once migrations
        # are applied.
        sql = """
            SELECT
                id::text          AS doc_id,
                doc_type,
                content,
                metadata,
                1 - (embedding <=> :query_vec::vector) AS similarity
            FROM town_documents
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :k
        """

        from sqlalchemy import text as sa_text
        from sqlalchemy.ext.asyncio import AsyncConnection

        async with engine.connect() as conn:
            conn: AsyncConnection
            result = await conn.execute(
                sa_text(sql),
                {"query_vec": str(query_vec), "k": k},
            )
            rows = result.fetchall()

        return [
            Document(
                doc_id=row.doc_id,
                doc_type=row.doc_type,
                content=row.content,
                metadata=row.metadata or {},
                similarity=float(row.similarity),
            )
            for row in rows
        ]

    async def index_event(self, event_id: str, text: str, metadata: dict[str, Any] = {}) -> None:
        """Embed and store a town event in the vector store."""
        await self._upsert_document(event_id, "event", text, metadata)

    async def index_dialogue(self, dialogue_id: str, text: str, metadata: dict[str, Any] = {}) -> None:
        """Embed and store an NPC dialogue."""
        await self._upsert_document(dialogue_id, "dialogue", text, metadata)

    async def index_newspaper(self, article_id: str, text: str, metadata: dict[str, Any] = {}) -> None:
        """Embed and store a newspaper article."""
        await self._upsert_document(article_id, "newspaper", text, metadata)

    async def _upsert_document(
        self,
        doc_id: str,
        doc_type: str,
        content: str,
        metadata: dict[str, Any],
    ) -> None:
        """Embed content and upsert into town_documents."""
        embedding = await self.embed_text(content)
        engine = await self._get_engine()

        upsert_sql = """
            INSERT INTO town_documents (id, doc_type, content, metadata, embedding)
            VALUES (:id, :doc_type, :content, :metadata::jsonb, :embedding::vector)
            ON CONFLICT (id) DO UPDATE
              SET content   = EXCLUDED.content,
                  metadata  = EXCLUDED.metadata,
                  embedding = EXCLUDED.embedding
        """

        import json
        from sqlalchemy import text as sa_text

        async with engine.begin() as conn:
            await conn.execute(
                sa_text(upsert_sql),
                {
                    "id": doc_id,
                    "doc_type": doc_type,
                    "content": content,
                    "metadata": json.dumps(metadata),
                    "embedding": str(embedding),
                },
            )

        logger.debug("indexed %s %s", doc_type, doc_id)
