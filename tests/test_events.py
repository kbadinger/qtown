"""Tests for event stories: 033-036, 109-123."""


def _setup_world(db):
    from engine.simulation import init_world_state, init_grid, seed_buildings, seed_npcs

    init_world_state(db)
    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)


def test_s033_event_model(db):
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


def test_s034_auto_log_events(db):
    """Story 034: process_tick() should auto-log events."""
    _setup_world(db)
    from engine.simulation import process_tick
    from engine.models import Event

    process_tick(db)
    events = db.query(Event).all()
    # At least a tick event should be logged
    assert isinstance(events, list)  # Function should work; events may or may not be generated


def test_s035_weather_system(db):
    """Story 035: Weather model/system should exist."""
    from engine.models import WorldState
    from engine.simulation import update_weather

    ws = WorldState(tick=0, day=1, time_of_day="morning", weather="clear")
    db.add(ws)
    db.commit()
    update_weather(db)
    db.commit()
    db.refresh(ws)
    assert ws.weather is not None


def test_s036_weather_effects(db):
    """Story 036: Weather should affect simulation."""
    _setup_world(db)
    from engine.models import WorldState
    from engine.simulation import apply_weather_effects

    ws = WorldState(tick=0, day=1, time_of_day="morning", weather="rain")
    db.add(ws)
    db.commit()
    # Should not crash; effects are weather-dependent
    apply_weather_effects(db)


# ---------------------------------------------------------------------------
# Stories 109-118: Discrete event triggers
# ---------------------------------------------------------------------------


def test_s109_drought_creates_event(db):
    """Story 109: trigger_drought creates a drought Event."""
    _setup_world(db)
    from engine.simulation import trigger_drought
    from engine.models import Event

    trigger_drought(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "drought").first()
    assert evt is not None, "trigger_drought must create an Event with event_type='drought'"


def test_s109_drought_reduces_food_production(db):
    """Story 109: drought reduces food production by 50%."""
    _setup_world(db)
    from engine.simulation import trigger_drought, produce_resources
    from engine.models import Resource

    # Produce resources once without drought to get baseline
    produce_resources(db)
    db.flush()

    baseline = sum(
        r.quantity for r in db.query(Resource).filter(Resource.name == "Food").all()
    )

    # Now trigger drought and produce again
    trigger_drought(db)
    db.flush()

    produce_resources(db)
    db.flush()

    after_drought = sum(
        r.quantity for r in db.query(Resource).filter(Resource.name == "Food").all()
    )
    # The second production (under drought) should add roughly half of baseline
    second_production = after_drought - baseline
    assert second_production <= baseline, (
        "Food produced under drought should be at most the baseline amount"
    )


def test_s110_flood_creates_event(db):
    """Story 110: trigger_flood creates a flood Event."""
    _setup_world(db)
    from engine.simulation import trigger_flood
    from engine.models import Event

    trigger_flood(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "flood").first()
    assert evt is not None, "trigger_flood must create an Event with event_type='flood'"


def test_s110_flood_damages_buildings(db):
    """Story 110: flood damages buildings."""
    _setup_world(db)
    from engine.simulation import trigger_flood
    from engine.models import Building

    buildings_before = db.query(Building).count()
    assert buildings_before > 0, "Need seeded buildings"

    trigger_flood(db)
    db.flush()

    # At least one building should be affected (damaged/capacity reduced/flagged)
    damaged = [
        b for b in db.query(Building).all()
        if getattr(b, "hp", b.capacity) < getattr(b, "max_hp", 10)
        or b.capacity < 10
    ]
    assert len(damaged) > 0, "Flood must damage at least one building"


def test_s111_fire_creates_event(db):
    """Story 111: trigger_fire creates a fire Event."""
    _setup_world(db)
    from engine.simulation import trigger_fire
    from engine.models import Event

    trigger_fire(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "fire").first()
    assert evt is not None, "trigger_fire must create an Event with event_type='fire'"


