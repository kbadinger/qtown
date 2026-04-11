"""
Tests for academy.cost_tracker.

Runs fully in-memory; no Postgres required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import academy.cost_tracker as ct


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_store() -> None:
    """Reset the module-level in-memory store between tests."""
    s = ct._store
    s.total_requests = 0
    s.total_tokens_in = 0
    s.total_tokens_out = 0
    s.total_cost_usd = 0.0
    s.latencies.clear()
    s.cost_by_model.clear()
    s.requests_by_model.clear()
    s.latency_by_model.clear()


@pytest.fixture(autouse=True)
def reset_store():
    _reset_store()
    yield
    _reset_store()


# ---------------------------------------------------------------------------
# InMemoryCostStore unit tests
# ---------------------------------------------------------------------------


class TestInMemoryCostStore:
    def test_record_increments_total_requests(self):
        ct._store.record("model-a", 10, 20, 150.0, 0.0)
        assert ct._store.total_requests == 1

    def test_record_accumulates_tokens(self):
        ct._store.record("model-a", 100, 200, 100.0, 0.0)
        ct._store.record("model-a", 50, 75, 80.0, 0.0)
        assert ct._store.total_tokens_in == 150
        assert ct._store.total_tokens_out == 275

    def test_record_tracks_cost(self):
        ct._store.record("gpt-4o-mini", 0, 0, 200.0, 0.005)
        assert ct._store.total_cost_usd == pytest.approx(0.005, rel=1e-6)

    def test_record_accumulates_cost_by_model(self):
        ct._store.record("model-a", 0, 0, 100.0, 0.001)
        ct._store.record("model-a", 0, 0, 100.0, 0.002)
        ct._store.record("model-b", 0, 0, 50.0, 0.003)

        assert ct._store.cost_by_model["model-a"] == pytest.approx(0.003, rel=1e-6)
        assert ct._store.cost_by_model["model-b"] == pytest.approx(0.003, rel=1e-6)

    def test_record_tracks_requests_by_model(self):
        ct._store.record("m1", 0, 0, 10.0, 0.0)
        ct._store.record("m1", 0, 0, 10.0, 0.0)
        ct._store.record("m2", 0, 0, 10.0, 0.0)

        assert ct._store.requests_by_model["m1"] == 2
        assert ct._store.requests_by_model["m2"] == 1

    def test_record_appends_latencies(self):
        ct._store.record("m1", 0, 0, 111.1, 0.0)
        ct._store.record("m1", 0, 0, 222.2, 0.0)
        assert ct._store.latencies == [111.1, 222.2]

    def test_record_tracks_latency_by_model(self):
        ct._store.record("fast-model", 0, 0, 50.0, 0.0)
        ct._store.record("fast-model", 0, 0, 60.0, 0.0)
        ct._store.record("slow-model", 0, 0, 500.0, 0.0)

        assert ct._store.latency_by_model["fast-model"] == [50.0, 60.0]
        assert ct._store.latency_by_model["slow-model"] == [500.0]


# ---------------------------------------------------------------------------
# record_request (async, with DB mock)
# ---------------------------------------------------------------------------


class TestRecordRequest:
    @pytest.mark.asyncio
    async def test_record_request_updates_in_memory_store(self):
        with patch("academy.cost_tracker._get_engine", new_callable=AsyncMock) as mock_engine:
            conn = AsyncMock()
            conn.__aenter__ = AsyncMock(return_value=conn)
            conn.__aexit__ = AsyncMock(return_value=False)
            conn.execute = AsyncMock()
            engine = MagicMock()
            engine.begin = MagicMock(return_value=conn)
            mock_engine.return_value = engine

            await ct.record_request(
                task_type="npc_dialogue",
                model="deepseek-r1:14b",
                tokens_in=100,
                tokens_out=200,
                latency_ms=350.0,
                cost_usd=0.0,
            )

        assert ct._store.total_requests == 1
        assert ct._store.total_tokens_in == 100
        assert ct._store.total_tokens_out == 200
        assert ct._store.latencies == [350.0]

    @pytest.mark.asyncio
    async def test_record_request_db_failure_does_not_raise(self):
        """DB write failures must be swallowed — generation should not be interrupted."""
        with patch("academy.cost_tracker._get_engine", side_effect=RuntimeError("db down")):
            # Should not raise
            await ct.record_request(
                task_type="newspaper",
                model="qwen3.5:27b",
                tokens_in=50,
                tokens_out=800,
                latency_ms=4000.0,
            )

        # In-memory update should still have happened
        assert ct._store.total_requests == 1

    @pytest.mark.asyncio
    async def test_record_request_multiple_calls(self):
        with patch("academy.cost_tracker._get_engine", new_callable=AsyncMock) as mock_engine:
            conn = AsyncMock()
            conn.__aenter__ = AsyncMock(return_value=conn)
            conn.__aexit__ = AsyncMock(return_value=False)
            conn.execute = AsyncMock()
            engine = MagicMock()
            engine.begin = MagicMock(return_value=conn)
            mock_engine.return_value = engine

            for i in range(5):
                await ct.record_request(
                    task_type="npc_chatter",
                    model="qwen3-coder-next",
                    tokens_in=10,
                    tokens_out=20,
                    latency_ms=float(i * 100),
                )

        assert ct._store.total_requests == 5


# ---------------------------------------------------------------------------
# get_metrics
# ---------------------------------------------------------------------------


class TestGetMetrics:
    def test_get_metrics_empty_store(self):
        metrics = ct.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["avg_latency_ms"] == 0.0
        assert metrics["cost_today_usd"] == 0.0
        assert isinstance(metrics["cost_by_model"], list)

    def test_get_metrics_after_recording(self):
        ct._store.record("m1", 100, 200, 300.0, 0.001)
        ct._store.record("m1", 50, 100, 200.0, 0.002)

        metrics = ct.get_metrics()
        assert metrics["total_requests"] == 2
        assert metrics["avg_latency_ms"] == pytest.approx(250.0, rel=1e-3)
        assert metrics["cost_today_usd"] == pytest.approx(0.003, rel=1e-6)

    def test_get_metrics_by_model_contains_entries(self):
        ct._store.record("fast", 10, 20, 50.0, 0.0)
        ct._store.record("slow", 200, 400, 5000.0, 0.01)

        metrics = ct.get_metrics()
        model_names = {m["model"] for m in metrics["cost_by_model"]}
        assert "fast" in model_names
        assert "slow" in model_names

    def test_get_metrics_avg_latency_correct(self):
        ct._store.record("m", 0, 0, 100.0, 0.0)
        ct._store.record("m", 0, 0, 200.0, 0.0)
        ct._store.record("m", 0, 0, 300.0, 0.0)

        metrics = ct.get_metrics()
        assert metrics["avg_latency_ms"] == pytest.approx(200.0, rel=1e-3)

    def test_get_metrics_cost_rounding(self):
        ct._store.record("m", 0, 0, 1.0, 0.0012345)
        metrics = ct.get_metrics()
        # Should be rounded to 6 decimal places
        assert metrics["cost_today_usd"] == pytest.approx(0.001235, rel=1e-3)


# ---------------------------------------------------------------------------
# get_db_metrics_today
# ---------------------------------------------------------------------------


class TestGetDbMetricsToday:
    @pytest.mark.asyncio
    async def test_db_metrics_returns_dict(self):
        mock_row = MagicMock()
        mock_row.model = "qwen3.5:27b"
        mock_row.request_count = 5
        mock_row.avg_latency_ms = 3500.0
        mock_row.total_cost_usd = 0.0

        with patch("academy.cost_tracker._get_engine", new_callable=AsyncMock) as mock_engine:
            conn = AsyncMock()
            conn.__aenter__ = AsyncMock(return_value=conn)
            conn.__aexit__ = AsyncMock(return_value=False)
            result = MagicMock()
            result.fetchall.return_value = [mock_row]
            conn.execute = AsyncMock(return_value=result)
            engine = MagicMock()
            engine.connect = MagicMock(return_value=conn)
            mock_engine.return_value = engine

            metrics = await ct.get_db_metrics_today()

        assert "total_requests" in metrics
        assert "cost_today_usd" in metrics
        assert "by_model" in metrics

    @pytest.mark.asyncio
    async def test_db_metrics_falls_back_on_error(self):
        with patch("academy.cost_tracker._get_engine", side_effect=Exception("db error")):
            metrics = await ct.get_db_metrics_today()

        # Should fall back to in-memory metrics
        assert "total_requests" in metrics
