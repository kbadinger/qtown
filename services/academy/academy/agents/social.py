"""
NPC Social Dynamics — P5-007.

Gossip propagation, reputation tracking, and social relationship management.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from academy.agents.personality import PersonalityProfile

logger = logging.getLogger("academy.agents.social")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Reputation decay per 10 ticks (forgiveness factor)
REPUTATION_DECAY_PER_10_TICKS: float = 0.01

# Gossip credibility multiplier per propagation hop
GOSSIP_CREDIBILITY_DECAY: float = 0.7

# Minimum gossip credibility for an NPC to believe gossip
MIN_BELIEF_CREDIBILITY: float = 0.2

# Minimum sociability for an NPC to be willing to spread gossip
MIN_SPREAD_SOCIABILITY: float = 0.3

# How much gossip affects reputation: sentiment * credibility * this factor
GOSSIP_REPUTATION_FACTOR: float = 0.1

# Maximum spread count per NPC = sociability * SPREAD_COUNT_FACTOR
SPREAD_COUNT_FACTOR: float = 5.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Gossip:
    """A piece of information spreading through the social network."""

    source_id: str              # NPC who originated the gossip
    target_id: str              # NPC the gossip is about
    event_summary: str          # Description of the event
    sentiment: str              # "positive" | "negative" | "neutral"
    credibility: float          # 0–1, decays with each hop
    tick: int                   # Simulation tick when gossip was created
    hop_count: int = 0          # Number of propagation hops so far


@dataclass
class GossipSpread:
    """Record of gossip being passed from one NPC to another."""

    sender_id: str
    receiver_id: str
    gossip: Gossip
    believed: bool      # Whether the receiver believed it (credibility > MIN_BELIEF_CREDIBILITY)
    reputation_delta: float  # Change applied to target's reputation in receiver's view


@dataclass
class Relationship:
    """Bidirectional relationship between two NPCs."""

    npc_a: str
    npc_b: str
    affinity: float = 0.0        # −1 to 1: −1 = bitter rivals, 1 = close friends
    interaction_count: int = 0
    last_interaction_tick: int = 0


# ---------------------------------------------------------------------------
# ReputationSystem
# ---------------------------------------------------------------------------


class ReputationSystem:
    """
    Tracks what each NPC thinks of every other NPC.

    Reputation is a float in [−1.0, 1.0]:
      −1.0 = utterly despised
       0.0 = neutral
      +1.0 = universally admired

    Storage: ``_scores[observer_id][target_id] → float``
    """

    def __init__(self) -> None:
        # observer_id → {target_id → score}
        self._scores: dict[str, dict[str, float]] = {}
        # Track the tick of the last decay pass
        self._last_decay_tick: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_reputation(
        self,
        observer_id: str,
        target_id: str,
        event_type: str,
        magnitude: float,
    ) -> None:
        """
        Adjust the reputation of ``target_id`` in the eyes of ``observer_id``.

        ``magnitude`` is the signed change to apply (positive = better reputation,
        negative = worse).  The resulting score is clamped to [−1, 1].
        """
        if observer_id not in self._scores:
            self._scores[observer_id] = {}

        current = self._scores[observer_id].get(target_id, 0.0)
        updated = _clamp_rep(current + magnitude)
        self._scores[observer_id][target_id] = updated

        logger.debug(
            "Reputation: %s sees %s %+.3f → %.3f (event: %s)",
            observer_id, target_id, magnitude, updated, event_type,
        )

    def get_reputation(self, observer_id: str, target_id: str) -> float:
        """Return what ``observer_id`` thinks of ``target_id`` (range [−1, 1])."""
        return self._scores.get(observer_id, {}).get(target_id, 0.0)

    def get_community_reputation(self, target_id: str) -> float:
        """
        Return the average reputation of ``target_id`` across all observers
        who have an opinion.  Returns 0.0 if no opinions exist.
        """
        opinions: list[float] = []
        for observer_id, scores in self._scores.items():
            if observer_id == target_id:
                continue  # skip self-assessment
            if target_id in scores:
                opinions.append(scores[target_id])
        if not opinions:
            return 0.0
        return sum(opinions) / len(opinions)

    def decay_reputations(self, current_tick: int) -> None:
        """
        Apply forgiveness decay: all reputation scores move toward 0 by
        ``REPUTATION_DECAY_PER_10_TICKS`` for every 10 ticks elapsed since
        the last decay pass.

        Call this periodically (e.g., every town tick) to model gradual forgiveness.
        """
        ticks_elapsed = current_tick - self._last_decay_tick
        if ticks_elapsed < 10:
            return

        periods = ticks_elapsed // 10
        decay = REPUTATION_DECAY_PER_10_TICKS * periods

        for observer_id, scores in self._scores.items():
            for target_id in list(scores.keys()):
                score = scores[target_id]
                if score == 0.0:
                    continue
                # Move toward 0
                if score > 0:
                    scores[target_id] = max(0.0, score - decay)
                else:
                    scores[target_id] = min(0.0, score + decay)

        self._last_decay_tick = current_tick - (ticks_elapsed % 10)

    def all_opinions_about(self, target_id: str) -> dict[str, float]:
        """Return all observer scores for ``target_id``."""
        return {
            obs: scores[target_id]
            for obs, scores in self._scores.items()
            if target_id in scores and obs != target_id
        }


# ---------------------------------------------------------------------------
# GossipEngine
# ---------------------------------------------------------------------------


class GossipEngine:
    """
    Simulates rumour propagation through the NPC social network.

    Gossip credibility decays with each hop and only sociable NPCs spread it.
    """

    def __init__(self, reputation_system: ReputationSystem) -> None:
        self._rep = reputation_system

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def propagate(
        self,
        source_npc_id: str,
        source_personality: PersonalityProfile,
        gossip: Gossip,
        nearby_npcs: list[dict[str, Any]],
    ) -> list[GossipSpread]:
        """
        Spread ``gossip`` from ``source_npc`` to nearby NPCs.

        Parameters
        ----------
        source_npc_id:
            The NPC passing on the gossip (may not be the original source).
        source_personality:
            Personality of the spreading NPC (sociability determines spread count).
        gossip:
            The Gossip instance to propagate.
        nearby_npcs:
            List of dicts with at least: ``npc_id``, ``personality`` (PersonalityProfile).

        Returns
        -------
        List of GossipSpread records describing each propagation event.
        """
        spreads: list[GossipSpread] = []

        # Only spread if sociability is above threshold
        if source_personality.sociability < MIN_SPREAD_SOCIABILITY:
            logger.debug(
                "NPC %s too unsociable (%.2f) to spread gossip",
                source_npc_id, source_personality.sociability,
            )
            return spreads

        # Maximum number of NPCs this source can spread to
        max_spread = max(1, int(source_personality.sociability * SPREAD_COUNT_FACTOR))

        # Decay credibility for this hop
        next_credibility = gossip.credibility * GOSSIP_CREDIBILITY_DECAY
        propagated_gossip = Gossip(
            source_id=gossip.source_id,
            target_id=gossip.target_id,
            event_summary=gossip.event_summary,
            sentiment=gossip.sentiment,
            credibility=next_credibility,
            tick=gossip.tick,
            hop_count=gossip.hop_count + 1,
        )

        recipients = nearby_npcs[:max_spread]

        for npc in recipients:
            receiver_id = npc.get("npc_id", "")
            if not receiver_id or receiver_id == source_npc_id:
                continue

            believed = next_credibility > MIN_BELIEF_CREDIBILITY
            reputation_delta = 0.0

            if believed:
                sentiment_sign = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}.get(
                    gossip.sentiment, 0.0
                )
                reputation_delta = sentiment_sign * next_credibility * GOSSIP_REPUTATION_FACTOR
                self._rep.update_reputation(
                    observer_id=receiver_id,
                    target_id=gossip.target_id,
                    event_type=f"gossip_{gossip.sentiment}",
                    magnitude=reputation_delta,
                )

            spreads.append(
                GossipSpread(
                    sender_id=source_npc_id,
                    receiver_id=receiver_id,
                    gossip=propagated_gossip,
                    believed=believed,
                    reputation_delta=round(reputation_delta, 4),
                )
            )

        return spreads

    def generate_gossip(
        self,
        npc_id: str,
        personality: PersonalityProfile,
        recent_events: list[dict[str, Any]],
        tick: int,
    ) -> list[Gossip]:
        """
        Generate Gossip objects from events this NPC witnessed.

        Only events involving other NPCs produce gossip.  More sociable NPCs
        generate more gossip items; low-sociability NPCs generate none.
        """
        if personality.sociability < MIN_SPREAD_SOCIABILITY:
            return []

        gossip_items: list[Gossip] = []
        # How many gossip items this NPC can generate
        max_items = max(1, int(personality.sociability * 4))

        for event in recent_events[:max_items * 2]:
            target_id = event.get("target_npc_id", event.get("other_npc_id", ""))
            if not target_id or target_id == npc_id:
                continue

            description = event.get("description", event.get("event_type", "something happened"))
            sentiment = self._infer_sentiment(event)
            # Initial credibility starts high (first-hand observation)
            credibility = 0.9 if event.get("witnessed", True) else 0.6

            gossip_items.append(
                Gossip(
                    source_id=npc_id,
                    target_id=target_id,
                    event_summary=description[:200],
                    sentiment=sentiment,
                    credibility=credibility,
                    tick=tick,
                    hop_count=0,
                )
            )

            if len(gossip_items) >= max_items:
                break

        return gossip_items

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_sentiment(event: dict[str, Any]) -> str:
        """Infer gossip sentiment from event data."""
        event_type = event.get("event_type", "").lower()
        outcome = event.get("outcome", "").lower()

        positive_keywords = {"success", "win", "help", "gift", "heal", "celebrat", "save"}
        negative_keywords = {"fail", "steal", "attack", "insult", "betray", "murder", "crime", "cheat"}

        for kw in positive_keywords:
            if kw in event_type or kw in outcome:
                return "positive"
        for kw in negative_keywords:
            if kw in event_type or kw in outcome:
                return "negative"
        return "neutral"


# ---------------------------------------------------------------------------
# SocialNetwork
# ---------------------------------------------------------------------------


class SocialNetwork:
    """
    Tracks pairwise relationships between NPCs over time.

    Relationships accumulate through interactions and are used by the
    conversation and gossip systems.
    """

    def __init__(self) -> None:
        # Key: (sorted tuple of two npc_ids) → Relationship
        self._relationships: dict[tuple[str, str], Relationship] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_from_interaction(
        self,
        npc_a: str,
        npc_b: str,
        interaction_type: str,
        outcome: str,
        tick: int = 0,
    ) -> Relationship:
        """
        Update (or create) the relationship between two NPCs after an interaction.

        Parameters
        ----------
        npc_a, npc_b:
            The two NPC identifiers (order doesn't matter).
        interaction_type:
            Category of interaction (e.g. "trade", "conversation", "combat").
        outcome:
            Result of the interaction ("positive", "negative", "neutral").
        tick:
            Current simulation tick.

        Returns
        -------
        Updated Relationship.
        """
        key = _rel_key(npc_a, npc_b)
        if key not in self._relationships:
            self._relationships[key] = Relationship(npc_a=npc_a, npc_b=npc_b)

        rel = self._relationships[key]
        delta = _affinity_delta(interaction_type, outcome)
        rel.affinity = _clamp_rep(rel.affinity + delta)
        rel.interaction_count += 1
        rel.last_interaction_tick = tick

        return rel

    def get_relationship(self, npc_a: str, npc_b: str) -> Relationship | None:
        """Return the Relationship between two NPCs, or None if none exists."""
        return self._relationships.get(_rel_key(npc_a, npc_b))

    def get_friends(self, npc_id: str, min_affinity: float = 0.3) -> list[str]:
        """Return NPC IDs with affinity ≥ ``min_affinity``."""
        friends: list[str] = []
        for key, rel in self._relationships.items():
            if npc_id not in key:
                continue
            if rel.affinity >= min_affinity:
                other = key[0] if key[1] == npc_id else key[1]
                friends.append(other)
        return friends

    def get_rivals(self, npc_id: str, max_affinity: float = -0.3) -> list[str]:
        """Return NPC IDs with affinity ≤ ``max_affinity``."""
        rivals: list[str] = []
        for key, rel in self._relationships.items():
            if npc_id not in key:
                continue
            if rel.affinity <= max_affinity:
                other = key[0] if key[1] == npc_id else key[1]
                rivals.append(other)
        return rivals

    def get_all_relationships(self, npc_id: str) -> list[Relationship]:
        """Return all relationships involving ``npc_id``."""
        return [
            rel for key, rel in self._relationships.items() if npc_id in key
        ]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _clamp_rep(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _rel_key(npc_a: str, npc_b: str) -> tuple[str, str]:
    """Return a canonical (sorted) key for a pair of NPC IDs."""
    return (min(npc_a, npc_b), max(npc_a, npc_b))


def _affinity_delta(interaction_type: str, outcome: str) -> float:
    """Compute affinity change from an interaction type and outcome."""
    base: dict[str, float] = {
        "trade": 0.05,
        "conversation": 0.08,
        "combat": -0.20,
        "cooperation": 0.12,
        "gossip": 0.03,
        "gift": 0.15,
        "insult": -0.12,
    }
    modifier: dict[str, float] = {
        "positive": 1.0,
        "negative": -2.0,   # negative outcomes amplify the negative direction
        "neutral": 0.3,
    }
    b = base.get(interaction_type.lower(), 0.05)
    m = modifier.get(outcome.lower(), 0.3)
    return b * m