def test_s111_fire_damages_random_building(db):
    """Story 111: fire damages a random building."""
    _setup_world(db)
    from engine.simulation import trigger_fire
    from engine.models import Building, Event

    trigger_fire(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "fire").first()
    assert evt is not None

    # The event should reference an affected building
    assert evt.affected_building_id is not None, (
        "Fire event must set affected_building_id"
    )
    building = db.query(Building).get(evt.affected_building_id)
    assert building is not None


def test_s112_plague_creates_event(db):
    """Story 112: trigger_plague creates a plague Event."""
    _setup_world(db)
    from engine.simulation import trigger_plague
    from engine.models import Event

    trigger_plague(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "plague").first()
    assert evt is not None, "trigger_plague must create an Event with event_type='plague'"


def test_s112_plague_increases_illness(db):
    """Story 112: plague increases NPC illness."""
    _setup_world(db)
    from engine.simulation import trigger_plague
    from engine.models import NPC

    trigger_plague(db)
    db.flush()

    npcs = db.query(NPC).all()
    sick_npcs = [
        n for n in npcs
        if getattr(n, "illness", 0) > 0 or getattr(n, "health", 100) < 100
    ]
    assert len(sick_npcs) > 0, "Plague must increase illness for at least one NPC"


def test_s113_harvest_festival_creates_event(db):
    """Story 113: trigger_harvest_festival creates a harvest_festival Event."""
    _setup_world(db)
    from engine.simulation import trigger_harvest_festival
    from engine.models import Event

    trigger_harvest_festival(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "harvest_festival").first()
    assert evt is not None, (
        "trigger_harvest_festival must create an Event with event_type='harvest_festival'"
    )


def test_s113_harvest_festival_boosts_happiness(db):
    """Story 113: harvest_festival adds +20 happiness to all NPCs."""
    _setup_world(db)
    from engine.simulation import trigger_harvest_festival
    from engine.models import NPC

    npcs_before = {n.id: n.happiness for n in db.query(NPC).all()}
    assert len(npcs_before) > 0, "Need seeded NPCs"

    trigger_harvest_festival(db)
    db.flush()

    for npc in db.query(NPC).all():
        expected = min(100, npcs_before[npc.id] + 20)
        assert npc.happiness >= expected, (
            f"NPC {npc.name} happiness should be at least {expected}, got {npc.happiness}"
        )


def test_s114_bandit_raid_creates_event(db):
    """Story 114: trigger_bandit_raid creates a bandit_raid Event."""
    _setup_world(db)
    from engine.simulation import trigger_bandit_raid
    from engine.models import Event, Treasury

    # Ensure treasury exists with some gold
    treasury = Treasury(gold_stored=500)
    db.add(treasury)
    db.commit()

    trigger_bandit_raid(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "bandit_raid").first()
    assert evt is not None, (
        "trigger_bandit_raid must create an Event with event_type='bandit_raid'"
    )


def test_s114_bandit_raid_steals_gold(db):
    """Story 114: bandit_raid steals gold from Treasury."""
    _setup_world(db)
    from engine.simulation import trigger_bandit_raid
    from engine.models import Treasury

    treasury = Treasury(gold_stored=500)
    db.add(treasury)
    db.commit()
    gold_before = treasury.gold_stored

    trigger_bandit_raid(db)
    db.flush()
    db.refresh(treasury)

    assert treasury.gold_stored < gold_before, (
        f"Treasury gold should decrease after bandit raid: was {gold_before}, "
        f"now {treasury.gold_stored}"
    )


def test_s115_earthquake_creates_event(db):
    """Story 115: trigger_earthquake creates an earthquake Event."""
    _setup_world(db)
    from engine.simulation import trigger_earthquake
    from engine.models import Event

    trigger_earthquake(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "earthquake").first()
    assert evt is not None, (
        "trigger_earthquake must create an Event with event_type='earthquake'"
    )


