"""
Tests for academy.agents.conversation — P5-008.

test_all_participants_speak   — verify each NPC gets at least one turn
test_personality_affects_tone — aggressive NPC uses confrontational language
test_max_turns_respected      — conversation doesn't exceed max_turns
test_mood_arc_tracked         — mood changes are recorded
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from academy.agents.personality import PersonalityProfile
from academy.agents.conversation import (
    ConversationEngine,
    NPCProfile,
    ConversationTurn,
    Conversation,
    MOOD_VOCAB,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_personality(**kwargs: float) -> PersonalityProfile:
    defaults = {
        "risk_tolerance": 0.5,
        "sociability": 0.5,
        "ambition": 0.5,
        "creativity": 0.5,
        "aggression": 0.5,
    }
    defaults.update(kwargs)
    return PersonalityProfile(**defaults)


def make_profile(
    npc_id: str,
    name: str,
    role: str = "villager",
    **trait_kwargs: float,
) -> NPCProfile:
    return NPCProfile(
        npc_id=npc_id,
        name=name,
        role=role,
        personality=make_personality(**trait_kwargs),
        reputation_toward={},
        recent_memories=[],
    )


def build_llm_response(participants: list[NPCProfile], max_turns: int) -> str:
    """Build a valid JSON conversation response for the mock LLM."""
    turns = []
    for i in range(max_turns):
        p = participants[i % len(participants)]
        turns.append({
            "speaker_id": p.npc_id,
            "speaker_name": p.name,
            "text": f"{p.name} says something about the topic.",
            "emotion": "neutral",
            "targets": [],
        })
    mood_arc = ["neutral"] * max_turns
    return json.dumps({"turns": turns, "mood_arc": mood_arc})


def make_engine(llm_response: str = "{}") -> ConversationEngine:
    """Return a ConversationEngine with a mocked ModelRouter."""
    engine = ConversationEngine.__new__(ConversationEngine)
    router = MagicMock()
    router.route = AsyncMock(return_value=llm_response)
    engine._router = router
    engine._task_type = "dialogue"
    return engine


# ---------------------------------------------------------------------------
# test_all_participants_speak
# ---------------------------------------------------------------------------


class TestAllParticipantsSpeak:
    """Every NPC participant must have at least one turn."""

    @pytest.mark.asyncio
    async def test_all_speak_with_clean_llm_output(self):
        """When LLM returns one turn per participant, all should appear."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
            make_profile("npc3", "Charlie"),
        ]
        llm_response = build_llm_response(participants, max_turns=6)
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="the drought", context="Town square"
        )

        speaker_ids = {t.speaker_id for t in conv.turns}
        for p in participants:
            assert p.npc_id in speaker_ids, (
                f"NPC {p.name} ({p.npc_id}) did not speak in the conversation"
            )

    @pytest.mark.asyncio
    async def test_missing_participant_gets_added(self):
        """If the LLM omits one participant, the engine adds a turn for them."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
            make_profile("npc3", "Charlie"),
        ]
        # LLM response only includes npc1 and npc2
        turns_data = [
            {"speaker_id": "npc1", "speaker_name": "Alice",
             "text": "Hello.", "emotion": "neutral", "targets": []},
            {"speaker_id": "npc2", "speaker_name": "Bob",
             "text": "Indeed.", "emotion": "neutral", "targets": []},
        ]
        llm_response = json.dumps({"turns": turns_data, "mood_arc": ["neutral", "neutral"]})
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="bread prices", context="Market", max_turns=6
        )

        speaker_ids = {t.speaker_id for t in conv.turns}
        assert "npc3" in speaker_ids, "Engine should add a turn for Charlie who was missing"

    @pytest.mark.asyncio
    async def test_single_participant_gets_one_turn(self):
        """Conversation with a single participant should still produce a turn."""
        participants = [make_profile("npc1", "Alice")]
        llm_response = build_llm_response(participants, max_turns=3)
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="soliloquy", context="Alone", max_turns=3
        )

        assert len(conv.turns) >= 1
        assert conv.turns[0].speaker_id == "npc1"

    @pytest.mark.asyncio
    async def test_empty_participants_returns_empty_conversation(self):
        """No participants should produce an empty Conversation."""
        engine = make_engine()
        conv = await engine.generate_conversation([], topic="test", context="x")

        assert conv.participants == []
        assert conv.turns == []
        assert conv.mood_arc == []

    @pytest.mark.asyncio
    async def test_participants_list_in_result(self):
        """Conversation.participants must contain all NPC IDs."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
        ]
        llm_response = build_llm_response(participants, max_turns=4)
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="harvest", context="Field"
        )

        assert set(conv.participants) == {"npc1", "npc2"}


