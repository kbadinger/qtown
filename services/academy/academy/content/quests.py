"""
Quest generation — procedural quests for Qtown NPCs.

QuestGenerator produces structured Quest objects using the ModelRouter.
Quests are tagged by type (fetch, trade, social, explore) and include
objectives, rewards, and a deadline.
"""

from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from academy.models.router import ModelRouter

logger = logging.getLogger("academy.content.quests")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUEST_TYPES = ["fetch", "trade", "social", "explore"]

DIFFICULTY_TIERS = {
    "easy":   {"gold_range": (10, 50),   "xp_range": (20, 80),   "deadline": 20},
    "medium": {"gold_range": (50, 150),  "xp_range": (80, 200),  "deadline": 40},
    "hard":   {"gold_range": (150, 400), "xp_range": (200, 500), "deadline": 60},
    "epic":   {"gold_range": (400, 999), "xp_range": (500, 999), "deadline": 100},
}

# Type-specific objective templates (used when LLM fallback is needed)
_OBJECTIVE_TEMPLATES: dict[str, list[str]] = {
    "fetch": [
        "Travel to {location} and retrieve {item}",
        "Collect {quantity} units of {item} from {location}",
        "Bring {item} back to {npc_name} before the deadline",
    ],
    "trade": [
        "Visit the Market District and sell {quantity} {item} for at least {gold} gold",
        "Buy {item} from a merchant in the Market District",
        "Complete {quantity} trades at the Market District",
    ],
    "social": [
        "Speak with {quantity} different NPCs in {neighborhood}",
        "Deliver a message from {npc_name} to another citizen",
        "Attend the town gathering and meet {quantity} new NPCs",
    ],
    "explore": [
        "Visit {quantity} distinct neighborhoods in Qtown",
        "Map the {location} district by walking its streets",
        "Discover and report a new location in {neighborhood}",
    ],
}

_LOCATIONS = [
    "Market District", "Academy", "Farmlands", "Riverside", "Old Quarter",
    "Town Square", "Harbor", "Blacksmith Row", "Temple Hill", "North Gate",
]

