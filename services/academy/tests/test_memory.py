"""
Tests for academy.agents.memory — P5-006.

test_consolidation_threshold  — verify consolidation only triggers with >10 events
test_summary_generation       — verify ModelRouter called with correct task_type
test_consolidated_retrieval   — verify consolidated memories have higher weight
test_tick_interval            — verify should_consolidate respects 50-tick interval
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from academy.agents.memory import (
    MemoryConsolidator,
    ConsolidatedMemory,
    ConsolidationResult,
    CONSOLIDATION_INTERVAL,
    MIN_EVENTS_PER_CATEGORY,
    CONSOLIDATED_IMPORTANCE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_consolidator(summary_response: str = "Summary of events.") -> MemoryConsolidator:
    """Return a MemoryConsolidator with mocked router and embedder."""
    consolidator = MemoryConsolidator.__new__(MemoryConsolidator)
    router = MagicMock()
    router.route = AsyncMock(return_value=summary_response)
    consolidator._router = router
    consolidator._store = {}
    consolidator._last_consolidation = {}
    return consolidator


def _mock_embed(consolidator: MemoryConsolidator) -> None:
    """Patch the _embed method to return a zero vector without calling Ollama."""
    consolidator._embed = AsyncMock(return_value=[0.0] * 768)


def trade_events(n: int, start_tick: int = 0) -> list[dict]:
    return [{"event_type": "trade", "tick": start_tick + i, "description": f"trade {i}"} for i in range(n)]


def work_events(n: int, start_tick: int = 0) -> list[dict]:
    return [{"event_type": "work_completed", "tick": start_tick + i, "description": f"work {i}"} for i in range(n)]


# ---------------------------------------------------------------------------
# test_consolidation_threshold
# ---------------------------------------------------------------------------


class TestConsolidationThreshold:
    """Consolidation only fires when a category has >10 (≥10+1) events."""

    @pytest.mark.asyncio
    async def test_fewer_than_threshold_not_consolidated(self):
        """9 events in a category should NOT be summarised."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        # 9 trade events — below MIN_EVENTS_PER_CATEGORY (10)
        events = trade_events(MIN_EVENTS_PER_CATEGORY - 1)
        result = await consolidator.consolidate("npc1", events, tick=100)

        assert "trade" not in result.categories_consolidated
        assert result.events_processed == 0

    @pytest.mark.asyncio
    async def test_exactly_threshold_consolidated(self):
        """Exactly MIN_EVENTS_PER_CATEGORY events triggers consolidation."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(MIN_EVENTS_PER_CATEGORY)
        result = await consolidator.consolidate("npc1", events, tick=100)

        assert "trade" in result.categories_consolidated
        assert result.events_processed == MIN_EVENTS_PER_CATEGORY

    @pytest.mark.asyncio
    async def test_above_threshold_consolidated(self):
        """More than the minimum events triggers consolidation."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(25)
        result = await consolidator.consolidate("npc1", events, tick=100)

        assert "trade" in result.categories_consolidated

    @pytest.mark.asyncio
    async def test_only_categories_above_threshold_consolidated(self):
        """Only categories with enough events are summarised; others are skipped."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        # 15 trade + 3 work events
        events = trade_events(15) + work_events(3)
        result = await consolidator.consolidate("npc1", events, tick=100)

        assert "trade" in result.categories_consolidated
        assert "work" not in result.categories_consolidated

    @pytest.mark.asyncio
    async def test_multiple_categories_above_threshold(self):
        """Both trade and work are consolidated when both exceed the threshold."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12) + work_events(11)
        result = await consolidator.consolidate("npc1", events, tick=100)

        assert "trade" in result.categories_consolidated
        assert "work" in result.categories_consolidated

    @pytest.mark.asyncio
    async def test_raw_events_flagged_after_consolidation(self):
        """Events that were consolidated should have consolidated=True flag set."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12)
        await consolidator.consolidate("npc1", events, tick=100)

        consolidated_events = [e for e in events if e.get("consolidated") is True]
        assert len(consolidated_events) == 12


# ---------------------------------------------------------------------------
# test_summary_generation
# ---------------------------------------------------------------------------


class TestSummaryGeneration:
    """ModelRouter must be called with task_type='memory_summary'."""

    @pytest.mark.asyncio
    async def test_router_called_with_memory_summary_task_type(self):
        """The router.route() call must use 'memory_summary' as the task_type."""
        consolidator = make_consolidator(summary_response="NPC traded wheat frequently.")
        _mock_embed(consolidator)

        events = trade_events(15)
        await consolidator.consolidate("npc1", events, tick=100)

        # Assert route was called with the correct task_type
        consolidator._router.route.assert_awaited()
        call_args = consolidator._router.route.call_args
        # First positional argument should be the task_type
        assert call_args[0][0] == "memory_summary", (
            f"Expected task_type='memory_summary', got {call_args[0][0]}"
        )

    @pytest.mark.asyncio
    async def test_summary_text_used_in_consolidated_memory(self):
        """The LLM summary should appear in the ConsolidatedMemory.summary_text."""
        expected_summary = "NPC successfully completed several profitable trades."
        consolidator = make_consolidator(summary_response=expected_summary)
        _mock_embed(consolidator)

        events = trade_events(12)
        result = await consolidator.consolidate("npc1", events, tick=100)

        assert len(result.new_summaries) >= 1
        trade_summary = next(m for m in result.new_summaries if m.category == "trade")
        assert trade_summary.summary_text == expected_summary

    @pytest.mark.asyncio
    async def test_fallback_summary_when_llm_fails(self):
        """If the router raises an exception, a fallback summary is used."""
        consolidator = MemoryConsolidator.__new__(MemoryConsolidator)
        router = MagicMock()
        router.route = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        consolidator._router = router
        consolidator._store = {}
        consolidator._last_consolidation = {}
        _mock_embed(consolidator)

        events = trade_events(12)
        result = await consolidator.consolidate("npc1", events, tick=100)

        # Should still produce a summary (fallback)
        assert len(result.new_summaries) >= 1
        assert result.new_summaries[0].summary_text != ""

    @pytest.mark.asyncio
    async def test_one_llm_call_per_category(self):
        """One LLM call is made per qualifying category."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12) + work_events(11)
        await consolidator.consolidate("npc1", events, tick=100)

        assert consolidator._router.route.await_count == 2


