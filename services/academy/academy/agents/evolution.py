"""
NPC Personality Evolution — P5-005.

Long-term personality drift driven by accumulated experiences and milestone events.
Trait history is stored for visualization; goals are generated via ModelRouter.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from academy.agents.personality import PersonalityProfile

logger = logging.getLogger("academy.agents.evolution")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRAIT_NAMES: tuple[str, ...] = (
    "risk_tolerance",
    "sociability",
    "ambition",
    "creativity",
    "aggression",
)

# Maximum absolute change a single tick evaluation can produce per trait.
MAX_DELTA_PER_TICK: float = 0.02

# Per-event-type contributions: (trait, delta).
# Positive delta pushes the trait up; negative pulls it down.
_EVENT_CONTRIBUTIONS: dict[str, list[tuple[str, float]]] = {
    "trade_success": [("ambition", 0.008), ("risk_tolerance", 0.005)],
    "trade_failure": [("ambition", -0.005), ("risk_tolerance", -0.003)],
    "social_success": [("sociability", 0.008), ("aggression", -0.004)],
    "social_failure": [("sociability", -0.005), ("aggression", 0.003)],
    "combat_win": [("aggression", 0.008), ("risk_tolerance", 0.005)],
    "combat_loss": [("aggression", -0.004), ("risk_tolerance", -0.006)],
    "creative_work": [("creativity", 0.008), ("ambition", 0.003)],
    "exploration": [("risk_tolerance", 0.007), ("creativity", 0.004)],
    "community_help": [("sociability", 0.006), ("aggression", -0.003)],
    "theft": [("risk_tolerance", 0.006), ("aggression", 0.005), ("sociability", -0.005)],
    "work_completed": [("ambition", 0.005), ("risk_tolerance", 0.002)],
    "rest": [("risk_tolerance", -0.002), ("aggression", -0.003)],
}

# Milestone events cause larger one-time shifts.
_MILESTONE_SHIFTS: dict[str, list[tuple[str, float]]] = {
    "first_crime": [("aggression", 0.10), ("risk_tolerance", 0.07), ("sociability", -0.05)],
    "first_child": [("risk_tolerance", -0.05), ("sociability", 0.06), ("ambition", 0.04)],
    "first_murder": [("aggression", 0.15), ("sociability", -0.10), ("risk_tolerance", 0.05)],
    "bankruptcy": [("ambition", -0.10), ("risk_tolerance", -0.08)],
    "great_wealth": [("ambition", 0.08), ("risk_tolerance", 0.05), ("sociability", -0.04)],
    "exile": [("sociability", -0.10), ("creativity", 0.06), ("risk_tolerance", 0.05)],
    "elected_leader": [("ambition", 0.08), ("sociability", 0.07), ("aggression", -0.04)],
    "lost_friend": [("sociability", -0.06), ("aggression", 0.04)],
    "discovered_talent": [("creativity", 0.10), ("ambition", 0.05)],
}

GOAL_TYPES: tuple[str, ...] = ("wealth", "social", "power", "knowledge", "peace")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LongTermGoal:
    """A persistent NPC objective derived from personality and town context."""

    goal_type: str  # wealth | social | power | knowledge | peace
    target_value: float  # abstract progress target (0–1)
    progress: float  # current progress toward target_value (0–1)
    deadline_tick: int  # tick by which this goal should be reached
    motivation_text: str  # LLM-generated flavour text


@dataclass
class GoalProgress:
    """Assessment of whether a goal is advancing, stalling, or complete."""

    goal: LongTermGoal
    is_complete: bool
    delta: float  # change in progress this evaluation
    status: str  # "advancing" | "stalling" | "complete" | "failed"


@dataclass
class EvolutionResult:
    """Output of a single personality evolution evaluation."""

    npc_id: str
    tick: int
    trait_changes: dict[str, float]          # trait → signed delta applied
    updated_personality: PersonalityProfile  # personality after changes
    trait_history_entry: dict[str, Any]      # snapshot for visualization
    new_goals: list[LongTermGoal]
    completed_goals: list[LongTermGoal]
    milestone_events: list[str]              # names of milestones triggered


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _apply_delta(traits: dict[str, float], trait: str, delta: float) -> float:
    """Apply delta to a trait value and return the new clamped value."""
    old = traits.get(trait, 0.5)
    new = _clamp(old + delta)
    traits[trait] = new
    return new - old  # actual applied change (may differ if clamped)


# ---------------------------------------------------------------------------
# PersonalityEvolver
# ---------------------------------------------------------------------------


class PersonalityEvolver:
    """
    Derives slow personality drift from accumulated NPC experiences.

    Usage::

        evolver = PersonalityEvolver()
        result = await evolver.evolve(
            npc_id="42",
            personality=profile,
            recent_events=[{"event_type": "trade_success"}, ...],
            tick=300,
        )
    """

    def __init__(self) -> None:
        from academy.models.router import ModelRouter

        self._router = ModelRouter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evolve(
        self,
        npc_id: str,
        personality: PersonalityProfile,
        recent_events: list[dict[str, Any]],
        tick: int,
        existing_goals: list[LongTermGoal] | None = None,
        town_state: dict[str, Any] | None = None,
    ) -> EvolutionResult:
        """
        Compute personality drift for one tick evaluation.

        Steps:
          1. Tally per-trait deltas from regular events.
          2. Cap total delta per trait at MAX_DELTA_PER_TICK.
          3. Apply milestone events (additive on top of regular, still clamped to [0,1]).
          4. Update goals (check completion, generate new ones if needed).
          5. Record trait snapshot.
        """
        traits = dict(personality.to_dict())
        applied_changes: dict[str, float] = {t: 0.0 for t in TRAIT_NAMES}
        milestone_events: list[str] = []
        completed_goals: list[LongTermGoal] = []

        # Step 1 — accumulate regular event contributions
        raw_deltas: dict[str, float] = {t: 0.0 for t in TRAIT_NAMES}
        for event in recent_events:
            event_type = event.get("event_type", "")
            contributions = _EVENT_CONTRIBUTIONS.get(event_type, [])
            for trait, delta in contributions:
                raw_deltas[trait] = raw_deltas.get(trait, 0.0) + delta

        # Step 2 — cap regular deltas and apply
        for trait in TRAIT_NAMES:
            delta = raw_deltas.get(trait, 0.0)
            # Clamp to ±MAX_DELTA_PER_TICK
            capped = max(-MAX_DELTA_PER_TICK, min(MAX_DELTA_PER_TICK, delta))
            if capped != 0.0:
                applied_changes[trait] += _apply_delta(traits, trait, capped)

        # Step 3 — milestone events (larger, uncapped by MAX_DELTA but still [0,1])
        for event in recent_events:
            event_type = event.get("event_type", "")
            if event_type in _MILESTONE_SHIFTS:
                milestone_events.append(event_type)
                for trait, delta in _MILESTONE_SHIFTS[event_type]:
                    applied_changes[trait] += _apply_delta(traits, trait, delta)

        updated_personality = PersonalityProfile(
            risk_tolerance=round(traits["risk_tolerance"], 4),
            sociability=round(traits["sociability"], 4),
            ambition=round(traits["ambition"], 4),
            creativity=round(traits["creativity"], 4),
            aggression=round(traits["aggression"], 4),
        )

        # Step 4 — evaluate existing goal progress
        goals_to_keep: list[LongTermGoal] = []
        if existing_goals:
            for goal in existing_goals:
                progress_result = self.evaluate_goal_progress(goal, {"personality": traits, "tick": tick})
                if progress_result.is_complete:
                    completed_goals.append(goal)
                elif tick > goal.deadline_tick:
                    # Expired without completion — drop silently
                    pass
                else:
                    goal.progress = min(1.0, goal.progress + max(0.0, progress_result.delta))
                    goals_to_keep.append(goal)

        # Generate new goals if fewer than 2 remain
        new_goals: list[LongTermGoal] = []
        if len(goals_to_keep) < 2:
            new_goals = await self.generate_goals(updated_personality, town_state or {}, tick)

        # Step 5 — trait history snapshot
        trait_history_entry: dict[str, Any] = {
            "tick": tick,
            "npc_id": npc_id,
            "traits": updated_personality.to_dict(),
            "changes": {k: round(v, 5) for k, v in applied_changes.items() if v != 0.0},
            "milestones": milestone_events,
        }

        return EvolutionResult(
            npc_id=npc_id,
            tick=tick,
            trait_changes={k: round(v, 5) for k, v in applied_changes.items()},
            updated_personality=updated_personality,
            trait_history_entry=trait_history_entry,
            new_goals=new_goals,
            completed_goals=completed_goals,
            milestone_events=milestone_events,
        )

    async def generate_goals(
        self,
        personality: PersonalityProfile,
        town_state: dict[str, Any],
        tick: int,
    ) -> list[LongTermGoal]:
        """
        Use ModelRouter(task_type='planning') to generate 1–3 personality-aligned goals.

        The LLM returns a JSON array of goal objects.
        """
        traits = personality.to_dict()
        dominant_traits = sorted(traits.items(), key=lambda kv: kv[1], reverse=True)[:2]
        dominant_str = ", ".join(f"{t}={v:.2f}" for t, v in dominant_traits)

        system_prompt = (
            "You are an NPC goal planner for a medieval town simulation. "
            "Given an NPC's personality traits and current town state, generate "
            "1 to 3 long-term goals. "
            "Reply ONLY with a JSON array (no markdown) where each element has keys: "
            "goal_type (one of: wealth, social, power, knowledge, peace), "
            "target_value (float 0-1), progress (float 0-0.1, start small), "
            "deadline_ticks (int, how many ticks from now), motivation_text (string, 1 sentence)."
        )
        user_prompt = (
            f"Personality traits: {json.dumps(traits, indent=None)}\n"
            f"Dominant traits: {dominant_str}\n"
            f"Current tick: {tick}\n"
            f"Town state summary: {json.dumps(town_state, indent=None)[:500]}\n"
            "Generate goals aligned with this NPC's personality."
        )

        try:
            raw = await self._router.route("planning", user_prompt, system=system_prompt)
            goals = self._parse_goals(raw, tick)
        except Exception as exc:
            logger.warning("Goal generation failed for tick %d: %s", tick, exc)
            goals = []

        # Fall back to heuristic goals if parsing produced nothing
        if not goals:
            goals = self._default_goals(personality, tick)

        return goals[:3]  # never return more than 3

    def evaluate_goal_progress(
        self,
        goal: LongTermGoal,
        npc_state: dict[str, Any],
    ) -> GoalProgress:
        """
        Check how much a goal has advanced given the current NPC state.

        Uses simple heuristics based on personality alignment rather than
        requiring additional LLM calls.
        """
        tick = npc_state.get("tick", 0)
        personality = npc_state.get("personality", {})

        # Derive progress delta from how aligned the NPC's dominant traits are
        # with the goal type.
        alignment = self._goal_trait_alignment(goal.goal_type, personality)
        # Base delta per evaluation: alignment drives faster progress
        delta = alignment * 0.05

        new_progress = goal.progress + delta
        is_complete = new_progress >= goal.target_value

        if is_complete:
            status = "complete"
        elif tick > goal.deadline_tick:
            status = "failed"
        elif delta > 0.0:
            status = "advancing"
        else:
            status = "stalling"

        return GoalProgress(
            goal=goal,
            is_complete=is_complete,
            delta=round(delta, 4),
            status=status,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _goal_trait_alignment(goal_type: str, traits: dict[str, float]) -> float:
        """Return 0–1 alignment score between a goal type and personality traits."""
        mapping: dict[str, list[str]] = {
            "wealth": ["ambition", "risk_tolerance"],
            "social": ["sociability", "creativity"],
            "power": ["ambition", "aggression"],
            "knowledge": ["creativity", "risk_tolerance"],
            "peace": ["sociability"],
        }
        relevant = mapping.get(goal_type, ["ambition"])
        values = [traits.get(t, 0.5) for t in relevant]
        return sum(values) / len(values)

    @staticmethod
    def _parse_goals(raw: str, tick: int) -> list[LongTermGoal]:
        """Parse LLM JSON output into LongTermGoal objects."""
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            # Try to find a JSON array in the output
            import re
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                items = json.loads(match.group(0))
            else:
                return []

        goals: list[LongTermGoal] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            goal_type = item.get("goal_type", "wealth")
            if goal_type not in GOAL_TYPES:
                goal_type = "wealth"
            goals.append(
                LongTermGoal(
                    goal_type=goal_type,
                    target_value=float(_clamp(item.get("target_value", 0.8))),
                    progress=float(_clamp(item.get("progress", 0.0), 0.0, 0.2)),
                    deadline_tick=tick + max(50, int(item.get("deadline_ticks", 200))),
                    motivation_text=str(item.get("motivation_text", ""))[:200],
                )
            )
        return goals

    @staticmethod
    def _default_goals(personality: PersonalityProfile, tick: int) -> list[LongTermGoal]:
        """Fallback goals derived purely from personality without LLM."""
        traits = personality.to_dict()
        # Pick the 1–2 highest traits and map them to goal types
        sorted_traits = sorted(traits.items(), key=lambda kv: kv[1], reverse=True)
        trait_to_goal: dict[str, str] = {
            "ambition": "wealth",
            "sociability": "social",
            "aggression": "power",
            "creativity": "knowledge",
            "risk_tolerance": "knowledge",
        }
        seen: set[str] = set()
        goals: list[LongTermGoal] = []
        for trait, value in sorted_traits[:2]:
            goal_type = trait_to_goal.get(trait, "peace")
            if goal_type in seen:
                continue
            seen.add(goal_type)
            goals.append(
                LongTermGoal(
                    goal_type=goal_type,
                    target_value=0.7,
                    progress=0.0,
                    deadline_tick=tick + 300,
                    motivation_text=f"Driven by strong {trait}, this NPC seeks {goal_type}.",
                )
            )
        return goals
