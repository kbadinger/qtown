"""Tests for building stories: 002, 004, 008-009, 031, 046-070, 209-210."""


def test_s002_building_model_exists(db):
    """Story 002: Building model should exist with required fields."""
    from engine.models import Building

    b = Building(name="Town Hall", building_type="civic", x=25, y=25)
    db.add(b)
    db.commit()
    assert b.id is not None
    assert b.name == "Town Hall"
    assert b.building_type == "civic"
    assert b.x == 25
    assert b.y == 25


def test_s004_seed_buildings(db):
    """Story 004: seed_buildings() should create starter buildings."""
    from engine.simulation import init_grid, seed_buildings

    init_grid(db)
    seed_buildings(db)
    from engine.models import Building

    count = db.query(Building).count()
    assert count >= 3, f"Expected at least 3 seed buildings, got {count}"


def test_s004_seed_buildings_on_valid_tiles(db):
    """Story 004: Seeded buildings must be on valid grid coordinates."""
    from engine.simulation import init_grid, seed_buildings

    init_grid(db)
    seed_buildings(db)
    from engine.models import Building

    for b in db.query(Building).all():
        assert 0 <= b.x < 50, f"Building {b.name} x={b.x} out of range"
        assert 0 <= b.y < 50, f"Building {b.name} y={b.y} out of range"