# ---------------------------------------------------------------------------
# test_consolidated_retrieval
# ---------------------------------------------------------------------------


class TestConsolidatedRetrieval:
    """Consolidated memories must be retrieved with higher importance weight."""

    @pytest.mark.asyncio
    async def test_consolidated_memories_have_high_importance(self):
        """Consolidated memories must have importance_score == CONSOLIDATED_IMPORTANCE."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12)
        result = await consolidator.consolidate("npc1", events, tick=100)

        for mem in result.new_summaries:
            assert mem.importance_score == CONSOLIDATED_IMPORTANCE, (
                f"Expected importance_score={CONSOLIDATED_IMPORTANCE}, got {mem.importance_score}"
            )

    @pytest.mark.asyncio
    async def test_get_consolidated_memories_returns_stored(self):
        """get_consolidated_memories returns the memories that were stored."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12)
        await consolidator.consolidate("npc1", events, tick=100)

        retrieved = consolidator.get_consolidated_memories("npc1")
        assert len(retrieved) >= 1
        assert all(isinstance(m, ConsolidatedMemory) for m in retrieved)

    @pytest.mark.asyncio
    async def test_get_consolidated_memories_respects_limit(self):
        """get_consolidated_memories must respect the limit parameter."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        # Create 3 categories worth of memories
        events = trade_events(12) + work_events(11)

        # Social events
        social_evs = [{"event_type": "social_success", "tick": i} for i in range(11)]
        await consolidator.consolidate("npc1", events + social_evs, tick=100)

        retrieved = consolidator.get_consolidated_memories("npc1", limit=2)
        assert len(retrieved) <= 2

    @pytest.mark.asyncio
    async def test_get_consolidated_memories_sorted_by_importance(self):
        """Memories are returned sorted by importance_score descending."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        # Manually inject two memories with different importance scores
        mem_high = ConsolidatedMemory(
            npc_id="npc1", category="trade", summary_text="high", event_count=10,
            tick_range=(0, 100), embedding=[], importance_score=0.9,
        )
        mem_low = ConsolidatedMemory(
            npc_id="npc1", category="work", summary_text="low", event_count=5,
            tick_range=(0, 50), embedding=[], importance_score=0.3,
        )
        consolidator._store["npc1"] = [mem_low, mem_high]

        retrieved = consolidator.get_consolidated_memories("npc1")
        assert retrieved[0].importance_score >= retrieved[-1].importance_score

    @pytest.mark.asyncio
    async def test_memories_for_different_npcs_are_separate(self):
        """Memories stored for npc1 should not be returned for npc2."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12)
        await consolidator.consolidate("npc1", events, tick=100)

        assert consolidator.get_consolidated_memories("npc2") == []


# ---------------------------------------------------------------------------
# test_tick_interval
# ---------------------------------------------------------------------------


class TestTickInterval:
    """should_consolidate must respect the 50-tick minimum interval."""

    def test_no_consolidation_before_interval(self):
        """should_consolidate returns False when fewer than 50 ticks have passed."""
        consolidator = make_consolidator()

        # First time: record consolidation at tick 0
        consolidator._last_consolidation["npc1"] = 0

        # At tick 30, 30 < 50
        assert consolidator.should_consolidate("npc1", current_tick=30) is False

    def test_consolidation_at_exactly_interval(self):
        """should_consolidate returns True at exactly the 50-tick boundary."""
        consolidator = make_consolidator()

        consolidator._last_consolidation["npc1"] = 100
        assert consolidator.should_consolidate("npc1", current_tick=150) is True

    def test_consolidation_after_interval(self):
        """should_consolidate returns True when more than 50 ticks have passed."""
        consolidator = make_consolidator()

        consolidator._last_consolidation["npc1"] = 100
        assert consolidator.should_consolidate("npc1", current_tick=200) is True

    def test_consolidation_with_explicit_last_tick(self):
        """Caller can pass last_consolidation_tick explicitly."""
        consolidator = make_consolidator()

        assert consolidator.should_consolidate("npc1", current_tick=200, last_consolidation_tick=100) is True
        assert consolidator.should_consolidate("npc1", current_tick=110, last_consolidation_tick=100) is False

    def test_first_time_npc_always_can_consolidate(self):
        """An NPC with no consolidation history is always eligible."""
        consolidator = make_consolidator()
        # No entry in _last_consolidation
        assert consolidator.should_consolidate("brand_new_npc", current_tick=0) is True

    def test_last_consolidation_tick_updated_after_run(self):
        """After consolidate(), last tick is recorded correctly."""
        import asyncio

        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12)
        asyncio.get_event_loop().run_until_complete(
            consolidator.consolidate("npc1", events, tick=250)
        )

        assert consolidator._last_consolidation.get("npc1") == 250

    @pytest.mark.asyncio
    async def test_consolidation_result_has_correct_tick(self):
        """ConsolidationResult.tick matches the tick passed to consolidate()."""
        consolidator = make_consolidator()
        _mock_embed(consolidator)

        events = trade_events(12)
        result = await consolidator.consolidate("npc1", events, tick=333)

        assert result.tick == 333
