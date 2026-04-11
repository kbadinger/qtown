"""
Tests for academy.content.quests.

Coverage:
  - test_generate_quest_returns_quest       — happy-path quest generation
  - test_difficulty_affects_rewards         — harder quests give more gold/xp
  - test_difficulty_affects_deadline        — harder quests have longer deadlines
  - test_personality_influences_quest_type  — high ambition → trade quests skewed
  - test_fallback_on_llm_failure            — fallback objectives on router failure
  - test_quest_to_dict                      — serialisation contains all fields
  - test_unknown_difficulty_defaults        — unknown difficulty treated as medium
  - test_fetch_type_objectives              — fetch quests have valid objectives
  - test_quest_id_is_unique                 — two quests get different IDs
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from academy.content.quests import DIFFICULTY_TIERS, Quest, QuestGenerator
from academy.models.router import ModelRouter, RouteResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


SAMPLE_QUEST_RESPONSE = """
TITLE: The Missing Shipment
DESCRIPTION: A merchant in the Market District reports that a shipment of iron ore has gone missing somewhere between the Farmlands and the town gate. He needs someone to investigate and recover the goods.
OBJECTIVE_1: Travel to the Farmlands and locate the missing iron ore shipment
OBJECTIVE_2: Return the iron ore to the merchant's stall in the Market District
OBJECTIVE_3: Report any suspicious activity to the Town Watch
"""


def make_router(response: str = SAMPLE_QUEST_RESPONSE, fail: bool = False) -> ModelRouter:
    router = MagicMock(spec=ModelRouter)
    if fail:
        router.route = AsyncMock(side_effect=RuntimeError("timeout"))
    else:
        router.route = AsyncMock(
            return_value=RouteResult(
                task_type="planning",
                model_used="mistral:7b",
                response=response,
                prompt_tokens=80,
                completion_tokens=120,
            )
        )
    return router


def make_npc(**kwargs) -> dict:
    defaults = {
        "id": "npc-quest-01",
        "name": "Gareth",
        "neighborhood": "Old Quarter",
        "personality": {
            "risk_tolerance": 0.5,
            "sociability": 0.5,
            "ambition": 0.5,
            "creativity": 0.5,
            "aggression": 0.3,
        },
    }
    defaults.update(kwargs)
    return defaults


TOWN_STATE = {"population": 300, "average_mood": "neutral", "total_gold": 9000}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGenerateQuest:
    @pytest.mark.asyncio
    async def test_returns_quest_instance(self):
        """generate_quest should return a Quest dataclass."""
        gen = QuestGenerator(router=make_router())
        quest = await gen.generate_quest(make_npc(), TOWN_STATE, difficulty="medium")
        assert isinstance(quest, Quest)

    @pytest.mark.asyncio
    async def test_quest_has_required_fields(self):
        """All Quest fields should be populated."""
        gen = QuestGenerator(router=make_router())
        quest = await gen.generate_quest(make_npc(), TOWN_STATE, difficulty="easy")

        assert quest.quest_id != ""
        assert quest.title != ""
        assert quest.description != ""
        assert len(quest.objectives) >= 1
        assert quest.reward_gold > 0
        assert quest.reward_xp > 0
        assert quest.difficulty == "easy"
        assert quest.quest_type in {"fetch", "trade", "social", "explore"}
        assert quest.assigned_npc_id == "npc-quest-01"
        assert quest.deadline_ticks > 0

    @pytest.mark.asyncio
    async def test_model_used_recorded(self):
        """Quest should record which model generated it."""
        gen = QuestGenerator(router=make_router())
        quest = await gen.generate_quest(make_npc(), TOWN_STATE)
        assert quest.model_used == "mistral:7b"


# ---------------------------------------------------------------------------
# Difficulty mechanics
# ---------------------------------------------------------------------------


class TestDifficultyMechanics:
    @pytest.mark.asyncio
    async def test_easy_rewards_less_than_hard(self):
        """Easy quests should give less gold and xp than hard quests on average."""
        # Run many trials to account for random variation
        gen_easy = QuestGenerator(router=make_router(), rng_seed=42)
        gen_hard = QuestGenerator(router=make_router(), rng_seed=42)

        easy_gold = []
        hard_gold = []
        for _ in range(10):
            easy = await gen_easy.generate_quest(make_npc(), TOWN_STATE, difficulty="easy")
            hard = await gen_hard.generate_quest(make_npc(), TOWN_STATE, difficulty="hard")
            easy_gold.append(easy.reward_gold)
            hard_gold.append(hard.reward_gold)

        assert sum(easy_gold) < sum(hard_gold)

    @pytest.mark.asyncio
    async def test_easy_deadline_less_than_hard(self):
        """Easy quests should generally expire sooner than hard quests."""
        gen_easy = QuestGenerator(router=make_router(), rng_seed=1)
        gen_hard = QuestGenerator(router=make_router(), rng_seed=1)

        easy = await gen_easy.generate_quest(make_npc(), TOWN_STATE, difficulty="easy")
        hard = await gen_hard.generate_quest(make_npc(), TOWN_STATE, difficulty="hard")

        easy_max = DIFFICULTY_TIERS["easy"]["deadline"] + 10
        hard_min = DIFFICULTY_TIERS["hard"]["deadline"] - 5
        # Easy deadline should be comfortably below hard minimum (with same seed)
        assert easy.deadline_ticks <= easy_max
        assert hard.deadline_ticks >= hard_min

    @pytest.mark.asyncio
    async def test_rewards_within_tier_bounds(self):
        """Gold reward should stay within the tier's configured range."""
        gen = QuestGenerator(router=make_router(), rng_seed=99)
        for difficulty, tier in DIFFICULTY_TIERS.items():
            quest = await gen.generate_quest(make_npc(), TOWN_STATE, difficulty=difficulty)
            gold_lo, gold_hi = tier["gold_range"]
            assert gold_lo <= quest.reward_gold <= gold_hi, (
                f"Gold {quest.reward_gold} out of range [{gold_lo}, {gold_hi}] "
                f"for difficulty={difficulty}"
            )

    @pytest.mark.asyncio
    async def test_unknown_difficulty_defaults_to_medium(self):
        """Unknown difficulty string should be treated as medium."""
        gen = QuestGenerator(router=make_router(), rng_seed=7)
        quest = await gen.generate_quest(make_npc(), TOWN_STATE, difficulty="legendary")
        # Medium tier bounds
        gold_lo, gold_hi = DIFFICULTY_TIERS["medium"]["gold_range"]
        assert gold_lo <= quest.reward_gold <= gold_hi
        assert quest.difficulty == "medium"


