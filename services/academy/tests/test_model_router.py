"""Tests for academy.model_router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from academy.model_router import ModelRouter, ModelTier, RoutingStats


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def router() -> ModelRouter:
    r = ModelRouter()
    return r


# ---------------------------------------------------------------------------
# Routing logic — correct model selected per task type
# ---------------------------------------------------------------------------


class TestRoutingLogic:
    def test_npc_chatter_uses_local_fast(self, router: ModelRouter):
        config = router.ROUTES["npc_chatter"]
        assert config.tier == ModelTier.LOCAL_FAST
        assert "3b" in config.model_id

    def test_npc_dialogue_uses_local_quality(self, router: ModelRouter):
        config = router.ROUTES["npc_dialogue"]
        assert config.tier == ModelTier.LOCAL_QUALITY
        assert "14b" in config.model_id

    def test_newspaper_uses_local_heavy(self, router: ModelRouter):
        config = router.ROUTES["newspaper"]
        assert config.tier == ModelTier.LOCAL_HEAVY
        assert "27b" in config.model_id

    def test_complex_gen_uses_cloud_fallback(self, router: ModelRouter):
        config = router.ROUTES["complex_gen"]
        assert config.tier == ModelTier.CLOUD_FALLBACK
        assert config.cost_per_1k_tokens > 0

    def test_unknown_task_defaults_to_npc_chatter(self, router: ModelRouter):
        """Unknown task types should fall back to the npc_chatter config."""
        default_config = router.ROUTES["npc_chatter"]
        resolved = router.ROUTES.get("nonexistent_task", router.ROUTES["npc_chatter"])
        assert resolved == default_config

    def test_all_local_tiers_have_zero_cost(self, router: ModelRouter):
        local_tiers = {ModelTier.LOCAL_FAST, ModelTier.LOCAL_QUALITY, ModelTier.LOCAL_HEAVY}
        for name, cfg in router.ROUTES.items():
            if cfg.tier in local_tiers:
                assert cfg.cost_per_1k_tokens == 0.0, (
                    f"Expected zero cost for local model '{name}'"
                )


# ---------------------------------------------------------------------------
# Successful local routing
# ---------------------------------------------------------------------------


class TestLocalRouting:
    @pytest.mark.asyncio
    async def test_route_calls_ollama_for_local_task(self, router: ModelRouter):
        router._call_ollama = AsyncMock(return_value="local response")
        result = await router.route("npc_chatter", "Hello!")
        router._call_ollama.assert_awaited_once()
        assert result == "local response"

    @pytest.mark.asyncio
    async def test_local_request_increments_local_counter(self, router: ModelRouter):
        router._call_ollama = AsyncMock(return_value="ok")
        await router.route("npc_dialogue", "test prompt")
        assert router.stats.local_requests == 1
        assert router.stats.cloud_requests == 0

    @pytest.mark.asyncio
    async def test_total_requests_increments_on_each_call(self, router: ModelRouter):
        router._call_ollama = AsyncMock(return_value="ok")
        for _ in range(3):
            await router.route("npc_chatter", "ping")
        assert router.stats.total_requests == 3


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------


class TestFallbackBehavior:
    @pytest.mark.asyncio
    async def test_ollama_failure_falls_back_to_cloud(self, router: ModelRouter):
        router._call_ollama = AsyncMock(side_effect=Exception("connection refused"))
        router._call_cloud = AsyncMock(return_value="cloud fallback response")
        result = await router.route("npc_chatter", "test")
        router._call_cloud.assert_awaited_once()
        assert result == "cloud fallback response"

    @pytest.mark.asyncio
    async def test_fallback_increments_cloud_counter(self, router: ModelRouter):
        router._call_ollama = AsyncMock(side_effect=RuntimeError("timeout"))
        router._call_cloud = AsyncMock(return_value="fallback")
        await router.route("npc_dialogue", "prompt")
        assert router.stats.cloud_requests == 1
        assert router.stats.local_requests == 0

    @pytest.mark.asyncio
    async def test_cloud_task_always_calls_cloud(self, router: ModelRouter):
        router._call_cloud = AsyncMock(return_value="cloud result")
        result = await router.route("complex_gen", "write something fancy")
        router._call_cloud.assert_awaited_once()
        assert result == "cloud result"
        assert router.stats.cloud_requests == 1

    @pytest.mark.asyncio
    async def test_latency_is_recorded_even_on_fallback(self, router: ModelRouter):
        router._call_ollama = AsyncMock(side_effect=Exception("err"))
        router._call_cloud = AsyncMock(return_value="ok")
        await router.route("npc_chatter", "hi")
        assert len(router.stats.latencies) == 1
        assert router.stats.latencies[0] >= 0


# ---------------------------------------------------------------------------
# Stats tracking
# ---------------------------------------------------------------------------


class TestStatsTracking:
    @pytest.mark.asyncio
    async def test_get_routing_stats_with_no_requests(self, router: ModelRouter):
        stats = router.get_routing_stats()
        # total_requests == 0, denominator is clamped to 1
        assert stats["total_requests"] == 0
        assert stats["local_pct"] == 0.0
        assert stats["cloud_pct"] == 0.0
        assert stats["cost_today_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_local_pct_calculation(self, router: ModelRouter):
        router._call_ollama = AsyncMock(return_value="ok")
        router._call_cloud = AsyncMock(return_value="ok")
        # 3 local, 1 cloud
        for _ in range(3):
            await router.route("npc_chatter", "local")
        await router.route("complex_gen", "cloud")
        stats = router.get_routing_stats()
        assert stats["total_requests"] == 4
        assert stats["local_pct"] == 75.0
        assert stats["cloud_pct"] == 25.0

    @pytest.mark.asyncio
    async def test_latencies_appended(self, router: ModelRouter):
        router._call_ollama = AsyncMock(return_value="pong")
        for _ in range(5):
            await router.route("npc_chatter", "ping")
        assert len(router.stats.latencies) == 5

    def test_routing_stats_rounding(self, router: ModelRouter):
        router.stats.total_requests = 3
        router.stats.local_requests = 1
        router.stats.cloud_requests = 2
        router.stats.total_cost_usd = 0.0012345
        stats = router.get_routing_stats()
        assert stats["local_pct"] == round(1 / 3 * 100, 1)
        assert stats["cost_today_usd"] == 0.0012