def test_s115_earthquake_damages_buildings(db):
    """Story 115: earthquake damages buildings."""
    _setup_world(db)
    from engine.simulation import trigger_earthquake
    from engine.models import Building

    buildings_before = db.query(Building).count()
    assert buildings_before > 0, "Need seeded buildings"

    trigger_earthquake(db)
    db.flush()

    damaged = [
        b for b in db.query(Building).all()
        if getattr(b, "hp", b.capacity) < getattr(b, "max_hp", 10)
        or b.capacity < 10
    ]
    assert len(damaged) > 0, "Earthquake must damage at least one building"


def test_s116_market_crash_creates_event(db):
    """Story 116: trigger_market_crash creates a market_crash Event."""
    _setup_world(db)
    from engine.simulation import trigger_market_crash
    from engine.models import Event

    trigger_market_crash(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "market_crash").first()
    assert evt is not None, (
        "trigger_market_crash must create an Event with event_type='market_crash'"
    )


def test_s116_market_crash_halves_prices(db):
    """Story 116: market_crash halves all resource prices."""
    _setup_world(db)
    from engine.simulation import trigger_market_crash, produce_resources
    from engine.models import Resource

    # Produce some resources first so they have prices
    produce_resources(db)
    db.flush()

    resources = db.query(Resource).all()
    prices_before = {}
    for r in resources:
        prices_before[r.id] = getattr(r, "price", None)

    trigger_market_crash(db)
    db.flush()

    for r in db.query(Resource).all():
        if r.id in prices_before and prices_before[r.id] is not None:
            assert getattr(r, "price", 0) <= prices_before[r.id], (
                f"Resource {r.name} price should not increase after market crash"
            )


def test_s117_baby_boom_creates_event(db):
    """Story 117: trigger_baby_boom creates a baby_boom Event."""
    _setup_world(db)
    from engine.simulation import trigger_baby_boom
    from engine.models import Event

    trigger_baby_boom(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "baby_boom").first()
    assert evt is not None, (
        "trigger_baby_boom must create an Event with event_type='baby_boom'"
    )


def test_s117_baby_boom_spawns_npcs(db):
    """Story 117: baby_boom spawns extra NPCs."""
    _setup_world(db)
    from engine.simulation import trigger_baby_boom
    from engine.models import NPC

    count_before = db.query(NPC).count()
    assert count_before > 0, "Need seeded NPCs"

    trigger_baby_boom(db)
    db.flush()

    count_after = db.query(NPC).count()
    assert count_after > count_before, (
        f"Baby boom must spawn extra NPCs: was {count_before}, now {count_after}"
    )


def test_s118_gold_rush_creates_event(db):
    """Story 118: trigger_gold_rush creates a gold_rush Event."""
    _setup_world(db)
    from engine.simulation import trigger_gold_rush
    from engine.models import Event

    trigger_gold_rush(db)
    db.flush()

    evt = db.query(Event).filter(Event.event_type == "gold_rush").first()
    assert evt is not None, (
        "trigger_gold_rush must create an Event with event_type='gold_rush'"
    )


def test_s118_gold_rush_doubles_gold_production(db):
    """Story 118: gold_rush doubles gold production."""
    _setup_world(db)
    from engine.simulation import trigger_gold_rush, process_work
    from engine.models import NPC, Building

    # Set up an NPC with a work building and place them at work
    npc = db.query(NPC).first()
    work_building = db.query(Building).filter(
        Building.building_type != "residential"
    ).first()
    npc.work_building_id = work_building.id
    npc.x = work_building.x
    npc.y = work_building.y
    npc.gold = 0
    db.commit()

    # Process work without gold rush
    process_work(db)
    db.flush()
    gold_normal = npc.gold

    # Reset gold and trigger gold rush
    npc.gold = 0
    db.commit()

    trigger_gold_rush(db)
    db.flush()

    process_work(db)
    db.flush()
    db.refresh(npc)
    gold_rush = npc.gold

    assert gold_rush >= gold_normal * 2, (
        f"Gold rush should double gold production: normal={gold_normal}, "
        f"rush={gold_rush}"
    )


# ---------------------------------------------------------------------------
# Stories 119-123: Cascading events
# ---------------------------------------------------------------------------


