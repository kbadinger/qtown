"""
Multi-NPC Conversation Engine — P5-008.

Generates turn-by-turn group dialogues between NPCs, where speech style and
topics are modulated by personality, inter-NPC reputation, and recent memories.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from academy.agents.personality import PersonalityProfile

logger = logging.getLogger("academy.agents.conversation")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum turns if caller provides no limit
DEFAULT_MAX_TURNS: int = 6

# Dialogue task type — routed to qwen3.5:35b-a3b by ModelRouter
DIALOGUE_TASK_TYPE: str = "dialogue"

# Fallback task type if 'dialogue' is not in the route table
FALLBACK_TASK_TYPE: str = "narration"

# Mood vocabulary for the arc
MOOD_VOCAB: tuple[str, ...] = (
    "friendly",
    "tense",
    "neutral",
    "curious",
    "angry",
    "joyful",
    "sad",
    "suspicious",
    "conspiratorial",
    "resolute",
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class NPCProfile:
    """Profile of an NPC participating in a conversation."""

    npc_id: str
    name: str
    role: str                               # e.g. "blacksmith", "merchant", "guard"
    personality: PersonalityProfile
    reputation_toward: dict[str, float]     # npc_id → reputation score (−1 to 1)
    recent_memories: list[str]              # brief text snippets of recent memories


@dataclass
class ConversationTurn:
    """A single NPC's utterance within a conversation."""

    speaker_id: str
    speaker_name: str
    text: str
    emotion: str                        # e.g. "curious", "angry", "cheerful"
    targets: list[str]                  # npc_ids being addressed (empty = all)


@dataclass
class Conversation:
    """A complete multi-NPC conversation."""

    participants: list[str]             # npc_ids
    turns: list[ConversationTurn]
    topic: str
    mood_arc: list[str]                 # mood at each turn
    duration_ticks: int                 # how many sim-ticks the conversation lasted


# ---------------------------------------------------------------------------
# ConversationEngine
# ---------------------------------------------------------------------------


