"""Building seed functions and build_building."""

import sys
from sqlalchemy.orm import Session

from engine.models import Building


def seed_all_buildings(db: Session) -> None:
    """Call every seed_* function in this module. All are idempotent.

    Auto-discovers functions matching seed_*(db) so new building types
    added by Qwen are picked up without editing this function.
    """
    import sys
    module = sys.modules[__name__]
    for name in sorted(dir(module)):
        if name.startswith("seed_") and name != "seed_all_buildings":
            fn = getattr(module, name)
            if callable(fn):
                fn(db)


def build_building(db: Session, name: str, building_type: str, x: int, y: int) -> Building:
    """Build a new building at the specified coordinates.
    
    Validates x,y are in 0-49 range. Creates a Building row.
    Returns the new Building object.
    Raises ValueError if coordinates out of range or occupied.
    """
    # Validate coordinates are in range
    if x < 0 or x > 49 or y < 0 or y > 49:
        raise ValueError(f"Coordinates ({x}, {y}) out of valid range (0-49)")
    
    # Check if tile is already occupied by another building
    existing_building = db.query(Building).filter(Building.x == x, Building.y == y).first()
    if existing_building:
        raise ValueError(f"Tile ({x}, {y}) is already occupied by {existing_building.name}")
    
    # Create the new building
    new_building = Building(
        name=name,
        building_type=building_type,
        x=x,
        y=y,
        capacity=10
    )
    
    db.add(new_building)
    db.commit()
    db.refresh(new_building)
    
    return new_building


def seed_bakery(db: Session) -> None:
    """Seed a bakery building into the town.

    Creates 1 bakery building at coordinates (18, 18).
    Idempotent: calling twice will not duplicate the bakery.
    """
    existing_bakery = db.query(Building).filter(
        Building.building_type == "bakery"
    ).first()
    if existing_bakery:
        return

    bakery = Building(
        name="Bakery",
        building_type="bakery",
        x=18,
        y=18,
        capacity=10
    )
    db.add(bakery)
    db.commit()


def seed_blacksmith(db: Session) -> None:
    """Seed a blacksmith building into the town.

    Creates 1 blacksmith building at coordinates (22, 22).
    Idempotent: calling twice will not duplicate the blacksmith.
    """
    existing_blacksmith = db.query(Building).filter(
        Building.building_type == "blacksmith"
    ).first()
    if existing_blacksmith:
        return

    blacksmith = Building(
        name="Blacksmith",
        building_type="blacksmith",
        x=22,
        y=22,
        capacity=10
    )
    db.add(blacksmith)
    db.commit()


def seed_farm(db: Session) -> None:
    """Seed a farm building into the town.

    Creates 1 farm building at coordinates (15, 15).
    Idempotent: calling twice will not duplicate the farm.
    """
    existing_farm = db.query(Building).filter(
        Building.building_type == "farm"
    ).first()
    if existing_farm:
        return

    farm = Building(
        name="Farm",
        building_type="farm",
        x=15,
        y=15,
        capacity=10
    )
    db.add(farm)
    db.commit()


def seed_church(db: Session) -> None:
    """Seed a church building into the town.

    Creates 1 church building at coordinates (35, 35).
    Idempotent: calling twice will not duplicate the church.
    """
    existing_church = db.query(Building).filter(
        Building.building_type == "church"
    ).first()
    if existing_church:
        return

    church = Building(
        name="Church",
        building_type="church",
        x=35,
        y=35,
        capacity=10
    )
    db.add(church)
    db.commit()


def seed_school(db: Session) -> None:
    """Seed school building idempotently.
    
    Creates one school if none exists.
    """
    existing = db.query(Building).filter(Building.building_type == "school").first()
    if existing:
        return
    
    db.add(Building(name="School", building_type="school", x=25, y=35, capacity=30))
    db.commit()


def seed_hospital(db: Session) -> None:
    """Seed a hospital building into the town.

    Creates 1 hospital building at coordinates (28, 28).
    Idempotent: calling twice will not duplicate the hospital.
    """
    existing_hospital = db.query(Building).filter(
        Building.building_type == "hospital"
    ).first()
    if existing_hospital:
        return

    hospital = Building(
        name="Hospital",
        building_type="hospital",
        x=28,
        y=28,
        capacity=10
    )
    db.add(hospital)
    db.commit()


def seed_tavern(db: Session) -> None:
    """Seed a tavern building into the town.

    Creates 1 tavern building at coordinates (40, 40).
    Idempotent: calling twice will not duplicate the tavern.
    """
    existing_tavern = db.query(Building).filter(
        Building.building_type == "tavern"
    ).first()
    if existing_tavern:
        return

    tavern = Building(
        name="Tavern",
        building_type="tavern",
        x=40,
        y=40,
        capacity=10
    )
    db.add(tavern)
    db.commit()