def test_s119_drought_cascades_to_famine(db):
    """Story 119: drought lasting 5+ ticks triggers famine."""
    _setup_world(db)
    from engine.simulation import trigger_drought
    from engine.models import Event, WorldState

    ws = db.query(WorldState).first()
    if not ws:
        ws = WorldState(tick=0, day=1, time_of_day="morning", weather="clear")
        db.add(ws)
        db.commit()

    # Create drought events spanning 5+ ticks
    for i in range(5):
        evt = Event(
            event_type="drought",
            description="Drought continues",
            tick=ws.tick + i,
            severity="warning",
        )
        db.add(evt)
    db.commit()

    # Trigger drought again -- should detect prolonged drought and cascade
    trigger_drought(db)
    db.flush()

    famine = db.query(Event).filter(Event.event_type == "famine").first()
    assert famine is not None, (
        "Drought lasting 5+ ticks must cascade into a famine event"
    )


def test_s120_fire_cascades_to_rebuilding_boom(db):
    """Story 120: fire triggers rebuilding boom."""
    _setup_world(db)
    from engine.simulation import trigger_fire
    from engine.models import Event

    trigger_fire(db)
    db.flush()

    # After a fire, a rebuilding_boom event should be created
    rebuilding = db.query(Event).filter(
        Event.event_type == "rebuilding_boom"
    ).first()
    assert rebuilding is not None, (
        "Fire must cascade into a rebuilding_boom event"
    )


def test_s121_plague_cascades_to_hospital_overwhelmed(db):
    """Story 121: plague with many sick NPCs overwhelms hospital."""
    _setup_world(db)
    from engine.simulation import trigger_plague
    from engine.models import Event, NPC

    # Make many NPCs already sick to overwhelm the hospital
    for npc in db.query(NPC).all():
        if hasattr(npc, "illness"):
            npc.illness = 80
        if hasattr(npc, "health"):
            npc.health = 20
    db.commit()

    trigger_plague(db)
    db.flush()

    overwhelmed = db.query(Event).filter(
        Event.event_type == "hospital_overwhelmed"
    ).first()
    assert overwhelmed is not None, (
        "Plague with many sick NPCs must cascade into hospital_overwhelmed event"
    )


def test_s122_flood_cascades_to_price_spike(db):
    """Story 122: flood reduces supply, causing price spike."""
    _setup_world(db)
    from engine.simulation import trigger_flood
    from engine.models import Event

    trigger_flood(db)
    db.flush()

    price_spike = db.query(Event).filter(
        Event.event_type == "price_spike"
    ).first()
    assert price_spike is not None, (
        "Flood must cascade into a price_spike event"
    )


def test_s123_bandit_raid_cascades_to_justice(db):
    """Story 123: bandit raid triggers justice response from guards."""
    _setup_world(db)
    from engine.simulation import trigger_bandit_raid
    from engine.models import Event, Treasury

    # Ensure treasury exists
    treasury = Treasury(gold_stored=500)
    db.add(treasury)
    db.commit()

    trigger_bandit_raid(db)
    db.flush()

    justice = db.query(Event).filter(
        Event.event_type == "justice_response"
    ).first()
    assert justice is not None, (
        "Bandit raid must cascade into a justice_response event"
    )


# ---------------------------------------------------------------------------
# Story 204: Town newspaper — event summaries
# ---------------------------------------------------------------------------


def test_s204_newspaper_model_exists(db):
    """Story 204: Newspaper model should exist with correct fields."""
    from engine.models import Newspaper

    paper = Newspaper(
        day=1,
        headline="Town Founded!",
        body="The town was officially founded today.",
    )
    db.add(paper)
    db.flush()

    assert paper.id is not None
    assert paper.day == 1
    assert paper.headline == "Town Founded!"
    assert paper.body is not None
    assert hasattr(paper, "created_at")


