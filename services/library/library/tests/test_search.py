"""Tests for the Library search API with a mocked Elasticsearch client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_es(search_return: dict[str, Any] | None = None) -> MagicMock:
    """Build a mock ElasticsearchClient with sensible defaults."""
    mock_es = MagicMock()
    mock_es.connect = AsyncMock()
    mock_es.close = AsyncMock()

    default_search = {
        "total": 2,
        "hits": [
            {
                "_index": "qtown-events",
                "_id": "evt-001",
                "_score": 1.5,
                "_source": {
                    "event_id": "evt-001",
                    "type": "npc_travel",
                    "description": "Alice traveled to the market",
                    "tick": 42,
                    "timestamp": "2024-01-15T10:00:00Z",
                    "npc_ids": ["npc-alice"],
                    "neighborhood": "market",
                    "metadata": {},
                },
                "highlight": {"description": ["Alice <em>traveled</em> to the market"]},
            },
            {
                "_index": "qtown-newspapers",
                "_id": "news-001",
                "_score": 1.2,
                "_source": {
                    "day": 15,
                    "headline": "Market sees record trade",
                    "lead": "The market district reported record trade volume today.",
                    "body": "Details of the market trade...",
                    "editorial": "The editor comments...",
                    "generated_at": "2024-01-15T12:00:00Z",
                },
                "highlight": {"headline": ["Market sees record <em>trade</em>"]},
            },
        ],
        "took_ms": 5,
    }

    mock_es.search = AsyncMock(return_value=search_return or default_search)
    mock_es.events_per_day = AsyncMock(
        return_value=[
            {"date": "2024-01-14T00:00:00.000Z", "count": 12},
            {"date": "2024-01-15T00:00:00.000Z", "count": 8},
        ]
    )
    mock_es.resource_trends = AsyncMock(
        return_value=[
            {
                "date": "2024-01-14T00:00:00.000Z",
                "avg_price": 10.5,
                "max_price": 12.0,
                "min_price": 9.0,
                "total_volume": 100.0,
                "trade_count": 5,
            }
        ]
    )
    mock_es.economic_indicators = AsyncMock(
        return_value={
            "gold_supply": 5000.0,
            "gold_avg_price": 15.0,
            "total_trade_volume": 250000.0,
            "trade_count": 1234,
            "top_resources": [{"resource": "gold", "trade_count": 200}],
            "gdp_proxy_30d": 250000.0,
        }
    )
    return mock_es


@pytest.fixture()
def mock_es_client() -> MagicMock:
    return _make_mock_es()


@pytest.fixture()
def mock_consumer() -> MagicMock:
    mock = MagicMock()
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.consume = AsyncMock(return_value=None)
    return mock


@pytest.fixture()
def client(mock_es_client: MagicMock, mock_consumer: MagicMock) -> TestClient:
    """Create a synchronous TestClient with mocked ES and Kafka consumer."""
    import asyncio

    async def _fake_consume() -> None:
        # Simulate long-running consume coroutine
        await asyncio.sleep(3600)

    mock_consumer.consume.side_effect = _fake_consume

    with (
        patch("library.main.get_es_client", return_value=mock_es_client),
        patch("library.main.get_consumer", return_value=mock_consumer),
    ):
        from library.main import app

        return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_ok(self, client: TestClient, mock_es_client: MagicMock) -> None:
        mock_es_client.client = MagicMock()
        mock_es_client.client.info = AsyncMock(
            return_value={"version": {"number": "8.12.0"}}
        )
        response = client.get("/health")
        # The app patches get_es_client so health check always uses mock
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_returns_hits(self, client: TestClient) -> None:
        response = client.get("/search?q=market")
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data
        assert data["total"] == 2
        assert len(data["hits"]) == 2

    def test_search_pagination(self, client: TestClient) -> None:
        response = client.get("/search?q=trade&limit=5&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 10

    def test_search_type_filter_single(self, client: TestClient, mock_es_client: MagicMock) -> None:
        response = client.get("/search?q=gold&types=events")
        assert response.status_code == 200
        data = response.json()
        assert data["indices"] == ["qtown-events"]

    def test_search_type_filter_multiple(self, client: TestClient) -> None:
        response = client.get("/search?q=gold&types=events,newspapers")
        assert response.status_code == 200
        data = response.json()
        assert "qtown-events" in data["indices"]
        assert "qtown-newspapers" in data["indices"]

    def test_search_unknown_type_returns_400(self, client: TestClient) -> None:
        response = client.get("/search?q=gold&types=unicorns")
        assert response.status_code == 400

    def test_search_missing_query_returns_422(self, client: TestClient) -> None:
        response = client.get("/search")
        assert response.status_code == 422

    def test_search_response_shape(self, client: TestClient) -> None:
        response = client.get("/search?q=alice")
        data = response.json()
        hit = data["hits"][0]
        assert "_index" in hit
        assert "_id" in hit
        assert "_source" in hit
        assert "_score" in hit


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------


class TestAggregations:
    def test_events_per_day_default(self, client: TestClient) -> None:
        response = client.get("/aggregations/events-per-day")
        assert response.status_code == 200
        data = response.json()
        assert "days" in data
        assert data["days"] == 30
        assert isinstance(data["data"], list)

    def test_events_per_day_custom(self, client: TestClient) -> None:
        response = client.get("/aggregations/events-per-day?days=7")
        assert response.status_code == 200
        assert response.json()["days"] == 7

    def test_resource_trends(self, client: TestClient) -> None:
        response = client.get("/aggregations/resource-trends?resource=gold")
        assert response.status_code == 200
        data = response.json()
        assert data["resource"] == "gold"
        assert isinstance(data["data"], list)
        if data["data"]:
            trend = data["data"][0]
            assert "avg_price" in trend
            assert "total_volume" in trend

    def test_resource_trends_missing_resource(self, client: TestClient) -> None:
        response = client.get("/aggregations/resource-trends")
        assert response.status_code == 422

    def test_economic_indicators(self, client: TestClient) -> None:
        response = client.get("/aggregations/economic-indicators")
        assert response.status_code == 200
        data = response.json()
        assert "gold_supply" in data
        assert "total_trade_volume" in data
        assert "gdp_proxy_30d" in data


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_search_es_error_returns_500(
        self, mock_es_client: MagicMock, mock_consumer: MagicMock
    ) -> None:
        mock_es_client.search = AsyncMock(side_effect=Exception("ES down"))

        import asyncio

        async def _fake_consume() -> None:
            await asyncio.sleep(3600)

        mock_consumer.consume.side_effect = _fake_consume

        with (
            patch("library.main.get_es_client", return_value=mock_es_client),
            patch("library.main.get_consumer", return_value=mock_consumer),
        ):
            from library.main import app

            c = TestClient(app, raise_server_exceptions=False)
            response = c.get("/search?q=gold")
            assert response.status_code == 500
