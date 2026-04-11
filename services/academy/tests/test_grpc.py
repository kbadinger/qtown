"""
Tests for academy.grpc_server.

Uses mocked Ollama responses — no live Ollama or Postgres required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from academy.grpc_server import AcademyServicer
from academy.qtown import academy_pb2, common_pb2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def servicer() -> AcademyServicer:
    """Return an AcademyServicer with mocked router and retriever."""
    with (
        patch("academy.grpc_server.ModelRouter") as MockRouter,
        patch("academy.grpc_server.TownHistoryRetriever") as MockRetriever,
    ):
        instance = AcademyServicer.__new__(AcademyServicer)
        instance._router = MockRouter.return_value
        instance._retriever = MockRetriever.return_value
        instance._router.ROUTES = {
            "npc_dialogue": MagicMock(model_id="deepseek-r1:14b", cost_per_1k_tokens=0.0),
            "newspaper": MagicMock(model_id="qwen3.5:27b", cost_per_1k_tokens=0.0),
            "npc_chatter": MagicMock(model_id="qwen3-coder-next", cost_per_1k_tokens=0.0),
        }
        yield instance


@pytest.fixture
def grpc_context() -> MagicMock:
    ctx = MagicMock()
    ctx.set_code = MagicMock()
    ctx.set_details = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, servicer: AcademyServicer, grpc_context: MagicMock):
        request = common_pb2.HealthRequest()
        response = servicer.Health(request, grpc_context)
        assert response.status == "ok"
        assert response.service == "academy"

    def test_health_includes_version(self, servicer: AcademyServicer, grpc_context: MagicMock):
        response = servicer.Health(common_pb2.HealthRequest(), grpc_context)
        assert response.version != ""

    def test_health_includes_details(self, servicer: AcademyServicer, grpc_context: MagicMock):
        response = servicer.Health(common_pb2.HealthRequest(), grpc_context)
        assert "grpc_port" in response.details


# ---------------------------------------------------------------------------
# GenerateDialogue
# ---------------------------------------------------------------------------


class TestGenerateDialogue:
    def test_dialogue_returns_lines(self, servicer: AcademyServicer, grpc_context: MagicMock):
        servicer._router.route = AsyncMock(
            return_value="1|happy|Hello there!\n2|neutral|Greetings, friend."
        )
        servicer._record_cost_sync = MagicMock()
        servicer._embed_dialogue_sync = MagicMock()

        request = academy_pb2.DialogueRequest(
            npc_id_a=1, npc_id_b=2, context="market", tone="friendly"
        )
        response = servicer.GenerateDialogue(request, grpc_context)

        assert isinstance(response, academy_pb2.DialogueResponse)
        assert len(response.lines) >= 1
        assert response.model_used != ""
        assert response.latency_ms >= 0

    def test_dialogue_model_is_recorded(self, servicer: AcademyServicer, grpc_context: MagicMock):
        servicer._router.route = AsyncMock(return_value="1|neutral|Hi.\n2|neutral|Hello.")
        servicer._record_cost_sync = MagicMock()
        servicer._embed_dialogue_sync = MagicMock()

        request = academy_pb2.DialogueRequest(npc_id_a=10, npc_id_b=20)
        response = servicer.GenerateDialogue(request, grpc_context)

        assert servicer._record_cost_sync.called

    def test_dialogue_parses_pipe_format(self, servicer: AcademyServicer, grpc_context: MagicMock):
        servicer._router.route = AsyncMock(
            return_value=(
                "1|happy|Good morning!\n"
                "2|surprised|You are up early.\n"
                "1|neutral|I have deliveries.\n"
                "2|friendly|Safe travels!"
            )
        )
        servicer._record_cost_sync = MagicMock()
        servicer._embed_dialogue_sync = MagicMock()

        request = academy_pb2.DialogueRequest(npc_id_a=1, npc_id_b=2)
        response = servicer.GenerateDialogue(request, grpc_context)

        assert len(response.lines) == 4
        assert response.lines[0].emotion == "happy"
        assert "Good morning" in response.lines[0].text

    def test_dialogue_fallback_when_format_missing(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        servicer._router.route = AsyncMock(return_value="Let us talk about the harvest.")
        servicer._record_cost_sync = MagicMock()
        servicer._embed_dialogue_sync = MagicMock()

        request = academy_pb2.DialogueRequest(npc_id_a=3, npc_id_b=4)
        response = servicer.GenerateDialogue(request, grpc_context)
        # Should not raise; must return at least one line
        assert len(response.lines) >= 1


# ---------------------------------------------------------------------------
# GenerateNewspaper
# ---------------------------------------------------------------------------


class TestGenerateNewspaper:
    def _newspaper_raw(self) -> str:
        return (
            "HEADLINE: Wheat Prices Rise\nCATEGORY: economy\n"
            "BODY: Prices at the market soared today after poor harvest.\n---\n"
            "HEADLINE: Fire Near the Docks\nCATEGORY: crime\n"
            "BODY: A warehouse fire was extinguished by the town guard.\n---\n"
        )

    def test_newspaper_returns_articles(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        servicer._router.route = AsyncMock(return_value=self._newspaper_raw())
        servicer._record_cost_sync = MagicMock()
        servicer._embed_article_sync = MagicMock()

        request = academy_pb2.NewspaperRequest(tick=100, max_articles=2)
        response = servicer.GenerateNewspaper(request, grpc_context)

        assert isinstance(response, academy_pb2.NewspaperResponse)
        assert len(response.articles) >= 1
        assert response.model_used != ""

    def test_newspaper_articles_have_headline_and_body(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        servicer._router.route = AsyncMock(return_value=self._newspaper_raw())
        servicer._record_cost_sync = MagicMock()
        servicer._embed_article_sync = MagicMock()

        request = academy_pb2.NewspaperRequest(tick=42, max_articles=2)
        response = servicer.GenerateNewspaper(request, grpc_context)

        for article in response.articles:
            assert article.headline != ""
            assert article.body != ""

    def test_newspaper_fallback_when_no_parse(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        servicer._router.route = AsyncMock(return_value="Nothing interesting happened.")
        servicer._record_cost_sync = MagicMock()
        servicer._embed_article_sync = MagicMock()

        request = academy_pb2.NewspaperRequest(tick=1, max_articles=3)
        response = servicer.GenerateNewspaper(request, grpc_context)

        # Fallback article should be present
        assert len(response.articles) >= 1

    def test_newspaper_respects_max_articles(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        servicer._router.route = AsyncMock(return_value=self._newspaper_raw())
        servicer._record_cost_sync = MagicMock()
        servicer._embed_article_sync = MagicMock()

        request = academy_pb2.NewspaperRequest(tick=5, max_articles=1)
        response = servicer.GenerateNewspaper(request, grpc_context)

        assert len(response.articles) <= 1


# ---------------------------------------------------------------------------
# SearchHistory
# ---------------------------------------------------------------------------


class TestSearchHistory:
    def test_search_empty_query_returns_error(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        import grpc

        request = academy_pb2.SearchHistoryRequest(query="", top_k=5)
        servicer.SearchHistory(request, grpc_context)

        grpc_context.set_code.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT)

    def test_search_returns_results(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        from academy.rag.retriever import Document

        servicer._retriever.search = AsyncMock(
            return_value=[
                Document(
                    doc_id="evt-1",
                    doc_type="event",
                    content="The wheat harvest failed.",
                    metadata={"event_type": "harvest", "tick": 10},
                    similarity=0.9,
                    final_score=0.95,
                ),
                Document(
                    doc_id="evt-2",
                    doc_type="event",
                    content="Market prices rose sharply.",
                    metadata={"event_type": "economy", "tick": 11},
                    similarity=0.8,
                    final_score=0.85,
                ),
            ]
        )

        request = academy_pb2.SearchHistoryRequest(query="wheat harvest", top_k=5)
        response = servicer.SearchHistory(request, grpc_context)

        assert isinstance(response, academy_pb2.SearchHistoryResponse)
        assert len(response.results) == 2
        assert response.search_latency_ms >= 0

    def test_search_result_has_score(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        from academy.rag.retriever import Document

        servicer._retriever.search = AsyncMock(
            return_value=[
                Document(
                    doc_id="d1",
                    doc_type="dialogue",
                    content="I heard the harbour is quiet.",
                    metadata={},
                    similarity=0.7,
                    final_score=0.8,
                )
            ]
        )
        request = academy_pb2.SearchHistoryRequest(query="harbour", top_k=3)
        response = servicer.SearchHistory(request, grpc_context)

        assert response.results[0].score > 0

    def test_search_internal_error_sets_grpc_code(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        import grpc

        servicer._retriever.search = AsyncMock(side_effect=RuntimeError("db down"))
        request = academy_pb2.SearchHistoryRequest(query="anything", top_k=5)
        servicer.SearchHistory(request, grpc_context)

        grpc_context.set_code.assert_called_once_with(grpc.StatusCode.INTERNAL)


# ---------------------------------------------------------------------------
# GetModelStats
# ---------------------------------------------------------------------------


class TestGetModelStats:
    def test_model_stats_returns_response(
        self, servicer: AcademyServicer, grpc_context: MagicMock
    ):
        servicer._router.get_routing_stats = MagicMock(
            return_value={
                "total_requests": 10,
                "local_pct": 80.0,
                "cloud_pct": 20.0,
                "avg_latency_ms": 250.0,
                "cost_today_usd": 0.0005,
                "by_model": [
                    {
                        "model_name": "qwen3-coder-next",
                        "request_count": 8,
                        "avg_latency_ms": 200.0,
                        "cost_usd": 0.0,
                    }
                ],
            }
        )

        request = academy_pb2.ModelStatsRequest()
        response = servicer.GetModelStats(request, grpc_context)

        assert isinstance(response, academy_pb2.ModelStatsResponse)
        assert response.total_requests == 10
        assert response.local_pct == 80.0
        assert len(response.by_model) == 1


# ---------------------------------------------------------------------------
# Travel RPCs
# ---------------------------------------------------------------------------


class TestTravelRPCs:
    def test_npc_arrive_accepts(self, servicer: AcademyServicer, grpc_context: MagicMock):
        request = common_pb2.TravelRequest(npc_id=42)
        response = servicer.NPCArrive(request, grpc_context)
        assert response.accepted is True

    def test_npc_depart_accepts(self, servicer: AcademyServicer, grpc_context: MagicMock):
        request = common_pb2.TravelRequest(npc_id=99)
        response = servicer.NPCDepart(request, grpc_context)
        assert response.accepted is True

    def test_npc_depart_has_eta(self, servicer: AcademyServicer, grpc_context: MagicMock):
        request = common_pb2.TravelRequest(npc_id=5)
        response = servicer.NPCDepart(request, grpc_context)
        assert response.eta_ticks >= 0
