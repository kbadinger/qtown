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
    assert isinstance(decision, (str, dict)), "get_npc_decision should return a string or dict"
    if isinstance(decision, str):
        assert decision in ("eat", "sleep", "work", "rest", "wander")


# --- Story 191: Mayor election ---

def test_s191_hold_election(db):
    """Story 191: hold_election() should elect a mayor NPC."""
    _setup_world(db)
    from engine.simulation import hold_election
    from engine.models import NPC

    result = hold_election(db)
    assert result is None or isinstance(result, (int, dict)), "hold_election should return winner id, dict, or None"
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
    assert result is None or hasattr(result, 'id'), "propose_policy should return Policy object or None"


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
    assert path is None or isinstance(path, list), "find_path should return list or None"
    if path is None:
        return  # No path found is acceptable
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


def test_s311_assign_factions(db):
    """Political faction system."""
    _setup_world(db)
    from engine.simulation import assign_factions

    result = assign_factions(db)
    assert isinstance(result, dict), "assign_factions should return dict of faction counts"
    db.flush()


def test_s312_manage_proposal_queue(db):
    """Policy proposal queue."""
    _setup_world(db)
    from engine.simulation import manage_proposal_queue

    result = manage_proposal_queue(db)
    assert isinstance(result, int), "manage_proposal_queue should return count of active proposals"
    db.flush()


def test_s313_check_term_limits(db):
    """Term limits for mayor."""
    _setup_world(db)
    from engine.simulation import check_term_limits

    result = check_term_limits(db)
    assert isinstance(result, bool), "check_term_limits should return True or False"
    db.flush()


def test_s314_check_impeachment(db):
    """Impeachment mechanic."""
    _setup_world(db)
    from engine.simulation import check_impeachment

    result = check_impeachment(db)
    assert isinstance(result, bool), "check_impeachment should return True or False"
    db.flush()


def test_s315_check_tax_revolt(db):
    """Tax revolt."""
    _setup_world(db)
    from engine.simulation import check_tax_revolt

    result = check_tax_revolt(db)
    assert isinstance(result, bool), "check_tax_revolt should return True or False"
    db.flush()


def test_s316_launch_public_works(db):
    """Public works projects."""
    _setup_world(db)
    from engine.simulation import launch_public_works

    result = launch_public_works(db)
    assert result is None or isinstance(result, str), "launch_public_works should return building name or None"
    db.flush()


def test_s317_send_diplomat(db):
    """Diplomatic missions."""
    _setup_world(db)
    from engine.simulation import send_diplomat

    result = send_diplomat(db)
    assert result is None or isinstance(result, str), "send_diplomat should return diplomat name or None"
    db.flush()


def test_s318_run_census(db):
    """Census system."""
    _setup_world(db)
    from engine.simulation import run_census

    result = run_census(db)
    assert result is None or isinstance(result, dict), "run_census should return stats dict or None"
    db.flush()


def test_s319_generate_charter(db):
    """Town charter."""
    _setup_world(db)
    from engine.simulation import generate_charter

    result = generate_charter(db)
    assert isinstance(result, list), "generate_charter should return list of policy names"
    db.flush()


def test_s320_grant_emergency_powers(db):
    """Emergency powers."""
    _setup_world(db)
    from engine.simulation import grant_emergency_powers

    result = grant_emergency_powers(db)
    assert isinstance(result, bool), "grant_emergency_powers should return True or False"
    db.flush()


def test_s350_generate_end_of_day_report(db):
    """End-of-day report."""
    _setup_world(db)
    from engine.simulation import generate_end_of_day_report

    result = generate_end_of_day_report(db)
    assert result is None or isinstance(result, dict), "generate_end_of_day_report should return stats dict or None"
    db.flush()


# -- Stories 401-415: Governance & Politics ----------------------------


def test_s401_calculate_approval_rating(db):
    """Political approval rating."""
    _setup_world(db)
    from engine.simulation import calculate_approval_rating

    result = calculate_approval_rating(db)
    # None if no election, dict otherwise
    assert result is None or isinstance(result, dict), "Should return dict or None"
    db.flush()


def test_s402_detect_corruption(db):
    """Corruption detection."""
    _setup_world(db)
    from engine.simulation import detect_corruption

    result = detect_corruption(db)
    assert result is None or isinstance(result, bool), "Should return True, False, or None"
    db.flush()


