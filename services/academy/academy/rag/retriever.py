"""
TownHistoryRetriever — semantic search over Qtown's historical records.

Backed by pgvector (academy.embeddings table) with cosine similarity.
Results are reranked by the Reranker (cross-encoder → BM25 fallback).

Top-K from vector search: 20 (fed to reranker)
Top-N returned to caller: 5 (after reranking)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("academy.rag.retriever")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://qtown:qtown@localhost:5432/qtown"
)

VECTOR_TOP_K = 20   # candidates from pgvector before reranking
RETURN_TOP_N = 5    # final results after reranking


# ---------------------------------------------------------------------------
# Engine singleton
# ---------------------------------------------------------------------------

_engine: Any = None


async def _get_engine() -> Any:
    """Lazily create the shared SQLAlchemy async engine."""
    global _engine
    if _engine is not None:
        return _engine

    from sqlalchemy.ext.asyncio import create_async_engine

    _engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    logger.info("pgvector engine initialised — %s", DATABASE_URL)
    return _engine


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Document:
    """A retrieved document with its relevance score."""

    doc_id: str
    doc_type: str  # "event" | "dialogue" | "newspaper"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    similarity: float = 0.0    # raw cosine similarity from pgvector
    final_score: float = 0.0   # after reranking (same as similarity if no reranker)

    # Convenience source label for gRPC source attribution
    @property
    def source(self) -> str:
        return f"academy.embeddings/{self.doc_type}/{self.doc_id}"


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------


class TownHistoryRetriever:
    """
    Two-stage retrieval: pgvector ANN search + reranking.

    Usage::

        retriever = TownHistoryRetriever()
        docs = await retriever.search("wheat shortage near market district", k=5)
    """

    def __init__(self) -> None:
        from academy.ollama_client import OllamaClient
        from academy.rag.reranker import get_reranker

        self._ollama = OllamaClient()
        self._reranker = get_reranker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        k: int = RETURN_TOP_N,
        *,
        doc_types: list[str] | None = None,
        rerank: bool = True,
    ) -> list[Document]:
        """
        Return the top-``k`` most relevant documents to ``query``.

        Args:
            query:      Natural-language search query.
            k:          How many documents to return (after reranking).
            doc_types:  Optional filter: ["event"], ["dialogue"], etc.
            rerank:     If False, skip reranking and return raw ANN results.
        """
        query_vec = await self.embed_text(query)

        # Step 1: vector ANN (top-K candidates)
        candidates = await self._vector_search(
            query_vec, top_k=VECTOR_TOP_K, doc_types=doc_types
        )
        if not candidates:
            return []

        if not rerank or len(candidates) <= 1:
            return [self._to_document(c) for c in candidates[:k]]

        # Step 2: rerank
        ranked = await self._reranker.rerank(query, candidates, top_n=k)
        return [
            Document(
                doc_id=r.doc_id,
                doc_type=r.doc_type,
                content=r.content,
                metadata=r.metadata,
                similarity=r.vector_score,
                final_score=r.final_score,
            )
            for r in ranked
        ]

    async def embed_text(self, text: str) -> list[float]:
        """Embed a text string via Ollama nomic-embed-text."""
        return await self._ollama.embed(text, model=EMBEDDING_MODEL)

    # ------------------------------------------------------------------
    # Indexing helpers (called by embedders)
    # ------------------------------------------------------------------

    async def index_event(
        self, event_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Embed and store a town event."""
        from academy.rag.embeddings import get_event_embedder

        embedder = get_event_embedder()
        await embedder.embed_and_store(event_id, text, metadata or {})

    async def index_dialogue(
        self, dialogue_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Embed and store an NPC dialogue."""
        from academy.rag.embeddings import get_dialogue_embedder

        embedder = get_dialogue_embedder()
        await embedder.embed_and_store(dialogue_id, text, metadata or {})

    async def index_newspaper(
        self, article_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Embed and store a newspaper article."""
        from academy.rag.embeddings import get_newspaper_embedder

        embedder = get_newspaper_embedder()
        await embedder.embed_and_store(article_id, text, metadata or {})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _vector_search(
        self,
        query_vec: list[float],
        top_k: int,
        doc_types: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Execute pgvector cosine-similarity ANN search."""
        from sqlalchemy import text as sa_text

        type_filter = ""
        params: dict[str, Any] = {"query_vec": str(query_vec), "top_k": top_k}

        if doc_types:
            placeholders = ", ".join(f":dt{i}" for i in range(len(doc_types)))
            type_filter = f"WHERE doc_type IN ({placeholders})"
            for i, dt in enumerate(doc_types):
                params[f"dt{i}"] = dt

        sql = f"""
            SELECT
                doc_id,
                doc_type,
                content,
                metadata,
                1 - (embedding <=> :query_vec::vector)  AS similarity
            FROM academy.embeddings
            {type_filter}
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :top_k
        """

        engine = await _get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(sa_text(sql), params)
            rows = result.fetchall()

        return [
            {
                "doc_id": row.doc_id,
                "doc_type": row.doc_type,
                "content": row.content,
                "metadata": row.metadata or {},
                "similarity": float(row.similarity),
            }
            for row in rows
        ]

    @staticmethod
    def _to_document(raw: dict[str, Any]) -> Document:
        return Document(
            doc_id=raw["doc_id"],
            doc_type=raw["doc_type"],
            content=raw["content"],
            metadata=raw.get("metadata", {}),
            similarity=float(raw.get("similarity", 0.0)),
            final_score=float(raw.get("similarity", 0.0)),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_retriever: TownHistoryRetriever | None = None


def get_retriever() -> TownHistoryRetriever:
    global _retriever
    if _retriever is None:
        _retriever = TownHistoryRetriever()
    return _retriever