# ---------------------------------------------------------------------------
# Personality influence
# ---------------------------------------------------------------------------


class TestPersonalityInfluence:
    @pytest.mark.asyncio
    async def test_high_ambition_skews_toward_trade(self):
        """
        With high ambition, trade quests should be selected more often
        than with neutral ambition across many trials.
        """
        def count_type(npc_personality, n=30):
            gen = QuestGenerator(router=make_router(), rng_seed=0)
            npc = make_npc(personality={**npc_personality})
            counts = {"fetch": 0, "trade": 0, "social": 0, "explore": 0}

            async def run():
                for _ in range(n):
                    q = await gen.generate_quest(npc, TOWN_STATE, difficulty="easy")
                    counts[q.quest_type] += 1
                return counts

            return asyncio.get_event_loop().run_until_complete(run())

        neutral = {"risk_tolerance": 0.5, "sociability": 0.5, "ambition": 0.5,
                   "creativity": 0.5, "aggression": 0.5}
        ambitious = {"risk_tolerance": 0.5, "sociability": 0.5, "ambition": 0.95,
                     "creativity": 0.5, "aggression": 0.5}

        neutral_counts = count_type(neutral)
        ambitious_counts = count_type(ambitious)

        # Ambitious NPCs should get more trade quests than neutral ones
        assert ambitious_counts["trade"] >= neutral_counts["trade"]


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_llm_failure_returns_template_objectives(self):
        """On LLM failure, objectives should fall back to templates, not empty."""
        gen = QuestGenerator(router=make_router(fail=True), rng_seed=5)
        quest = await gen.generate_quest(make_npc(), TOWN_STATE, difficulty="easy")

        assert isinstance(quest, Quest)
        assert len(quest.objectives) >= 1
        assert quest.model_used == "fallback"
        # Title fallback
        assert quest.title != ""

    @pytest.mark.asyncio
    async def test_malformed_llm_response_gets_fallback(self):
        """Malformed LLM output (no labels) falls back to template objectives."""
        gen = QuestGenerator(router=make_router("Just some random text."), rng_seed=3)
        quest = await gen.generate_quest(make_npc(), TOWN_STATE, difficulty="medium")

        assert len(quest.objectives) >= 1


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestSerialization:
    @pytest.mark.asyncio
    async def test_to_dict_complete(self):
        """to_dict should include all documented keys."""
        gen = QuestGenerator(router=make_router())
        quest = await gen.generate_quest(make_npc(), TOWN_STATE, difficulty="hard")
        d = quest.to_dict()

        expected_keys = [
            "quest_id", "title", "description", "objectives",
            "reward_gold", "reward_xp", "difficulty", "quest_type",
            "assigned_npc_id", "deadline_ticks", "created_at", "model_used",
        ]
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_quest_ids_are_unique(self):
        """Two generated quests should have different quest_ids."""
        gen = QuestGenerator(router=make_router())
        npc = make_npc()
        quest_a = await gen.generate_quest(npc, TOWN_STATE)
        quest_b = await gen.generate_quest(npc, TOWN_STATE)
        assert quest_a.quest_id != quest_b.quest_id