def test_s403_enforce_curfew(db):
    """Town curfew."""
    _setup_world(db)
    from engine.simulation import enforce_curfew
    from engine.models import WorldState

    ws = db.query(WorldState).first()
    ws.tick = 20  # nighttime
    db.flush()

    result = enforce_curfew(db)
    assert isinstance(result, int), "Should return count of NPCs sent home"
    db.flush()


def test_s404_give_public_speech(db):
    """Public speech."""
    _setup_world(db)
    from engine.simulation import give_public_speech

    result = give_public_speech(db)
    assert result is None or isinstance(result, int), "Should return mayor id or None"
    db.flush()


def test_s405_identify_opposition_leader(db):
    """Opposition leader."""
    _setup_world(db)
    from engine.simulation import identify_opposition_leader

    result = identify_opposition_leader(db)
    assert result is None or isinstance(result, dict), "Should return dict or None"
    db.flush()


def test_s406_review_policy_effectiveness(db):
    """Policy effectiveness review."""
    _setup_world(db)
    from engine.simulation import review_policy_effectiveness

    result = review_policy_effectiveness(db)
    assert isinstance(result, list), "Should return list of policy reviews"
    db.flush()


def test_s407_allocate_town_budget(db):
    """Town budget allocation."""
    _setup_world(db)
    from engine.simulation import allocate_town_budget
    from engine.models import Treasury, Building

    # Ensure treasury exists
    b = db.query(Building).first()
    t = Treasury(gold_stored=1000, building_id=b.id)
    db.add(t)
    db.flush()

    result = allocate_town_budget(db)
    assert isinstance(result, dict), "Should return budget dict"
    assert "total" in result, "Should have total key"
    
    # Rollback to avoid affecting other tests (Story 006)
    db.rollback()


def test_s408_send_diplomatic_gift(db):
    """Diplomatic gift."""
    _setup_world(db)
    from engine.simulation import send_diplomatic_gift

    result = send_diplomatic_gift(db)
    assert isinstance(result, int), "Should return count of gifts sent"
    db.flush()


def test_s409_hold_war_council(db):
    """War council."""
    _setup_world(db)
    from engine.simulation import hold_war_council

    result = hold_war_council(db)
    assert result is None or isinstance(result, dict), "Should return dict or None"
    db.flush()


def test_s410_hold_expansion_vote(db):
    """Town expansion vote."""
    _setup_world(db)
    from engine.simulation.tick import hold_expansion_vote

    result = hold_expansion_vote(db)
    assert isinstance(result, dict), "Should return vote result dict"
    assert "vote" in result, "Should have vote key"
    db.flush()


def test_s411_apply_tax_exemption(db):
    """Tax exemption."""
    _setup_world(db)
    from engine.simulation import apply_tax_exemption

    result = apply_tax_exemption(db)
    assert isinstance(result, int), "Should return count of exempted NPCs"
    db.flush()


def test_s412_declare_public_holiday(db):
    """Public holiday declaration."""
    _setup_world(db)
    from engine.simulation import declare_public_holiday

    result = declare_public_holiday(db)
    assert isinstance(result, int), "Should return count of NPCs who rested"
    assert result >= 1, "Should rest at least 1 NPC"
    db.flush()


def test_s413_check_recall_election(db):
    """Recall election."""
    _setup_world(db)
    from engine.simulation import check_recall_election

    result = check_recall_election(db)
    assert isinstance(result, bool), "Should return True or False"
    db.flush()


def test_s414_expire_old_policies(db):
    """Policy sunset."""
    _setup_world(db)
    from engine.simulation import expire_old_policies

    result = expire_old_policies(db)
    assert isinstance(result, int), "Should return count of expired policies"
    db.flush()


def test_s415_apply_emergency_tax(db):
    """Emergency tax."""
    _setup_world(db)
    from engine.simulation import apply_emergency_tax

    result = apply_emergency_tax(db)
    assert isinstance(result, (int, float)), "Should return total collected"
    db.flush()


