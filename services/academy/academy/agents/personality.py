"""
NPC personality system.

Provides PersonalityProfile, a weighting function that modifies action scores
based on personality traits, and a generator that produces plausible correlated
personalities.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class PersonalityProfile:
    """
    Five-axis personality for an NPC.

    Each axis is a float in [0, 1]:
      risk_tolerance  — willingness to try uncertain actions
      sociability     — preference for social interactions
      ambition        — drive to acquire wealth/status
      creativity      — tendency toward novel or varied choices
      aggression      — confrontational vs. cooperative stance
    """

    risk_tolerance: float = 0.5
    sociability: float = 0.5
    ambition: float = 0.5
    creativity: float = 0.5
    aggression: float = 0.5

    def to_dict(self) -> dict[str, float]:
        return {
            "risk_tolerance": self.risk_tolerance,
            "sociability": self.sociability,
            "ambition": self.ambition,
            "creativity": self.creativity,
            "aggression": self.aggression,
        }


# ---------------------------------------------------------------------------
# Weighting function
# ---------------------------------------------------------------------------

# Per-action trait contributions: {action: [(trait, weight), ...]}
# Positive weight means the trait boosts the action score.
# The contributions sum to a multiplier centred near 1.0.
_ACTION_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "eat": [
        ("risk_tolerance", -0.05),   # low risk → prefer safe fallback
        ("sociability", 0.0),
        ("ambition", -0.10),          # ambitious NPCs deprioritise eating
        ("creativity", 0.0),
        ("aggression", 0.0),
    ],
    "sleep": [
        ("risk_tolerance", -0.10),
        ("sociability", -0.05),
        ("ambition", -0.15),          # ambitious NPCs avoid idling
        ("creativity", 0.0),
        ("aggression", -0.05),
    ],
    "work": [
        ("risk_tolerance", 0.05),
        ("sociability", -0.05),
        ("ambition", 0.30),           # strong boost for ambitious NPCs
        ("creativity", 0.05),
        ("aggression", 0.05),
    ],
    "travel": [
        ("risk_tolerance", 0.25),     # risky — strong boost for adventurous NPCs
        ("sociability", 0.05),
        ("ambition", 0.15),           # travel to trade/learn
        ("creativity", 0.15),
        ("aggression", 0.05),
    ],
    "socialize": [
        ("risk_tolerance", 0.05),
        ("sociability", 0.35),        # strong boost for sociable NPCs
        ("ambition", -0.05),
        ("creativity", 0.10),
        ("aggression", -0.15),        # aggressive NPCs socialise less
    ],
    "idle": [
        ("risk_tolerance", -0.20),
        ("sociability", -0.10),
        ("ambition", -0.25),
        ("creativity", -0.10),
        ("aggression", -0.05),
    ],
}


def personality_weight(action: str, personality: PersonalityProfile | dict[str, float]) -> float:
    """
    Return a multiplicative modifier (>0) for ``action`` given ``personality``.

    Modifier = 1.0 + sum(trait_value * contribution_weight for each trait).
    Clamped to [0.1, 3.0] so it never makes an option impossible or infinite.

    Parameters
    ----------
    action:
        One of: eat, sleep, work, travel, socialize, idle.
        Unknown actions receive a neutral weight of 1.0.
    personality:
        Either a PersonalityProfile or a plain dict with the same keys.

    Returns
    -------
    float modifier
        Multiply an option's base score by this value.
    """
    contributions = _ACTION_WEIGHTS.get(action)
    if contributions is None:
        return 1.0

    # Normalise to dict
    if isinstance(personality, PersonalityProfile):
        traits = personality.to_dict()
    else:
        traits = personality

    modifier = 1.0
    for trait, weight in contributions:
        trait_value = traits.get(trait, 0.5)
        # Centre at 0.5 so a neutral personality contributes 0.
        modifier += (trait_value - 0.5) * weight * 2

    return max(0.1, min(3.0, modifier))


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def generate_personality(seed: int | None = None) -> PersonalityProfile:
    """
    Generate a plausible, correlated personality.

    Correlations:
      - High ambition tends to reduce sociability (r ≈ -0.4).
      - High creativity loosely correlates with risk_tolerance (r ≈ +0.3).
      - High aggression loosely correlates with low sociability (r ≈ -0.3).

    All values stay in [0.0, 1.0].
    """
    rng = random.Random(seed)

    # Draw base traits from Beta(2,2) — peaks at 0.5, rarely extreme.
    def beta22() -> float:
        return float(rng.betavariate(2, 2))

    ambition = beta22()
    risk_tolerance = beta22()
    creativity = beta22()

    # Correlated traits
    sociability_base = beta22()
    sociability = _clamp(sociability_base - 0.4 * (ambition - 0.5) - 0.3 * (creativity - 0.5))

    aggression_base = beta22()
    aggression = _clamp(aggression_base - 0.3 * (sociability - 0.5))

    # creativity nudges risk_tolerance up slightly
    risk_tolerance = _clamp(risk_tolerance + 0.3 * (creativity - 0.5))

    return PersonalityProfile(
        risk_tolerance=round(risk_tolerance, 3),
        sociability=round(sociability, 3),
        ambition=round(ambition, 3),
        creativity=round(creativity, 3),
        aggression=round(aggression, 3),
    )


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
