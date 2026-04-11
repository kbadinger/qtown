"""Tests for academy.rag."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from academy.rag import EMBEDDING_DIM, RAGStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rag(tmp_path) -> RAGStore:
    """Return a RAGStore with a mock engine — no real DB needed."""
    store = RAGStore.__new__(RAGStore)
    store._http_client = AsyncMock()
    # Provide a minimal stub so attribute access doesn't fail
    store.engine = MagicMock()
    store.SessionLocal = MagicMock()
    return store


def _fake_embedding(dim: int = EMBEDDING_DIM) -> list[float]:
    return [0.1] * dim


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------


class TestEmbedding:
    @pytest.mark.asyncio
    async def test_embed_event_returns_correct_dimension(self, rag: RAGStore):
        rag._http_client.post = AsyncMock(
            return_value=AsyncMock(
                raise_for_status=MagicMock(),
                json=MagicMock(return_value={"embedding": _fake_embedding()}),
            )
        )
        result = await rag.embed_event("The market opened today.")
        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_embed_event_calls_ollama_endpoint(self, rag: RAGStore):
        mock_resp = AsyncMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"embedding": _fake_embedding()}),
        )
        rag._http_client.post = AsyncMock(return_value=mock_resp)
        await rag.embed_event("test text")
        call_kwargs = rag._http_client.post.call_args
        # Ensure the Ollama endpoint was targeted
        assert "ollama" in str(call_kwargs).lower() or "11434" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_embed_event_passes_text_as_prompt(self, rag: RAGStore):
        mock_resp = AsyncMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"embedding": _fake_embedding()}),
        )
        rag._http_client.post = AsyncMock(return_value=mock_resp)
        test_text = "The harvest festival begins at dusk."
        await rag.embed_event(test_text)
        _, kwargs = rag._http_client.post.call_args
        assert kwargs.get("json", {}).get("prompt") == test_text

    @pytest.mark.asyncio
    async def test_embed_event_raises_on_http_error(self, rag: RAGStore):
        import httpx

        rag._http_client.post = AsyncMock(
            return_value=AsyncMock(
                raise_for_status=MagicMock(side_effect=httpx.HTTPStatusError(
                    "500", request=MagicMock(), response=MagicMock()
                )),
            )
        )
        with pytest.raises(Exception):
            await rag.embed_event("bad request")


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


class TestSimilaritySearch:
    @pytest.mark.asyncio
    async def test_search_similar_returns_list(self, rag: RAGStore):
        """search_similar should always return a list."""
        # Mock embed_event
        rag.embed_event = AsyncMock(return_value=_fake_embedding())

        # Mock DB session returning two rows
        row1 = MagicMock(event_id=1, text="Fire in the market district", distance=0.12)
        row2 = MagicMock(event_id=2, text="Harvest festival announced", distance=0.34)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.all.return_value = [row1, row2]
        mock_session.execute = AsyncMock(return_value=mock_result)
        rag.SessionLocal = MagicMock(return_value=mock_session)

        results = await rag.search_similar("market fire", top_k=2)
        assert isinstance(results, list)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_returns_relevant_results(self, rag: RAGStore):
        rag.embed_event = AsyncMock(return_value=_fake_embedding())

        row = MagicMock(event_id=42, text="Dragon spotted near the inn", distance=0.05)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.all.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)
        rag.SessionLocal = MagicMock(return_value=mock_session)

        results = await rag.search_similar("dragon sighting")
        assert results[0]["event_id"] == 42
        assert "dragon" in results[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_search_results_include_distance(self, rag: RAGStore):
        rag.embed_event = AsyncMock(return_value=_fake_embedding())

        row = MagicMock(event_id=7, text="New merchant arrived", distance=0.2345)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.all.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)
        rag.SessionLocal = MagicMock(return_value=mock_session)

        results = await rag.search_similar("merchant")
        assert "distance" in results[0]
        assert isinstance(results[0]["distance"], float)

    # ------------------------------------------------------------------
    # Source attribution
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_results_include_source_attribution(self, rag: RAGStore):
        """Each result must contain a 'source' field for attribution."""
        rag.embed_event = AsyncMock(return_value=_fake_embedding())

        row = MagicMock(event_id=10, text="The mayor resigned", distance=0.1)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.all.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)
        rag.SessionLocal = MagicMock(return_value=mock_session)

        results = await rag.search_similar("mayor")
        assert "source" in results[0]
        assert results[0]["source"] == "town_events"

    @pytest.mark.asyncio
    async def test_source_attribution_present_for_all_results(self, rag: RAGStore):
        rag.embed_event = AsyncMock(return_value=_fake_embedding())

        rows = [
            MagicMock(event_id=i, text=f"Event {i}", distance=float(i) * 0.1)
            for i in range(5)
        ]
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)
        rag.SessionLocal = MagicMock(return_value=mock_session)

        results = await rag.search_similar("any query", top_k=5)
        assert all("source" in r for r in results)

    @pytest.mark.asyncio
    async def test_empty_search_returns_empty_list(self, rag: RAGStore):
        rag.embed_event = AsyncMock(return_value=_fake_embedding())

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        rag.SessionLocal = MagicMock(return_value=mock_session)

        results = await rag.search_similar("nothing here")
        assert results == []