_ITEMS = [
    "wheat", "iron ore", "medicinal herbs", "enchanted parchment", "fresh fish",
    "leather", "timber", "copper coins", "ancient relic", "trade goods",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Quest:
    """
    A structured quest for an NPC.

    Fields
    ------
    quest_id:
        UUID string uniquely identifying this quest.
    title:
        Short quest title (< 60 chars).
    description:
        Narrative description of the quest context.
    objectives:
        Ordered list of concrete objectives the NPC must complete.
    reward_gold:
        Gold awarded on completion.
    reward_xp:
        Experience points awarded on completion.
    difficulty:
        One of: easy, medium, hard, epic.
    quest_type:
        One of: fetch, trade, social, explore.
    assigned_npc_id:
        ID of the NPC this quest is assigned to.
    deadline_ticks:
        Number of ticks from assignment until the quest expires.
    created_at:
        UTC ISO-8601 timestamp of generation.
    model_used:
        Model that generated this quest (for audit).
    """

    quest_id: str
    title: str
    description: str
    objectives: list[str]
    reward_gold: int
    reward_xp: int
    difficulty: str
    quest_type: str
    assigned_npc_id: str
    deadline_ticks: int
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    model_used: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "title": self.title,
            "description": self.description,
            "objectives": self.objectives,
            "reward_gold": self.reward_gold,
            "reward_xp": self.reward_xp,
            "difficulty": self.difficulty,
            "quest_type": self.quest_type,
            "assigned_npc_id": self.assigned_npc_id,
            "deadline_ticks": self.deadline_ticks,
            "created_at": self.created_at,
            "model_used": self.model_used,
        }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class QuestGenerator:
    """
    Generates quests for NPCs using the ModelRouter.

    Usage::

        gen = QuestGenerator()
        quest = await gen.generate_quest(npc, town_state, difficulty="medium")
    """

    _SYSTEM_PROMPT = (
        "You are a quest designer for Qtown, a fantasy medieval town simulation. "
        "You create immersive, specific, and achievable quests for NPC citizens. "
        "Quests should feel grounded in the town's daily life and economy."
    )

    def __init__(self, router: ModelRouter | None = None, rng_seed: int | None = None) -> None:
        self._router = router or ModelRouter()
        self._rng = random.Random(rng_seed)

    def _pick_quest_type(self, npc: dict[str, Any], town_state: dict[str, Any]) -> str:
        """
        Choose a quest type based on NPC traits and town state.

        Personality hints:
          - High ambition → prefer trade
          - High sociability → prefer social
          - High risk_tolerance → prefer explore
          - Default → fetch
        """
        personality = npc.get("personality", {})
        ambition = personality.get("ambition", 0.5)
        sociability = personality.get("sociability", 0.5)
        risk_tolerance = personality.get("risk_tolerance", 0.5)

        weights = {
            "fetch":   0.25,
            "trade":   0.25 + 0.30 * ambition,
            "social":  0.25 + 0.30 * sociability,
            "explore": 0.25 + 0.30 * risk_tolerance,
        }
        total = sum(weights.values())
        roll = self._rng.uniform(0, total)
        cumulative = 0.0
        for qtype, w in weights.items():
            cumulative += w
            if roll <= cumulative:
                return qtype
        return "fetch"

    def _rewards(self, difficulty: str) -> tuple[int, int]:
        """Return (gold, xp) for the given difficulty."""
        tier = DIFFICULTY_TIERS.get(difficulty, DIFFICULTY_TIERS["medium"])
        gold = self._rng.randint(*tier["gold_range"])
        xp = self._rng.randint(*tier["xp_range"])
        return gold, xp

    def _deadline(self, difficulty: str) -> int:
        tier = DIFFICULTY_TIERS.get(difficulty, DIFFICULTY_TIERS["medium"])
        base = tier["deadline"]
        return base + self._rng.randint(-5, 10)

    def _build_prompt(
        self,
        npc: dict[str, Any],
        town_state: dict[str, Any],
        difficulty: str,
        quest_type: str,
        reward_gold: int,
        reward_xp: int,
        deadline_ticks: int,
    ) -> str:
        npc_name = npc.get("name", "Unknown")
        npc_id = npc.get("id", "npc-0")
        neighborhood = npc.get("neighborhood", "Town Square")
        personality = npc.get("personality", {})
        pop = town_state.get("population", "unknown")
        mood = town_state.get("average_mood", "neutral")

        return (
            f"Generate a {difficulty} {quest_type} quest for NPC '{npc_name}' "
            f"(id={npc_id}) living in {neighborhood}.\n\n"
            f"TOWN STATE: population={pop}, average mood={mood}\n"
            f"NPC PERSONALITY: {personality}\n"
            f"QUEST TYPE: {quest_type}\n"
            f"DIFFICULTY: {difficulty}\n"
            f"REWARD: {reward_gold} gold, {reward_xp} XP\n"
            f"DEADLINE: {deadline_ticks} ticks\n\n"
            f"Quest types guide:\n"
            f"  fetch   — go to a location, bring back an item\n"
            f"  trade   — buy or sell at the Market District\n"
            f"  social  — talk to a number of NPCs\n"
            f"  explore — visit several neighborhoods\n\n"
            f"Return EXACTLY:\n"
            f"TITLE: <short quest title>\n"
            f"DESCRIPTION: <2-3 sentence narrative description>\n"
            f"OBJECTIVE_1: <first concrete objective>\n"
            f"OBJECTIVE_2: <second concrete objective>\n"
            f"OBJECTIVE_3: <optional third objective, or leave blank>\n\n"
            f"Be specific about locations, items, and quantities. "
            f"Keep it grounded in Qtown's medieval economy."
        )

    @staticmethod
    def _parse_response(raw: str, quest_type: str) -> dict[str, Any]:
        """Extract quest fields from LLM output."""
        result: dict[str, Any] = {
            "title": "",
            "description": "",
            "objectives": [],
        }

        for line in raw.splitlines():
            stripped = line.strip()
            upper = stripped.upper()
            if upper.startswith("TITLE:"):
                result["title"] = stripped[6:].strip()
            elif upper.startswith("DESCRIPTION:"):
                result["description"] = stripped[12:].strip()
            elif upper.startswith("OBJECTIVE_1:"):
                obj = stripped[12:].strip()
                if obj:
                    result["objectives"].append(obj)
            elif upper.startswith("OBJECTIVE_2:"):
                obj = stripped[12:].strip()
                if obj:
                    result["objectives"].append(obj)
            elif upper.startswith("OBJECTIVE_3:"):
                obj = stripped[12:].strip()
                if obj:
                    result["objectives"].append(obj)

        # Fallback templates if LLM output is malformed
        if not result["title"]:
            result["title"] = f"A {quest_type.title()} Task"
        if not result["description"]:
            result["description"] = f"Complete a {quest_type} task for the good of Qtown."
        if not result["objectives"]:
            templates = _OBJECTIVE_TEMPLATES.get(quest_type, _OBJECTIVE_TEMPLATES["fetch"])
            result["objectives"] = [
                t.format(
                    location=random.choice(_LOCATIONS),
                    item=random.choice(_ITEMS),
                    quantity=random.randint(2, 5),
                    npc_name="a citizen",
                    neighborhood="Town Square",
                    gold=random.randint(50, 150),
                )
                for t in templates[:2]
            ]

        return result

    async def generate_quest(
        self,
        npc: dict[str, Any],
        town_state: dict[str, Any],
        difficulty: str = "medium",
    ) -> Quest:
        """
        Generate a Quest for the given NPC.

        Parameters
        ----------
        npc:
            Dict with keys: id, name, neighborhood, personality (dict).
        town_state:
            Dict with keys: population, average_mood, etc.
        difficulty:
            One of: easy, medium, hard, epic.

        Returns
        -------
        Quest
        """
        if difficulty not in DIFFICULTY_TIERS:
            logger.warning("Unknown difficulty %r; defaulting to medium", difficulty)
            difficulty = "medium"

        quest_type = self._pick_quest_type(npc, town_state)
        reward_gold, reward_xp = self._rewards(difficulty)
        deadline_ticks = self._deadline(difficulty)

        prompt = self._build_prompt(
            npc, town_state, difficulty, quest_type,
            reward_gold, reward_xp, deadline_ticks,
        )

        npc_name = npc.get("name", "Unknown")
        npc_id = npc.get("id", "npc-0")
        logger.info(
            "Generating %s %s quest for %s (id=%s)",
            difficulty, quest_type, npc_name, npc_id,
        )

        model_used = "fallback"
        try:
            result = await self._router.route(
                "planning",
                {
                    "prompt": prompt,
                    "system": self._SYSTEM_PROMPT,
                    "temperature": 0.7,
                    "max_tokens": 300,
                },
            )
            raw = result.response
            model_used = result.model_used
        except Exception as exc:
            logger.error("Quest generation LLM call failed: %s", exc)
            raw = ""

        fields = self._parse_response(raw, quest_type)

        return Quest(
            quest_id=str(uuid.uuid4()),
            title=fields["title"],
            description=fields["description"],
            objectives=fields["objectives"],
            reward_gold=reward_gold,
            reward_xp=reward_xp,
            difficulty=difficulty,
            quest_type=quest_type,
            assigned_npc_id=npc_id,
            deadline_ticks=deadline_ticks,
            model_used=model_used,
        )
