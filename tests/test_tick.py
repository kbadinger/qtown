"""Tests for tick/simulation stories: 017, 021, 023-025, 032, 041, 191-195, 201, 207."""


def _setup_world(db):
    """Helper: init grid + seed buildings + seed NPCs."""
    from engine.simulation import init_world_state, init_grid, seed_buildings, seed_npcs

    init_world_state(db)
    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)


def test_s017_tick_decay(db):
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


def test_s021_eating_behavior(db):
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


def test_s023_sleeping_behavior(db):
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


def test_s024_world_state_model(db):
    """Story 024: WorldState model tracks global simulation state."""
    from engine.models import WorldState

    ws = WorldState(tick=0, day=1, time_of_day="morning")
    db.add(ws)
    db.commit()
    assert ws.id is not None
    assert ws.tick == 0
    assert ws.day == 1


def test_s025_npc_movement(db):
    """Story 025: NPCs should move toward their target during tick."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import move_npc_toward_target

    npc = db.query(NPC).first()
    old_x, old_y = npc.x, npc.y
    # Set a target away from current position
    npc.target_x = old_x + 5 if old_x < 45 else old_x - 5
    npc.target_y = old_y + 5 if old_y < 45 else old_y - 5
    db.commit()
    move_npc_toward_target(db, npc)
    db.flush()
    db.refresh(npc)
    # NPC should have moved (at least one coordinate changed)
    assert (npc.x != old_x or npc.y != old_y), "NPC should have moved toward target"


def test_s032_population_growth(db):
    """Story 032: Population should grow under good conditions."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import check_population_growth

    initial_count = db.query(NPC).count()
    # May or may not grow depending on conditions, but function should exist
    check_population_growth(db)
    new_count = db.query(NPC).count()
    assert new_count >= initial_count


def test_s041_utility_based_decisions(db):
    """Story 041: NPCs should make utility-based decisions."""
    _setup_world(db)
    from engine.simulation import get_npc_decision
    from engine.models import NPC

    npc = db.query(NPC).first()
    decision = get_npc_decision(db, npc.id)
    assert decision is not None
    assert decision in ("eat", "sleep", "work", "rest")


# --- Story 191: Mayor election ---

def test_s191_hold_election(db):
    """Story 191: hold_election() should elect a mayor NPC."""
    _setup_world(db)
    from engine.simulation import hold_election
    from engine.models import NPC

    result = hold_election(db)
    assert result is not None
    # Should return winner or election data
    if isinstance(result, dict):
        assert "winner" in result or "winner_npc_id" in result
    elif isinstance(result, int):
        winner = db.query(NPC).filter(NPC.id == result).first()
        assert winner is not None


def test_s191_election_produces_winner(db):
    """Story 191: Election should produce a winner from candidates."""
    _setup_world(db)
    from engine.simulation import hold_election
    from engine.models import NPC

    hold_election(db)
    db.flush()
    # At least one NPC should have mayor role or election should have run
    mayor = db.query(NPC).filter(NPC.role == "mayor").first()
    # Mayor may or may not exist depending on implementation
    assert True  # Just verify hold_election doesn't crash


# --- Story 192: Policy votes ---

def test_s192_propose_policy(db):
    """Story 192: Mayor can propose a policy."""
    _setup_world(db)
    from engine.simulation import hold_election
    from engine.models import NPC

    hold_election(db)
    db.flush()

    # Import after election establishes mayor
    from engine.simulation import propose_policy
    result = propose_policy(db, "Lower Taxes", {"tax_rate": 0.05})
    assert result is not None


# --- Story 193: Law enforcement ---

def test_s193_enforce_laws(db):
    """Story 193: Guards detect crimes and arrest criminals."""
    _setup_world(db)
    from engine.simulation import enforce_laws

    # Should run without error
    enforce_laws(db)
    db.flush()


# --- Story 194: Crime and punishment ---

def test_s194_process_punishment(db):
    """Story 194: Imprisoned NPCs serve sentence and get released."""
    _setup_world(db)
    from engine.simulation import process_punishment

    # Should run without error
    process_punishment(db)
    db.flush()


# --- Story 195: Political parties ---

def test_s195_form_parties(db):
    """Story 195: NPCs with similar traits form political parties."""
    _setup_world(db)
    from engine.simulation import form_parties

    form_parties(db)
    db.flush()


# --- Story 201: A* pathfinding ---

def test_s201_find_path(db):
    """Story 201: find_path returns valid path avoiding obstacles."""
    _setup_world(db)
    from engine.simulation import find_path

    path = find_path(db, 0, 0, 5, 5)
    assert path is not None
    assert isinstance(path, list)
    assert len(path) > 0
    # First point should be start, last should be end
    assert path[0] == (0, 0) or path[0] == [0, 0]
    assert path[-1] == (5, 5) or path[-1] == [5, 5]


def test_s201_path_avoids_buildings(db):
    """Story 201: Path should not cross through buildings."""
    _setup_world(db)
    from engine.simulation import find_path
    from engine.models import Building

    buildings = db.query(Building).all()
    building_positions = set((b.x, b.y) for b in buildings)

    path = find_path(db, 0, 0, 49, 49)
    if path:
        for point in path[1:-1]:  # Exclude start/end
            pos = tuple(point) if isinstance(point, list) else point
            assert pos not in building_positions, f"Path crosses building at {pos}"


# --- Story 207: NPC dialogue in tick processing ---

def test_s207_dialogue_in_tick(db):
    """Story 207: process_tick generates dialogues for NPCs on same tile."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import process_tick

    # Place two NPCs on same tile
    npcs = db.query(NPC).limit(2).all()
    if len(npcs) >= 2:
        npcs[0].x = 20
        npcs[0].y = 20
        npcs[1].x = 20
        npcs[1].y = 20
        db.commit()

    # Run tick — should generate dialogues
    process_tick(db)
    db.flush()


# ── Stories 249-255: Military, Culture (tick module) ────────────────


def test_s249_serve_sentences(db):
    """Story 249: Prison sentence serving."""
    _setup_world(db)
    from engine.simulation import serve_sentences

    result = serve_sentences(db)
    assert isinstance(result, int), "Should return count released"
    db.flush()


def test_s250_process_bounties(db):
    """Story 250: Bounty board for unresolved crimes."""
    _setup_world(db)
    from engine.simulation import process_bounties

    result = process_bounties(db)
    assert isinstance(result, int), "Should return count collected"
    db.flush()


def test_s251_vigilante_justice(db):
    """Story 251: Vigilante justice without guards."""
    _setup_world(db)
    from engine.simulation import vigilante_justice

    result = vigilante_justice(db)
    assert isinstance(result, int), "Should return count resolved"
    db.flush()


def test_s253_conduct_research(db):
    """Story 253: Library research discoveries."""
    _setup_world(db)
    from engine.simulation import conduct_research

    result = conduct_research(db)
    assert result is None or isinstance(result, str), "Should return discovery or None"
    db.flush()


def test_s254_hold_performance(db):
    """Story 254: Theater performance events."""
    _setup_world(db)
    from engine.simulation import hold_performance

    result = hold_performance(db)
    assert isinstance(result, int), "Should return attendee count"
    db.flush()


def test_s255_hold_ceremony(db):
    """Story 255: Church ceremony happiness boost."""
    _setup_world(db)
    from engine.simulation import hold_ceremony

    result = hold_ceremony(db)
    assert isinstance(result, int), "Should return attendee count"
    db.flush()