def test_s008_get_buildings_api(client, admin_headers):
    """Story 008: GET /api/buildings returns list of buildings."""
    resp = client.get("/api/buildings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_s009_create_building_api(client, admin_headers):
    """Story 009: POST /api/buildings creates a building (admin only)."""
    resp = client.post(
        "/api/buildings",
        json={"name": "Bakery", "building_type": "food", "x": 10, "y": 10},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "Bakery"


def test_s009_create_building_requires_admin(client):
    """Story 009: POST /api/buildings without admin key returns 401/422."""
    resp = client.post(
        "/api/buildings",
        json={"name": "Bakery", "building_type": "food", "x": 10, "y": 10},
    )
    assert resp.status_code in (401, 422)


def test_s031_build_building_via_simulation(db):
    """Story 031: build_building() should deduct resources and create building."""
    from engine.simulation import init_grid, build_building

    init_grid(db)
    result = build_building(db, name="Market", building_type="commerce", x=15, y=15)
    assert result is not None
    from engine.models import Building

    assert db.query(Building).filter_by(name="Market").first() is not None


def test_s046_bakery_in_building_types():
    """Story 046: 'bakery' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES

    assert "bakery" in BUILDING_TYPES


def test_s046_seed_bakery(db):
    """Story 046: seed_bakery() should create exactly one bakery building."""
    from engine.simulation import init_grid, seed_bakery

    init_grid(db)
    seed_bakery(db)
    from engine.models import Building

    bakeries = db.query(Building).filter_by(building_type="bakery").all()
    assert len(bakeries) == 1
    assert bakeries[0].name == "Bakery"

    # Idempotent — calling again should not duplicate
    seed_bakery(db)
    assert db.query(Building).filter_by(building_type="bakery").count() == 1


def test_s046_bakery_production(db):
    """Story 046: Bakery converts Wheat into Bread (5 per tick if Wheat available)."""
    from engine.simulation import init_grid, seed_bakery, produce_bakery_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_bakery(db)

    bakery = db.query(Building).filter_by(building_type="bakery").first()

    # Add Wheat resource to bakery
    wheat = Resource(name="Wheat", quantity=3, building_id=bakery.id)
    db.add(wheat)
    db.commit()

    # Run production — should consume 1 Wheat, produce 5 Bread
    produce_bakery_resources(db)
    db.flush()

    wheat = db.query(Resource).filter_by(name="Wheat", building_id=bakery.id).first()
    bread = db.query(Resource).filter_by(name="Bread", building_id=bakery.id).first()
    assert wheat.quantity == 2
    assert bread is not None
    assert bread.quantity == 5

    # No Wheat → no Bread produced
    wheat.quantity = 0
    db.flush()
    produce_bakery_resources(db)
    db.flush()
    bread = db.query(Resource).filter_by(name="Bread", building_id=bakery.id).first()
    assert bread.quantity == 5  # unchanged


# --- Story 047: Blacksmith ---

def test_s047_blacksmith_in_building_types():
    """Story 047: 'blacksmith' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "blacksmith" in BUILDING_TYPES


def test_s047_seed_blacksmith(db):
    """Story 047: seed_blacksmith() should create exactly one blacksmith building."""
    from engine.simulation import init_grid, seed_blacksmith
    from engine.models import Building

    init_grid(db)
    seed_blacksmith(db)
    smiths = db.query(Building).filter_by(building_type="blacksmith").all()
    assert len(smiths) == 1

    seed_blacksmith(db)
    assert db.query(Building).filter_by(building_type="blacksmith").count() == 1


def test_s047_blacksmith_production(db):
    """Story 047: Blacksmith converts Ore into Tools (3 per tick if Ore available)."""
    from engine.simulation import init_grid, seed_blacksmith, produce_blacksmith_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_blacksmith(db)
    smithy = db.query(Building).filter_by(building_type="blacksmith").first()

    ore = Resource(name="Ore", quantity=5, building_id=smithy.id)
    db.add(ore)
    db.commit()

    produce_blacksmith_resources(db)
    db.flush()

    ore = db.query(Resource).filter_by(name="Ore", building_id=smithy.id).first()
    tools = db.query(Resource).filter_by(name="Tools", building_id=smithy.id).first()
    assert ore.quantity == 4
    assert tools is not None
    assert tools.quantity == 3


# --- Story 048: Farm ---

def test_s048_farm_in_building_types():
    """Story 048: 'farm' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "farm" in BUILDING_TYPES


def test_s048_seed_farm(db):
    """Story 048: seed_farm() should create exactly one farm building."""
    from engine.simulation import init_grid, seed_farm
    from engine.models import Building

    init_grid(db)
    seed_farm(db)
    farms = db.query(Building).filter_by(building_type="farm").all()
    assert len(farms) == 1

    seed_farm(db)
    assert db.query(Building).filter_by(building_type="farm").count() == 1


def test_s048_farm_production(db):
    """Story 048: Farm produces Wheat and Food (10 each per tick)."""
    from engine.simulation import init_grid, seed_farm, produce_farm_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_farm(db)
    farm = db.query(Building).filter_by(building_type="farm").first()

    produce_farm_resources(db)
    db.flush()

    wheat = db.query(Resource).filter_by(name="Wheat", building_id=farm.id).first()
    food = db.query(Resource).filter_by(name="Food", building_id=farm.id).first()
    assert wheat is not None and wheat.quantity == 10
    assert food is not None and food.quantity == 10


# --- Story 049: Church ---

def test_s049_church_in_building_types():
    """Story 049: 'church' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "church" in BUILDING_TYPES


def test_s049_seed_church(db):
    """Story 049: seed_church() should create exactly one church building."""
    from engine.simulation import init_grid, seed_church
    from engine.models import Building

    init_grid(db)
    seed_church(db)
    churches = db.query(Building).filter_by(building_type="church").all()
    assert len(churches) == 1

    seed_church(db)
    assert db.query(Building).filter_by(building_type="church").count() == 1


def test_s049_church_happiness_effect(db):
    """Story 049: Church increases happiness of nearby NPCs by 5 within radius 10."""
    from engine.simulation import init_grid, seed_church, apply_church_effects
    from engine.models import Building, NPC

    init_grid(db)
    seed_church(db)
    church = db.query(Building).filter_by(building_type="church").first()

    # Place NPC near church (within radius 10)
    npc = NPC(name="Test", role="priest", x=church.x + 3, y=church.y + 3, happiness=50)
    db.add(npc)
    db.commit()

    apply_church_effects(db)
    db.refresh(npc)
    assert npc.happiness == 55


# --- Story 050: School ---

def test_s050_school_in_building_types():
    """Story 050: 'school' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "school" in BUILDING_TYPES


def test_s050_seed_school(db):
    """Story 050: seed_school() should create exactly one school building."""
    from engine.simulation import init_grid, seed_school
    from engine.models import Building

    init_grid(db)
    seed_school(db)
    schools = db.query(Building).filter_by(building_type="school").all()
    assert len(schools) == 1

    seed_school(db)
    assert db.query(Building).filter_by(building_type="school").count() == 1


# --- Story 051: Hospital ---

def test_s051_hospital_in_building_types():
    """Story 051: 'hospital' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "hospital" in BUILDING_TYPES


def test_s051_seed_hospital(db):
    """Story 051: seed_hospital() should create exactly one hospital building."""
    from engine.simulation import init_grid, seed_hospital
    from engine.models import Building

    init_grid(db)
    seed_hospital(db)
    hospitals = db.query(Building).filter_by(building_type="hospital").all()
    assert len(hospitals) == 1

    seed_hospital(db)
    assert db.query(Building).filter_by(building_type="hospital").count() == 1


# --- Story 052: Tavern ---

def test_s052_tavern_in_building_types():
    """Story 052: 'tavern' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "tavern" in BUILDING_TYPES


def test_s052_seed_tavern(db):
    """Story 052: seed_tavern() should create exactly one tavern building."""
    from engine.simulation import init_grid, seed_tavern
    from engine.models import Building

    init_grid(db)
    seed_tavern(db)
    taverns = db.query(Building).filter_by(building_type="tavern").all()
    assert len(taverns) == 1

    seed_tavern(db)
    assert db.query(Building).filter_by(building_type="tavern").count() == 1


def test_s052_tavern_effects(db):
    """Story 052: Tavern restores energy +20 and happiness +10 for gold."""
    from engine.simulation import init_grid, seed_tavern, visit_tavern
    from engine.models import Building, NPC

    init_grid(db)
    seed_tavern(db)

    npc = NPC(name="Test", role="farmer", x=0, y=0, gold=20, energy=50, happiness=40)
    db.add(npc)
    db.commit()

    result = visit_tavern(db, npc.id)
    assert result is True
    db.refresh(npc)
    assert npc.energy == 70
    assert npc.happiness == 50


# --- Story 053: Library ---

def test_s053_library_in_building_types():
    """Story 053: 'library' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "library" in BUILDING_TYPES


def test_s053_seed_library(db):
    """Story 053: seed_library() should create exactly one library building."""
    from engine.simulation import init_grid, seed_library
    from engine.models import Building

    init_grid(db)
    seed_library(db)
    libs = db.query(Building).filter_by(building_type="library").all()
    assert len(libs) == 1

    seed_library(db)
    assert db.query(Building).filter_by(building_type="library").count() == 1


def test_s053_library_production(db):
    """Story 053: Library produces 2 Books per tick."""
    from engine.simulation import init_grid, seed_library, produce_library_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_library(db)
    library = db.query(Building).filter_by(building_type="library").first()

    produce_library_resources(db)
    db.flush()

    books = db.query(Resource).filter_by(name="Books", building_id=library.id).first()
    assert books is not None and books.quantity == 2


# --- Story 054: Mine ---

def test_s054_mine_in_building_types():
    """Story 054: 'mine' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "mine" in BUILDING_TYPES


def test_s054_seed_mine(db):
    """Story 054: seed_mine() should create exactly one mine building."""
    from engine.simulation import init_grid, seed_mine
    from engine.models import Building

    init_grid(db)
    seed_mine(db)
    mines = db.query(Building).filter_by(building_type="mine").all()
    assert len(mines) == 1

    seed_mine(db)
    assert db.query(Building).filter_by(building_type="mine").count() == 1


def test_s054_mine_production(db):
    """Story 054: Mine produces 8 Ore per tick."""
    from engine.simulation import init_grid, seed_mine, produce_mine_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_mine(db)
    mine = db.query(Building).filter_by(building_type="mine").first()

    produce_mine_resources(db)
    db.flush()

    ore = db.query(Resource).filter_by(name="Ore", building_id=mine.id).first()
    assert ore is not None and ore.quantity == 8


# --- Story 055: Lumber Mill ---

def test_s055_lumber_mill_in_building_types():
    """Story 055: 'lumber_mill' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "lumber_mill" in BUILDING_TYPES


def test_s055_seed_lumber_mill(db):
    """Story 055: seed_lumber_mill() should create exactly one lumber_mill building."""
    from engine.simulation import init_grid, seed_lumber_mill
    from engine.models import Building

    init_grid(db)
    seed_lumber_mill(db)
    mills = db.query(Building).filter_by(building_type="lumber_mill").all()
    assert len(mills) == 1

    seed_lumber_mill(db)
    assert db.query(Building).filter_by(building_type="lumber_mill").count() == 1


def test_s055_lumber_mill_production(db):
    """Story 055: Lumber mill produces 8 Wood per tick."""
    from engine.simulation import init_grid, seed_lumber_mill, produce_lumber_mill_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_lumber_mill(db)
    mill = db.query(Building).filter_by(building_type="lumber_mill").first()

    produce_lumber_mill_resources(db)
    db.flush()

    wood = db.query(Resource).filter_by(name="Wood", building_id=mill.id).first()
    assert wood is not None and wood.quantity == 8


# --- Story 056: Fishing Dock ---

def test_s056_fishing_dock_in_building_types():
    """Story 056: 'fishing_dock' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "fishing_dock" in BUILDING_TYPES


def test_s056_seed_fishing_dock(db):
    """Story 056: seed_fishing_dock() should create exactly one fishing_dock building."""
    from engine.simulation import init_grid, seed_fishing_dock
    from engine.models import Building

    init_grid(db)
    seed_fishing_dock(db)
    docks = db.query(Building).filter_by(building_type="fishing_dock").all()
    assert len(docks) == 1

    seed_fishing_dock(db)
    assert db.query(Building).filter_by(building_type="fishing_dock").count() == 1


def test_s056_fishing_dock_production(db):
    """Story 056: Fishing dock produces 6 Fish per tick."""
    from engine.simulation import init_grid, seed_fishing_dock, produce_fishing_dock_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_fishing_dock(db)
    dock = db.query(Building).filter_by(building_type="fishing_dock").first()

    produce_fishing_dock_resources(db)
    db.flush()

    fish = db.query(Resource).filter_by(name="Fish", building_id=dock.id).first()
    assert fish is not None and fish.quantity == 6


# --- Story 057: Guard Tower ---

def test_s057_guard_tower_in_building_types():
    """Story 057: 'guard_tower' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "guard_tower" in BUILDING_TYPES


def test_s057_seed_guard_tower(db):
    """Story 057: seed_guard_tower() should create exactly one guard_tower building."""
    from engine.simulation import init_grid, seed_guard_tower
    from engine.models import Building

    init_grid(db)
    seed_guard_tower(db)
    towers = db.query(Building).filter_by(building_type="guard_tower").all()
    assert len(towers) == 1

    seed_guard_tower(db)
    assert db.query(Building).filter_by(building_type="guard_tower").count() == 1


# --- Story 058: Wall ---

def test_s058_wall_in_building_types():
    """Story 058: 'wall' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "wall" in BUILDING_TYPES


def test_s058_seed_wall(db):
    """Story 058: seed_wall() should create exactly one wall building."""
    from engine.simulation import init_grid, seed_wall
    from engine.models import Building

    init_grid(db)
    seed_wall(db)
    walls = db.query(Building).filter_by(building_type="wall").all()
    assert len(walls) == 1

    seed_wall(db)
    assert db.query(Building).filter_by(building_type="wall").count() == 1


# --- Story 059: Gate ---

def test_s059_gate_in_building_types():
    """Story 059: 'gate' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "gate" in BUILDING_TYPES


def test_s059_seed_gate(db):
    """Story 059: seed_gate() should create exactly one gate building."""
    from engine.simulation import init_grid, seed_gate
    from engine.models import Building

    init_grid(db)
    seed_gate(db)
    gates = db.query(Building).filter_by(building_type="gate").all()
    assert len(gates) == 1

    seed_gate(db)
    assert db.query(Building).filter_by(building_type="gate").count() == 1


# --- Story 060: Fountain ---

def test_s060_fountain_in_building_types():
    """Story 060: 'fountain' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "fountain" in BUILDING_TYPES


def test_s060_seed_fountain(db):
    """Story 060: seed_fountain() should create exactly one fountain building."""
    from engine.simulation import init_grid, seed_fountain
    from engine.models import Building

    init_grid(db)
    seed_fountain(db)
    fountains = db.query(Building).filter_by(building_type="fountain").all()
    assert len(fountains) == 1

    seed_fountain(db)
    assert db.query(Building).filter_by(building_type="fountain").count() == 1


def test_s060_fountain_happiness_effect(db):
    """Story 060: Fountain increases happiness of NPCs within radius 8 by 3."""
    from engine.simulation import init_grid, seed_fountain, apply_fountain_effects
    from engine.models import Building, NPC

    init_grid(db)
    seed_fountain(db)
    fountain = db.query(Building).filter_by(building_type="fountain").first()

    npc = NPC(name="Test", role="farmer", x=fountain.x + 2, y=fountain.y + 2, happiness=50)
    db.add(npc)
    db.commit()

    apply_fountain_effects(db)
    db.refresh(npc)
    assert npc.happiness == 53


# --- Story 061: Well ---

def test_s061_well_in_building_types():
    """Story 061: 'well' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "well" in BUILDING_TYPES


def test_s061_seed_well(db):
    """Story 061: seed_well() should create exactly one well building."""
    from engine.simulation import init_grid, seed_well
    from engine.models import Building

    init_grid(db)
    seed_well(db)
    wells = db.query(Building).filter_by(building_type="well").all()
    assert len(wells) == 1

    seed_well(db)
    assert db.query(Building).filter_by(building_type="well").count() == 1


def test_s061_well_production(db):
    """Story 061: Well produces 20 Water per tick."""
    from engine.simulation import init_grid, seed_well, produce_well_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_well(db)
    well = db.query(Building).filter_by(building_type="well").first()

    produce_well_resources(db)
    db.flush()

    water = db.query(Resource).filter_by(name="Water", building_id=well.id).first()
    assert water is not None and water.quantity == 20


# --- Story 062: Warehouse ---

def test_s062_warehouse_in_building_types():
    """Story 062: 'warehouse' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "warehouse" in BUILDING_TYPES


def test_s062_seed_warehouse(db):
    """Story 062: seed_warehouse() should create exactly one warehouse building."""
    from engine.simulation import init_grid, seed_warehouse
    from engine.models import Building

    init_grid(db)
    seed_warehouse(db)
    warehouses = db.query(Building).filter_by(building_type="warehouse").all()
    assert len(warehouses) == 1

    seed_warehouse(db)
    assert db.query(Building).filter_by(building_type="warehouse").count() == 1


# --- Story 063: Bank ---

def test_s063_bank_in_building_types():
    """Story 063: 'bank' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "bank" in BUILDING_TYPES


def test_s063_seed_bank(db):
    """Story 063: seed_bank() should create exactly one bank building."""
    from engine.simulation import init_grid, seed_bank
    from engine.models import Building

    init_grid(db)
    seed_bank(db)
    banks = db.query(Building).filter_by(building_type="bank").all()
    assert len(banks) == 1

    seed_bank(db)
    assert db.query(Building).filter_by(building_type="bank").count() == 1


# --- Story 064: Theater ---

def test_s064_theater_in_building_types():
    """Story 064: 'theater' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "theater" in BUILDING_TYPES


def test_s064_seed_theater(db):
    """Story 064: seed_theater() should create exactly one theater building."""
    from engine.simulation import init_grid, seed_theater
    from engine.models import Building

    init_grid(db)
    seed_theater(db)
    theaters = db.query(Building).filter_by(building_type="theater").all()
    assert len(theaters) == 1

    seed_theater(db)
    assert db.query(Building).filter_by(building_type="theater").count() == 1


def test_s064_theater_production(db):
    """Story 064: Theater produces 2 Art per tick."""
    from engine.simulation import init_grid, seed_theater, produce_theater_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_theater(db)
    theater = db.query(Building).filter_by(building_type="theater").first()

    produce_theater_resources(db)
    db.flush()

    art = db.query(Resource).filter_by(name="Art", building_id=theater.id).first()
    assert art is not None and art.quantity == 2


# --- Story 065: Arena ---

def test_s065_arena_in_building_types():
    """Story 065: 'arena' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "arena" in BUILDING_TYPES


def test_s065_seed_arena(db):
    """Story 065: seed_arena() should create exactly one arena building."""
    from engine.simulation import init_grid, seed_arena
    from engine.models import Building

    init_grid(db)
    seed_arena(db)
    arenas = db.query(Building).filter_by(building_type="arena").all()
    assert len(arenas) == 1

    seed_arena(db)
    assert db.query(Building).filter_by(building_type="arena").count() == 1


# --- Story 066: Prison ---

def test_s066_prison_in_building_types():
    """Story 066: 'prison' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "prison" in BUILDING_TYPES


def test_s066_seed_prison(db):
    """Story 066: seed_prison() should create exactly one prison building."""
    from engine.simulation import init_grid, seed_prison
    from engine.models import Building

    init_grid(db)
    seed_prison(db)
    prisons = db.query(Building).filter_by(building_type="prison").all()
    assert len(prisons) == 1

    seed_prison(db)
    assert db.query(Building).filter_by(building_type="prison").count() == 1


# --- Story 067: Graveyard ---

def test_s067_graveyard_in_building_types():
    """Story 067: 'graveyard' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "graveyard" in BUILDING_TYPES


def test_s067_seed_graveyard(db):
    """Story 067: seed_graveyard() should create exactly one graveyard building."""
    from engine.simulation import init_grid, seed_graveyard
    from engine.models import Building

    init_grid(db)
    seed_graveyard(db)
    graveyards = db.query(Building).filter_by(building_type="graveyard").all()
    assert len(graveyards) == 1

    seed_graveyard(db)
    assert db.query(Building).filter_by(building_type="graveyard").count() == 1


# --- Story 068: Garden ---

def test_s068_garden_in_building_types():
    """Story 068: 'garden' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "garden" in BUILDING_TYPES


def test_s068_seed_garden(db):
    """Story 068: seed_garden() should create exactly one garden building."""
    from engine.simulation import init_grid, seed_garden
    from engine.models import Building

    init_grid(db)
    seed_garden(db)
    gardens = db.query(Building).filter_by(building_type="garden").all()
    assert len(gardens) == 1

    seed_garden(db)
    assert db.query(Building).filter_by(building_type="garden").count() == 1


def test_s068_garden_production(db):
    """Story 068: Garden produces 4 Herbs per tick."""
    from engine.simulation import init_grid, seed_garden, produce_garden_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_garden(db)
    garden = db.query(Building).filter_by(building_type="garden").first()

    produce_garden_resources(db)
    db.flush()

    herbs = db.query(Resource).filter_by(name="Herbs", building_id=garden.id).first()
    assert herbs is not None and herbs.quantity == 4


# --- Story 069: Windmill ---

def test_s069_windmill_in_building_types():
    """Story 069: 'windmill' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "windmill" in BUILDING_TYPES


def test_s069_seed_windmill(db):
    """Story 069: seed_windmill() should create exactly one windmill building."""
    from engine.simulation import init_grid, seed_windmill
    from engine.models import Building

    init_grid(db)
    seed_windmill(db)
    windmills = db.query(Building).filter_by(building_type="windmill").all()
    assert len(windmills) == 1

    seed_windmill(db)
    assert db.query(Building).filter_by(building_type="windmill").count() == 1


def test_s069_windmill_production(db):
    """Story 069: Windmill converts Wheat to Flour (8 per tick if Wheat available)."""
    from engine.simulation import init_grid, seed_windmill, produce_windmill_resources
    from engine.models import Building, Resource

    init_grid(db)
    seed_windmill(db)
    windmill = db.query(Building).filter_by(building_type="windmill").first()

    wheat = Resource(name="Wheat", quantity=5, building_id=windmill.id)
    db.add(wheat)
    db.commit()

    produce_windmill_resources(db)
    db.flush()

    wheat = db.query(Resource).filter_by(name="Wheat", building_id=windmill.id).first()
    flour = db.query(Resource).filter_by(name="Flour", building_id=windmill.id).first()
    assert wheat.quantity == 4
    assert flour is not None and flour.quantity == 8


# --- Story 070: Watchtower ---

def test_s070_watchtower_in_building_types():
    """Story 070: 'watchtower' should be in BUILDING_TYPES."""
    from engine.simulation import BUILDING_TYPES
    assert "watchtower" in BUILDING_TYPES


def test_s070_seed_watchtower(db):
    """Story 070: seed_watchtower() should create exactly one watchtower building."""
    from engine.simulation import init_grid, seed_watchtower
    from engine.models import Building

    init_grid(db)
    seed_watchtower(db)
    towers = db.query(Building).filter_by(building_type="watchtower").all()
    assert len(towers) == 1

    seed_watchtower(db)
    assert db.query(Building).filter_by(building_type="watchtower").count() == 1


# ---------------------------------------------------------------------------
# Story 209: Building level and upgrade system
# ---------------------------------------------------------------------------


def test_s209_building_has_level_field(db):
    """Story 209: Building should have a level field defaulting to 1."""
    from engine.models import Building

    b = Building(name="Farm", building_type="farm", x=0, y=0)
    db.add(b)
    db.flush()

    assert hasattr(b, "level"), "Building must have a 'level' field"
    assert b.level == 1, f"Building level should default to 1, got {b.level}"


def test_s209_upgrade_building_increases_level(db):
    """Story 209: upgrade_building() increases building level by 1."""
    from engine.models import Building
    from engine.simulation import upgrade_building

    b = Building(name="Farm", building_type="farm", x=0, y=0)
    db.add(b)
    db.flush()

    level_before = b.level
    upgrade_building(db, b.id)
    db.flush()
    db.refresh(b)

    assert b.level == level_before + 1, (
        f"upgrade_building should increase level by 1: was {level_before}, "
        f"now {b.level}"
    )


def test_s209_upgrade_building_api(client, admin_headers):
    """Story 209: POST /api/buildings/{id}/upgrade with admin auth works."""
    # Create a building first
    resp = client.post(
        "/api/buildings",
        json={"name": "TestUpgrade", "building_type": "farm", "x": 5, "y": 5},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201), f"Failed to create building: {resp.text}"
    building_id = resp.json()["id"]

    # Upgrade it
    resp = client.post(
        f"/api/buildings/{building_id}/upgrade",
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201), (
        f"POST /api/buildings/{building_id}/upgrade failed: {resp.text}"
    )
