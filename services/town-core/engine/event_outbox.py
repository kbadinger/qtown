"""Post-commit event outbox drain — grounding slice 2.

After each tick commits, publish that tick's *narrative* events to
`qtown.events.broadcast` so academy can embed them (→ grounded NPC dialogue that
references what actually happened). Runs on the MAIN event loop (where the
`AIOKafkaProducer` singleton lives), not inside the threaded tick body — so the
loop-bound producer is reused rather than re-created per event.

Design notes:
- **No central Event chokepoint.** Events are created at ~150 `db.add(Event(...))`
  sites, so we don't emit inline; we drain the tick's rows once, post-commit.
- **Best-effort.** A Kafka failure logs and stops this drain — it never touches
  the sim (the tick already committed).
- **Gated by `EVENTS_BROADCAST`** so unit tests / single-service runs are no-ops.
- **Filtered.** Report/summary/snapshot events dump large JSON blobs as their
  description (embedding noise); those, and any oversized description, are skipped
  — we broadcast the narrative events NPCs would actually talk about.
"""
from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from engine.kafka_producer import emit_event_broadcast
from engine.models import Event

logger = logging.getLogger("town-core.event_outbox")

# Event types whose descriptions are machine reports, not narrative — excluded.
_DENY_KEYWORDS = ("report", "summary", "snapshot", "news", "digest", "log")
# Reports dump the full events list into `description`; skip blob descriptions.
_MAX_DESCRIPTION = 400


def _enabled() -> bool:
    return os.environ.get("EVENTS_BROADCAST", "").lower() in ("1", "true", "yes")


def _should_broadcast(event_type: str | None, description: str | None) -> bool:
    et = (event_type or "").lower()
    if any(k in et for k in _DENY_KEYWORDS):
        return False
    if description and len(description) > _MAX_DESCRIPTION:
        return False
    return True


async def drain_events(db: Session, tick: int) -> int:
    """Publish this tick's narrative events to `qtown.events.broadcast`.

    Returns the number emitted (0 when disabled / nothing to send). No-op unless
    `EVENTS_BROADCAST` is set. Never raises — a broker outage just skips this tick.
    """
    if not _enabled():
        return 0

    events = db.query(Event).filter(Event.tick == tick).all()
    sent = 0
    for event in events:
        if not _should_broadcast(event.event_type, event.description):
            continue
        try:
            await emit_event_broadcast(
                tick=event.tick,
                event_type=event.event_type,
                description=event.description or "",
                npc_id=event.affected_npc_id,
                severity=event.severity or "info",
                event_id=event.id,
            )
            sent += 1
        except Exception as exc:  # broker down/slow — stop, retry next tick
            logger.warning("event broadcast failed (tick=%s id=%s): %s", tick, event.id, exc)
            break

    if sent:
        logger.info("broadcast %d/%d events for tick %d", sent, len(events), tick)
    return sent