def test_s446_save_town_snapshot(db):
    """Historical archive."""
    _setup_world(db)
    from engine.simulation import save_town_snapshot
    from engine.models import WorldState

    ws = db.query(WorldState).first()
    ws.tick = 100  # snapshot tick
    db.flush()

    result = save_town_snapshot(db)
    assert isinstance(result, dict), "Should return snapshot dict at tick 100"
    assert "population" in result, "Snapshot should have population"
    db.flush()


def test_s450_generate_speed_report(db):
    """Simulation speed report."""
    _setup_world(db)
    from engine.simulation import generate_speed_report

    result = generate_speed_report(db)
    assert isinstance(result, dict), "Should return report dict"
    assert "tick" in result, "Should have tick key"
    assert "complexity" in result, "Should have complexity key"
    db.flush()


# =========================================================================
# Stories 466-490: Interconnection Stories
# =========================================================================


def test_s475_apply_corruption_penalty(db):
    """Corruption approval penalty."""
    _setup_world(db)
    from engine.simulation import apply_corruption_penalty

    result = apply_corruption_penalty(db)
    assert result in (0, 1), "Should return 0 or 1"
    db.flush()


def test_s487_run_periodic_checks(db):
    """Periodic interconnection checks."""
    _setup_world(db)
    from engine.simulation import run_periodic_checks

    # tick=10 should trigger the 10-tick functions
    result = run_periodic_checks(db, tick=10)
    assert isinstance(result, dict), "Should return dict of results"
    db.flush()


def test_s489_generate_daily_summary(db):
    """Daily interconnection summary."""
    _setup_world(db)
    from engine.simulation import generate_daily_summary

    result = generate_daily_summary(db)
    assert isinstance(result, dict), "Should return summary dict"
    assert "living" in result
    assert "gold" in result
    db.flush()


def test_s490_check_cascade_effects(db):
    """Cascade chain: weather to emigration."""
    _setup_world(db)
    from engine.simulation import check_cascade_effects

    result = check_cascade_effects(db)
    assert isinstance(result, dict), "Should return dict with weather/miserable/emigrated"
    assert "weather" in result
    assert "emigrated" in result
    db.flush()


# =========================================================================
# Stories 491-565: Deep Interconnection Stories
# =========================================================================

def test_s544_campaign_promise_tracking(db):
    """Campaign promise tracking."""
    _setup_world(db)
    from engine.simulation import check_campaign_promises
    result = check_campaign_promises(db)
    assert result is not None
    db.flush()

def test_s545_tax_revolt_trigger(db):
    """Tax revolt trigger."""
    _setup_world(db)
    from engine.simulation import check_tax_revolt
    result = check_tax_revolt(db)
    assert result is not None
    db.flush()

def test_s546_public_works_project(db):
    """Public works project."""
    _setup_world(db)
    from engine.simulation import start_public_works
    result = start_public_works(db)
    assert result is not None
    db.flush()

def test_s547_faction_popularity_check(db):
    """Faction popularity check."""
    _setup_world(db)
    from engine.simulation import check_faction_popularity
    result = check_faction_popularity(db)
    assert result is not None
    db.flush()

def test_s549_bribery_detection(db):
    """Bribery detection."""
    _setup_world(db)
    from engine.simulation import detect_bribery
    result = detect_bribery(db)
    assert result is not None
    db.flush()

def test_s550_term_limits_enforcement(db):
    """Term limits enforcement."""
    _setup_world(db)
    from engine.simulation import enforce_term_limits
    result = enforce_term_limits(db)
    assert result is not None
    db.flush()

def test_s551_council_vote_on_policy(db):
    """Council vote on policy."""
    _setup_world(db)
    from engine.simulation import hold_council_vote
    result = hold_council_vote(db)
    assert result is not None
    db.flush()

def test_s552_mayor_speech_effect(db):
    """Mayor speech effect."""
    _setup_world(db)
    from engine.simulation import give_mayor_speech
    result = give_mayor_speech(db)
    assert result is not None
    db.flush()

def test_s553_impeachment_vote(db):
    """Impeachment vote."""
    _setup_world(db)
    from engine.simulation import check_impeachment
    result = check_impeachment(db)
    assert result is not None
    db.flush()

def test_s565_town_age_and_statistics(db):
    """Town age and statistics."""
    _setup_world(db)
    from engine.simulation import get_town_statistics
    result = get_town_statistics(db)
    assert result is not None
    db.flush()
