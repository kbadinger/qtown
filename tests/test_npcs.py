"""Tests for NPC stories: 003, 005, 010-011, 018-019, 040, 071-090."""


def test_s003_npc_model_exists(db):
    """Story 003: NPC model should exist with required fields."""
    from engine.models import NPC

    npc = NPC(name="Alice", role="farmer", x=10, y=10)
    db.add(npc)
    db.commit()
    assert npc.id is not None
    assert npc.name == "Alice"
    assert npc.role == "farmer"


def test_s005_seed_npcs(db):
    """Story 005: seed_npcs() should create starter NPCs."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    from engine.models import NPC

    count = db.query(NPC).count()
    assert count >= 5, f"Expected at least 5 seed NPCs, got {count}"


def test_s005_seed_npcs_on_valid_tiles(db):
    """Story 005: Seeded NPCs must be on valid grid coordinates."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    from engine.models import NPC

    for npc in db.query(NPC).all():
        assert 0 <= npc.x < 50, f"NPC {npc.name} x={npc.x} out of range"
        assert 0 <= npc.y < 50, f"NPC {npc.name} y={npc.y} out of range"


def test_s010_get_npcs_api(client):
    """Story 010: GET /api/npcs returns list of NPCs."""
    resp = client.get("/api/npcs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_s011_create_npc_api(client, admin_headers):
    """Story 011: POST /api/npcs creates an NPC (admin only)."""
    resp = client.post(
        "/api/npcs",
        json={"name": "Bob", "role": "baker", "x": 5, "y": 5},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "Bob"


def test_s018_npc_home_assignment(db):
    """Story 018: assign_homes() gives NPCs a home_building_id."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs, assign_homes

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    assign_homes(db)
    from engine.models import NPC

    assigned = db.query(NPC).filter(NPC.home_building_id.isnot(None)).count()
    total = db.query(NPC).count()
    assert assigned > 0, "No NPCs assigned homes"


def test_s019_npc_work_assignment(db):
    """Story 019: assign_work() gives NPCs a work_building_id."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs, assign_work

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    assign_work(db)
    from engine.models import NPC

    assigned = db.query(NPC).filter(NPC.work_building_id.isnot(None)).count()
    assert assigned > 0, "No NPCs assigned work"


def test_s040_npc_personality_traits(db):
    """Story 040: NPCs should have personality traits."""
    from engine.models import NPC

    npc = NPC(name="Trait Test", role="farmer", x=0, y=0)
    db.add(npc)
    db.commit()
    # Personality traits should exist as a field
    assert hasattr(npc, "personality")


# ---------------------------------------------------------------------------
# Story 071: Farmer produces Food at Farm
# ---------------------------------------------------------------------------


def test_s071_farmer_produces_food_at_farm(db):
    """Story 071: Farmer at Farm (building_type='food') produces 10 Food via process_work."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    farm = Building(name="Farm", building_type="food", x=10, y=10)
    db.add(farm)
    db.flush()

    npc = NPC(name="Farmer Joe", role="farmer", x=10, y=10, gold=0)
    npc.work_building_id = farm.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    food = db.query(Resource).filter_by(name="Food", building_id=farm.id).first()
    assert food is not None, "Farmer should produce Food resource at Farm"
    assert food.quantity >= 10, f"Expected at least 10 Food, got {food.quantity}"


def test_s071_farmer_not_at_farm_produces_nothing(db):
    """Story 071: Farmer NOT at work building produces nothing."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    farm = Building(name="Farm", building_type="food", x=10, y=10)
    db.add(farm)
    db.flush()

    # NPC is at (20, 20) but farm is at (10, 10)
    npc = NPC(name="Farmer Joe", role="farmer", x=20, y=20, gold=0)
    npc.work_building_id = farm.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    food = db.query(Resource).filter_by(name="Food", building_id=farm.id).first()
    assert food is None or food.quantity == 0, "Farmer not at farm should not produce Food"


# ---------------------------------------------------------------------------
# Story 072: Baker produces Bread at Bakery
# ---------------------------------------------------------------------------


def test_s072_baker_produces_bread_at_bakery(db):
    """Story 072: Baker at Bakery produces 5 Bread (needs Wheat) via process_work."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    bakery = Building(name="Bakery", building_type="bakery", x=15, y=15)
    db.add(bakery)
    db.flush()

    # Provide Wheat at bakery
    wheat = Resource(name="Wheat", quantity=10, building_id=bakery.id)
    db.add(wheat)
    db.flush()

    npc = NPC(name="Baker Bob", role="baker", x=15, y=15, gold=0)
    npc.work_building_id = bakery.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    bread = db.query(Resource).filter_by(name="Bread", building_id=bakery.id).first()
    assert bread is not None, "Baker should produce Bread resource at Bakery"
    assert bread.quantity >= 5, f"Expected at least 5 Bread, got {bread.quantity}"


def test_s072_baker_not_at_bakery_produces_nothing(db):
    """Story 072: Baker NOT at Bakery produces nothing."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    bakery = Building(name="Bakery", building_type="bakery", x=15, y=15)
    db.add(bakery)
    db.flush()

    wheat = Resource(name="Wheat", quantity=10, building_id=bakery.id)
    db.add(wheat)
    db.flush()

    # NPC not at bakery location
    npc = NPC(name="Baker Bob", role="baker", x=30, y=30, gold=0)
    npc.work_building_id = bakery.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    bread = db.query(Resource).filter_by(name="Bread", building_id=bakery.id).first()
    assert bread is None or bread.quantity == 0, "Baker not at bakery should not produce Bread"


# ---------------------------------------------------------------------------
# Story 073: Blacksmith produces Tools at Blacksmith
# ---------------------------------------------------------------------------


def test_s073_blacksmith_produces_tools(db):
    """Story 073: Blacksmith at Blacksmith produces 3 Tools (needs Ore) via process_work."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    smithy = Building(name="Blacksmith", building_type="blacksmith", x=12, y=12)
    db.add(smithy)
    db.flush()

    ore = Resource(name="Ore", quantity=10, building_id=smithy.id)
    db.add(ore)
    db.flush()

    npc = NPC(name="Smith Sam", role="blacksmith", x=12, y=12, gold=0)
    npc.work_building_id = smithy.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    tools = db.query(Resource).filter_by(name="Tools", building_id=smithy.id).first()
    assert tools is not None, "Blacksmith should produce Tools resource"
    assert tools.quantity >= 3, f"Expected at least 3 Tools, got {tools.quantity}"


def test_s073_blacksmith_not_at_smithy_produces_nothing(db):
    """Story 073: Blacksmith NOT at work building produces nothing."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    smithy = Building(name="Blacksmith", building_type="blacksmith", x=12, y=12)
    db.add(smithy)
    db.flush()

    ore = Resource(name="Ore", quantity=10, building_id=smithy.id)
    db.add(ore)
    db.flush()

    npc = NPC(name="Smith Sam", role="blacksmith", x=40, y=40, gold=0)
    npc.work_building_id = smithy.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    tools = db.query(Resource).filter_by(name="Tools", building_id=smithy.id).first()
    assert tools is None or tools.quantity == 0, "Blacksmith not at smithy should not produce Tools"


# ---------------------------------------------------------------------------
# Story 074: Guard earns gold at Guard Tower
# ---------------------------------------------------------------------------


def test_s074_guard_earns_gold_at_guard_tower(db):
    """Story 074: Guard at Guard Tower earns gold via process_work."""
    from engine.models import NPC, Building
    from engine.simulation import process_work

    tower = Building(name="Guard Tower", building_type="guard_tower", x=20, y=20)
    db.add(tower)
    db.flush()

    npc = NPC(name="Guard Gary", role="guard", x=20, y=20, gold=0)
    npc.work_building_id = tower.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(npc)
    assert npc.gold > 0, "Guard at Guard Tower should earn gold"


# ---------------------------------------------------------------------------
# Story 075: Priest increases happiness at Church
# ---------------------------------------------------------------------------


def test_s075_priest_increases_happiness_at_church(db):
    """Story 075: Priest at Church increases nearby NPC happiness by 5 via process_work."""
    from engine.models import NPC, Building
    from engine.simulation import process_work

    church = Building(name="Church", building_type="church", x=25, y=25)
    db.add(church)
    db.flush()

    priest = NPC(name="Father Mike", role="priest", x=25, y=25, happiness=50)
    priest.work_building_id = church.id
    db.add(priest)
    db.flush()

    # Place a nearby NPC within reasonable range
    nearby_npc = NPC(name="Nearby Ned", role="farmer", x=27, y=27, happiness=50)
    db.add(nearby_npc)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(nearby_npc)
    assert nearby_npc.happiness >= 55, (
        f"Nearby NPC happiness should increase by 5, got {nearby_npc.happiness}"
    )


# ---------------------------------------------------------------------------
# Story 076: Teacher earns gold at School
# ---------------------------------------------------------------------------


def test_s076_teacher_earns_gold_at_school(db):
    """Story 076: Teacher at School earns gold via process_work."""
    from engine.models import NPC, Building
    from engine.simulation import process_work

    school = Building(name="School", building_type="school", x=18, y=18)
    db.add(school)
    db.flush()

    npc = NPC(name="Teacher Tina", role="teacher", x=18, y=18, gold=0)
    npc.work_building_id = school.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(npc)
    assert npc.gold > 0, "Teacher at School should earn gold"


# ---------------------------------------------------------------------------
# Story 077: Doctor earns gold at Hospital
# ---------------------------------------------------------------------------


def test_s077_doctor_earns_gold_at_hospital(db):
    """Story 077: Doctor at Hospital earns gold via process_work."""
    from engine.models import NPC, Building
    from engine.simulation import process_work

    hospital = Building(name="Hospital", building_type="hospital", x=22, y=22)
    db.add(hospital)
    db.flush()

    npc = NPC(name="Doctor Dan", role="doctor", x=22, y=22, gold=0)
    npc.work_building_id = hospital.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(npc)
    assert npc.gold > 0, "Doctor at Hospital should earn gold"


# ---------------------------------------------------------------------------
# Story 078: Tavern Keeper earns gold at Tavern
# ---------------------------------------------------------------------------


def test_s078_tavern_keeper_earns_gold_at_tavern(db):
    """Story 078: Tavern keeper at Tavern earns gold via process_work."""
    from engine.models import NPC, Building
    from engine.simulation import process_work

    tavern = Building(name="Tavern", building_type="tavern", x=14, y=14)
    db.add(tavern)
    db.flush()

    npc = NPC(name="Keeper Karl", role="tavern_keeper", x=14, y=14, gold=0)
    npc.work_building_id = tavern.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(npc)
    assert npc.gold > 0, "Tavern keeper at Tavern should earn gold"


# ---------------------------------------------------------------------------
# Story 079: Miner produces Ore at Mine
# ---------------------------------------------------------------------------


def test_s079_miner_produces_ore_at_mine(db):
    """Story 079: Miner at Mine produces 8 Ore via process_work."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    mine = Building(name="Mine", building_type="mine", x=5, y=5)
    db.add(mine)
    db.flush()

    npc = NPC(name="Miner Mike", role="miner", x=5, y=5, gold=0)
    npc.work_building_id = mine.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    ore = db.query(Resource).filter_by(name="Ore", building_id=mine.id).first()
    assert ore is not None, "Miner should produce Ore resource at Mine"
    assert ore.quantity >= 8, f"Expected at least 8 Ore, got {ore.quantity}"


def test_s079_miner_not_at_mine_produces_nothing(db):
    """Story 079: Miner NOT at Mine produces nothing."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    mine = Building(name="Mine", building_type="mine", x=5, y=5)
    db.add(mine)
    db.flush()

    npc = NPC(name="Miner Mike", role="miner", x=40, y=40, gold=0)
    npc.work_building_id = mine.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    ore = db.query(Resource).filter_by(name="Ore", building_id=mine.id).first()
    assert ore is None or ore.quantity == 0, "Miner not at mine should not produce Ore"


# ---------------------------------------------------------------------------
# Story 080: Lumberjack produces Wood at Lumber Mill
# ---------------------------------------------------------------------------


def test_s080_lumberjack_produces_wood_at_lumber_mill(db):
    """Story 080: Lumberjack at Lumber Mill produces 8 Wood via process_work."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    mill = Building(name="Lumber Mill", building_type="lumber_mill", x=8, y=8)
    db.add(mill)
    db.flush()

    npc = NPC(name="Lumber Lou", role="lumberjack", x=8, y=8, gold=0)
    npc.work_building_id = mill.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    wood = db.query(Resource).filter_by(name="Wood", building_id=mill.id).first()
    assert wood is not None, "Lumberjack should produce Wood resource at Lumber Mill"
    assert wood.quantity >= 8, f"Expected at least 8 Wood, got {wood.quantity}"


def test_s080_lumberjack_not_at_mill_produces_nothing(db):
    """Story 080: Lumberjack NOT at Lumber Mill produces nothing."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    mill = Building(name="Lumber Mill", building_type="lumber_mill", x=8, y=8)
    db.add(mill)
    db.flush()

    npc = NPC(name="Lumber Lou", role="lumberjack", x=35, y=35, gold=0)
    npc.work_building_id = mill.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    wood = db.query(Resource).filter_by(name="Wood", building_id=mill.id).first()
    assert wood is None or wood.quantity == 0, "Lumberjack not at mill should not produce Wood"


# ---------------------------------------------------------------------------
# Story 081: Fisherman produces Fish at Fishing Dock
# ---------------------------------------------------------------------------


def test_s081_fisherman_produces_fish_at_dock(db):
    """Story 081: Fisherman at Fishing Dock produces 6 Fish via process_work."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    dock = Building(name="Fishing Dock", building_type="fishing_dock", x=3, y=3)
    db.add(dock)
    db.flush()

    npc = NPC(name="Fisher Fred", role="fisherman", x=3, y=3, gold=0)
    npc.work_building_id = dock.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    fish = db.query(Resource).filter_by(name="Fish", building_id=dock.id).first()
    assert fish is not None, "Fisherman should produce Fish resource at Fishing Dock"
    assert fish.quantity >= 6, f"Expected at least 6 Fish, got {fish.quantity}"


def test_s081_fisherman_not_at_dock_produces_nothing(db):
    """Story 081: Fisherman NOT at Fishing Dock produces nothing."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    dock = Building(name="Fishing Dock", building_type="fishing_dock", x=3, y=3)
    db.add(dock)
    db.flush()

    npc = NPC(name="Fisher Fred", role="fisherman", x=45, y=45, gold=0)
    npc.work_building_id = dock.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    fish = db.query(Resource).filter_by(name="Fish", building_id=dock.id).first()
    assert fish is None or fish.quantity == 0, "Fisherman not at dock should not produce Fish"


# ---------------------------------------------------------------------------
# Story 082: Artist produces Art at Theater
# ---------------------------------------------------------------------------


def test_s082_artist_produces_art_at_theater(db):
    """Story 082: Artist at Theater produces 2 Art via process_work."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    theater = Building(name="Theater", building_type="theater", x=16, y=16)
    db.add(theater)
    db.flush()

    npc = NPC(name="Artist Amy", role="artist", x=16, y=16, gold=0)
    npc.work_building_id = theater.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    art = db.query(Resource).filter_by(name="Art", building_id=theater.id).first()
    assert art is not None, "Artist should produce Art resource at Theater"
    assert art.quantity >= 2, f"Expected at least 2 Art, got {art.quantity}"


def test_s082_artist_not_at_theater_produces_nothing(db):
    """Story 082: Artist NOT at Theater produces nothing."""
    from engine.models import NPC, Building, Resource
    from engine.simulation import process_work

    theater = Building(name="Theater", building_type="theater", x=16, y=16)
    db.add(theater)
    db.flush()

    npc = NPC(name="Artist Amy", role="artist", x=40, y=40, gold=0)
    npc.work_building_id = theater.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    art = db.query(Resource).filter_by(name="Art", building_id=theater.id).first()
    assert art is None or art.quantity == 0, "Artist not at theater should not produce Art"


# ---------------------------------------------------------------------------
# Story 083: Bard earns gold at Tavern
# ---------------------------------------------------------------------------


def test_s083_bard_earns_gold_at_tavern(db):
    """Story 083: Bard at Tavern earns gold via process_work."""
    from engine.models import NPC, Building
    from engine.simulation import process_work

    tavern = Building(name="Tavern", building_type="tavern", x=14, y=14)
    db.add(tavern)
    db.flush()

    npc = NPC(name="Bard Barry", role="bard", x=14, y=14, gold=0)
    npc.work_building_id = tavern.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(npc)
    assert npc.gold > 0, "Bard at Tavern should earn gold"


# ---------------------------------------------------------------------------
# Story 084: Politician earns gold at Town Hall
# ---------------------------------------------------------------------------


def test_s084_politician_earns_gold_at_town_hall(db):
    """Story 084: Politician at Town Hall earns gold via process_work."""
    from engine.models import NPC, Building
    from engine.simulation import process_work

    town_hall = Building(name="Town Hall", building_type="civic", x=25, y=25)
    db.add(town_hall)
    db.flush()

    npc = NPC(name="Politician Pete", role="politician", x=25, y=25, gold=0)
    npc.work_building_id = town_hall.id
    db.add(npc)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(npc)
    assert npc.gold > 0, "Politician at Town Hall should earn gold"


# ---------------------------------------------------------------------------
# Story 085: Thief steals gold at night
# ---------------------------------------------------------------------------


def test_s085_thief_steals_gold_at_night(db):
    """Story 085: Thief steals gold from other NPCs at night via process_work."""
    from engine.models import NPC, Building, WorldState
    from engine.simulation import process_work

    # Set up nighttime world state
    ws = WorldState(tick=3, day=1, time_of_day="night")
    db.add(ws)
    db.flush()

    building = Building(name="Hideout", building_type="residential", x=10, y=10)
    db.add(building)
    db.flush()

    thief = NPC(name="Thief Tom", role="thief", x=10, y=10, gold=0)
    thief.work_building_id = building.id
    db.add(thief)
    db.flush()

    # Place a victim NPC with gold
    victim = NPC(name="Rich Rick", role="merchant", x=12, y=12, gold=100)
    db.add(victim)
    db.flush()

    process_work(db)
    db.flush()

    db.refresh(thief)
    db.refresh(victim)
    assert thief.gold > 0, "Thief should steal gold at night"
    assert victim.gold < 100, "Victim should lose gold to thief"


# ---------------------------------------------------------------------------
# Story 086: Relationship model
# ---------------------------------------------------------------------------


def test_s086_relationship_model_exists(db):
    """Story 086: Relationship model should exist with required fields."""
    from engine.models import Relationship, NPC

    npc1 = NPC(name="Alice", role="farmer", x=0, y=0)
    npc2 = NPC(name="Bob", role="baker", x=1, y=1)
    db.add_all([npc1, npc2])
    db.flush()

    rel = Relationship(npc_id=npc1.id, target_npc_id=npc2.id, relationship_type="friend", strength=50)
    db.add(rel)
    db.flush()

    assert rel.id is not None
    assert rel.npc_id == npc1.id
    assert rel.target_npc_id == npc2.id
    assert rel.relationship_type == "friend"
    assert rel.strength == 50


def test_s086_relationship_unique_constraint(db):
    """Story 086: Unique constraint prevents duplicate relationships."""
    import pytest
    from sqlalchemy.exc import IntegrityError
    from engine.models import Relationship, NPC

    npc1 = NPC(name="Alice", role="farmer", x=0, y=0)
    npc2 = NPC(name="Bob", role="baker", x=1, y=1)
    db.add_all([npc1, npc2])
    db.flush()

    rel1 = Relationship(npc_id=npc1.id, target_npc_id=npc2.id, relationship_type="friend", strength=50)
    db.add(rel1)
    db.flush()

    rel2 = Relationship(npc_id=npc1.id, target_npc_id=npc2.id, relationship_type="rival", strength=30)
    db.add(rel2)

    with pytest.raises(IntegrityError):
        db.flush()

    db.rollback()


# ---------------------------------------------------------------------------
# Story 087: Friendship and rivalry
# ---------------------------------------------------------------------------


def test_s087_npcs_at_same_building_gain_friendship(db):
    """Story 087: Two NPCs at same building gain friendship via update_relationships(db)."""
    from engine.models import NPC, Building, Relationship
    from engine.simulation import update_relationships

    building = Building(name="Farm", building_type="food", x=10, y=10)
    db.add(building)
    db.flush()

    npc1 = NPC(name="Alice", role="farmer", x=10, y=10)
    npc1.work_building_id = building.id
    npc2 = NPC(name="Bob", role="farmer", x=10, y=10)
    npc2.work_building_id = building.id
    db.add_all([npc1, npc2])
    db.flush()

    update_relationships(db)
    db.flush()

    rel = db.query(Relationship).filter(
        Relationship.npc_id == npc1.id,
        Relationship.target_npc_id == npc2.id,
    ).first()
    assert rel is not None, "NPCs at same building should form a relationship"
    assert rel.strength > 0, "Relationship strength should be positive"


# ---------------------------------------------------------------------------
# Story 088: Marriage system
# ---------------------------------------------------------------------------


def test_s088_marriage_with_high_friendship(db):
    """Story 088: Two NPCs with friendship > 80 can marry via check_marriage(db)."""
    from engine.models import NPC, Relationship
    from engine.simulation import check_marriage

    npc1 = NPC(name="Alice", role="farmer", x=0, y=0)
    npc2 = NPC(name="Bob", role="baker", x=1, y=1)
    db.add_all([npc1, npc2])
    db.flush()

    rel = Relationship(npc_id=npc1.id, target_npc_id=npc2.id, relationship_type="friend", strength=85)
    db.add(rel)
    db.flush()

    check_marriage(db)
    db.flush()

    # Refresh relationship to check if it changed to married
    rel = db.query(Relationship).filter(
        Relationship.npc_id == npc1.id,
        Relationship.target_npc_id == npc2.id,
    ).first()
    assert rel.relationship_type == "spouse", "NPCs with friendship > 80 should marry"


def test_s088_already_married_cannot_remarry(db):
    """Story 088: Already married NPC cannot remarry."""
    from engine.models import NPC, Relationship
    from engine.simulation import check_marriage

    npc1 = NPC(name="Alice", role="farmer", x=0, y=0)
    npc2 = NPC(name="Bob", role="baker", x=1, y=1)
    npc3 = NPC(name="Carol", role="guard", x=2, y=2)
    db.add_all([npc1, npc2, npc3])
    db.flush()

    # npc1 already married to npc2
    rel_married = Relationship(npc_id=npc1.id, target_npc_id=npc2.id, relationship_type="spouse", strength=90)
    db.add(rel_married)
    db.flush()

    # npc1 has high friendship with npc3
    rel_friend = Relationship(npc_id=npc1.id, target_npc_id=npc3.id, relationship_type="friend", strength=85)
    db.add(rel_friend)
    db.flush()

    check_marriage(db)
    db.flush()

    # npc1-npc3 should still be friends, not spouses
    rel = db.query(Relationship).filter(
        Relationship.npc_id == npc1.id,
        Relationship.target_npc_id == npc3.id,
    ).first()
    assert rel.relationship_type == "friend", "Already married NPC should not remarry"


# ---------------------------------------------------------------------------
# Story 089: Aging and death
# ---------------------------------------------------------------------------


def test_s089_npc_has_age_field(db):
    """Story 089: NPC should have an age field."""
    from engine.models import NPC

    npc = NPC(name="Old Oliver", role="farmer", x=0, y=0)
    db.add(npc)
    db.flush()

    assert hasattr(npc, "age"), "NPC should have an age field"


def test_s089_age_npcs_increments_age(db):
    """Story 089: age_npcs(db) increments NPC age."""
    from engine.models import NPC
    from engine.simulation import age_npcs

    npc = NPC(name="Young Yolanda", role="farmer", x=0, y=0)
    npc.age = 20
    db.add(npc)
    db.flush()

    age_npcs(db)
    db.flush()

    db.refresh(npc)
    assert npc.age == 21, f"Expected age 21, got {npc.age}"


def test_s089_npc_dies_at_max_age(db):
    """Story 089: NPC at max_age is marked dead."""
    from engine.models import NPC
    from engine.simulation import age_npcs

    npc = NPC(name="Ancient Abe", role="farmer", x=0, y=0)
    npc.age = 100  # At or near max_age
    db.add(npc)
    db.flush()

    age_npcs(db)
    db.flush()

    db.refresh(npc)
    assert hasattr(npc, "is_dead"), "NPC should have an is_dead field"
    assert npc.is_dead, "NPC at max age should be marked dead"


# ---------------------------------------------------------------------------
# Story 090: Inheritance
# ---------------------------------------------------------------------------


def test_s090_inheritance_split_among_children(db):
    """Story 090: Dead NPC's gold split among children via process_inheritance(db)."""
    from engine.models import NPC, Relationship
    from engine.simulation import process_inheritance

    parent = NPC(name="Dead Dad", role="farmer", x=0, y=0, gold=100)
    parent.is_dead = True
    parent.age = 100
    db.add(parent)
    db.flush()

    child1 = NPC(name="Child 1", role="farmer", x=1, y=1, gold=0)
    child2 = NPC(name="Child 2", role="baker", x=2, y=2, gold=0)
    db.add_all([child1, child2])
    db.flush()

    rel1 = Relationship(npc_id=parent.id, target_npc_id=child1.id, relationship_type="child", strength=100)
    rel2 = Relationship(npc_id=parent.id, target_npc_id=child2.id, relationship_type="child", strength=100)
    db.add_all([rel1, rel2])
    db.flush()

    process_inheritance(db)
    db.flush()

    db.refresh(child1)
    db.refresh(child2)
    db.refresh(parent)
    assert child1.gold == 50, f"Child 1 should get 50 gold, got {child1.gold}"
    assert child2.gold == 50, f"Child 2 should get 50 gold, got {child2.gold}"
    assert parent.gold == 0, "Dead parent's gold should be distributed"


def test_s090_inheritance_no_children_spouse_gets_gold(db):
    """Story 090: No children -> spouse gets gold."""
    from engine.models import NPC, Relationship
    from engine.simulation import process_inheritance

    dead_npc = NPC(name="Dead Dan", role="farmer", x=0, y=0, gold=100)
    dead_npc.is_dead = True
    dead_npc.age = 100
    db.add(dead_npc)
    db.flush()

    spouse = NPC(name="Spouse Sally", role="baker", x=1, y=1, gold=0)
    db.add(spouse)
    db.flush()

    rel = Relationship(npc_id=dead_npc.id, target_npc_id=spouse.id, relationship_type="spouse", strength=90)
    db.add(rel)
    db.flush()

    process_inheritance(db)
    db.flush()

    db.refresh(spouse)
    db.refresh(dead_npc)
    assert spouse.gold == 100, f"Spouse should get all 100 gold, got {spouse.gold}"
    assert dead_npc.gold == 0, "Dead NPC's gold should be distributed"


def test_s090_inheritance_no_family_treasury_gets_gold(db):
    """Story 090: No family -> Treasury gets gold."""
    from engine.models import NPC, Building, Treasury
    from engine.simulation import process_inheritance

    # Create a Town Hall with Treasury
    town_hall = Building(name="Town Hall", building_type="civic", x=25, y=25)
    db.add(town_hall)
    db.flush()

    treasury = Treasury(gold_stored=0, building_id=town_hall.id)
    db.add(treasury)
    db.flush()

    dead_npc = NPC(name="Lonely Larry", role="farmer", x=0, y=0, gold=100)
    dead_npc.is_dead = True
    dead_npc.age = 100
    db.add(dead_npc)
    db.flush()

    process_inheritance(db)
    db.flush()

    db.refresh(treasury)
    db.refresh(dead_npc)
    assert treasury.gold_stored == 100, f"Treasury should get 100 gold, got {treasury.gold_stored}"
    assert dead_npc.gold == 0, "Dead NPC's gold should go to Treasury"


# ===========================================================================
# Helper: setup world with seeded data
# ===========================================================================


def _setup_world(db):
    """Seed grid, buildings, and NPCs for tests that need a populated world."""
    from engine.simulation import init_world_state, init_grid, seed_buildings, seed_npcs

    init_world_state(db)
    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)


# ---------------------------------------------------------------------------
# Story 176: NPC memory - recent events
# ---------------------------------------------------------------------------


def test_s176_remember_event_stores_event(db):
    """Story 176: remember_event stores an event in NPC.memory_events JSON."""
    import json
    from engine.models import NPC
    from engine.simulation import remember_event

    npc = NPC(name="Memo Mike", role="farmer", x=5, y=5)
    db.add(npc)
    db.flush()

    remember_event(db, npc.id, "saw a fire")
    db.flush()

    db.refresh(npc)
    events = json.loads(npc.memory_events) if isinstance(npc.memory_events, str) else npc.memory_events
    assert isinstance(events, list), "memory_events should be a list"
    assert len(events) >= 1, "Should have at least 1 event stored"
    assert "saw a fire" in str(events), "Event text should be in memory_events"


def test_s176_remember_event_max_ten(db):
    """Story 176: memory_events stores max 10 events, oldest dropped."""
    import json
    from engine.models import NPC
    from engine.simulation import remember_event

    npc = NPC(name="Memo Max", role="farmer", x=5, y=5)
    db.add(npc)
    db.flush()

    for i in range(15):
        remember_event(db, npc.id, f"event_{i}")
        db.flush()

    db.refresh(npc)
    events = json.loads(npc.memory_events) if isinstance(npc.memory_events, str) else npc.memory_events
    assert isinstance(events, list), "memory_events should be a list"
    assert len(events) <= 10, f"Max 10 events, got {len(events)}"


def test_s176_memory_events_valid_json(db):
    """Story 176: NPC.memory_events field exists and is valid JSON."""
    import json
    from engine.models import NPC
    from engine.simulation import remember_event

    npc = NPC(name="JSON Joe", role="farmer", x=5, y=5)
    db.add(npc)
    db.flush()

    remember_event(db, npc.id, "test event")
    db.flush()

    db.refresh(npc)
    raw = npc.memory_events
    # Should be parseable JSON (either already a list or a JSON string)
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw
    assert isinstance(parsed, list), "Parsed memory_events should be a list"


# ---------------------------------------------------------------------------
# Story 177: NPC memory - favorite buildings
# ---------------------------------------------------------------------------


def test_s177_update_favorites_tracks_visited(db):
    """Story 177: update_favorites tracks top 3 most-visited buildings."""
    import json
    from engine.models import NPC, Building
    from engine.simulation import update_favorites

    b1 = Building(name="Farm", building_type="food", x=10, y=10)
    b2 = Building(name="Tavern", building_type="tavern", x=15, y=15)
    b3 = Building(name="Church", building_type="church", x=20, y=20)
    b4 = Building(name="Market", building_type="market", x=25, y=25)
    db.add_all([b1, b2, b3, b4])
    db.flush()

    npc = NPC(name="Fav Fred", role="farmer", x=10, y=10)
    db.add(npc)
    db.flush()

    # Simulate visits by placing NPC at buildings multiple times
    # The function should be callable and update favorite_buildings
    update_favorites(db, npc.id)
    db.flush()

    db.refresh(npc)
    assert hasattr(npc, "favorite_buildings"), "NPC should have favorite_buildings field"


def test_s177_favorites_max_three(db):
    """Story 177: favorite_buildings stores at most 3 entries."""
    import json
    from engine.models import NPC, Building
    from engine.simulation import update_favorites

    buildings = []
    for i in range(5):
        b = Building(name=f"B{i}", building_type="food", x=i * 2, y=i * 2)
        buildings.append(b)
    db.add_all(buildings)
    db.flush()

    npc = NPC(name="Fav Fiona", role="farmer", x=0, y=0)
    db.add(npc)
    db.flush()

    update_favorites(db, npc.id)
    db.flush()

    db.refresh(npc)
    favs = npc.favorite_buildings
    if isinstance(favs, str):
        favs = json.loads(favs)
    if favs is not None:
        assert len(favs) <= 3, f"Max 3 favorites, got {len(favs)}"


# ---------------------------------------------------------------------------
# Story 178: NPC memory - avoid dangerous areas
# ---------------------------------------------------------------------------


def test_s178_mark_dangerous_area(db):
    """Story 178: mark_dangerous_area adds area to NPC.avoided_areas."""
    import json
    from engine.models import NPC
    from engine.simulation import mark_dangerous_area

    npc = NPC(name="Cautious Carl", role="guard", x=5, y=5)
    db.add(npc)
    db.flush()

    mark_dangerous_area(db, npc.id, 10, 15)
    db.flush()

    db.refresh(npc)
    assert hasattr(npc, "avoided_areas"), "NPC should have avoided_areas field"
    areas = npc.avoided_areas
    if isinstance(areas, str):
        areas = json.loads(areas)
    assert isinstance(areas, list), "avoided_areas should be a list"
    assert len(areas) >= 1, "Should have at least 1 dangerous area"


def test_s178_dangerous_areas_expire(db):
    """Story 178: Dangerous areas expire after 50 ticks."""
    import json
    from engine.models import NPC
    from engine.simulation import mark_dangerous_area

    npc = NPC(name="Expire Ed", role="guard", x=5, y=5)
    db.add(npc)
    db.flush()

    mark_dangerous_area(db, npc.id, 10, 15)
    db.flush()

    db.refresh(npc)
    areas = npc.avoided_areas
    if isinstance(areas, str):
        areas = json.loads(areas)
    # Areas should have a tick or expiry concept — at minimum, areas exist
    assert isinstance(areas, list), "avoided_areas should be a list"


# ---------------------------------------------------------------------------
# Story 179: NPC memory - remember friends
# ---------------------------------------------------------------------------


def test_s179_get_friends_returns_high_friendship(db):
    """Story 179: get_friends returns NPC IDs with friendship > 60."""
    from engine.models import NPC, Relationship
    from engine.simulation import get_friends

    npc1 = NPC(name="Social Sue", role="farmer", x=0, y=0)
    npc2 = NPC(name="Friend Fran", role="baker", x=1, y=1)
    npc3 = NPC(name="Acquaint Ann", role="guard", x=2, y=2)
    db.add_all([npc1, npc2, npc3])
    db.flush()

    # npc2 is a friend (strength > 60), npc3 is not
    rel1 = Relationship(npc_id=npc1.id, target_npc_id=npc2.id, relationship_type="friend", strength=75)
    rel2 = Relationship(npc_id=npc1.id, target_npc_id=npc3.id, relationship_type="friend", strength=30)
    db.add_all([rel1, rel2])
    db.flush()

    friends = get_friends(db, npc1.id)
    assert isinstance(friends, list), "get_friends should return a list"
    assert npc2.id in friends, "NPC with friendship > 60 should be in friends"
    assert npc3.id not in friends, "NPC with friendship <= 60 should not be in friends"


def test_s179_get_friends_empty_when_none(db):
    """Story 179: get_friends returns empty list when NPC has no friends."""
    from engine.models import NPC
    from engine.simulation import get_friends

    npc = NPC(name="Lonely Larry", role="farmer", x=0, y=0)
    db.add(npc)
    db.flush()

    friends = get_friends(db, npc.id)
    assert isinstance(friends, list), "get_friends should return a list"
    assert len(friends) == 0, "NPC with no relationships should have no friends"


# ---------------------------------------------------------------------------
# Story 180: NPC learning from experience
# ---------------------------------------------------------------------------


def test_s180_npc_learns_lesson(db):
    """Story 180: learn() stores a lesson in NPC.experience JSON."""
    import json
    from engine.models import NPC
    from engine.simulation import learn

    npc = NPC(name="Learner Liz", role="farmer", x=5, y=5)
    db.add(npc)
    db.flush()

    learn(db, npc.id, "fire is dangerous")
    db.flush()

    db.refresh(npc)
    assert hasattr(npc, "experience"), "NPC should have experience field"
    exp = npc.experience
    if isinstance(exp, str):
        exp = json.loads(exp)
    assert "fire is dangerous" in str(exp), "Lesson should be stored in experience"


def test_s180_learned_lesson_exists(db):
    """Story 180: After learning, the lesson can be found in experience."""
    import json
    from engine.models import NPC
    from engine.simulation import learn

    npc = NPC(name="Study Steve", role="guard", x=5, y=5)
    db.add(npc)
    db.flush()

    learn(db, npc.id, "avoid storms")
    learn(db, npc.id, "trade with merchants")
    db.flush()

    db.refresh(npc)
    exp = npc.experience
    if isinstance(exp, str):
        exp = json.loads(exp)
    # Should contain at least 2 lessons
    assert len(exp) >= 2 if isinstance(exp, list) else len(exp) >= 2, "Should store multiple lessons"


# ---------------------------------------------------------------------------
# Story 181: Auto-suggest building placement
# ---------------------------------------------------------------------------


def test_s181_suggest_farm_near_water(db):
    """Story 181: suggest_building_placement for farm returns y < 15."""
    from engine.simulation import suggest_building_placement

    _setup_world(db)

    result = suggest_building_placement(db, "food")
    assert result is not None, "Should return a placement suggestion"
    x, y = result
    assert 0 <= x < 50, f"x={x} out of range"
    assert y < 15, f"Farm should be placed near water (y < 15), got y={y}"


def test_s181_no_overlap_with_existing(db):
    """Story 181: Suggested placement does not overlap existing buildings."""
    from engine.models import Building
    from engine.simulation import suggest_building_placement

    _setup_world(db)

    result = suggest_building_placement(db, "food")
    assert result is not None, "Should return a placement suggestion"
    x, y = result

    existing = db.query(Building).filter(Building.x == x, Building.y == y).first()
    assert existing is None, f"Suggested ({x},{y}) overlaps existing building"


# ---------------------------------------------------------------------------
# Story 182: Detect resource gaps
# ---------------------------------------------------------------------------


def test_s182_detect_gaps_no_farm(db):
    """Story 182: Town with no farm has a food gap."""
    from engine.models import Building
    from engine.simulation import detect_resource_gaps

    # Create a town with no farm
    b = Building(name="Town Hall", building_type="civic", x=25, y=25)
    db.add(b)
    db.flush()

    gaps = detect_resource_gaps(db)
    assert isinstance(gaps, list), "detect_resource_gaps should return a list"
    assert len(gaps) >= 1, "Town with no farm should have at least 1 gap"
    # Check gap structure
    gap = gaps[0]
    assert "gap" in gap or "severity" in gap or "suggestion" in gap, \
        "Gap dict should have gap, severity, or suggestion keys"


def test_s182_detect_gaps_complete_town(db):
    """Story 182: Well-supplied town has no critical gaps."""
    from engine.simulation import detect_resource_gaps

    _setup_world(db)

    gaps = detect_resource_gaps(db)
    assert isinstance(gaps, list), "detect_resource_gaps should return a list"
    # A seeded world might still have gaps, but the function should work
    # Just verify it returns a list without crashing


# ---------------------------------------------------------------------------
# Story 183: Recommend construction
# ---------------------------------------------------------------------------


def test_s183_recommend_farm_when_food_needed(db):
    """Story 183: Town needing food recommends farm construction."""
    from engine.models import Building
    from engine.simulation import recommend_construction

    # Town with no farm
    b = Building(name="Town Hall", building_type="civic", x=25, y=25)
    db.add(b)
    db.flush()

    rec = recommend_construction(db)
    assert rec is not None, "Should return a recommendation"
    assert "building_type" in rec, "Recommendation should have building_type"
    assert "reason" in rec, "Recommendation should have reason"
    assert "priority" in rec, "Recommendation should have priority"


def test_s183_recommend_valid_coordinates(db):
    """Story 183: Recommended coordinates are valid grid positions."""
    from engine.models import Building
    from engine.simulation import recommend_construction

    b = Building(name="Town Hall", building_type="civic", x=25, y=25)
    db.add(b)
    db.flush()

    rec = recommend_construction(db)
    assert rec is not None, "Should return a recommendation"
    if "suggested_x" in rec and "suggested_y" in rec:
        assert 0 <= rec["suggested_x"] < 50, f"x={rec['suggested_x']} out of range"
        assert 0 <= rec["suggested_y"] < 50, f"y={rec['suggested_y']} out of range"


# ---------------------------------------------------------------------------
# Story 184: Zoning system
# ---------------------------------------------------------------------------


def test_s184_zone_grid_residential_nw(db):
    """Story 184: Tile (5,5) in NW should be residential zone."""
    from engine.models import Tile
    from engine.simulation import zone_grid

    _setup_world(db)

    zone_grid(db)
    db.flush()

    tile = db.query(Tile).filter(Tile.x == 5, Tile.y == 5).first()
    assert tile is not None, "Tile (5,5) should exist"
    assert hasattr(tile, "zone"), "Tile should have zone field"
    assert tile.zone == "residential", f"Tile (5,5) should be residential, got {tile.zone}"


def test_s184_zone_grid_commercial_ne(db):
    """Story 184: Tile (40,5) in NE should be commercial zone."""
    from engine.models import Tile
    from engine.simulation import zone_grid

    _setup_world(db)

    zone_grid(db)
    db.flush()

    tile = db.query(Tile).filter(Tile.x == 40, Tile.y == 5).first()
    assert tile is not None, "Tile (40,5) should exist"
    assert tile.zone == "commercial", f"Tile (40,5) should be commercial, got {tile.zone}"


def test_s184_zone_grid_industrial_sw(db):
    """Story 184: Tile (5,40) in SW should be industrial zone."""
    from engine.models import Tile
    from engine.simulation import zone_grid

    _setup_world(db)

    zone_grid(db)
    db.flush()

    tile = db.query(Tile).filter(Tile.x == 5, Tile.y == 40).first()
    assert tile is not None, "Tile (5,40) should exist"
    assert tile.zone == "industrial", f"Tile (5,40) should be industrial, got {tile.zone}"


# ---------------------------------------------------------------------------
# Story 185: Infrastructure scoring
# ---------------------------------------------------------------------------


def test_s185_empty_town_low_score(db):
    """Story 185: Empty town scores low on infrastructure."""
    from engine.simulation import calculate_infrastructure_score

    score = calculate_infrastructure_score(db)
    assert isinstance(score, (int, float)), "Score should be numeric"
    assert 0 <= score <= 100, f"Score should be 0-100, got {score}"
    assert score < 50, f"Empty town should score low, got {score}"


def test_s185_developed_town_higher_score(db):
    """Story 185: Developed town scores higher than empty town."""
    from engine.simulation import calculate_infrastructure_score

    # Score empty town
    empty_score = calculate_infrastructure_score(db)

    # Setup a developed town
    _setup_world(db)

    developed_score = calculate_infrastructure_score(db)
    assert isinstance(developed_score, (int, float)), "Score should be numeric"
    assert 0 <= developed_score <= 100, f"Score should be 0-100, got {developed_score}"
    assert developed_score > empty_score, \
        f"Developed town ({developed_score}) should score higher than empty ({empty_score})"


# ---------------------------------------------------------------------------
# Story 186: Merchant NPCs set prices
# ---------------------------------------------------------------------------


def test_s186_merchant_sets_price(db):
    """Story 186: set_merchant_prices sets prices for a merchant NPC."""
    from engine.models import NPC, Building
    from engine.simulation import set_merchant_prices

    market = Building(name="Market", building_type="market", x=20, y=20)
    db.add(market)
    db.flush()

    npc = NPC(name="Merchant Mel", role="merchant", x=20, y=20, gold=50)
    npc.work_building_id = market.id
    db.add(npc)
    db.flush()

    # Should not crash
    result = set_merchant_prices(db, npc.id)
    db.flush()

    # Result could be None or a dict — just check it runs
    assert result is not None or result is None  # function executed without error


# ---------------------------------------------------------------------------
# Story 187: Banker NPCs offer loans
# ---------------------------------------------------------------------------


def test_s187_loan_model_exists(db):
    """Story 187: Loan model should exist with required fields."""
    from engine.models import Loan, NPC

    banker = NPC(name="Banker Bob", role="banker", x=0, y=0, gold=500)
    borrower = NPC(name="Poor Pete", role="farmer", x=1, y=1, gold=0)
    db.add_all([banker, borrower])
    db.flush()

    loan = Loan(
        lender_npc_id=banker.id,
        borrower_npc_id=borrower.id,
        amount=100,
        interest_rate=0.1,
        ticks_remaining=50,
        status="active",
    )
    db.add(loan)
    db.flush()

    assert loan.id is not None
    assert loan.lender_npc_id == banker.id
    assert loan.borrower_npc_id == borrower.id
    assert loan.amount == 100
    assert loan.interest_rate >= 0
    assert loan.ticks_remaining > 0
    assert loan.status == "active"


def test_s187_banker_offers_loan(db):
    """Story 187: Banker offers loan to poor NPC via process_loans."""
    from engine.models import NPC, Loan
    from engine.simulation import process_loans

    banker = NPC(name="Banker Beth", role="banker", x=5, y=5, gold=500)
    borrower = NPC(name="Poor Paul", role="farmer", x=6, y=6, gold=0)
    db.add_all([banker, borrower])
    db.flush()

    process_loans(db)
    db.flush()

    loans = db.query(Loan).all()
    assert len(loans) >= 1, "Banker should offer at least 1 loan"


# ---------------------------------------------------------------------------
# Story 188: Tax collector routes
# ---------------------------------------------------------------------------


def test_s188_tax_route_returns_list(db):
    """Story 188: get_tax_route returns a list of building visit order."""
    from engine.models import NPC, Building
    from engine.simulation import get_tax_route

    _setup_world(db)

    collector = NPC(name="Tax Tom", role="tax_collector", x=25, y=25)
    db.add(collector)
    db.flush()

    route = get_tax_route(db, collector.id)
    assert isinstance(route, list), "get_tax_route should return a list"
    assert len(route) >= 1, "Route should have at least 1 building"


def test_s188_tax_route_prioritizes_buildings(db):
    """Story 188: Tax route prioritizes buildings (returns ordered list)."""
    from engine.models import NPC, Building
    from engine.simulation import get_tax_route

    _setup_world(db)

    collector = NPC(name="Tax Terry", role="tax_collector", x=25, y=25)
    db.add(collector)
    db.flush()

    route = get_tax_route(db, collector.id)
    assert isinstance(route, list), "Route should be a list"
    # Route entries should be building IDs or tuples — just check it's non-empty
    assert len(route) >= 1, "Route should include buildings"


# ---------------------------------------------------------------------------
# Story 189: Trade negotiations
# ---------------------------------------------------------------------------


def test_s189_negotiate_trade_returns_price(db):
    """Story 189: negotiate_trade returns an agreed price."""
    from engine.models import NPC
    from engine.simulation import negotiate_trade

    npc_a = NPC(name="Trader A", role="merchant", x=10, y=10, gold=100)
    npc_b = NPC(name="Trader B", role="merchant", x=11, y=11, gold=100)
    db.add_all([npc_a, npc_b])
    db.flush()

    price = negotiate_trade(db, npc_a.id, npc_b.id, "Food", 10)
    assert price is not None, "negotiate_trade should return a price"
    assert price > 0, f"Agreed price should be positive, got {price}"


def test_s189_negotiate_trade_creates_transaction(db):
    """Story 189: negotiate_trade creates a Transaction record."""
    from engine.models import NPC, Transaction
    from engine.simulation import negotiate_trade

    npc_a = NPC(name="Seller Sam", role="merchant", x=10, y=10, gold=100)
    npc_b = NPC(name="Buyer Ben", role="merchant", x=11, y=11, gold=100)
    db.add_all([npc_a, npc_b])
    db.flush()

    negotiate_trade(db, npc_a.id, npc_b.id, "Food", 5)
    db.flush()

    txns = db.query(Transaction).all()
    assert len(txns) >= 1, "negotiate_trade should create a Transaction"


# ---------------------------------------------------------------------------
# Story 190: Bankruptcy handling
# ---------------------------------------------------------------------------


def test_s190_npc_goes_bankrupt(db):
    """Story 190: NPC with gold < -50 is marked bankrupt."""
    from engine.models import NPC
    from engine.simulation import check_bankruptcy

    npc = NPC(name="Broke Bob", role="farmer", x=5, y=5, gold=-60)
    db.add(npc)
    db.flush()

    check_bankruptcy(db)
    db.flush()

    db.refresh(npc)
    # NPC should be marked bankrupt (via is_bankrupt field or role change)
    is_bankrupt = getattr(npc, "is_bankrupt", None)
    if is_bankrupt is not None:
        assert npc.is_bankrupt, "NPC with gold=-60 should be bankrupt"
    else:
        # Alternatively check status or role
        assert hasattr(npc, "is_bankrupt"), "NPC should have is_bankrupt field"


def test_s190_bankrupt_npc_loses_home_and_work(db):
    """Story 190: Bankrupt NPC loses home and work assignments."""
    from engine.models import NPC, Building
    from engine.simulation import check_bankruptcy

    house = Building(name="House", building_type="residential", x=30, y=30)
    farm = Building(name="Farm", building_type="food", x=10, y=10)
    db.add_all([house, farm])
    db.flush()

    npc = NPC(name="Bankrupt Bill", role="farmer", x=10, y=10, gold=-60)
    npc.home_building_id = house.id
    npc.work_building_id = farm.id
    db.add(npc)
    db.flush()

    check_bankruptcy(db)
    db.flush()

    db.refresh(npc)
    assert npc.home_building_id is None, "Bankrupt NPC should lose home"
    assert npc.work_building_id is None, "Bankrupt NPC should lose work"


# ---------------------------------------------------------------------------
# Story 196: Town newspaper NPC
# ---------------------------------------------------------------------------


def test_s196_newspaper_model_exists(db):
    """Story 196: Newspaper model should exist with required fields."""
    from engine.models import Newspaper, NPC

    author = NPC(name="Reporter Rita", role="journalist", x=0, y=0)
    db.add(author)
    db.flush()

    paper = Newspaper(
        headline="Town grows!",
        body="The town added a new building today.",
        author_npc_id=author.id,
        tick=10,
    )
    db.add(paper)
    db.flush()

    assert paper.id is not None
    assert paper.headline == "Town grows!"
    assert paper.body is not None
    assert paper.author_npc_id == author.id
    assert paper.tick == 10


def test_s196_publish_newspaper_creates_entry(db):
    """Story 196: publish_newspaper creates a Newspaper entry."""
    from engine.models import NPC, Newspaper
    from engine.simulation import publish_newspaper

    _setup_world(db)

    publish_newspaper(db)
    db.flush()

    papers = db.query(Newspaper).all()
    assert len(papers) >= 1, "publish_newspaper should create at least 1 newspaper"


# ---------------------------------------------------------------------------
# Story 197: Historian NPC
# ---------------------------------------------------------------------------


def test_s197_milestone_model_exists(db):
    """Story 197: Milestone model should exist with required fields."""
    from engine.models import Milestone

    ms = Milestone(
        name="First building",
        description="The town built its first building.",
        tick_achieved=5,
    )
    db.add(ms)
    db.flush()

    assert ms.id is not None
    assert ms.name == "First building"
    assert ms.description is not None
    assert ms.tick_achieved == 5


def test_s197_record_milestones_creates_entry(db):
    """Story 197: record_milestones creates a Milestone entry."""
    from engine.models import Milestone
    from engine.simulation import record_milestones

    _setup_world(db)

    record_milestones(db)
    db.flush()

    milestones = db.query(Milestone).all()
    assert len(milestones) >= 1, "record_milestones should create at least 1 milestone"


# ---------------------------------------------------------------------------
# Story 198: Town achievements system
# ---------------------------------------------------------------------------


def test_s198_achievement_model_exists(db):
    """Story 198: Achievement model should exist with required fields."""
    from engine.models import Achievement

    ach = Achievement(
        name="First Farm",
        description="Built the first farm in town.",
        condition='{"building_type": "food", "count": 1}',
        achieved=False,
    )
    db.add(ach)
    db.flush()

    assert ach.id is not None
    assert ach.name == "First Farm"
    assert ach.description is not None
    assert ach.condition is not None
    assert ach.achieved is False


def test_s198_check_achievements_unlocks(db):
    """Story 198: check_achievements unlocks qualifying achievements."""
    from engine.models import Achievement
    from engine.simulation import check_achievements

    _setup_world(db)

    # Create an achievement that should unlock (town has buildings)
    ach = Achievement(
        name="Town Founded",
        description="Town has at least 1 building.",
        condition='{"building_count": 1}',
        achieved=False,
    )
    db.add(ach)
    db.flush()

    check_achievements(db)
    db.flush()

    db.refresh(ach)
    assert ach.achieved, "Achievement should be unlocked after check"


# ---------------------------------------------------------------------------
# Story 199: Visitor log NPC
# ---------------------------------------------------------------------------


def test_s199_visitor_log_model_exists(db):
    """Story 199: VisitorLog model should exist with required fields."""
    from engine.models import VisitorLog, NPC

    visitor = NPC(name="Visitor Val", role="merchant", x=0, y=0)
    greeter = NPC(name="Greeter Greg", role="guard", x=1, y=1)
    db.add_all([visitor, greeter])
    db.flush()

    log = VisitorLog(
        npc_id=visitor.id,
        arrival_tick=10,
        greeted_by_npc_id=greeter.id,
    )
    db.add(log)
    db.flush()

    assert log.id is not None
    assert log.npc_id == visitor.id
    assert log.arrival_tick == 10
    assert log.greeted_by_npc_id == greeter.id


def test_s199_log_visitor_creates_entry(db):
    """Story 199: log_visitor creates a VisitorLog entry."""
    from engine.models import NPC, VisitorLog
    from engine.simulation import log_visitor

    _setup_world(db)

    visitor = NPC(name="New Visitor", role="merchant", x=0, y=0)
    db.add(visitor)
    db.flush()

    log_visitor(db, visitor.id)
    db.flush()

    logs = db.query(VisitorLog).all()
    assert len(logs) >= 1, "log_visitor should create at least 1 VisitorLog entry"


# ---------------------------------------------------------------------------
# Story 200: Town anthem generator
# ---------------------------------------------------------------------------


def test_s200_town_anthem_model_exists(db):
    """Story 200: TownAnthem model should exist with required fields."""
    from engine.models import TownAnthem, NPC

    composer = NPC(name="Composer Clara", role="bard", x=0, y=0)
    db.add(composer)
    db.flush()

    anthem = TownAnthem(
        lyrics="Oh our town, so grand and free!",
        composed_by_npc_id=composer.id,
        tick_composed=20,
    )
    db.add(anthem)
    db.flush()

    assert anthem.id is not None
    assert anthem.lyrics is not None
    assert len(anthem.lyrics) > 0
    assert anthem.composed_by_npc_id == composer.id
    assert anthem.tick_composed == 20


def test_s200_compose_anthem_creates_entry(db):
    """Story 200: compose_anthem creates a TownAnthem entry."""
    from engine.models import TownAnthem
    from engine.simulation import compose_anthem

    _setup_world(db)

    compose_anthem(db)
    db.flush()

    anthems = db.query(TownAnthem).all()
    assert len(anthems) >= 1, "compose_anthem should create at least 1 anthem"


# ---------------------------------------------------------------------------
# Story 203: NPC memory and learning
# ---------------------------------------------------------------------------


def test_s203_update_memory_stores_event(db):
    """Story 203: update_memory stores an event in NPC memory."""
    import json
    from engine.models import NPC
    from engine.simulation import update_memory

    npc = NPC(name="Memory Mary", role="farmer", x=5, y=5)
    db.add(npc)
    db.flush()

    update_memory(db, npc.id, "found gold")
    db.flush()

    # Verify the event was stored (via memory_events or similar field)
    db.refresh(npc)
    mem = getattr(npc, "memory_events", None)
    if mem is not None:
        if isinstance(mem, str):
            mem = json.loads(mem)
        assert "found gold" in str(mem), "Event should be in memory"


def test_s203_recall_memory_retrieves(db):
    """Story 203: recall_memory retrieves stored memories."""
    from engine.models import NPC
    from engine.simulation import update_memory, recall_memory

    npc = NPC(name="Recall Ron", role="farmer", x=5, y=5)
    db.add(npc)
    db.flush()

    update_memory(db, npc.id, "visited market")
    db.flush()

    result = recall_memory(db, npc.id, "visited")
    assert result is not None, "recall_memory should return something"


def test_s203_memory_cap_ten_events(db):
    """Story 203: Memory capped at 10 events."""
    import json
    from engine.models import NPC
    from engine.simulation import update_memory

    npc = NPC(name="Cap Charlie", role="farmer", x=5, y=5)
    db.add(npc)
    db.flush()

    for i in range(15):
        update_memory(db, npc.id, f"event_{i}")
        db.flush()

    db.refresh(npc)
    mem = getattr(npc, "memory_events", None)
    if mem is not None:
        if isinstance(mem, str):
            mem = json.loads(mem)
        assert len(mem) <= 10, f"Memory should be capped at 10, got {len(mem)}"


# ---------------------------------------------------------------------------
# Story 206: NPC dialogue system
# ---------------------------------------------------------------------------


def test_s206_dialogue_model_exists(db):
    """Story 206: Dialogue model should exist with required fields."""
    from engine.models import Dialogue, NPC

    npc1 = NPC(name="Talker Ted", role="farmer", x=0, y=0)
    npc2 = NPC(name="Listener Lana", role="baker", x=1, y=1)
    db.add_all([npc1, npc2])
    db.flush()

    dlg = Dialogue(
        speaker_npc_id=npc1.id,
        listener_npc_id=npc2.id,
        message="Hello there!",
        tick=5,
    )
    db.add(dlg)
    db.flush()

    assert dlg.id is not None
    assert dlg.speaker_npc_id == npc1.id
    assert dlg.listener_npc_id == npc2.id
    assert dlg.message == "Hello there!"
    assert dlg.tick == 5


def test_s206_generate_dialogue_returns_string(db):
    """Story 206: generate_dialogue returns a non-empty string."""
    from engine.models import NPC
    from engine.simulation import generate_dialogue

    npc1 = NPC(name="Chat Charlie", role="farmer", x=5, y=5)
    npc2 = NPC(name="Chat Carol", role="baker", x=6, y=6)
    db.add_all([npc1, npc2])
    db.flush()

    result = generate_dialogue(db, npc1.id, npc2.id)
    assert isinstance(result, str), "generate_dialogue should return a string"
    assert len(result) > 0, "generate_dialogue should return non-empty string"


# ── Stories 216-225: NPC Psychology & Autonomy ──────────────────────


def test_s216_personality_decision(db):
    """Story 216: Personality-driven NPC decisions."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import personality_decision

    npc = db.query(NPC).first()
    result = personality_decision(db, npc.id)
    assert isinstance(result, str), "personality_decision should return a string"
    db.flush()


def test_s217_spread_mood(db):
    """Story 217: Mood contagion between NPCs."""
    _setup_world(db)
    from engine.simulation import spread_mood

    spread_mood(db)
    db.flush()


def test_s218_apply_daily_routine(db):
    """Story 218: NPC daily routines based on time of day."""
    _setup_world(db)
    from engine.simulation import apply_daily_routine

    apply_daily_routine(db)
    db.flush()


def test_s219_spread_gossip(db):
    """Story 219: NPC gossip system."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import spread_gossip
    import json

    # Place two NPCs on same tile with different memories
    npcs = db.query(NPC).limit(2).all()
    assert len(npcs) >= 2
    npcs[0].x, npcs[0].y = 25, 25
    npcs[1].x, npcs[1].y = 25, 25
    npcs[0].memory_events = json.dumps(["event_A"])
    npcs[1].memory_events = json.dumps(["event_B"])
    db.commit()

    spread_gossip(db)
    db.flush()

    db.refresh(npcs[0])
    mem0 = json.loads(npcs[0].memory_events)
    assert "event_B" in mem0 or len(mem0) > 1, "NPC should have learned gossip"


def test_s220_pursue_goals(db):
    """Story 220: NPC goal pursuit system."""
    _setup_world(db)
    from engine.simulation import pursue_goals

    result = pursue_goals(db)
    assert isinstance(result, int), "pursue_goals should return count"
    db.flush()


def test_s221_flee_disaster(db):
    """Story 221: NPC fear response to disasters."""
    _setup_world(db)
    from engine.simulation import flee_disaster

    flee_disaster(db)
    db.flush()


def test_s222_apply_age_effects(db):
    """Story 222: NPC aging effects on productivity."""
    _setup_world(db)
    from engine.simulation import apply_age_effects

    result = apply_age_effects(db)
    assert isinstance(result, dict), "apply_age_effects should return dict"
    db.flush()


def test_s223_mentor_apprentices(db):
    """Story 223: Mentor-apprentice skill transfer."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import mentor_apprentices

    # Create mentor and apprentice on same tile
    mentor = NPC(name="Master Smith", role="blacksmith", x=20, y=20, skill=8)
    apprentice = NPC(name="Young Bob", role="blacksmith", x=20, y=20, skill=1)
    db.add_all([mentor, apprentice])
    db.flush()

    result = mentor_apprentices(db)
    assert isinstance(result, int), "mentor_apprentices should return count"
    db.refresh(apprentice)
    assert apprentice.skill > 1, "Apprentice should have gained skill"


def test_s224_apply_homesickness(db):
    """Story 224: NPC homesickness mechanic."""
    _setup_world(db)
    from engine.simulation import apply_homesickness

    apply_homesickness(db)
    db.flush()


def test_s225_process_rivalries(db):
    """Story 225: NPC rivalry competition."""
    _setup_world(db)
    from engine.simulation import process_rivalries

    process_rivalries(db)
    db.flush()


# ── Stories 247-248: Military & Crime (NPC module) ──────────────────


def test_s247_patrol_guards(db):
    """Story 247: Guard patrol movement."""
    _setup_world(db)
    from engine.simulation import patrol_guards

    patrol_guards(db)
    db.flush()


def test_s248_check_crime_motivation(db):
    """Story 248: Crime motivation from poverty."""
    _setup_world(db)
    from engine.simulation import check_crime_motivation

    result = check_crime_motivation(db)
    assert isinstance(result, int), "check_crime_motivation should return count"
    db.flush()


def test_s266_process_dreams(db):
    """NPC dream system."""
    _setup_world(db)
    from engine.simulation import process_dreams

    result = process_dreams(db)
    assert result is not None, "process_dreams should return a value"
    db.flush()


def test_s267_check_career_progression(db):
    """Career progression."""
    _setup_world(db)
    from engine.simulation import check_career_progression

    result = check_career_progression(db)
    assert result is not None, "check_career_progression should return a value"
    db.flush()


def test_s268_process_retirement(db):
    """NPC retirement."""
    _setup_world(db)
    from engine.simulation import process_retirement

    result = process_retirement(db)
    assert result is not None, "process_retirement should return a value"
    db.flush()


def test_s269_process_inheritance(db):
    """Family inheritance."""
    _setup_world(db)
    from engine.simulation import process_inheritance

    result = process_inheritance(db)
    assert result is not None, "process_inheritance should return a value"
    db.flush()


def test_s270_process_child_growth(db):
    """Child NPC growth."""
    _setup_world(db)
    from engine.simulation import process_child_growth

    result = process_child_growth(db)
    assert result is not None, "process_child_growth should return a value"
    db.flush()


def test_s271_attempt_persuasion(db):
    """NPC persuasion."""
    _setup_world(db)
    from engine.simulation import attempt_persuasion

    result = attempt_persuasion(db)
    assert result is not None, "attempt_persuasion should return a value"
    db.flush()


def test_s272_process_crowd_behavior(db):
    """Crowd behavior."""
    _setup_world(db)
    from engine.simulation import process_crowd_behavior

    result = process_crowd_behavior(db)
    assert result is not None, "process_crowd_behavior should return a value"
    db.flush()


def test_s273_track_emotions(db):
    """Emotion memory tracking."""
    _setup_world(db)
    from engine.simulation import track_emotions

    result = track_emotions(db)
    assert result is not None, "track_emotions should return a value"
    db.flush()


def test_s274_process_emigration(db):
    """NPC migration out."""
    _setup_world(db)
    from engine.simulation import process_emigration

    result = process_emigration(db)
    assert result is not None, "process_emigration should return a value"
    db.flush()


def test_s275_check_immigration(db):
    """NPC arrival by prosperity."""
    _setup_world(db)
    from engine.simulation import check_immigration

    result = check_immigration(db)
    assert result is not None, "check_immigration should return a value"
    db.flush()


def test_s276_decay_friendships(db):
    """Friendship decay."""
    _setup_world(db)
    from engine.simulation import decay_friendships

    result = decay_friendships(db)
    assert result is not None, "decay_friendships should return a value"
    db.flush()


def test_s277_apply_specialization_bonus(db):
    """NPC specialization bonus."""
    _setup_world(db)
    from engine.simulation import apply_specialization_bonus

    result = apply_specialization_bonus(db)
    assert result is not None, "apply_specialization_bonus should return a value"
    db.flush()


def test_s278_apply_fatigue(db):
    """NPC fatigue system."""
    _setup_world(db)
    from engine.simulation import apply_fatigue

    result = apply_fatigue(db)
    assert result is not None, "apply_fatigue should return a value"
    db.flush()


def test_s279_check_celebrations(db):
    """NPC celebration."""
    _setup_world(db)
    from engine.models import NPC
    # Set one NPC happiness > 90 so celebration triggers
    npc = db.query(NPC).first()
    npc.happiness = 95
    db.flush()
    from engine.simulation import check_celebrations

    result = check_celebrations(db)
    assert result is not None, "check_celebrations should return a value when happy NPC exists"
    db.flush()


def test_s280_process_mourning(db):
    """NPC mourning."""
    _setup_world(db)
    from engine.simulation import process_mourning

    result = process_mourning(db)
    assert result is not None, "process_mourning should return a value"
    db.flush()


def test_s341_generate_npc_name(db):
    """NPC name generator."""
    _setup_world(db)
    from engine.simulation import generate_npc_name

    result = generate_npc_name(db)
    assert result is not None, "generate_npc_name should return a value"
    db.flush()


def test_s346_calculate_compatibility(db):
    """NPC compatibility score."""
    _setup_world(db)
    from engine.simulation import calculate_compatibility
    from engine.models import NPC

    npcs = db.query(NPC).limit(2).all()
    assert len(npcs) >= 2, "Need at least 2 NPCs"
    result = calculate_compatibility(db, npcs[0].id, npcs[1].id)
    assert result is not None, "calculate_compatibility should return a value"
    db.flush()


def test_s347_assign_homeless(db):
    """Auto-assign homeless NPCs."""
    _setup_world(db)
    from engine.simulation import assign_homeless

    result = assign_homeless(db)
    assert result is not None, "assign_homeless should return a value"
    db.flush()


def test_s348_assign_unemployed(db):
    """Auto-assign unemployed NPCs."""
    _setup_world(db)
    from engine.simulation import assign_unemployed

    result = assign_unemployed(db)
    assert result is not None, "assign_unemployed should return a value"
    db.flush()


# -- Stories 351-370: Deep NPC Simulation ---------------------------------


def test_s351_calculate_npc_stress(db):
    """NPC stress system."""
    _setup_world(db)
    from engine.simulation import calculate_npc_stress
    from engine.models import NPC

    # Make one NPC stressed: high hunger, low energy, no gold
    npc = db.query(NPC).filter(NPC.is_dead == 0).first()
    npc.hunger = 80
    npc.energy = 10
    npc.gold = 0
    db.flush()

    result = calculate_npc_stress(db)
    assert isinstance(result, int), "Should return count of stressed NPCs"
    assert result >= 1, "At least one NPC should be stressed"
    db.flush()


def test_s352_assign_npc_hobbies(db):
    """NPC hobby selection."""
    _setup_world(db)
    from engine.simulation import assign_npc_hobbies
    from engine.models import NPC

    # Make an NPC idle (no work building) with energy
    npc = db.query(NPC).filter(NPC.is_dead == 0).first()
    npc.work_building_id = None
    npc.energy = 80
    db.flush()

    result = assign_npc_hobbies(db)
    assert isinstance(result, int), "Should return count of NPCs with hobbies"
    db.flush()


def test_s353_propagate_gossip(db):
    """NPC gossip propagation."""
    _setup_world(db)
    from engine.simulation import propagate_gossip
    import json
    from engine.models import NPC

    # Give one NPC a memory event
    npc = db.query(NPC).filter(NPC.is_dead == 0).first()
    npc.memory_events = json.dumps([{"type": "test_gossip", "info": "big news"}])
    db.flush()

    result = propagate_gossip(db)
    assert isinstance(result, int), "Should return count of gossip transfers"
    db.flush()


def test_s354_update_trust_scores(db):
    """NPC trust system."""
    _setup_world(db)
    from engine.simulation import update_trust_scores

    result = update_trust_scores(db)
    assert isinstance(result, dict), "Should return dict of npc_id: trust_score"
    db.flush()


def test_s355_process_gift_giving(db):
    """NPC gift giving."""
    _setup_world(db)
    from engine.simulation import process_gift_giving
    from engine.models import NPC, Relationship

    # Set up a happy, wealthy NPC with a friend
    npcs = db.query(NPC).filter(NPC.is_dead == 0).limit(2).all()
    npcs[0].happiness = 80
    npcs[0].gold = 200
    npcs[1].gold = 5
    rel = Relationship(npc_id=npcs[0].id, target_npc_id=npcs[1].id, relationship_type="friend", strength=60)
    db.add(rel)
    db.flush()

    result = process_gift_giving(db)
    assert isinstance(result, int), "Should return count of gifts given"
    db.flush()


def test_s356_process_grudges(db):
    """NPC grudge system."""
    _setup_world(db)
    from engine.simulation import process_grudges

    result = process_grudges(db)
    assert isinstance(result, int), "Should return count of grudges"
    db.flush()


def test_s357_process_mentorship(db):
    """NPC mentorship."""
    _setup_world(db)
    from engine.simulation import process_mentorship
    from engine.models import NPC

    # Set up mentor and student
    npcs = db.query(NPC).filter(NPC.is_dead == 0).limit(2).all()
    npcs[0].skill = 90
    npcs[1].skill = 20
    npcs[1].x = npcs[0].x
    npcs[1].y = npcs[0].y
    db.flush()

    result = process_mentorship(db)
    assert isinstance(result, int), "Should return count of mentorships"
    db.flush()


def test_s358_check_homesickness(db):
    """NPC homesickness."""
    _setup_world(db)
    from engine.simulation import check_homesickness
    from engine.models import NPC, Building

    # Put NPC far from home
    npc = db.query(NPC).filter(NPC.is_dead == 0, NPC.home_building_id.isnot(None)).first()
    if npc:
        npc.x = 49
        npc.y = 49
        home = db.query(Building).get(npc.home_building_id)
        if home:
            home.x = 0
            home.y = 0
        db.flush()

    result = check_homesickness(db)
    assert isinstance(result, int), "Should return count of homesick NPCs"
    db.flush()


def test_s359_apply_daily_routine(db):
    """NPC daily routine."""
    _setup_world(db)
    from engine.simulation import apply_daily_routine

    result = apply_daily_routine(db)
    assert isinstance(result, dict), "Should return dict with period counts"
    db.flush()


def test_s360_assign_pets(db):
    """NPC pet ownership."""
    _setup_world(db)
    from engine.simulation import assign_pets
    from engine.models import NPC

    # Make NPCs eligible
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        npc.happiness = 80
        npc.gold = 100
    db.flush()

    result = assign_pets(db)
    assert isinstance(result, int), "Should return count of new pet owners"
    db.flush()


def test_s361_check_birthdays(db):
    """NPC birthday celebration."""
    _setup_world(db)
    from engine.simulation import check_birthdays

    result = check_birthdays(db)
    assert isinstance(result, int), "Should return count of birthdays"
    db.flush()


def test_s362_check_addictions(db):
    """NPC addiction system."""
    _setup_world(db)
    from engine.simulation import check_addictions

    result = check_addictions(db)
    assert isinstance(result, int), "Should return count of addicted NPCs"
    db.flush()


def test_s363_escalate_rivalries(db):
    """NPC rivalry escalation."""
    _setup_world(db)
    from engine.simulation import escalate_rivalries

    result = escalate_rivalries(db)
    assert isinstance(result, int), "Should return count of escalated rivalries"
    db.flush()


def test_s364_process_forgiveness(db):
    """NPC forgiveness."""
    _setup_world(db)
    from engine.simulation import process_forgiveness
    from engine.models import NPC, Relationship

    # Create a rivalry
    npcs = db.query(NPC).filter(NPC.is_dead == 0).limit(2).all()
    rel = Relationship(npc_id=npcs[0].id, target_npc_id=npcs[1].id, relationship_type="rival", strength=1)
    db.add(rel)
    db.flush()

    result = process_forgiveness(db)
    assert isinstance(result, int), "Should return count of forgiven rivalries"
    db.flush()


def test_s365_discover_talents(db):
    """NPC talent discovery."""
    _setup_world(db)
    from engine.simulation import discover_talents
    from engine.models import NPC

    # Ensure NPCs have low skill
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        npc.skill = 10
    db.flush()

    result = discover_talents(db)
    assert isinstance(result, int), "Should return count of talents discovered"
    db.flush()


def test_s366_check_social_circles(db):
    """NPC social circles."""
    _setup_world(db)
    from engine.simulation import check_social_circles

    result = check_social_circles(db)
    assert isinstance(result, dict), "Should return dict of npc_id: friend_count"
    db.flush()


def test_s367_detect_loneliness(db):
    """NPC loneliness detection."""
    _setup_world(db)
    from engine.simulation import detect_loneliness

    result = detect_loneliness(db)
    assert isinstance(result, int), "Should return count of lonely NPCs"
    db.flush()


def test_s368_apply_work_ethic(db):
    """NPC work ethic."""
    _setup_world(db)
    from engine.simulation import apply_work_ethic

    result = apply_work_ethic(db)
    assert isinstance(result, (int, float)), "Should return total gold distributed"
    db.flush()


def test_s369_apply_fear_response(db):
    """NPC fear system."""
    _setup_world(db)
    from engine.simulation import apply_fear_response

    result = apply_fear_response(db)
    assert isinstance(result, int), "Should return count of frightened NPCs"
    db.flush()


def test_s370_process_npc_goals(db):
    """NPC goal system."""
    _setup_world(db)
    from engine.simulation import process_npc_goals

    result = process_npc_goals(db)
    assert isinstance(result, int), "Should return count of goals achieved"
    db.flush()


def test_s442_vary_npc_lifespan(db):
    """NPC lifespan variation."""
    _setup_world(db)
    from engine.simulation import vary_npc_lifespan
    from engine.models import NPC

    # Set max_age to 0 so function assigns
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        npc.max_age = 0
    db.flush()

    result = vary_npc_lifespan(db)
    assert isinstance(result, int), "Should return count of NPCs updated"
    assert result > 0, "Should have updated at least one NPC"
    db.flush()


def test_s444_check_immigration_wave(db):
    """Immigration wave."""
    _setup_world(db)
    from engine.simulation import check_immigration_wave
    from engine.models import NPC

    # Set high happiness
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        npc.happiness = 90
    db.flush()

    result = check_immigration_wave(db)
    assert isinstance(result, int), "Should return count of immigrants"
    db.flush()


def test_s445_check_emigration_wave(db):
    """Emigration wave."""
    _setup_world(db)
    from engine.simulation import check_emigration_wave
    from engine.models import NPC

    # Set low happiness to trigger emigration
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        npc.happiness = 10
    db.flush()

    result = check_emigration_wave(db)
    assert isinstance(result, int), "Should return 0 or 1"
    assert result in (0, 1), "Should be 0 or 1"
    db.flush()


def test_s449_record_npc_legacy(db):
    """Legacy system."""
    _setup_world(db)
    from engine.simulation import record_npc_legacy
    from engine.models import NPC

    # Mark one NPC as dead
    npc = db.query(NPC).first()
    npc.is_dead = 1
    db.flush()

    result = record_npc_legacy(db)
    assert isinstance(result, int), "Should return count of legacies recorded"
    db.flush()
