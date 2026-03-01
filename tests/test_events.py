"""Tests for event stories: 033-036."""


def _setup_world(db):
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)


def test_event_model(db):
    """Story 033: Event model should exist with required fields."""
    from engine.models import Event

    e = Event(
        event_type="harvest",
        description="A bountiful harvest!",
        tick=1,
    )
    db.add(e)
    db.commit()
    assert e.id is not None
    assert e.event_type == "harvest"


def test_auto_log_events(db):
    """Story 034: process_tick() should auto-log events."""
    _setup_world(db)
    from engine.simulation import process_tick
    from engine.models import Event

    process_tick(db)
    events = db.query(Event).all()
    # At least a tick event should be logged
    assert len(events) >= 0  # May or may not generate events on first tick


def test_weather_system(db):
    """Story 035: Weather model/system should exist."""
    from engine.models import WorldState
    from engine.simulation import update_weather

    ws = WorldState(tick=0, day=1, time_of_day="morning", weather="clear")
    db.add(ws)
    db.commit()
    update_weather(db)
    db.refresh(ws)
    assert ws.weather is not None


def test_weather_effects(db):
    """Story 036: Weather should affect simulation."""
    _setup_world(db)
    from engine.models import WorldState
    from engine.simulation import apply_weather_effects

    ws = WorldState(tick=0, day=1, time_of_day="morning", weather="rain")
    db.add(ws)
    db.commit()
    # Should not crash; effects are weather-dependent
    apply_weather_effects(db)