def seed_library(db: Session) -> None:
    """Seed a library building into the town.

    Creates 1 library building at coordinates (20, 20).
    Idempotent: calling twice will not duplicate the library.
    """
    existing_library = db.query(Building).filter(Building.building_type == "library").first()
    if existing_library:
        return

    db.add(Building(name="Library", building_type="library", x=20, y=20))
    db.commit()


def seed_mine(db: Session) -> None:
    """Seed a mine building into the town.

    Creates 1 mine building at coordinates (45, 45).
    Idempotent - will not create if one already exists.
    """
    existing_mines = db.query(Building).filter(Building.building_type == 'mine').count()
    if existing_mines > 0:
        return
    
    # Create mine at (45, 45)
    mine = Building(
        name="Town Mine",
        building_type="mine",
        x=45,
        y=45,
        capacity=5
    )
    db.add(mine)
    db.commit()


def seed_lumber_mill(db: Session) -> None:
    """Seed a lumber mill building into the town.

    Creates 1 lumber mill building at coordinates (46, 46).
    Idempotent - will not create if one already exists.
    """
    existing_mills = db.query(Building).filter(Building.building_type == 'lumber_mill').count()
    if existing_mills > 0:
        return
    
    # Create lumber mill at (46, 46)
    lumber_mill = Building(
        name="Town Lumber Mill",
        building_type="lumber_mill",
        x=46,
        y=46,
        capacity=5
    )
    db.add(lumber_mill)
    db.commit()


def seed_fishing_dock(db: Session) -> None:
    """Seed a fishing dock building into the town.

    Creates 1 fishing dock building at coordinates (47, 47).
    Idempotent - will not create if one already exists.
    """
    existing_docks = db.query(Building).filter(Building.building_type == 'fishing_dock').count()
    if existing_docks > 0:
        return
    
    # Create fishing dock at (47, 47)
    fishing_dock = Building(
        name="Town Fishing Dock",
        building_type="fishing_dock",
        x=47,
        y=47,
        capacity=5
    )
    db.add(fishing_dock)
    db.commit()


def seed_guard_tower(db: Session) -> None:
    """Seed a guard tower building into the town.

    Creates 1 guard tower building at coordinates (48, 48).
    Idempotent - will not create if one already exists.
    """
    existing_towers = db.query(Building).filter(Building.building_type == 'guard_tower').count()
    if existing_towers > 0:
        return
    
    # Create guard tower at (48, 48)
    guard_tower = Building(
        name="Town Guard Tower",
        building_type="guard_tower",
        x=48,
        y=48,
        capacity=5
    )
    db.add(guard_tower)
    db.commit()


def seed_wall(db: Session) -> None:
    """Seed a wall building into the town.

    Creates 1 wall building at coordinates (49, 49).
    Idempotent - will not create if one already exists.
    """
    existing_walls = db.query(Building).filter(Building.building_type == 'wall').count()
    if existing_walls > 0:
        return
    
    # Create wall at (49, 49)
    wall = Building(
        name="Town Wall",
        building_type="wall",
        x=49,
        y=49,
        capacity=5
    )
    db.add(wall)
    db.commit()


def seed_gate(db: Session) -> None:
    """Seed a gate building into the town.

    Creates 1 gate building at coordinates (50, 50).
    Idempotent - will not create if one already exists.
    """
    existing_gates = db.query(Building).filter(Building.building_type == 'gate').count()
    if existing_gates > 0:
        return
    
    # Create gate at (50, 50)
    gate = Building(
        name="Town Gate",
        building_type="gate",
        x=50,
        y=50,
        capacity=5
    )
    db.add(gate)
    db.commit()


def seed_fountain(db: Session) -> None:
    """Seed a fountain building into the town.

    Creates 1 fountain building at coordinates (40, 40).
    Idempotent - will not create if one already exists.
    """
    existing_fountains = db.query(Building).filter(Building.building_type == 'fountain').count()
    if existing_fountains > 0:
        return
    
    # Create fountain at (40, 40)
    fountain = Building(
        name="Town Fountain",
        building_type="fountain",
        x=40,
        y=40,
        capacity=5
    )
    db.add(fountain)
    db.commit()


def seed_well(db: Session) -> None:
    """Seed a well building into the town.

    Creates 1 well building at coordinates (41, 41).
    Idempotent - will not create if one already exists.
    """
    existing_wells = db.query(Building).filter(Building.building_type == 'well').count()
    if existing_wells > 0:
        return
    
    # Create well at (41, 41)
    well = Building(
        name="Town Well",
        building_type="well",
        x=41,
        y=41,
        capacity=5
    )
    db.add(well)
    db.commit()