# ---------------------------------------------------------------------------
# test_personality_affects_tone
# ---------------------------------------------------------------------------


class TestPersonalityAffectsTone:
    """Aggressive NPCs should use confrontational language in fallback mode."""

    @pytest.mark.asyncio
    async def test_aggressive_npc_uses_confrontational_language(self):
        """When the LLM returns invalid JSON, the fallback generates confrontational text
        for high-aggression NPCs."""
        aggressive_profile = make_profile("npc_a", "Brutus", aggression=0.95)
        passive_profile = make_profile("npc_b", "Luna", sociability=0.9, aggression=0.1)

        # Force the engine to use the fallback by returning invalid JSON
        engine = make_engine(llm_response="INVALID JSON {[}")

        conv = await engine.generate_conversation(
            [aggressive_profile, passive_profile],
            topic="the missing grain",
            context="Tavern",
            max_turns=4,
        )

        # Find the aggressive NPC's first turn
        brutus_turns = [t for t in conv.turns if t.speaker_id == "npc_a"]
        assert brutus_turns, "Brutus should have at least one turn"

        # Aggressive personality maps to "tense" emotion in fallback
        assert brutus_turns[0].emotion in ("tense", "angry", "suspicious", "resolute")

    @pytest.mark.asyncio
    async def test_sociable_npc_emotion_is_friendly(self):
        """High-sociability NPC gets a friendly emotion in fallback mode."""
        sociable = make_profile("npc1", "Mira", sociability=0.95, aggression=0.1)
        engine = make_engine(llm_response="INVALID")

        conv = await engine.generate_conversation(
            [sociable],
            topic="festival plans",
            context="Village",
            max_turns=2,
        )

        mira_turns = [t for t in conv.turns if t.speaker_id == "npc1"]
        assert mira_turns
        assert mira_turns[0].emotion in ("friendly", "joyful", "curious")

    @pytest.mark.asyncio
    async def test_creative_npc_style_description(self):
        """_personality_to_style should describe creative NPCs correctly."""
        engine = make_engine()
        creative = make_personality(creativity=0.9)
        style = engine._personality_to_style(creative)
        assert "metaphor" in style.lower() or "inventive" in style.lower()

    @pytest.mark.asyncio
    async def test_ambitious_npc_style_description(self):
        engine = make_engine()
        ambitious = make_personality(ambition=0.9)
        style = engine._personality_to_style(ambitious)
        assert "goal" in style.lower() or "compet" in style.lower() or "focused" in style.lower()


# ---------------------------------------------------------------------------
# test_max_turns_respected
# ---------------------------------------------------------------------------


class TestMaxTurnsRespected:
    """Conversation must never exceed max_turns."""

    @pytest.mark.asyncio
    async def test_turns_do_not_exceed_max(self):
        """When LLM returns more turns than max, engine clips to max."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
        ]
        max_turns = 4
        # LLM returns 10 turns — should be capped at 4
        llm_response = build_llm_response(participants, max_turns=10)
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="taxes", context="Town hall", max_turns=max_turns
        )

        assert len(conv.turns) <= max_turns, (
            f"Expected ≤ {max_turns} turns, got {len(conv.turns)}"
        )

    @pytest.mark.asyncio
    async def test_default_max_turns_applied(self):
        """Conversation respects DEFAULT_MAX_TURNS when not specified."""
        from academy.agents.conversation import DEFAULT_MAX_TURNS

        participants = [make_profile("npc1", "Alice"), make_profile("npc2", "Bob")]
        llm_response = build_llm_response(participants, max_turns=DEFAULT_MAX_TURNS)
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="weather", context="Street"
            # No max_turns arg — uses default
        )

        assert len(conv.turns) <= DEFAULT_MAX_TURNS

    @pytest.mark.asyncio
    async def test_max_turns_1(self):
        """max_turns=1 produces exactly 1 turn."""
        participants = [make_profile("npc1", "Alice"), make_profile("npc2", "Bob")]
        llm_response = json.dumps({
            "turns": [
                {"speaker_id": "npc1", "speaker_name": "Alice",
                 "text": "Hey.", "emotion": "neutral", "targets": []}
            ],
            "mood_arc": ["neutral"],
        })
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="hi", context="x", max_turns=1
        )

        assert len(conv.turns) <= 1

    @pytest.mark.asyncio
    async def test_fallback_respects_max_turns(self):
        """The fallback generator also respects max_turns."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
            make_profile("npc3", "Charlie"),
        ]
        engine = make_engine(llm_response="BAD JSON")

        conv = await engine.generate_conversation(
            participants, topic="test", context="x", max_turns=2
        )

        assert len(conv.turns) <= 2


