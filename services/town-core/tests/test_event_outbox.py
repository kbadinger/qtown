"""Unit tests for the post-commit event outbox drain (grounding slice 2)."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from engine.event_outbox import drain_events
from engine.models import Base, Event


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_drain_is_noop_when_disabled(db, monkeypatch):
    monkeypatch.delenv("EVENTS_BROADCAST", raising=False)
    db.add(Event(event_type="fire", description="A fire broke out", tick=5))
    db.commit()

    with patch("engine.event_outbox.emit_event_broadcast", new=AsyncMock()) as emit:
        n = await drain_events(db, 5)

    assert n == 0
    emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_drain_emits_only_this_tick_narrative_events(db, monkeypatch):
    monkeypatch.setenv("EVENTS_BROADCAST", "1")
    db.add(Event(event_type="festival_start", description="Harvest festival begins", tick=10, affected_npc_id=3))
    db.add(Event(event_type="crime", description="A theft occurred", tick=10))
    db.add(Event(event_type="daily_report", description="x" * 600, tick=10))  # denied: report + blob
    db.add(Event(event_type="fire", description="A fire", tick=9))  # wrong tick
    db.commit()

    with patch("engine.event_outbox.emit_event_broadcast", new=AsyncMock()) as emit:
        n = await drain_events(db, 10)

    assert n == 2
    kinds = {c.kwargs["event_type"] for c in emit.await_args_list}
    assert kinds == {"festival_start", "crime"}
    # The row PK must ride along (else the embedder drops it).
    assert all(c.kwargs["event_id"] is not None for c in emit.await_args_list)


@pytest.mark.asyncio
async def test_drain_stops_on_broker_failure(db, monkeypatch):
    monkeypatch.setenv("EVENTS_BROADCAST", "1")
    db.add(Event(event_type="crime", description="theft", tick=1))
    db.add(Event(event_type="fire", description="blaze", tick=1))
    db.commit()

    failing = AsyncMock(side_effect=RuntimeError("kafka down"))
    with patch("engine.event_outbox.emit_event_broadcast", new=failing):
        n = await drain_events(db, 1)  # must not raise

    assert n == 0