def seed_warehouse(db: Session) -> None:
    """Seed a warehouse building into the town.

    Creates 1 warehouse building at coordinates (42, 42).
    Idempotent - will not create if one already exists.
    """
    existing_warehouses = db.query(Building).filter(Building.building_type == 'warehouse').count()
    if existing_warehouses > 0:
        return
    
    # Create warehouse at (42, 42)
    warehouse = Building(
        name="Town Warehouse",
        building_type="warehouse",
        x=42,
        y=42,
        capacity=5
    )
    db.add(warehouse)
    db.commit()


def seed_bank(db: Session) -> None:
    """Seed a bank building into the town.

    Creates 1 bank building at coordinates (51, 51).
    Idempotent - will not create if one already exists.
    """
    existing_banks = db.query(Building).filter(Building.building_type == 'bank').count()
    if existing_banks > 0:
        return
    
    # Create bank at (51, 51)
    bank = Building(
        name="Town Bank",
        building_type="bank",
        x=51,
        y=51,
        capacity=5
    )
    db.add(bank)
    db.commit()


def seed_theater(db: Session) -> None:
    """Seed a theater building into the town.

    Creates 1 theater building at coordinates (52, 52).
    Idempotent - will not create if one already exists.
    """
    existing_theaters = db.query(Building).filter(Building.building_type == 'theater').count()
    if existing_theaters > 0:
        return
    
    # Create theater at (52, 52)
    theater = Building(
        name="Town Theater",
        building_type="theater",
        x=52,
        y=52,
        capacity=5
    )
    db.add(theater)
    db.commit()


def seed_arena(db: Session) -> None:
    """Seed an arena building into the town.

    Creates 1 arena building at coordinates (53, 53).
    Idempotent - will not create if one already exists.
    """
    existing_arenas = db.query(Building).filter(Building.building_type == 'arena').count()
    if existing_arenas > 0:
        return
    
    # Create arena at (53, 53)
    arena = Building(
        name="Town Arena",
        building_type="arena",
        x=53,
        y=53,
        capacity=5
    )
    db.add(arena)
    db.commit()


def seed_prison(db: Session) -> None:
    """Seed a prison building into the town.

    Creates 1 prison building at coordinates (54, 54).
    Idempotent - will not create if one already exists.
    """
    existing_prisons = db.query(Building).filter(Building.building_type == 'prison').count()
    if existing_prisons > 0:
        return
    
    # Create prison at (54, 54)
    prison = Building(
        name="Town Prison",
        building_type="prison",
        x=54,
        y=54,
        capacity=5
    )
    db.add(prison)
    db.commit()


def seed_graveyard(db: Session) -> None:
    """Seed a graveyard building into the town.

    Creates 1 graveyard building at coordinates (55, 55).
    Idempotent - will not create if one already exists.
    """
    existing_graveyards = db.query(Building).filter(Building.building_type == 'graveyard').count()
    if existing_graveyards > 0:
        return
    
    # Create graveyard at (55, 55)
    graveyard = Building(
        name="Town Graveyard",
        building_type="graveyard",
        x=55,
        y=55,
        capacity=5
    )
    db.add(graveyard)
    db.commit()


def seed_garden(db: Session) -> None:
    """Seed a garden building into the town.

    Creates 1 garden building at coordinates (56, 56).
    Idempotent - will not create if one already exists.
    """
    existing_gardens = db.query(Building).filter(Building.building_type == 'garden').count()
    if existing_gardens > 0:
        return
    
    # Create garden at (56, 56)
    garden = Building(
        name="Town Garden",
        building_type="garden",
        x=56,
        y=56,
        capacity=5
    )
    db.add(garden)
    db.commit()


def seed_watchtower(db: Session) -> None:
    """Seed a watchtower building into the town.

    Creates 1 watchtower building at coordinates (57, 57).
    Idempotent - will not create if one already exists.
    """
    existing_watchtowers = db.query(Building).filter(Building.building_type == 'watchtower').count()
    if existing_watchtowers > 0:
        return
    
    # Create watchtower at (57, 57)
    watchtower = Building(
        name="Town Watchtower",
        building_type="watchtower",
        x=57,
        y=57,
        capacity=5
    )
    db.add(watchtower)
    db.commit()


def seed_windmill(db: Session) -> None:
    """Seed a windmill building into the town.

    Creates 1 windmill building at coordinates (58, 58).
    Idempotent - will not create if one already exists.
    """
    existing_windmills = db.query(Building).filter(Building.building_type == 'windmill').count()
    if existing_windmills > 0:
        return
    
    # Create windmill at (58, 58)
    windmill = Building(
        name="Town Windmill",
        building_type="windmill",
        x=58,
        y=58,
        capacity=5
    )
    db.add(windmill)
    db.commit()