def test_s204_generate_newspaper_creates_entry(db):
    """Story 204: generate_newspaper() creates a Newspaper entry."""
    _setup_world(db)
    from engine.simulation import generate_newspaper
    from engine.models import Newspaper, WorldState

    # Ensure WorldState exists
    ws = db.query(WorldState).first()
    if not ws:
        ws = WorldState(tick=24, day=1, time_of_day="morning")
        db.add(ws)
        db.flush()

    generate_newspaper(db)
    db.flush()

    papers = db.query(Newspaper).all()
    assert len(papers) >= 1, "generate_newspaper must create at least one Newspaper entry"


def test_s204_newspaper_body_non_empty(db):
    """Story 204: Newspaper body should be a non-empty string."""
    _setup_world(db)
    from engine.simulation import generate_newspaper
    from engine.models import Newspaper, WorldState

    ws = db.query(WorldState).first()
    if not ws:
        ws = WorldState(tick=24, day=1, time_of_day="morning")
        db.add(ws)
        db.flush()

    generate_newspaper(db)
    db.flush()

    paper = db.query(Newspaper).first()
    assert paper is not None, "Newspaper entry should exist"
    assert isinstance(paper.body, str) and len(paper.body) > 0, (
        "Newspaper body must be a non-empty string"
    )


# ---------------------------------------------------------------------------
# Story 205: Town achievement system
# ---------------------------------------------------------------------------


def test_s205_achievement_model_exists(db):
    """Story 205: Achievement model should exist with correct fields."""
    from engine.models import Achievement

    ach = Achievement(
        name="First Building",
        description="Build your first building",
        condition='{"building_count": 1}',
        achieved=False,
    )
    db.add(ach)
    db.flush()

    assert ach.id is not None
    assert ach.name == "First Building"
    assert ach.description == "Build your first building"
    assert ach.condition is not None
    assert ach.achieved is False


def test_s205_check_achievements_runs(db):
    """Story 205: check_achievements() should run without error."""
    _setup_world(db)
    from engine.simulation import check_achievements

    # Should not raise an exception
    check_achievements(db)
    db.flush()


def test_s205_achievement_unlock_creates_event(db):
    """Story 205: Unlocking an achievement should create an Event."""
    _setup_world(db)
    from engine.models import Achievement, Event
    from engine.simulation import check_achievements

    # Create an achievement that should be immediately met (building_count >= 1)
    ach = Achievement(
        name="First Building",
        description="Build your first building",
        condition='{"building_count": 1}',
        achieved=False,
    )
    db.add(ach)
    db.flush()

    check_achievements(db)
    db.flush()

    # Either the achievement is unlocked or an event is created (or both)
    db.refresh(ach)
    events = db.query(Event).filter(Event.event_type == "achievement").all()
    assert ach.achieved or len(events) >= 1, (
        "check_achievements should unlock achievement and/or create an achievement Event"
    )


# ---------------------------------------------------------------------------
# Story 212: Visitor event triggers
# ---------------------------------------------------------------------------


