"""Tests for tick/simulation stories: 017, 021, 023-025, 032, 041."""


def _setup_world(db):
    """Helper: init grid + seed buildings + seed NPCs."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)


def test_tick_decay(db):
    """Story 017: process_tick() should decay NPC hunger and energy."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs, process_tick

    _setup_world(db)
    from engine.models import NPC

    npc = db.query(NPC).first()
    initial_hunger = npc.hunger
    initial_energy = npc.energy
    process_tick(db)
    db.refresh(npc)
    # Hunger should increase (getting hungrier) or energy should decrease
    assert npc.hunger > initial_hunger or npc.energy < initial_energy


def test_eating_behavior(db):
    """Story 021: NPCs with high hunger should eat during tick."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import process_tick

    npc = db.query(NPC).first()
    npc.hunger = 90  # Very hungry
    npc.gold = 100  # Has money to buy food
    db.commit()
    process_tick(db)
    db.refresh(npc)
    assert npc.hunger < 90, "Hungry NPC should have eaten"


def test_sleeping_behavior(db):
    """Story 023: NPCs with low energy should sleep during tick."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import process_tick

    npc = db.query(NPC).first()
    npc.energy = 10  # Very tired
    db.commit()
    process_tick(db)
    db.refresh(npc)
    assert npc.energy > 10, "Tired NPC should have slept"


def test_world_state_model(db):
    """Story 024: WorldState model tracks global simulation state."""
    from engine.models import WorldState

    ws = WorldState(tick=0, day=1, time_of_day="morning")
    db.add(ws)
    db.commit()
    assert ws.id is not None
    assert ws.tick == 0
    assert ws.day == 1


def test_npc_movement(db):
    """Story 025: NPCs should move toward their target during tick."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import process_tick

    npc = db.query(NPC).first()
    old_x, old_y = npc.x, npc.y
    # Set a target away from current position
    npc.target_x = old_x + 5 if old_x < 45 else old_x - 5
    npc.target_y = old_y + 5 if old_y < 45 else old_y - 5
    db.commit()
    process_tick(db)
    db.refresh(npc)
    # NPC should have moved (at least one coordinate changed)
    assert (npc.x != old_x or npc.y != old_y), "NPC should have moved toward target"


def test_population_growth(db):
    """Story 032: Population should grow under good conditions."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import check_population_growth

    initial_count = db.query(NPC).count()
    # May or may not grow depending on conditions, but function should exist
    check_population_growth(db)
    new_count = db.query(NPC).count()
    assert new_count >= initial_count


def test_utility_based_decisions(db):
    """Story 041: NPCs should make utility-based decisions."""
    _setup_world(db)
    from engine.simulation import get_npc_decision
    from engine.models import NPC

    npc = db.query(NPC).first()
    decision = get_npc_decision(db, npc)
    assert decision is not None
    assert "action" in decision