def suggest_building_placement(db: Session, building_type: str) -> tuple[int, int] | None:
    """Suggest optimal placement for a building based on type.
    
    Args:
        db: Database session
        building_type: Type of building ("food", "residential", "civic", "guard", etc.)
    
    Returns:
        (x, y) tuple for placement, or None if no valid placement found
    """
    from engine.models import Building
    
    # Get all existing buildings to avoid overlap
    existing_buildings = db.query(Building).all()
    occupied_tiles = set((b.x, b.y) for b in existing_buildings)
    
    # Find Town Hall position for residential placement
    town_hall = None
    for b in existing_buildings:
        if b.building_type == "civic":
            town_hall = (b.x, b.y)
            break
    
    # Grid dimensions
    GRID_SIZE = 50
    
    if building_type == "food":
        # Farms should be near water (y < 15)
        for y in range(15):
            for x in range(GRID_SIZE):
                if (x, y) not in occupied_tiles:
                    return (x, y)
    
    elif building_type == "residential":
        # Near Town Hall (within 5 tiles)
        if town_hall:
            tx, ty = town_hall
            for dy in range(-5, 6):
                for dx in range(-5, 6):
                    x, y = tx + dx, ty + dy
                    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE and (x, y) not in occupied_tiles:
                        return (x, y)
        # Fallback: any available spot
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if (x, y) not in occupied_tiles:
                    return (x, y)
    
    elif building_type == "guard":
        # Guard towers at grid edges
        edge_positions = []
        for x in range(GRID_SIZE):
            edge_positions.append((x, 0))
            edge_positions.append((x, GRID_SIZE - 1))
        for y in range(GRID_SIZE):
            edge_positions.append((0, y))
            edge_positions.append((GRID_SIZE - 1, y))
        
        for x, y in edge_positions:
            if (x, y) not in occupied_tiles:
                return (x, y)
    
    # Default fallback: first available tile
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if (x, y) not in occupied_tiles:
                return (x, y)
    
    return None


def detect_resource_gaps(db: Session) -> list[dict]:
    """Detect missing critical resources in the town.
    
    Returns a list of gap dictionaries with gap type, severity, and suggestion.
    """
    from sqlalchemy.orm import Session
    from engine.models import Building
    
    gaps = []
    
    # Check for food production (farm)
    farm = db.query(Building).filter(Building.building_type == "farm").first()
    if not farm:
        gaps.append({
            "gap": "food",
            "severity": "critical",
            "suggestion": "Build a farm to produce food for NPCs"
        })
    
    # Check for healing (hospital)
    hospital = db.query(Building).filter(Building.building_type == "hospital").first()
    if not hospital:
        gaps.append({
            "gap": "healing",
            "severity": "high",
            "suggestion": "Build a hospital to heal sick NPCs"
        })
    
    # Check for defense (guard tower)
    guard_tower = db.query(Building).filter(Building.building_type == "guard_tower").first()
    if not guard_tower:
        gaps.append({
            "gap": "defense",
            "severity": "medium",
            "suggestion": "Build a guard tower to protect the town"
        })
    
    return gaps


def recommend_construction(db: Session) -> dict:
    """Recommend next building to construct based on resource gaps and population."""
    from engine.models import Building, NPC, Resource, WorldState
    
    # Detect resource gaps
    gaps = detect_resource_gaps(db)
    
    # Check population growth needs
    npcs = db.query(NPC).filter_by(is_dead=0).all()
    population = len(npcs)
    
    # Determine priority building
    building_type = None
    reason = None
    priority = 1
    
    # Check for food gap first (highest priority)
    if gaps and any(g.get('resource') == 'food' for g in gaps):
        building_type = 'farm'
        reason = 'Food shortage detected'
        priority = 1
    # Check for housing needs based on population
    elif population > 50:
        building_type = 'residential'
        reason = 'Growing population needs housing'
        priority = 2
    # Default to something useful
    else:
        building_type = 'farm'
        reason = 'Build farm for food production'
        priority = 3
    
    # Get suggested placement
    placement = suggest_building_placement(db, building_type)
    
    # Handle tuple vs dict return from suggest_building_placement
    if isinstance(placement, tuple):
        suggested_x, suggested_y = placement
    else:
        suggested_x = placement.get('x', 0)
        suggested_y = placement.get('y', 0)
    
    return {
        'building_type': building_type,
        'reason': reason,
        'priority': priority,
        'suggested_x': suggested_x,
        'suggested_y': suggested_y
    }