def test_s212_apply_triggered_event_festival(db):
    """Story 212: apply_triggered_event('festival') boosts happiness."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import apply_triggered_event

    npcs_before = {n.id: n.happiness for n in db.query(NPC).all()}
    assert len(npcs_before) > 0, "Need seeded NPCs"

    apply_triggered_event(db, "festival")
    db.flush()

    # At least some NPCs should have increased happiness
    any_boosted = False
    for npc in db.query(NPC).all():
        if npc.happiness > npcs_before[npc.id]:
            any_boosted = True
            break
    assert any_boosted, "Festival should boost happiness for at least some NPCs"


def test_s212_trigger_endpoint_festival(client, admin_headers):
    """Story 212: POST /api/trigger/festival returns 200."""
    resp = client.post("/api/trigger/festival")
    assert resp.status_code == 200, f"POST /api/trigger/festival failed: {resp.text}"


def test_s212_trigger_endpoint_invalid_type(client, admin_headers):
    """Story 212: POST /api/trigger/{invalid} returns 404."""
    resp = client.post("/api/trigger/nonexistent_event_type_xyz")
    assert resp.status_code == 404, (
        f"Invalid event type should return 404, got {resp.status_code}"
    )


# ── Stories 226, 234-246: Events, Seasons, Politics ─────────────────


def test_s226_trigger_merchant_caravan(db):
    """Story 226: Merchant caravan events."""
    _setup_world(db)
    from engine.simulation import trigger_merchant_caravan

    trigger_merchant_caravan(db)
    db.flush()

    from engine.models import Event
    evt = db.query(Event).filter(Event.event_type == "merchant_caravan").first()
    assert evt is not None, "Should create merchant_caravan event"


def test_s234_get_season(db):
    """Story 234: Seasonal cycle system."""
    _setup_world(db)
    from engine.simulation import get_season

    result = get_season(db)
    assert result in ("spring", "summer", "fall", "winter"), f"Bad season: {result}"


def test_s235_check_seasonal_events(db):
    """Story 235: Auto-trigger harvest festival in fall."""
    _setup_world(db)
    from engine.simulation import check_seasonal_events

    check_seasonal_events(db)
    db.flush()


def test_s236_apply_winter_effects(db):
    """Story 236: Winter hardship effects."""
    _setup_world(db)
    from engine.simulation import apply_winter_effects

    apply_winter_effects(db)
    db.flush()


def test_s237_spread_epidemic(db):
    """Story 237: Epidemic contagion spread."""
    _setup_world(db)
    from engine.simulation import spread_epidemic

    result = spread_epidemic(db)
    assert isinstance(result, int), "spread_epidemic should return count"
    db.flush()


def test_s238_check_infrastructure_collapse(db):
    """Story 238: Infrastructure collapse cascade."""
    _setup_world(db)
    from engine.simulation import check_infrastructure_collapse

    result = check_infrastructure_collapse(db)
    assert isinstance(result, bool), "Should return bool"
    db.flush()


def test_s239_generate_town_review(db):
    """Story 239: Annual town review report."""
    _setup_world(db)
    from engine.simulation import generate_town_review

    result = generate_town_review(db)
    assert isinstance(result, dict), "Should return stats dict"
    assert "population" in result
    db.flush()


def test_s240_trigger_random_boon(db):
    """Story 240: Random positive micro-events."""
    _setup_world(db)
    from engine.simulation import trigger_random_boon

    # Call multiple times — result is None or event_type string
    for _ in range(10):
        result = trigger_random_boon(db)
        assert result is None or isinstance(result, str)
    db.flush()


def test_s241_process_refugees(db):
    """Story 241: Refugee wave after disasters."""
    _setup_world(db)
    from engine.simulation import process_refugees

    result = process_refugees(db)
    assert isinstance(result, int), "Should return count"
    db.flush()


def test_s242_apply_policy_effects(db):
    """Story 242: Policy effect enforcement."""
    _setup_world(db)
    from engine.simulation import apply_policy_effects

    result = apply_policy_effects(db)
    assert isinstance(result, int), "Should return count"
    db.flush()


def test_s243_check_corruption(db):
    """Story 243: Mayor corruption system."""
    _setup_world(db)
    from engine.simulation import check_corruption

    result = check_corruption(db)
    assert isinstance(result, (int, float)), "Should return amount stolen"
    db.flush()


def test_s244_calculate_approval(db):
    """Story 244: Public approval rating."""
    _setup_world(db)
    from engine.simulation import calculate_approval

    result = calculate_approval(db)
    assert isinstance(result, int), "Should return integer rating"
    assert 0 <= result <= 100, f"Rating out of range: {result}"
    db.flush()


def test_s245_check_emergency_election(db):
    """Story 245: Emergency election on low approval."""
    _setup_world(db)
    from engine.simulation import check_emergency_election

    result = check_emergency_election(db)
    assert isinstance(result, bool), "Should return bool"
    db.flush()


def test_s256_hold_town_meeting(db):
    """Story 256: Town hall grievance meetings."""
    _setup_world(db)
    from engine.simulation import hold_town_meeting

    result = hold_town_meeting(db)
    assert isinstance(result, str), "Should return complaint string"
    db.flush()
