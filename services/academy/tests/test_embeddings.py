"""
Tests for academy.rag.embeddings.

Mocks pgvector and Ollama — no live services required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from academy.rag.embeddings import (
    EMBEDDING_DIM,
    EventEmbedder,
    DialogueEmbedder,
    NewspaperEmbedder,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_vec(dim: int = EMBEDDING_DIM) -> list[float]:
    return [0.1] * dim


def _make_embedder(cls, mock_ollama, mock_engine):
    """Construct an embedder bypassing __init__."""
    embedder = cls.__new__(cls)
    embedder._ollama = mock_ollama
    embedder._get_engine = mock_engine
    return embedder


def _mock_ollama(vec=None):
    m = MagicMock()
    m.embed = AsyncMock(return_value=vec or _fake_vec())
    m.embed_batch = AsyncMock(return_value=[vec or _fake_vec()])
    return m


def _mock_engine():
    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    result = MagicMock()
    result.fetchone.return_value = MagicMock(spec_set=["__getitem__"])
    result.fetchone.return_value.__getitem__ = lambda self, i: "mock-uuid"
    conn.execute = AsyncMock(return_value=result)

    engine = AsyncMock()
    engine.begin = MagicMock(return_value=conn)

    async def get_engine():
        return engine

    return get_engine


# ---------------------------------------------------------------------------
# EventEmbedder
# ---------------------------------------------------------------------------


class TestEventEmbedder:
    @pytest.mark.asyncio
    async def test_process_event_calls_embed(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        payload = {
            "id": "evt-001",
            "event_type": "harvest_failure",
            "tick": 42,
            "npc_id": 7,
            "description": "The northern fields yielded nothing.",
        }
        await embedder.process_event(payload)
        ollama.embed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_event_missing_id_returns_none(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        result = await embedder.process_event({"event_type": "test"})
        assert result is None
        ollama.embed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_event_constructs_content_string(self):
        captured_texts: list[str] = []
        ollama = MagicMock()
        ollama.embed = AsyncMock(
            side_effect=lambda text, model=None: captured_texts.append(text) or _fake_vec()
        )
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        payload = {
            "id": "e1",
            "event_type": "festival_start",
            "tick": 10,
            "npc_id": 3,
            "description": "The harvest festival begins.",
        }
        await embedder.process_event(payload)

        assert len(captured_texts) == 1
        text = captured_texts[0]
        assert "festival_start" in text
        assert "10" in text  # tick
        assert "harvest festival" in text

    @pytest.mark.asyncio
    async def test_process_event_returns_record_id_on_success(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        result = await embedder.process_event({"id": "evt-99", "tick": 1})
        # Should return a string (record id or doc_id)
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_event_handles_embed_failure_gracefully(self):
        ollama = MagicMock()
        ollama.embed = AsyncMock(side_effect=RuntimeError("ollama down"))
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        result = await embedder.process_event({"id": "evt-fail", "tick": 0})
        assert result is None  # should not raise, return None on failure


# ---------------------------------------------------------------------------
# DialogueEmbedder
# ---------------------------------------------------------------------------


class TestDialogueEmbedder:
    @pytest.mark.asyncio
    async def test_process_dialogue_embeds_lines(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(DialogueEmbedder, ollama, _mock_engine())

        lines = [
            {"npc_id": 1, "text": "Good morning!"},
            {"npc_id": 2, "text": "Hello there."},
        ]
        result = await embedder.process_dialogue("dlg-001", lines)
        ollama.embed.assert_awaited_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_dialogue_empty_lines_returns_none(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(DialogueEmbedder, ollama, _mock_engine())

        result = await embedder.process_dialogue("dlg-empty", [])
        assert result is None
        ollama.embed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dialogue_content_joins_speaker_text(self):
        captured: list[str] = []
        ollama = MagicMock()
        ollama.embed = AsyncMock(
            side_effect=lambda text, model=None: captured.append(text) or _fake_vec()
        )
        embedder = _make_embedder(DialogueEmbedder, ollama, _mock_engine())

        lines = [
            {"npc_id": 5, "text": "Selling fresh bread!"},
            {"npc_id": 6, "text": "I'll take two loaves."},
        ]
        await embedder.process_dialogue("dlg-market", lines)

        assert len(captured) == 1
        assert "NPC#5" in captured[0]
        assert "fresh bread" in captured[0]

    @pytest.mark.asyncio
    async def test_process_dialogue_passes_metadata(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(DialogueEmbedder, ollama, _mock_engine())

        metadata = {"tone": "hostile", "location": "tavern"}
        result = await embedder.process_dialogue(
            "dlg-tavern", [{"npc_id": 1, "text": "Back off!"}], metadata
        )
        assert result is not None


# ---------------------------------------------------------------------------
# NewspaperEmbedder
# ---------------------------------------------------------------------------


class TestNewspaperEmbedder:
    @pytest.mark.asyncio
    async def test_process_article_calls_embed(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(NewspaperEmbedder, ollama, _mock_engine())

        result = await embedder.process_article(
            "art-001",
            "Wheat Prices Rise",
            "Market analysts report a 30% increase...",
            tick=100,
            category="economy",
        )
        ollama.embed.assert_awaited_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_article_content_includes_headline(self):
        captured: list[str] = []
        ollama = MagicMock()
        ollama.embed = AsyncMock(
            side_effect=lambda text, model=None: captured.append(text) or _fake_vec()
        )
        embedder = _make_embedder(NewspaperEmbedder, ollama, _mock_engine())

        await embedder.process_article(
            "art-002",
            "Dragon Spotted Near Inn",
            "Residents panicked as a dragon circled overhead.",
            tick=50,
        )
        assert "Dragon Spotted Near Inn" in captured[0]

    @pytest.mark.asyncio
    async def test_process_article_handles_embed_error_gracefully(self):
        ollama = MagicMock()
        ollama.embed = AsyncMock(side_effect=RuntimeError("embed error"))
        embedder = _make_embedder(NewspaperEmbedder, ollama, _mock_engine())

        result = await embedder.process_article("art-err", "Headline", "Body", tick=1)
        assert result is None  # should not raise


# ---------------------------------------------------------------------------
# Batch embedding (BaseEmbedder)
# ---------------------------------------------------------------------------


class TestBatchEmbedding:
    @pytest.mark.asyncio
    async def test_embed_and_store_batch_multiple_docs(self):
        vecs = [_fake_vec() for _ in range(3)]
        ollama = MagicMock()
        ollama.embed_batch = AsyncMock(return_value=vecs)
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        docs = [
            {"doc_id": f"d{i}", "content": f"Content {i}", "metadata": {}}
            for i in range(3)
        ]
        ids = await embedder.embed_and_store_batch(docs)
        assert len(ids) == 3

    @pytest.mark.asyncio
    async def test_embed_and_store_batch_empty_returns_empty(self):
        ollama = _mock_ollama()
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        result = await embedder.embed_and_store_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_size_exceeds_cap_raises(self):
        from academy.rag.embeddings import BATCH_SIZE

        ollama = _mock_ollama()
        embedder = _make_embedder(EventEmbedder, ollama, _mock_engine())

        # Test that oversized batches are chunked (no exception should be raised
        # from embed_and_store_batch itself — it splits automatically)
        docs = [{"doc_id": f"d{i}", "content": f"text {i}"} for i in range(BATCH_SIZE + 1)]
        ollama.embed_batch = AsyncMock(return_value=[_fake_vec()] * len(docs))
        # Should NOT raise; the batch is split internally
        # (but embed_batch will be called with chunks ≤ BATCH_SIZE)
        ids = await embedder.embed_and_store_batch(docs)
        assert len(ids) == len(docs)
