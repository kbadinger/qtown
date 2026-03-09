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
    """Seed a bakery building into the town."""
    existing = db.query(Building).filter(Building.building_type == "bakery").first()
    if existing:
        return
    db.add(Building(name="Bakery", building_type="bakery", x=27, y=22, capacity=10))
    db.commit()


def seed_blacksmith(db: Session) -> None:
    """Seed a blacksmith building into the town."""
    existing = db.query(Building).filter(Building.building_type == "blacksmith").first()
    if existing:
        return
    db.add(Building(name="Blacksmith", building_type="blacksmith", x=30, y=20, capacity=10))
    db.commit()


def seed_farm(db: Session) -> None:
    """Seed a farm building into the town."""
    existing = db.query(Building).filter(Building.building_type == "farm").first()
    if existing:
        return
    db.add(Building(name="Farm", building_type="farm", x=15, y=12, capacity=10))
    db.commit()


def seed_church(db: Session) -> None:
    """Seed a church building into the town."""
    existing = db.query(Building).filter(Building.building_type == "church").first()
    if existing:
        return
    db.add(Building(name="Church", building_type="church", x=22, y=30, capacity=10))
    db.commit()


def seed_school(db: Session) -> None:
    """Seed school building idempotently."""
    existing = db.query(Building).filter(Building.building_type == "school").first()
    if existing:
        return
    db.add(Building(name="School", building_type="school", x=20, y=28, capacity=30))
    db.commit()


def seed_hospital(db: Session) -> None:
    """Seed a hospital building into the town."""
    existing = db.query(Building).filter(Building.building_type == "hospital").first()
    if existing:
        return
    db.add(Building(name="Hospital", building_type="hospital", x=32, y=26, capacity=10))
    db.commit()


def seed_tavern(db: Session) -> None:
    """Seed a tavern building into the town."""
    existing = db.query(Building).filter(Building.building_type == "tavern").first()
    if existing:
        return
    db.add(Building(name="Tavern", building_type="tavern", x=28, y=28, capacity=10))
    db.commit()


def seed_library(db: Session) -> None:
    """Seed a library building into the town."""
    existing = db.query(Building).filter(Building.building_type == "library").first()
    if existing:
        return
    db.add(Building(name="Library", building_type="library", x=18, y=26, capacity=10))
    db.commit()


def seed_mine(db: Session) -> None:
    """Seed a mine building into the town."""
    existing = db.query(Building).filter(Building.building_type == "mine").count()
    if existing > 0:
        return
    db.add(Building(name="Town Mine", building_type="mine", x=42, y=8, capacity=5))
    db.commit()


def seed_lumber_mill(db: Session) -> None:
    """Seed a lumber mill building into the town."""
    existing = db.query(Building).filter(Building.building_type == "lumber_mill").count()
    if existing > 0:
        return
    db.add(Building(name="Town Lumber Mill", building_type="lumber_mill", x=8, y=38, capacity=5))
    db.commit()


def seed_fishing_dock(db: Session) -> None:
    """Seed a fishing dock building into the town."""
    existing = db.query(Building).filter(Building.building_type == "fishing_dock").count()
    if existing > 0:
        return
    db.add(Building(name="Town Fishing Dock", building_type="fishing_dock", x=5, y=45, capacity=5))
    db.commit()


def seed_guard_tower(db: Session) -> None:
    """Seed a guard tower building into the town."""
    existing = db.query(Building).filter(Building.building_type == "guard_tower").count()
    if existing > 0:
        return
    db.add(Building(name="Town Guard Tower", building_type="guard_tower", x=45, y=5, capacity=5))
    db.commit()


def seed_wall(db: Session) -> None:
    """Seed a wall building into the town."""
    existing = db.query(Building).filter(Building.building_type == "wall").count()
    if existing > 0:
        return
    db.add(Building(name="Town Wall", building_type="wall", x=48, y=25, capacity=5))
    db.commit()


def seed_gate(db: Session) -> None:
    """Seed a gate building into the town."""
    existing = db.query(Building).filter(Building.building_type == "gate").count()
    if existing > 0:
        return
    db.add(Building(name="Town Gate", building_type="gate", x=48, y=24, capacity=5))
    db.commit()


def seed_fountain(db: Session) -> None:
    """Seed a fountain building into the town."""
    existing = db.query(Building).filter(Building.building_type == "fountain").count()
    if existing > 0:
        return
    db.add(Building(name="Town Fountain", building_type="fountain", x=25, y=24, capacity=5))
    db.commit()


