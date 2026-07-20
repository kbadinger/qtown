"""AI-dialogue trigger — Flow 2 (W1-A7).

When two NPCs share a tile, town-core asks Academy to write their conversation
over gRPC. Academy generates it (model-routed), embeds it, and emits
``qtown.ai.content.generated`` for Tavern to broadcast to the dashboard. town-core
also persists the lines to the ``dialogues`` table for its own history/UI.

The context we send is built entirely from town-core's own DB (the pair's
name/role/personality/mood + the weather + a few recent events) — no cross-service
retrieval, so there's nothing to back-fill. Whole thing is a no-op unless
``ACADEMY_GRPC_ADDR`` is configured, so unit tests and single-service runs are
unaffected.
"""
from __future__ import annotations

import json
import logging
import random

from sqlalchemy.orm import Session

from engine.clients.academy_client import get_academy_client
from engine.models import NPC, Dialogue, Event, Relationship, WorldState

logger = logging.getLogger("town-core.dialogue")

RECENT_EVENT_TICKS = 12
MAX_CONTEXT_EVENTS = 3


def _pick_pair(db: Session) -> tuple[NPC, NPC] | None:
    """Pick two living NPCs that share a tile (same pattern as attempt_persuasion)."""
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    tiles: dict[tuple[int, int], list[NPC]] = {}
    for npc in npcs:
        tiles.setdefault((npc.x, npc.y), []).append(npc)
    groups = [g for g in tiles.values() if len(g) >= 2]
    if not groups:
        return None
    group = random.choice(groups)
    a, b = random.sample(group, 2)
    return a, b


def _tone_for(db: Session, a: NPC, b: NPC) -> str:
    """Colour the conversation by the pair's relationship, if any."""
    rel = (
        db.query(Relationship)
        .filter(Relationship.npc_id == a.id, Relationship.target_npc_id == b.id)
        .first()
    )
    if rel is not None:
        rtype = (rel.relationship_type or "").lower()
        if rtype in ("rival", "enemy"):
            return "hostile"
        if rtype in ("business", "trade"):
            return "negotiation"
    return "friendly"


def _traits(personality: str | None) -> str:
    """Turn the NPC's JSON personality flags into a short descriptor."""
    if not personality:
        return ""
    try:
        flags = json.loads(personality)
    except (ValueError, TypeError):
        return ""
    on = [k for k, v in flags.items() if v] if isinstance(flags, dict) else []
    return ", ".join(on[:3])


def _mood(npc: NPC) -> str:
    if npc.hunger is not None and npc.hunger > 80:
        return "hungry"
    if npc.energy is not None and npc.energy < 20:
        return "tired"
    if npc.happiness is not None and npc.happiness < 30:
        return "unhappy"
    if npc.happiness is not None and npc.happiness > 75:
        return "cheerful"
    return "content"


def _describe(npc: NPC) -> str:
    traits = _traits(npc.personality)
    trait_str = f", {traits}" if traits else ""
    return f"{npc.name} (a {_mood(npc)} {npc.role}{trait_str})"


def _build_context(db: Session, a: NPC, b: NPC, world_state: WorldState | None) -> str:
    weather = (world_state.weather if world_state else None) or "clear"
    tod = (world_state.time_of_day if world_state else None) or "day"
    current_tick = world_state.tick if world_state else 0

    parts = [
        f"{_describe(a)} and {_describe(b)} meet in the town ({weather} weather, {tod})."
    ]
    recent = (
        db.query(Event)
        .filter(Event.tick > current_tick - RECENT_EVENT_TICKS)
        .order_by(Event.tick.desc())
        .limit(MAX_CONTEXT_EVENTS)
        .all()
    )
    blurbs = [e.description for e in recent if e.description]
    if blurbs:
        parts.append("Recently around town: " + "; ".join(blurbs) + ".")
    return " ".join(parts)


def trigger_ai_dialogue(db: Session) -> int:
    """Ask Academy to write a conversation between a co-located NPC pair.

    Returns the number of lines generated (0 if Academy isn't configured, no pair
    is co-located, or the call fails). Best-effort: never raises — the tick must
    continue even if Academy is down.
    """
    client = get_academy_client()
    if client is None:  # ACADEMY_GRPC_ADDR unset → fast no-op
        return 0

    pair = _pick_pair(db)
    if pair is None:
        return 0
    a, b = pair

    world_state = db.query(WorldState).first()
    tone = _tone_for(db, a, b)
    context = _build_context(db, a, b, world_state)

    lines = client.generate_dialogue(
        npc_id_a=a.id, npc_id_b=b.id, context=context, tone=tone
    )
    if not lines:
        return 0

    current_tick = world_state.tick if world_state else 0
    # Persist each line. Speaker/listener are derived from the PAIR (alternating),
    # NOT the LLM-returned npc_id — that comes from lenient free-form parsing on
    # the Academy side and can't be trusted for a foreign key.
    persisted = 0
    for i, line in enumerate(lines):
        text = (line.text or "").strip()
        if not text:
            continue
        speaker, listener = (a, b) if i % 2 == 0 else (b, a)
        db.add(
            Dialogue(
                speaker_npc_id=speaker.id,
                listener_npc_id=listener.id,
                message=text,
                tick=current_tick,
            )
        )
        persisted += 1
    db.commit()
    logger.info(
        "AI dialogue: %s <-> %s (%d lines, %s)", a.name, b.name, persisted, tone
    )
    return persisted
