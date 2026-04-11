"""
Embedding pipeline for the Academy RAG system.

Embedders consume Kafka events and store vectors in the academy.embeddings
pgvector table.

Table schema (created by init-db.sql)::

    CREATE TABLE academy.embeddings (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        doc_type    TEXT NOT NULL,        -- 'event' | 'dialogue' | 'newspaper'
        doc_id      TEXT NOT NULL UNIQUE,
        content     TEXT NOT NULL,
        embedding   vector(768) NOT NULL,
        metadata    JSONB DEFAULT '{}',
        created_at  TIMESTAMPTZ DEFAULT now()
    );

Batch size cap: 32 texts per Ollama call.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("academy.rag.embeddings")

EMBEDDING_DIM = 768
EMBED_MODEL = "nomic-embed-text"
BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# Base embedder
# ---------------------------------------------------------------------------


class BaseEmbedder:
    """Common embedding + storage logic shared by all embedder types."""

    doc_type: str  # override in subclass

    def __init__(self) -> None:
        from academy.ollama_client import OllamaClient
        from academy.rag.retriever import _get_engine

        self._ollama = OllamaClient()
        self._get_engine = _get_engine

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in batches of BATCH_SIZE."""
        results: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            vecs = await self._ollama.embed_batch(batch, model=EMBED_MODEL)
            results.extend(vecs)
        return results

    async def embed_and_store(
        self, doc_id: str, content: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """Embed a single document and upsert into academy.embeddings."""
        embedding = await self._ollama.embed(content, model=EMBED_MODEL)
        return await self._upsert(doc_id, content, embedding, metadata or {})

    async def embed_and_store_batch(
        self,
        docs: list[dict[str, Any]],
    ) -> list[str]:
        """
        Embed and store multiple documents.

        Each item in ``docs`` must have keys: ``doc_id``, ``content``,
        and optionally ``metadata``.
        """
        if not docs:
            return []

        texts = [d["content"] for d in docs]
        embeddings = await self._embed_texts(texts)

        ids: list[str] = []
        for doc, embedding in zip(docs, embeddings):
            doc_id = await self._upsert(
                doc["doc_id"], doc["content"], embedding, doc.get("metadata", {})
            )
            ids.append(doc_id)
        return ids

    async def _upsert(
        self,
        doc_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> str:
        from sqlalchemy import text as sa_text

        sql = """
            INSERT INTO academy.embeddings (doc_type, doc_id, content, embedding, metadata)
            VALUES (:doc_type, :doc_id, :content, :embedding::vector, :metadata::jsonb)
            ON CONFLICT (doc_id) DO UPDATE
              SET content    = EXCLUDED.content,
                  embedding  = EXCLUDED.embedding,
                  metadata   = EXCLUDED.metadata
            RETURNING id::text
        """
        engine = await self._get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(
                sa_text(sql),
                {
                    "doc_type": self.doc_type,
                    "doc_id": doc_id,
                    "content": content,
                    "embedding": str(embedding),
                    "metadata": json.dumps(metadata),
                },
            )
            row = result.fetchone()
            record_id: str = row[0] if row else doc_id

        logger.debug("Upserted %s doc_id=%s -> record %s", self.doc_type, doc_id, record_id)
        return record_id


# ---------------------------------------------------------------------------
# Concrete embedders
# ---------------------------------------------------------------------------


class EventEmbedder(BaseEmbedder):
    """
    Embeds town events from the events.broadcast Kafka topic.

    Extracts a human-readable text summary from the event payload
    before embedding.
    """

    doc_type = "event"

    async def process_event(self, event_payload: dict[str, Any]) -> str | None:
        """
        Process a single event dict and embed it.

        Returns the database record ID, or None on failure.
        """
        doc_id = str(event_payload.get("id", event_payload.get("event_id", "")))
        if not doc_id:
            logger.warning("EventEmbedder: missing id in payload %r", event_payload)
            return None

        # Build human-readable content
        description = event_payload.get("description", "")
        event_type = event_payload.get("event_type", "unknown")
        tick = event_payload.get("tick", 0)
        npc_id = event_payload.get("npc_id", "")

        content_parts = [f"[Tick {tick}] {event_type}"]
        if npc_id:
            content_parts.append(f"NPC #{npc_id}")
        if description:
            content_parts.append(description)

        content = " — ".join(content_parts)

        metadata = {
            "event_type": event_type,
            "tick": tick,
            "npc_id": npc_id,
            "source": event_payload.get("source", ""),
        }

        try:
            return await self.embed_and_store(doc_id, content, metadata)
        except Exception as exc:
            logger.error("EventEmbedder failed for doc_id=%s: %s", doc_id, exc)
            return None


class DialogueEmbedder(BaseEmbedder):
    """
    Embeds NPC dialogue exchanges.

    Called directly from the gRPC server after a GenerateDialogue response.
    """

    doc_type = "dialogue"

    async def process_dialogue(
        self,
        dialogue_id: str,
        lines: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Embed a list of dialogue lines as a single document.

        ``lines`` should be a list of dicts with ``npc_id`` and ``text``.
        """
        if not lines:
            return None

        content = "\n".join(
            f"NPC#{ln.get('npc_id', '?')}: {ln.get('text', '')}" for ln in lines
        )

        return await self.embed_and_store(dialogue_id, content, metadata or {})


class NewspaperEmbedder(BaseEmbedder):
    """
    Embeds generated newspaper articles.

    Called from the gRPC server after a GenerateNewspaper response.
    """

    doc_type = "newspaper"

    async def process_article(
        self,
        article_id: str,
        headline: str,
        body: str,
        tick: int,
        category: str = "",
    ) -> str | None:
        """Embed a newspaper article as ``headline + body``."""
        content = f"{headline}\n\n{body}"
        metadata = {"tick": tick, "category": category, "headline": headline}
        try:
            return await self.embed_and_store(article_id, content, metadata)
        except Exception as exc:
            logger.error("NewspaperEmbedder failed article_id=%s: %s", article_id, exc)
            return None


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_event_embedder: EventEmbedder | None = None
_dialogue_embedder: DialogueEmbedder | None = None
_newspaper_embedder: NewspaperEmbedder | None = None


def get_event_embedder() -> EventEmbedder:
    global _event_embedder
    if _event_embedder is None:
        _event_embedder = EventEmbedder()
    return _event_embedder


def get_dialogue_embedder() -> DialogueEmbedder:
    global _dialogue_embedder
    if _dialogue_embedder is None:
        _dialogue_embedder = DialogueEmbedder()
    return _dialogue_embedder


def get_newspaper_embedder() -> NewspaperEmbedder:
    global _newspaper_embedder
    if _newspaper_embedder is None:
        _newspaper_embedder = NewspaperEmbedder()
    return _newspaper_embedder