def seed_well(db: Session) -> None:
    """Seed a well building into the town."""
    existing = db.query(Building).filter(Building.building_type == "well").count()
    if existing > 0:
        return
    db.add(Building(name="Town Well", building_type="well", x=12, y=18, capacity=5))
    db.commit()


def seed_warehouse(db: Session) -> None:
    """Seed a warehouse building into the town."""
    existing = db.query(Building).filter(Building.building_type == "warehouse").count()
    if existing > 0:
        return
    db.add(Building(name="Town Warehouse", building_type="warehouse", x=35, y=15, capacity=5))
    db.commit()


def seed_bank(db: Session) -> None:
    """Seed a bank building into the town."""
    existing = db.query(Building).filter(Building.building_type == "bank").count()
    if existing > 0:
        return
    db.add(Building(name="Town Bank", building_type="bank", x=30, y=24, capacity=5))
    db.commit()


def seed_theater(db: Session) -> None:
    """Seed a theater building into the town."""
    existing = db.query(Building).filter(Building.building_type == "theater").count()
    if existing > 0:
        return
    db.add(Building(name="Town Theater", building_type="theater", x=35, y=30, capacity=5))
    db.commit()


def seed_arena(db: Session) -> None:
    """Seed an arena building into the town."""
    existing = db.query(Building).filter(Building.building_type == "arena").count()
    if existing > 0:
        return
    db.add(Building(name="Town Arena", building_type="arena", x=40, y=35, capacity=5))
    db.commit()


def seed_prison(db: Session) -> None:
    """Seed a prison building into the town."""
    existing = db.query(Building).filter(Building.building_type == "prison").count()
    if existing > 0:
        return
    db.add(Building(name="Town Prison", building_type="prison", x=44, y=10, capacity=5))
    db.commit()


def seed_graveyard(db: Session) -> None:
    """Seed a graveyard building into the town."""
    existing = db.query(Building).filter(Building.building_type == "graveyard").count()
    if existing > 0:
        return
    db.add(Building(name="Town Graveyard", building_type="graveyard", x=8, y=42, capacity=5))
    db.commit()


def seed_garden(db: Session) -> None:
    """Seed a garden building into the town."""
    existing = db.query(Building).filter(Building.building_type == "garden").count()
    if existing > 0:
        return
    db.add(Building(name="Town Garden", building_type="garden", x=22, y=20, capacity=5))
    db.commit()


def seed_watchtower(db: Session) -> None:
    """Seed a watchtower building into the town."""
    existing = db.query(Building).filter(Building.building_type == "watchtower").count()
    if existing > 0:
        return
    db.add(Building(name="Town Watchtower", building_type="watchtower", x=5, y=5, capacity=5))
    db.commit()


def seed_windmill(db: Session) -> None:
    """Seed a windmill building into the town."""
    existing = db.query(Building).filter(Building.building_type == "windmill").count()
    if existing > 0:
        return
    db.add(Building(name="Town Windmill", building_type="windmill", x=12, y=8, capacity=5))
    db.commit()


def suggest_building_placement(db: Session, building_type: str) -> tuple[int, int] | None:
    """Suggest optimal placement for a building based on type."""
    from engine.models import Building

    existing_buildings = db.query(Building).all()
    occupied_tiles = set((b.x, b.y) for b in existing_buildings)

    town_hall = None
    for b in existing_buildings:
        if b.building_type == "civic":
            town_hall = (b.x, b.y)
            break

    GRID_SIZE = 50

    if building_type == "food":
        for y in range(15):
            for x in range(GRID_SIZE):
                if (x, y) not in occupied_tiles:
                    return (x, y)
    elif building_type == "residential":
        if town_hall:
            tx, ty = town_hall
            for dy in range(-5, 6):
                for dx in range(-5, 6):
                    x, y = tx + dx, ty + dy
                    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE and (x, y) not in occupied_tiles:
                        return (x, y)
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if (x, y) not in occupied_tiles:
                    return (x, y)
    elif building_type == "guard":
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

    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if (x, y) not in occupied_tiles:
                return (x, y)

    return None


def detect_resource_gaps(db: Session) -> list[dict]:
    """Detect missing critical resources in the town."""
    from engine.models import Building

    gaps = []

    farm = db.query(Building).filter(Building.building_type == "farm").first()
    if not farm:
        gaps.append({"gap": "food", "severity": "critical", "suggestion": "Build a farm to produce food for NPCs"})

    hospital = db.query(Building).filter(Building.building_type == "hospital").first()
    if not hospital:
        gaps.append({"gap": "healing", "severity": "high", "suggestion": "Build a hospital to heal sick NPCs"})

    guard_tower = db.query(Building).filter(Building.building_type == "guard_tower").first()
    if not guard_tower:
        gaps.append({"gap": "defense", "severity": "medium", "suggestion": "Build a guard tower to protect the town"})

    return gaps