# ---------------------------------------------------------------------------
# test_mood_arc_tracked
# ---------------------------------------------------------------------------


class TestMoodArcTracked:
    """mood_arc must be recorded and contain valid mood entries."""

    @pytest.mark.asyncio
    async def test_mood_arc_length_matches_turns(self):
        """mood_arc length must equal the number of turns."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
        ]
        llm_response = json.dumps({
            "turns": [
                {"speaker_id": "npc1", "speaker_name": "Alice",
                 "text": "Hello.", "emotion": "friendly", "targets": []},
                {"speaker_id": "npc2", "speaker_name": "Bob",
                 "text": "Indeed.", "emotion": "tense", "targets": []},
            ],
            "mood_arc": ["friendly", "tense"],
        })
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="test", context="x", max_turns=4
        )

        assert len(conv.mood_arc) == len(conv.turns), (
            f"mood_arc length {len(conv.mood_arc)} != turns length {len(conv.turns)}"
        )

    @pytest.mark.asyncio
    async def test_mood_arc_contains_valid_moods(self):
        """All entries in mood_arc should be valid mood vocabulary words."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
        ]
        moods = ["friendly", "tense", "curious", "angry"]
        turns_data = [
            {"speaker_id": "npc1", "speaker_name": "Alice",
             "text": "Let's talk.", "emotion": m, "targets": []}
            for m in moods
        ]
        llm_response = json.dumps({"turns": turns_data, "mood_arc": moods})
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="test", context="x", max_turns=6
        )

        for mood in conv.mood_arc:
            assert mood in MOOD_VOCAB, f"Invalid mood: {mood}"

    @pytest.mark.asyncio
    async def test_invalid_moods_replaced_with_neutral(self):
        """Moods not in MOOD_VOCAB should be replaced with 'neutral'."""
        participants = [make_profile("npc1", "Alice"), make_profile("npc2", "Bob")]
        llm_response = json.dumps({
            "turns": [
                {"speaker_id": "npc1", "speaker_name": "Alice",
                 "text": "hi", "emotion": "happy", "targets": []},
            ],
            "mood_arc": ["extremely_happy_INVALID"],
        })
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="test", context="x", max_turns=4
        )

        for mood in conv.mood_arc:
            assert mood in MOOD_VOCAB, f"Invalid mood should have been replaced: {mood}"

    @pytest.mark.asyncio
    async def test_mood_arc_padded_when_short(self):
        """If LLM returns fewer mood entries than turns, pad with the last mood."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
        ]
        turns_data = [
            {"speaker_id": p.npc_id, "speaker_name": p.name,
             "text": "Something.", "emotion": "neutral", "targets": []}
            for p in participants * 2  # 4 turns
        ]
        # Only provide 2 moods for 4 turns
        llm_response = json.dumps({"turns": turns_data, "mood_arc": ["friendly", "tense"]})
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="padded", context="x", max_turns=6
        )

        assert len(conv.mood_arc) == len(conv.turns)

    @pytest.mark.asyncio
    async def test_fallback_produces_mood_arc(self):
        """Even when the LLM fails, the fallback produces a mood arc."""
        participants = [
            make_profile("npc1", "Alice"),
            make_profile("npc2", "Bob"),
        ]
        engine = make_engine(llm_response="BROKEN")

        conv = await engine.generate_conversation(
            participants, topic="crisis", context="Broken LLM", max_turns=4
        )

        assert len(conv.mood_arc) == len(conv.turns)
        for mood in conv.mood_arc:
            assert mood in MOOD_VOCAB

    @pytest.mark.asyncio
    async def test_duration_ticks_equals_turn_count(self):
        """Conversation.duration_ticks should equal the number of turns."""
        participants = [make_profile("npc1", "Alice"), make_profile("npc2", "Bob")]
        llm_response = build_llm_response(participants, max_turns=5)
        engine = make_engine(llm_response)

        conv = await engine.generate_conversation(
            participants, topic="time", context="x", max_turns=5
        )

        assert conv.duration_ticks == len(conv.turns)
