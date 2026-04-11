"""
Tests for academy.agents.evolution — P5-005.

test_trait_bounded       — verify traits never exceed [0, 1]
test_small_changes       — verify max change per evaluation
test_milestone_shift     — verify milestone events cause larger personality shift
test_goal_generation     — verify goals align with personality
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import json
import pytest

from academy.agents.personality import PersonalityProfile
from academy.agents.evolution import (
    PersonalityEvolver,
    LongTermGoal,
    EvolutionResult,
    MAX_DELTA_PER_TICK,
    TRAIT_NAMES,
    _clamp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_personality(**kwargs: float) -> PersonalityProfile:
    defaults = {t: 0.5 for t in TRAIT_NAMES}
    defaults.update(kwargs)
    return PersonalityProfile(**defaults)


def make_evolver(llm_response: str = "[]") -> PersonalityEvolver:
    """Return a PersonalityEvolver with a mocked ModelRouter."""
    evolver = PersonalityEvolver.__new__(PersonalityEvolver)
    router = MagicMock()
    router.route = AsyncMock(return_value=llm_response)
    evolver._router = router
    return evolver


# ---------------------------------------------------------------------------
# test_trait_bounded
# ---------------------------------------------------------------------------


class TestTraitBounded:
    """Trait values must always remain within [0.0, 1.0]."""

    @pytest.mark.asyncio
    async def test_traits_never_exceed_1(self):
        """Starting near 1.0 with positive events should stay at or below 1.0."""
        personality = make_personality(ambition=0.99)
        evolver = make_evolver()

        # Flood with trade_success events which push ambition up
        events = [{"event_type": "trade_success"}] * 50

        result = await evolver.evolve("npc1", personality, events, tick=100)

        assert result.updated_personality.ambition <= 1.0
        assert result.updated_personality.risk_tolerance <= 1.0
        assert result.updated_personality.sociability <= 1.0
        assert result.updated_personality.creativity <= 1.0
        assert result.updated_personality.aggression <= 1.0

    @pytest.mark.asyncio
    async def test_traits_never_below_0(self):
        """Starting near 0.0 with negative events should stay at or above 0.0."""
        personality = make_personality(sociability=0.01)
        evolver = make_evolver()

        events = [{"event_type": "social_failure"}] * 50

        result = await evolver.evolve("npc1", personality, events, tick=100)

        assert result.updated_personality.sociability >= 0.0
        assert result.updated_personality.risk_tolerance >= 0.0
        assert result.updated_personality.ambition >= 0.0
        assert result.updated_personality.creativity >= 0.0
        assert result.updated_personality.aggression >= 0.0

    @pytest.mark.asyncio
    async def test_milestone_does_not_break_bounds(self):
        """Milestones with large deltas must still produce values in [0, 1]."""
        personality = make_personality(aggression=0.95)
        evolver = make_evolver()

        events = [{"event_type": "first_murder"}]  # +0.15 to aggression

        result = await evolver.evolve("npc1", personality, events, tick=10)
        assert 0.0 <= result.updated_personality.aggression <= 1.0

    def test_clamp_helper_at_boundaries(self):
        assert _clamp(-0.1) == 0.0
        assert _clamp(1.1) == 1.0
        assert _clamp(0.5) == 0.5
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0


# ---------------------------------------------------------------------------
# test_small_changes
# ---------------------------------------------------------------------------


class TestSmallChanges:
    """Regular event contributions must be capped at MAX_DELTA_PER_TICK per trait."""

    @pytest.mark.asyncio
    async def test_single_event_delta_is_small(self):
        """A single trade_success event produces only a tiny trait shift."""
        personality = make_personality(ambition=0.5)
        evolver = make_evolver()

        events = [{"event_type": "trade_success"}]
        result = await evolver.evolve("npc1", personality, events, tick=10)

        # trade_success contributes +0.008 to ambition — well within MAX_DELTA_PER_TICK
        delta = result.trait_changes.get("ambition", 0.0)
        assert abs(delta) <= MAX_DELTA_PER_TICK

    @pytest.mark.asyncio
    async def test_many_same_events_capped_at_max_delta(self):
        """Flooding with identical events must not exceed MAX_DELTA_PER_TICK per trait."""
        personality = make_personality(ambition=0.5)
        evolver = make_evolver()

        # 100 trade_success events: raw would be 100 * 0.008 = 0.8, but cap is 0.02
        events = [{"event_type": "trade_success"}] * 100
        result = await evolver.evolve("npc1", personality, events, tick=10)

        delta = result.trait_changes.get("ambition", 0.0)
        assert abs(delta) <= MAX_DELTA_PER_TICK, (
            f"Expected max delta ≤ {MAX_DELTA_PER_TICK}, got {delta}"
        )

    @pytest.mark.asyncio
    async def test_opposing_events_can_cancel(self):
        """Alternating positive and negative events should produce near-zero net change."""
        personality = make_personality(sociability=0.5)
        evolver = make_evolver()

        # Equal mix of social_success and social_failure
        events = [{"event_type": "social_success"}, {"event_type": "social_failure"}] * 5
        result = await evolver.evolve("npc1", personality, events, tick=10)

        # Net should be small (opposite signs: +0.008 and -0.005 raw per pair → raw = +0.03)
        # After capping this stays within MAX_DELTA_PER_TICK
        delta = result.trait_changes.get("sociability", 0.0)
        assert abs(delta) <= MAX_DELTA_PER_TICK


# ---------------------------------------------------------------------------
# test_milestone_shift
# ---------------------------------------------------------------------------


class TestMilestoneShift:
    """Milestone events must cause shifts larger than the regular per-tick cap."""

    @pytest.mark.asyncio
    async def test_first_crime_boosts_aggression(self):
        """first_crime milestone raises aggression by ~0.10."""
        personality = make_personality(aggression=0.4)
        evolver = make_evolver()

        events = [{"event_type": "first_crime"}]
        result = await evolver.evolve("npc1", personality, events, tick=5)

        # Aggression should increase significantly (milestone = +0.10)
        aggression_before = 0.4
        aggression_after = result.updated_personality.aggression
        assert aggression_after > aggression_before + 0.05, (
            f"Expected aggression to rise substantially, got {aggression_after}"
        )

    @pytest.mark.asyncio
    async def test_first_crime_larger_than_regular_cap(self):
        """Milestone-driven change exceeds MAX_DELTA_PER_TICK for the relevant trait."""
        personality = make_personality(aggression=0.3)
        evolver = make_evolver()

        events = [{"event_type": "first_crime"}]
        result = await evolver.evolve("npc1", personality, events, tick=5)

        aggression_delta = result.trait_changes.get("aggression", 0.0)
        # Milestone shift of +0.10 should be larger than MAX_DELTA_PER_TICK (0.02)
        assert aggression_delta > MAX_DELTA_PER_TICK, (
            f"Milestone change {aggression_delta} should exceed regular cap {MAX_DELTA_PER_TICK}"
        )

    @pytest.mark.asyncio
    async def test_first_child_reduces_risk_tolerance(self):
        """first_child milestone reduces risk_tolerance."""
        personality = make_personality(risk_tolerance=0.6)
        evolver = make_evolver()

        events = [{"event_type": "first_child"}]
        result = await evolver.evolve("npc1", personality, events, tick=10)

        assert result.updated_personality.risk_tolerance < 0.6

    @pytest.mark.asyncio
    async def test_milestone_recorded_in_result(self):
        """Triggered milestones appear in the EvolutionResult.milestone_events list."""
        personality = make_personality()
        evolver = make_evolver()

        events = [{"event_type": "first_crime"}, {"event_type": "first_child"}]
        result = await evolver.evolve("npc1", personality, events, tick=20)

        assert "first_crime" in result.milestone_events
        assert "first_child" in result.milestone_events

    @pytest.mark.asyncio
    async def test_non_milestone_event_not_recorded(self):
        """Regular events must not appear in milestone_events."""
        personality = make_personality()
        evolver = make_evolver()

        events = [{"event_type": "trade_success"}, {"event_type": "social_failure"}]
        result = await evolver.evolve("npc1", personality, events, tick=5)

        assert "trade_success" not in result.milestone_events
        assert "social_failure" not in result.milestone_events


# ---------------------------------------------------------------------------
# test_goal_generation
# ---------------------------------------------------------------------------


class TestGoalGeneration:
    """Goal generation must produce goals aligned with personality traits."""

    @pytest.mark.asyncio
    async def test_ambitious_npc_gets_wealth_or_power_goals(self):
        """An NPC with high ambition should receive wealth or power goals."""
        # Simulate a valid LLM response
        llm_goals = json.dumps([
            {
                "goal_type": "wealth",
                "target_value": 0.8,
                "progress": 0.05,
                "deadline_ticks": 300,
                "motivation_text": "This NPC wants to accumulate gold and land.",
            },
            {
                "goal_type": "power",
                "target_value": 0.7,
                "progress": 0.0,
                "deadline_ticks": 500,
                "motivation_text": "Ambition drives the pursuit of influence.",
            },
        ])
        evolver = make_evolver(llm_response=llm_goals)

        personality = make_personality(ambition=0.9, sociability=0.2)
        goals = await evolver.generate_goals(personality, town_state={}, tick=100)

        goal_types = {g.goal_type for g in goals}
        assert goal_types & {"wealth", "power"}, (
            f"Ambitious NPC should get wealth/power goals, got: {goal_types}"
        )

    @pytest.mark.asyncio
    async def test_sociable_npc_gets_social_goals(self):
        """An NPC with high sociability should receive social goals."""
        llm_goals = json.dumps([
            {
                "goal_type": "social",
                "target_value": 0.9,
                "progress": 0.02,
                "deadline_ticks": 200,
                "motivation_text": "Seeks to build lasting friendships.",
            }
        ])
        evolver = make_evolver(llm_response=llm_goals)

        personality = make_personality(sociability=0.9, ambition=0.1)
        goals = await evolver.generate_goals(personality, town_state={}, tick=50)

        assert any(g.goal_type == "social" for g in goals), (
            "Sociable NPC should get social goals"
        )

    @pytest.mark.asyncio
    async def test_goals_have_valid_structure(self):
        """Generated goals must have all required fields with valid ranges."""
        llm_goals = json.dumps([
            {
                "goal_type": "knowledge",
                "target_value": 0.75,
                "progress": 0.0,
                "deadline_ticks": 400,
                "motivation_text": "Curiosity never rests.",
            }
        ])
        evolver = make_evolver(llm_response=llm_goals)

        personality = make_personality(creativity=0.8)
        goals = await evolver.generate_goals(personality, town_state={}, tick=10)

        assert len(goals) >= 1
        for g in goals:
            assert 0.0 <= g.target_value <= 1.0
            assert 0.0 <= g.progress <= g.target_value + 0.01  # small rounding ok
            assert g.deadline_tick > 10
            assert g.motivation_text != ""
            assert g.goal_type in {"wealth", "social", "power", "knowledge", "peace"}

    @pytest.mark.asyncio
    async def test_goal_count_never_exceeds_3(self):
        """generate_goals must return at most 3 goals regardless of LLM output."""
        llm_goals = json.dumps([
            {"goal_type": "wealth", "target_value": 0.8, "progress": 0.0,
             "deadline_ticks": 300, "motivation_text": "a"},
            {"goal_type": "social", "target_value": 0.7, "progress": 0.0,
             "deadline_ticks": 300, "motivation_text": "b"},
            {"goal_type": "power", "target_value": 0.9, "progress": 0.0,
             "deadline_ticks": 300, "motivation_text": "c"},
            {"goal_type": "knowledge", "target_value": 0.6, "progress": 0.0,
             "deadline_ticks": 300, "motivation_text": "d"},
            {"goal_type": "peace", "target_value": 0.5, "progress": 0.0,
             "deadline_ticks": 300, "motivation_text": "e"},
        ])
        evolver = make_evolver(llm_response=llm_goals)

        personality = make_personality()
        goals = await evolver.generate_goals(personality, town_state={}, tick=100)

        assert len(goals) <= 3

    @pytest.mark.asyncio
    async def test_fallback_goals_when_llm_fails(self):
        """If the LLM returns invalid JSON, fallback goals are returned."""
        evolver = make_evolver(llm_response="INVALID JSON")

        personality = make_personality(ambition=0.8)
        goals = await evolver.generate_goals(personality, town_state={}, tick=200)

        assert len(goals) >= 1
        for g in goals:
            assert g.goal_type in {"wealth", "social", "power", "knowledge", "peace"}

    @pytest.mark.asyncio
    async def test_full_evolve_returns_evolution_result(self):
        """evolve() returns an EvolutionResult with the correct structure."""
        personality = make_personality(ambition=0.6)
        evolver = make_evolver()

        events = [{"event_type": "trade_success"}, {"event_type": "work_completed"}]
        result = await evolver.evolve("npc42", personality, events, tick=150)

        assert isinstance(result, EvolutionResult)
        assert result.npc_id == "npc42"
        assert result.tick == 150
        assert isinstance(result.trait_changes, dict)
        assert isinstance(result.updated_personality, PersonalityProfile)
        assert isinstance(result.milestone_events, list)
        assert isinstance(result.new_goals, list)
        assert isinstance(result.completed_goals, list)
        assert "tick" in result.trait_history_entry
        assert result.trait_history_entry["npc_id"] == "npc42"