def recommend_construction(db: Session) -> dict:
    """Recommend next building to construct based on resource gaps and population."""
    from engine.models import Building, NPC, Resource, WorldState

    gaps = detect_resource_gaps(db)
    npcs = db.query(NPC).filter_by(is_dead=0).all()
    population = len(npcs)

    building_type = None
    reason = None
    priority = 1

    if gaps and any(g.get('resource') == 'food' for g in gaps):
        building_type = 'farm'
        reason = 'Food shortage detected'
        priority = 1
    elif population > 50:
        building_type = 'residential'
        reason = 'Growing population needs housing'
        priority = 2
    else:
        building_type = 'farm'
        reason = 'Build farm for food production'
        priority = 3

    placement = suggest_building_placement(db, building_type)

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


def zone_grid(db: Session) -> None:
    """Divide the 50x50 grid into zones: residential (NW), commercial (NE), industrial (SW), civic (SE)."""
    from engine.models import Tile

    tiles = db.query(Tile).all()
    for tile in tiles:
        if tile.x < 25 and tile.y < 25:
            tile.zone = "residential"
        elif tile.x >= 25 and tile.y < 25:
            tile.zone = "commercial"
        elif tile.x < 25 and tile.y >= 25:
            tile.zone = "industrial"
        else:
            tile.zone = "civic"

    db.commit()


def calculate_infrastructure_score(db: Session) -> float:
    """Calculate infrastructure score 0-100."""
    from engine.models import Building, NPC, Resource, WorldState
    from sqlalchemy import func

    score = 0.0

    building_types = db.query(func.distinct(Building.building_type)).all()
    unique_types = len(building_types)
    score += min(unique_types / 10.0, 1.0) * 25

    resources = db.query(Resource).all()
    essential_resources = ["food", "wood", "stone", "metal"]
    covered_resources = sum(1 for r in resources if r.name in essential_resources and r.quantity > 0)
    score += (covered_resources / len(essential_resources)) * 25

    total_npcs = db.query(NPC).filter(NPC.is_dead == 0).count()
    housed_npcs = db.query(NPC).filter(NPC.is_dead == 0, NPC.home_building_id.isnot(None)).count()
    housing_rate = housed_npcs / total_npcs if total_npcs > 0 else 0
    score += housing_rate * 25

    defense_types = ["guard_tower", "wall", "gate", "watchtower"]
    defense_buildings = db.query(Building).filter(Building.building_type.in_(defense_types)).count()
    score += min(defense_buildings / 4.0, 1.0) * 25

    world_state = db.query(WorldState).first()
    if world_state:
        world_state.infrastructure_score = score
        db.commit()

    return score


def upgrade_building(db: Session, building_id: int) -> None:
    """Upgrade a building by increasing its level by 1."""
    building = db.query(Building).filter(Building.id == building_id).first()
    if building:
        building.level = (building.level or 1) + 1
        db.commit()


def calculate_adjacency_bonuses(db: Session) -> dict:
    """Calculate adjacency bonuses for all buildings.
    
    Bonuses:
    - farm near well = +2 capacity
    - blacksmith near mine = +2 capacity
    - tavern near residential = +1 capacity
    
    Returns: dict of {building_id: bonus}
    """
    from engine.models import Building
    
    buildings = db.query(Building).all()
    bonuses = {}
    
    for building in buildings:
        bonus = 0
        
        for other in buildings:
            if other.id == building.id:
                continue
            
            # Calculate squared Euclidean distance
            dx = other.x - building.x
            dy = other.y - building.y
            distance_sq = dx * dx + dy * dy
            
            # Check if within 3 tiles (distance_sq <= 9)
            if distance_sq > 9:
                continue
            
            # Check for specific adjacency bonuses
            if building.building_type == "farm" and other.building_type == "well":
                bonus += 2
            elif building.building_type == "blacksmith" and other.building_type == "mine":
                bonus += 2
            elif building.building_type == "tavern" and other.building_type == "residential":
                bonus += 1
        
        if bonus > 0:
            bonuses[building.id] = bonus
    
    return bonuses


def calculate_road_bonus(db: Session) -> int:
    """Calculate movement speed bonus based on road network."""
    from engine.models import Building
    
    # Count buildings with type 'road' or 'gate'
    road_count = db.query(Building).filter(
        Building.building_type.in_(['road', 'gate'])
    ).count()
    
    # 1% per road, capped at 20%
    bonus = road_count * 1
    return min(bonus, 20)