class ConversationEngine:
    """
    Generates turn-by-turn group dialogues using ModelRouter.

    Usage::

        engine = ConversationEngine()
        conv = await engine.generate_conversation(
            participants=[profile_a, profile_b, profile_c],
            topic="the wheat shortage",
            context="Market district, noon",
        )
    """

    def __init__(self) -> None:
        from academy.models.router import ModelRouter, ROUTE_TABLE

        self._router = ModelRouter()
        # Use 'dialogue' if present (routes to qwen3.5:35b-a3b), else 'narration'
        self._task_type = DIALOGUE_TASK_TYPE if DIALOGUE_TASK_TYPE in ROUTE_TABLE else FALLBACK_TASK_TYPE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_conversation(
        self,
        participants: list[NPCProfile],
        topic: str,
        context: str,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> Conversation:
        """
        Generate a conversation between all participants about ``topic``.

        Each NPC speaks based on their personality and relationships.  The
        engine generates all turns in a single LLM call and parses the
        structured response.

        Parameters
        ----------
        participants:
            List of NPCProfile objects (2–6 NPCs supported well).
        topic:
            The subject of conversation.
        context:
            Environmental / narrative context string.
        max_turns:
            Maximum number of total turns.  Actual turns ≤ max_turns.

        Returns
        -------
        Conversation dataclass.
        """
        if not participants:
            return Conversation(
                participants=[],
                turns=[],
                topic=topic,
                mood_arc=[],
                duration_ticks=0,
            )

        system_prompt = self._build_system_prompt(participants, topic, context, max_turns)
        user_prompt = (
            f"Generate exactly {max_turns} conversation turns about '{topic}'. "
            "Reply ONLY with a valid JSON object — no markdown, no explanation."
        )

        try:
            raw = await self._router.route(self._task_type, user_prompt, system=system_prompt)
            turns, mood_arc = self._parse_turns(raw, participants, max_turns)
        except Exception as exc:
            logger.warning("Conversation generation failed: %s — using fallback", exc)
            turns, mood_arc = self._fallback_turns(participants, topic, max_turns)

        # Ensure every participant has spoken at least once
        turns = self._ensure_all_speak(turns, participants, topic, max_turns)

        # Cap at max_turns
        turns = turns[:max_turns]
        mood_arc = mood_arc[:max_turns]

        # Pad mood arc to match turn count
        while len(mood_arc) < len(turns):
            mood_arc.append(mood_arc[-1] if mood_arc else "neutral")

        return Conversation(
            participants=[p.npc_id for p in participants],
            turns=turns,
            topic=topic,
            mood_arc=mood_arc,
            duration_ticks=len(turns),
        )

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        participants: list[NPCProfile],
        topic: str,
        context: str,
        max_turns: int,
    ) -> str:
        """Build the LLM system prompt describing all participants."""
        npc_descriptions: list[str] = []
        for p in participants:
            style = self._personality_to_style(p.personality)
            rep_lines = "; ".join(
                f"thinks {nid} is {'a friend' if score > 0.3 else 'a rival' if score < -0.3 else 'neutral'}"
                for nid, score in p.reputation_toward.items()
            )
            memory_hint = ". ".join(p.recent_memories[:2]) if p.recent_memories else "Nothing notable recently."
            npc_descriptions.append(
                f"- {p.name} (id={p.npc_id}, role={p.role}): "
                f"Speech style: {style}. "
                f"Relationships: {rep_lines or 'none known'}. "
                f"Recent memories: {memory_hint}"
            )

        npc_block = "\n".join(npc_descriptions)
        participant_ids = [p.npc_id for p in participants]
        participant_names = [p.name for p in participants]

        return (
            "You are a narrative director for a medieval town simulation.\n"
            f"Context: {context}\n"
            f"Topic: {topic}\n\n"
            "Participants:\n"
            f"{npc_block}\n\n"
            f"Generate exactly {max_turns} conversation turns as a JSON object with this structure:\n"
            '{"turns": [{"speaker_id": "...", "speaker_name": "...", "text": "...", '
            '"emotion": "...", "targets": ["..."]}], '
            '"mood_arc": ["mood_at_turn_1", "mood_at_turn_2", ...]}\n\n'
            f"Valid speaker_ids: {participant_ids}\n"
            f"Valid speaker_names: {participant_names}\n"
            f"Each NPC must speak at least once.\n"
            "Personality styles:\n"
            "  - high aggression → confrontational, blunt, challenging\n"
            "  - high sociability → warm, inclusive, asks questions\n"
            "  - high creativity → metaphorical, inventive language\n"
            "  - high ambition → goal-oriented, competitive\n"
            "  - low risk_tolerance → cautious, hedging language\n"
            "Mood arc tracks overall conversation mood; pick from: "
            f"{', '.join(MOOD_VOCAB)}\n"
            "Reply ONLY with the JSON object, no markdown fences."
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_turns(
        self,
        raw: str,
        participants: list[NPCProfile],
        max_turns: int,
    ) -> tuple[list[ConversationTurn], list[str]]:
        """Parse LLM JSON output into ConversationTurn objects and a mood arc."""
        text = raw.strip()
        # Strip markdown fences
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        # Try to find JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        data = json.loads(text)

        raw_turns = data.get("turns", [])
        mood_arc: list[str] = data.get("mood_arc", [])

        # Build a quick lookup for participant name resolution
        id_to_name = {p.npc_id: p.name for p in participants}
        name_to_id = {p.name: p.npc_id for p in participants}
        valid_ids = set(id_to_name.keys())

        turns: list[ConversationTurn] = []
        for item in raw_turns[:max_turns]:
            if not isinstance(item, dict):
                continue
            speaker_id = str(item.get("speaker_id", ""))
            speaker_name = str(item.get("speaker_name", ""))

            # Resolve mismatches between id and name
            if speaker_id not in valid_ids and speaker_name in name_to_id:
                speaker_id = name_to_id[speaker_name]
            if speaker_id in valid_ids and not speaker_name:
                speaker_name = id_to_name[speaker_id]
            if speaker_id not in valid_ids:
                # Fallback: pick first participant
                speaker_id = participants[0].npc_id
                speaker_name = participants[0].name

            turns.append(
                ConversationTurn(
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    text=str(item.get("text", ""))[:500],
                    emotion=str(item.get("emotion", "neutral")),
                    targets=list(item.get("targets", [])),
                )
            )

        # Validate mood_arc entries
        valid_moods = set(MOOD_VOCAB)
        mood_arc = [m if m in valid_moods else "neutral" for m in mood_arc]

        return turns, mood_arc

    def _fallback_turns(
        self,
        participants: list[NPCProfile],
        topic: str,
        max_turns: int,
    ) -> tuple[list[ConversationTurn], list[str]]:
        """Generate simple deterministic turns when the LLM fails."""
        turns: list[ConversationTurn] = []
        mood_arc: list[str] = []

        openers: dict[str, list[str]] = {
            "high_aggression": [
                "What's your problem with {topic}?",
                "I don't like where this is heading.",
                "Someone has to say it — {topic} is a mess.",
            ],
            "high_sociability": [
                "Has everyone heard about {topic}?",
                "What does everyone think?",
                "We should work this out together.",
            ],
            "default": [
                "About {topic} — I have thoughts.",
                "This concerns all of us.",
                "Let me be clear on where I stand.",
            ],
        }

        for i in range(min(max_turns, len(participants) * 2)):
            p = participants[i % len(participants)]
            style_key = (
                "high_aggression" if p.personality.aggression > 0.7
                else "high_sociability" if p.personality.sociability > 0.7
                else "default"
            )
            templates = openers[style_key]
            text = templates[i % len(templates)].format(topic=topic)

            emotion = self._default_emotion(p.personality)
            mood_arc.append(emotion)

            turns.append(
                ConversationTurn(
                    speaker_id=p.npc_id,
                    speaker_name=p.name,
                    text=text,
                    emotion=emotion,
                    targets=[],
                )
            )

        return turns, mood_arc

    def _ensure_all_speak(
        self,
        turns: list[ConversationTurn],
        participants: list[NPCProfile],
        topic: str,
        max_turns: int,
    ) -> list[ConversationTurn]:
        """Add a turn for any participant who hasn't spoken, if room remains."""
        speakers = {t.speaker_id for t in turns}
        for p in participants:
            if p.npc_id in speakers:
                continue
            if len(turns) >= max_turns:
                break  # can't exceed max_turns
            emotion = self._default_emotion(p.personality)
            turns.append(
                ConversationTurn(
                    speaker_id=p.npc_id,
                    speaker_name=p.name,
                    text=f"{p.name} nods thoughtfully about {topic}.",
                    emotion=emotion,
                    targets=[],
                )
            )
        return turns

    # ------------------------------------------------------------------
    # Personality helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _personality_to_style(personality: PersonalityProfile) -> str:
        """Describe an NPC's speech style based on their dominant traits."""
        traits = personality.to_dict()
        dominant = max(traits.items(), key=lambda kv: kv[1])
        trait_name, value = dominant

        styles: dict[str, str] = {
            "aggression": "confrontational and blunt" if value > 0.6 else "direct",
            "sociability": "warm and inclusive" if value > 0.6 else "conversational",
            "ambition": "goal-oriented and competitive" if value > 0.6 else "focused",
            "creativity": "metaphorical and inventive" if value > 0.6 else "thoughtful",
            "risk_tolerance": "bold and decisive" if value > 0.6 else "cautious and hedging",
        }
        return styles.get(trait_name, "measured")

    @staticmethod
    def _default_emotion(personality: PersonalityProfile) -> str:
        """Map dominant personality trait to a default emotion."""
        traits = personality.to_dict()
        dominant_trait = max(traits, key=lambda t: traits[t])
        mapping: dict[str, str] = {
            "aggression": "tense",
            "sociability": "friendly",
            "ambition": "resolute",
            "creativity": "curious",
            "risk_tolerance": "neutral",
        }
        return mapping.get(dominant_trait, "neutral")
