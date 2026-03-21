"""Building seed functions and build_building."""

import sys
from sqlalchemy.orm import Session

from engine.models import Building
from typing import Optional
import json
from engine.models import Tile, Building, NPC
from typing import List, Dict
from engine.models import Treasury, Event, WorldState
from engine.models import Resource
import random
from sqlalchemy import func
from math import sqrt


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


def set_building_focus(db: Session, building_id: int, focus: str) -> Building:
    """Set building specialization focus.
    
    Valid focuses: 'production', 'training', 'storage'
    - Production: +50% output
    - Training: workers gain +1 skill per cycle
    - Storage: +5 effective capacity
    
    Stores focus as building name suffix.
    """
    from engine.models import Building
    
    if focus not in ['production', 'training', 'storage']:
        raise ValueError(f"Invalid focus: {focus}. Must be 'production', 'training', or 'storage'")
    
    building = db.query(Building).filter(Building.id == building_id).first()
    if building is None:
        raise ValueError(f"Building not found: {building_id}")
    
    # Store focus as name suffix
    if not building.name.endswith(f" ({focus})"):
        building.name = f"{building.name} ({focus})"
    
    db.commit()
    return building


def process_building_decay(db: Session) -> int:
    """Process building decay for buildings with no workers.
    
    For each building with no workers (no NPC has work_building_id pointing to it),
    reduce capacity by 1 per call (floor at 1). If capacity reaches 1, rename to 
    'Ruins of {original_name}' if not already. Create Event for decayed buildings.
    
    Returns count of decayed buildings.
    """
    from engine.models import Building, NPC, Event, WorldState
    
    decayed_count = 0
    buildings = db.query(Building).all()
    
    # Get current tick for events
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    for building in buildings:
        # Check if any NPC has this building as work_building_id
        worker_count = db.query(NPC).filter(NPC.work_building_id == building.id).count()
        
        if worker_count == 0:
            # Building has no workers, decay it
            if building.capacity > 1:
                building.capacity -= 1
            
            # If capacity reaches 1 and not already named as ruins
            if building.capacity == 1 and not building.name.startswith('Ruins of '):
                building.name = f'Ruins of {building.name}'
                decayed_count += 1
                
                # Create event for decayed building
                event = Event(
                    day=current_tick,
                    headline=f'{building.name} has decayed',
                    body=f'{building.name} has no workers and has decayed.',
                    author_npc_id=None,
                    tick=current_tick
                )
                db.add(event)
    
    db.commit()
    return decayed_count


def process_construction(db: Session) -> Optional[str]:
    """Process construction queue for builders."""
    # Find builder NPC
    builder = db.query(NPC).filter(NPC.role == 'builder').first()
    
    if not builder:
        return None
    
    # Parse experience JSON
    try:
        experience = json.loads(builder.experience)
        experience = experience if isinstance(experience, dict) else {}
    except (json.JSONDecodeError, TypeError):
        experience = {}
    
    # Check if builder has a construction project
    project_id = experience.get('construction_project')
    
    if project_id is None:
        # Find empty tile for new building
        empty_tile = _find_empty_tile(db)
        if not empty_tile:
            return "No empty tiles available"
        
        # Create building stub with capacity=0
        new_building = Building(
            name=f"Construction Site {db.query(Building).count() + 1}",
            building_type="construction",
            x=empty_tile.x,
            y=empty_tile.y,
            capacity=0,
            level=1
        )
        db.add(new_building)
        db.commit()
        
        # Assign project to builder
        experience['construction_project'] = new_building.id
        builder.experience = json.dumps(experience)
        db.commit()
        
        return f"Started construction at ({empty_tile.x}, {empty_tile.y})"
    
    # Builder has an active project
    project = db.query(Building).filter(Building.id == project_id).first()
    
    if not project:
        # Project was deleted, clear the assignment
        del experience['construction_project']
        builder.experience = json.dumps(experience)
        db.commit()
        return None
    
    # Increase capacity by 1
    project.capacity += 1
    db.commit()
    
    if project.capacity >= 5:
        # Building is complete
        del experience['construction_project']
        builder.experience = json.dumps(experience)
        project.building_type = "completed"
        db.commit()
        return f"Completed building at ({project.x}, {project.y})"
    
    return f"Construction in progress: {project.capacity}/5"


def process_insurance(db: Session) -> int:
    """Process insurance for all buildings."""
    from engine.models import Building, Treasury
    
    insured_count = 0
    buildings = db.query(Building).all()
    
    for building in buildings:
        # Check if building is insured (flag in name)
        if "insured" in building.name.lower():
            insured_count += 1
            
            # Auto-repair: add +2 capacity for insured buildings
            building.capacity = building.capacity + 2
            
            # Deduct insurance cost from Treasury (5 gold per insured building)
            treasury = db.query(Treasury).first()
            if treasury and treasury.gold >= 5:
                treasury.gold = treasury.gold - 5
    
    db.commit()
    return insured_count


def check_landmarks(db: Session) -> int:
    """Check for landmark buildings and apply town-wide happiness bonus.
    
    Buildings with level >= 4 become landmarks.
    Landmarks give town-wide happiness +1 per landmark (cap +5 total).
    Creates an Event with type 'landmark_status' listing landmark names.
    
    Returns:
        int: Count of landmarks found.
    """
    from engine.models import Building, Event, NPC
    from sqlalchemy import func
    
    # Find all buildings with level >= 4
    landmarks = db.query(Building).filter(Building.level >= 4).all()
    landmark_count = len(landmarks)
    landmark_names = [b.name for b in landmarks]
    
    # Calculate happiness bonus (capped at +5)
    happiness_bonus = min(landmark_count, 5)
    
    # Apply happiness bonus to all NPCs
    if happiness_bonus > 0:
        db.query(NPC).update({NPC.happiness: func.least(NPC.happiness + happiness_bonus, 100)})
    
    # Create event if there are landmarks
    if landmark_count > 0:
        event_body = f"Landmarks active: {', '.join(landmark_names)}"
        event = Event(
            event_type='landmark_status',
            description=event_body,
            severity=0  # 0 = info
        )
        db.add(event)
    
    db.commit()
    
    return landmark_count


def inspect_buildings(db: Session) -> List[Dict]:
    """Inspect all buildings and return their status."""
    from engine.models import Building, NPC
    from sqlalchemy import func
    
    buildings = db.query(Building).all()
    results = []
    
    for building in buildings:
        # Count workers at this building
        worker_count = db.query(NPC).filter(NPC.work_building_id == building.id).count()
        
        # Determine status based on capacity and workers
        if worker_count == 0:
            status = 'abandoned'
        elif building.capacity < 3:
            status = 'critical'
        elif building.capacity < 5:
            status = 'damaged'
        else:
            status = 'operational'
        
        results.append({
            'building_id': building.id,
            'name': building.name,
            'status': status,
            'capacity': building.capacity
        })
    
    return results


def enforce_storage_limits(db: Session) -> int:
    """Enforce storage limits on resources based on warehouse capacity."""
    from engine.models import Building, Resource, Event, WorldState
    
    # Count warehouse buildings
    warehouse_count = db.query(Building).filter(Building.building_type == 'warehouse').count()
    
    # Calculate storage cap (base 200 + 100 per warehouse)
    storage_cap = 200 + (warehouse_count * 100)
    
    # Get all resources
    resources = db.query(Resource).all()
    
    # Track if any were capped
    any_capped = False
    
    for resource in resources:
        if resource.quantity > storage_cap:
            resource.quantity = storage_cap
            any_capped = True
    
    # Create event if any resources were capped
    if any_capped:
        world_state = db.query(WorldState).first()
        current_tick = world_state.tick if world_state else 0
        
        event = Event(
            event_type='storage_overflow',
            description=f'Storage overflow occurred. Cap: {storage_cap}',
            tick=current_tick
        )
        db.add(event)
        db.commit()
    
    return storage_cap


def rename_building(db: Session, building_id: int, new_name: str) -> Optional[str]:
    """Rename a building and log the event.
    
    Args:
        db: Database session
        building_id: ID of the building to rename
        new_name: New name for the building (1-50 chars, alphanumeric + spaces)
    
    Returns:
        Updated building name or None if invalid
    """
    from engine.models import Building, Event, WorldState
    
    # Validate new_name: 1-50 chars, alphanumeric + spaces only
    if not new_name or len(new_name) < 1 or len(new_name) > 50:
        return None
    
    if not all(c.isalnum() or c.isspace() for c in new_name):
        return None
    
    # Get the building
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        return None
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Store old name
    old_name = building.name
    
    # Update the building name
    building.name = new_name
    
    # Create event
    event = Event(
        event_type='building_renamed',
        description=f"Building {building_id} renamed from '{old_name}' to '{new_name}'",
        tick=current_tick,
        severity='info',
        affected_building_id=building_id
    )
    db.add(event)
    
    db.commit()
    
    return new_name


def generate_building_description(db: Session, building_id: int) -> str:
    """Generate a description string for a building based on its type and level."""
    from engine.models import Building
    
    building = db.query(Building).filter(Building.id == building_id).first()
    if building is None:
        return "Unknown building"
    
    # Description mapping: (building_type, level) -> description
    descriptions = {
        ("farm", 1): "A modest farm with basic tools",
        ("farm", 2): "A well-maintained farm with improved equipment",
        ("farm", 3): "A prosperous farm with irrigation",
        ("farm", 4): "A thriving farm with advanced machinery",
        ("farm", 5): "A legendary farm with automated systems",
        ("bakery", 1): "A small bakery with a single oven",
        ("bakery", 2): "A cozy bakery with fresh bread daily",
        ("bakery", 3): "A bustling bakery with multiple ovens",
        ("bakery", 4): "A renowned bakery with specialty pastries",
        ("bakery", 5): "A legendary bakery known across the kingdom",
        ("blacksmith", 1): "A humble forge with basic tools",
        ("blacksmith", 2): "A working forge with quality iron",
        ("blacksmith", 3): "A skilled forge with steel weapons",
        ("blacksmith", 4): "A master forge with enchanted items",
        ("blacksmith", 5): "A legendary forge crafting mythical artifacts",
        ("church", 1): "A small chapel with simple altar",
        ("church", 2): "A modest church with stained glass",
        ("church", 3): "A grand church with ornate decorations",
        ("church", 4): "A cathedral with towering spires",
        ("church", 5): "A holy sanctuary with divine presence",
        ("school", 1): "A basic schoolhouse with wooden desks",
        ("school", 2): "A well-stocked school with books",
        ("school", 3): "A prestigious academy with tutors",
        ("school", 4): "A renowned university with scholars",
        ("school", 5): "A legendary institution of learning",
        ("hospital", 1): "A small clinic with basic supplies",
        ("hospital", 2): "A functioning hospital with doctors",
        ("hospital", 3): "A well-equipped hospital with specialists",
        ("hospital", 4): "A medical center with advanced treatment",
        ("hospital", 5): "A legendary hospital with miraculous healing",
        ("tavern", 1): "A simple tavern with ale and food",
        ("tavern", 2): "A cozy tavern with regular patrons",
        ("tavern", 3): "A lively tavern with entertainment",
        ("tavern", 4): "A famous tavern with exotic drinks",
        ("tavern", 5): "A legendary tavern known for its stories",
        ("library", 1): "A small library with basic books",
        ("library", 2): "A well-stocked library with scrolls",
        ("library", 3): "A grand library with rare texts",
        ("library", 4): "A scholarly library with ancient knowledge",
        ("library", 5): "A legendary library with forbidden tomes",
        ("mine", 1): "A shallow mine with basic tools",
        ("mine", 2): "A productive mine with deeper shafts",
        ("mine", 3): "A rich mine with precious ores",
        ("mine", 4): "A vast mine with rare gems",
        ("mine", 5): "A legendary mine with mythical treasures",
        ("lumber_mill", 1): "A simple mill with basic saws",
        ("lumber_mill", 2): "A working mill with quality lumber",
        ("lumber_mill", 3): "A efficient mill with processed wood",
        ("lumber_mill", 4): "A advanced mill with treated timber",
        ("lumber_mill", 5): "A legendary mill with enchanted wood",
        ("fishing_dock", 1): "A small dock with basic boats",
        ("fishing_dock", 2): "A busy dock with fresh catch",
        ("fishing_dock", 3): "A prosperous dock with diverse fish",
        ("fishing_dock", 4): "A thriving dock with rare seafood",
        ("fishing_dock", 5): "A legendary dock with mythical creatures",
        ("guard_tower", 1): "A watchtower with basic guards",
        ("guard_tower", 2): "A fortified tower with trained soldiers",
        ("guard_tower", 3): "A strong tower with elite warriors",
        ("guard_tower", 4): "A imposing tower with legendary guards",
        ("guard_tower", 5): "A mythical tower with divine protection",
        ("wall", 1): "A simple wall with basic materials",
        ("wall", 2): "A sturdy wall with reinforced sections",
        ("wall", 3): "A strong wall with defensive features",
        ("wall", 4): "A formidable wall with magical barriers",
        ("wall", 5): "A legendary wall with impenetrable defenses",
        ("gate", 1): "A basic gate with wooden doors",
        ("gate", 2): "A secure gate with iron reinforcements",
        ("gate", 3): "A fortified gate with guards",
        ("gate", 4): "A grand gate with magical seals",
        ("gate", 5): "A legendary gate with divine protection",
        ("fountain", 1): "A simple fountain with clear water",
        ("fountain", 2): "A decorative fountain with flowing streams",
        ("fountain", 3): "An ornate fountain with sculpted figures",
        ("fountain", 4): "A majestic fountain with magical waters",
        ("fountain", 5): "A legendary fountain with healing properties",
        ("well", 1): "A basic well with clean water",
        ("well", 2): "A maintained well with fresh supply",
        ("well", 3): "A deep well with abundant water",
        ("well", 4): "A sacred well with blessed waters",
        ("well", 5): "A legendary well with eternal spring",
        ("warehouse", 1): "A small warehouse with basic storage",
        ("warehouse", 2): "A functional warehouse with organized goods",
        ("warehouse", 3): "A large warehouse with diverse supplies",
        ("warehouse", 4): "A massive warehouse with rare items",
        ("warehouse", 5): "A legendary warehouse with infinite storage",
        ("bank", 1): "A small bank with basic services",
        ("bank", 2): "A trusted bank with savings accounts",
        ("bank", 3): "A prosperous bank with loans",
        ("bank", 4): "A wealthy bank with investments",
        ("bank", 5): "A legendary bank with magical vaults",
        ("theater", 1): "A simple theater with basic stage",
        ("theater", 2): "A cozy theater with performances",
        ("theater", 3): "A grand theater with elaborate shows",
        ("theater", 4): "A famous theater with legendary acts",
        ("theater", 5): "A mythical theater with divine entertainment",
        ("arena", 1): "A small arena with basic seating",
        ("arena", 2): "A functional arena with events",
        ("arena", 3): "A large arena with competitions",
        ("arena", 4): "A grand arena with legendary battles",
        ("arena", 5): "A mythical arena with epic showdowns",
        ("prison", 1): "A basic prison with simple cells",
        ("prison", 2): "A secure prison with guards",
        ("prison", 3): "A fortified prison with strong walls",
        ("prison", 4): "A impenetrable prison with magical locks",
        ("prison", 5): "A legendary prison with eternal confinement",
        ("graveyard", 1): "A small graveyard with basic plots",
        ("graveyard", 2): "A maintained graveyard with headstones",
        ("graveyard", 3): "A peaceful graveyard with monuments",
        ("graveyard", 4): "A sacred graveyard with eternal rest",
        ("graveyard", 5): "A legendary graveyard with divine protection",
        ("garden", 1): "A small garden with basic plants",
        ("garden", 2): "A pleasant garden with flowers",
        ("garden", 3): "A beautiful garden with exotic plants",
        ("garden", 4): "A magnificent garden with rare blooms",
        ("garden", 5): "A legendary garden with magical flora",
        ("watchtower", 1): "A simple tower with basic view",
        ("watchtower", 2): "A elevated tower with clear sight",
        ("watchtower", 3): "A high tower with distant vision",
        ("watchtower", 4): "A grand tower with magical sight",
        ("watchtower", 5): "A legendary tower with omniscient view",
        ("windmill", 1): "A basic windmill with simple blades",
        ("windmill", 2): "A functional windmill with steady power",
        ("windmill", 3): "An efficient windmill with strong output",
        ("windmill", 4): "A advanced windmill with magical energy",
        ("windmill", 5): "A legendary windmill with eternal power",
    }
    
    key = (building.building_type, building.level)
    return descriptions.get(key, f"A {building.building_type} at level {building.level}")


def get_population_cap(db: Session) -> tuple[bool, int]:
    """Get town population cap based on residential building capacity.
    
    Returns:
        tuple: (can_spawn: bool, cap: int)
        - can_spawn: True if current living NPCs < cap, False otherwise
        - cap: total capacity of all residential buildings
    """
    from engine.models import Building, NPC
    
    # Residential building types that provide housing capacity
    residential_types = ["house", "apartment", "dormitory", "residential", "cabin", "shelter", "inn"]
    
    # Calculate total residential capacity
    residential_buildings = db.query(Building).filter(Building.building_type.in_(residential_types)).all()
    total_capacity = sum(b.capacity for b in residential_buildings)
    
    # Count living NPCs (is_dead == 0 for Postgres compatibility)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    # Determine if new NPCs can spawn
    can_spawn = living_npcs < total_capacity
    
    return (can_spawn, total_capacity)


def repair_damaged_buildings(db: Session) -> int:
    """Repair damaged buildings using treasury gold."""
    count_repaired = 0
    
    # Get treasury gold
    treasury = db.query(Treasury).first()
    if not treasury:
        return 0
    
    treasury_gold = treasury.gold_stored
    
    # Get current tick from WorldState
    from engine.models import WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find buildings that need repair (level < 3 and capacity > 0)
    buildings_to_repair = db.query(Building).filter(
        Building.level < 3,
        Building.capacity > 0
    ).all()
    
    for building in buildings_to_repair:
        if treasury_gold >= 30:
            # Spend 30 gold
            treasury.gold_stored -= 30
            treasury_gold -= 30
            
            # Increase building level
            building.level += 1
            
            # Create repair event
            event = Event(
                event_type='building_repair',
                description=f"Building {building.name} repaired",
                tick=current_tick,
                severity='info',
                affected_building_id=building.id
            )
            db.add(event)
            
            count_repaired += 1
    
    db.commit()
    return count_repaired


def calculate_upgrade_cost(db: Session, building_id: int) -> dict | None:
    """Calculate the cost to upgrade a building.
    
    Cost = level * 50
    Returns dict with building_id, current_level, cost, can_afford
    Returns None if building not found
    """
    from engine.models import Building, Treasury
    
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        return None
    
    cost = building.level * 50
    
    # Check Treasury for this building
    treasury = db.query(Treasury).filter(Treasury.building_id == building_id).first()
    can_afford = False
    if treasury:
        can_afford = treasury.gold_stored >= cost
    
    return {
        "building_id": building_id,
        "current_level": building.level,
        "cost": cost,
        "can_afford": can_afford
    }


def calculate_building_efficiency(db: Session) -> dict:
    """Calculate efficiency rating for all buildings with capacity > 0.
    
    Efficiency = workers / capacity (capped at 1.0)
    Returns dict of {building_id: efficiency}
    """
    from engine.models import Building, NPC
    
    result = {}
    
    # Get all buildings with capacity > 0
    buildings = db.query(Building).filter(Building.capacity > 0).all()
    
    for building in buildings:
        # Count NPCs working at this building
        workers = db.query(NPC).filter(NPC.work_building_id == building.id).count()
        
        # Calculate efficiency (capped at 1.0)
        efficiency = min(workers / building.capacity, 1.0)
        
        result[building.id] = efficiency
    
    return result


def decorate_building(db: Session, building_id: int, gold_amount: int) -> bool:
    """Decorate a building with gold."""
    from engine.models import Building, Treasury, Event, NPC, WorldState
    
    # Get the building
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        return False
    
    # Get treasury for this building
    treasury = db.query(Treasury).filter(Treasury.building_id == building_id).first()
    if not treasury or treasury.gold_stored < gold_amount:
        return False
    
    # Deduct gold from Treasury
    treasury.gold_stored -= gold_amount
    
    # Find nearby NPCs (distance <= 5)
    for npc in db.query(NPC).all():
        distance_sq = (building.x - npc.x) ** 2 + (building.y - npc.y) ** 2
        if distance_sq <= 25:  # 5^2 = 25
            npc.happiness += 2
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create event with required fields
    event = Event(
        event_type='building_decorated',
        description=f'Building {building.name} was decorated with {gold_amount} gold',
        tick=current_tick,
        severity='info',
        affected_building_id=building_id
    )
    db.add(event)
    
    db.commit()
    return True


def demolish_building(db: Session, building_id: int) -> bool:
    """Demolish a building if its capacity is 0.
    
    If capacity == 0:
    - Reassign workers/residents to homeless/unemployed state
    - Delete associated Resources
    - Delete the building
    - Return True
    
    If capacity > 0:
    - Return False (cannot demolish active building)
    """
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        return False
        
    if building.capacity > 0:
        return False
    
    # Reassign residents (home_building_id) to None
    db.query(NPC).filter(NPC.home_building_id == building_id).update({"home_building_id": None})
    
    # Reassign workers (work_building_id) to None
    db.query(NPC).filter(NPC.work_building_id == building_id).update({"work_building_id": None})
    
    # Delete associated Resources
    db.query(Resource).filter(Resource.building_id == building_id).delete()
    
    # Delete the building
    db.delete(building)
    db.commit()
    
    return True


def apply_infrastructure_decay(db: Session) -> int:
    """Apply infrastructure decay to buildings with level > 1."""
    from engine.models import Building, Event
    import random
    
    decayed_count = 0
    buildings = db.query(Building).filter(Building.level > 1).all()
    
    for building in buildings:
        if random.random() < 0.03:  # 3% chance
            building.level -= 1
            db.add(Event(event_type='infrastructure_decay'))
            decayed_count += 1
    
    db.commit()
    return decayed_count


def create_building_blueprint(db: Session, name: str, building_type: str, x: int, y: int) -> int | None:
    """Create a building blueprint at the given coordinates.
    
    Args:
        db: Database session
        name: Name of the building
        building_type: Type of building (civic, food, etc.)
        x: X coordinate
        y: Y coordinate
    
    Returns:
        New building id if successful, None if tile is occupied
    """
    from engine.models import Building
    
    # Check if tile is already occupied
    existing = db.query(Building).filter(Building.x == x, Building.y == y).first()
    if existing:
        return None
    
    # Create new building blueprint with capacity=0, level=0
    new_building = Building(
        name=name,
        building_type=building_type,
        x=x,
        y=y,
        capacity=0,
        level=0
    )
    db.add(new_building)
    db.commit()
    db.refresh(new_building)
    
    return new_building.id


def get_public_buildings(db: Session) -> list[dict]:
    """Get all public buildings (civic, market, church, tavern, hospital)."""
    from engine.models import Building
    
    public_types = ('civic', 'market', 'church', 'tavern', 'hospital')
    buildings = db.query(Building).filter(Building.building_type.in_(public_types)).all()
    
    return [
        {
            "id": b.id,
            "name": b.name,
            "type": b.building_type,
            "x": b.x,
            "y": b.y
        }
        for b in buildings
    ]


def get_production_multiplier(db: Session, building_id: int) -> float:
    """Calculate production multiplier for a building based on level and worker capacity."""
    from engine.models import Building, NPC
    
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        return 1.0
    
    # Base multiplier from level: 1.0 + (level-1)*0.25
    multiplier = 1.0 + (building.level - 1) * 0.25
    
    # Bonus if workers >= capacity and capacity > 0
    if building.capacity and building.capacity > 0:
        workers = db.query(NPC).filter(
            NPC.work_building_id == building_id,
            NPC.is_dead == 0
        ).count()
        
        if workers >= building.capacity:
            multiplier += 0.1
    
    return float(multiplier)


def calculate_fire_safety(db: Session) -> dict[int, int]:
    """Calculate fire safety rating for each building based on nearby guards."""
    from engine.models import Building, NPC
    
    buildings = db.query(Building).all()
    result = {}
    
    for building in buildings:
        guards = db.query(NPC).filter(
            NPC.role == "guard",
            NPC.is_dead == 0,
            (func.abs(NPC.x - building.x) + func.abs(NPC.y - building.y)) <= 5
        ).count()
        
        safety = min(100, guards * 25)
        result[building.id] = safety
    
    return result


def calculate_noise_levels(db: Session) -> dict[int, int]:
    """Calculate noise levels for all buildings.
    
    Tavern noise=3, market=2, others=0.
    For residential buildings: sum noise from buildings within distance 3.
    If > 3, residents happiness -= 2.
    Returns dict {building_id: noise}.
    """
    from engine.models import Building, NPC
    from math import sqrt
    
    # Define noise sources
    NOISE_SOURCES = {
        "tavern": 3,
        "market": 2
    }
    
    # Get all buildings
    buildings = db.query(Building).all()
    building_map = {b.id: b for b in buildings}
    
    # Calculate noise for each building
    noise_levels = {}
    
    for building in buildings:
        total_noise = 0
        
        # Check if this building is a noise source itself
        if building.building_type in NOISE_SOURCES:
            total_noise += NOISE_SOURCES[building.building_type]
        
        # If residential, check nearby noise sources
        if building.building_type == "residential":
            for other_building in buildings:
                if other_building.id == building.id:
                    continue
                
                # Calculate distance
                dx = other_building.x - building.x
                dy = other_building.y - building.y
                distance = sqrt(dx * dx + dy * dy)
                
                if distance <= 3 and other_building.building_type in NOISE_SOURCES:
                    total_noise += NOISE_SOURCES[other_building.building_type]
        
        noise_levels[building.id] = total_noise
        
        # Apply happiness penalty if noise > 3
        if building.building_type == "residential" and total_noise > 3:
            residents = db.query(NPC).filter(
                NPC.home_building_id == building.id,
                NPC.is_dead == 0
            ).all()
            
            for npc in residents:
                npc.happiness = max(0, npc.happiness - 2)
    
    db.commit()
    return noise_levels


def calculate_historical_value(db: Session) -> dict:
    """Calculate historical value/prestige for all buildings.
    
    prestige = level * 10 + min(WorldState.tick // 100, 50) per building.
    Returns dict with town_prestige total and per-building prestige.
    """
    from engine.models import Building, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    tick = world_state.tick if world_state else 0
    
    # Calculate prestige for each building
    buildings = db.query(Building).all()
    per_building = {}
    town_prestige = 0
    
    for building in buildings:
        prestige = building.level * 10 + min(tick // 100, 50)
        per_building[building.id] = {
            "name": building.name,
            "level": building.level,
            "prestige": prestige
        }
        town_prestige += prestige
    
    return {
        "town_prestige": town_prestige,
        "per_building": per_building
    }


def setup_market_stalls(db: Session) -> int:
    """Create market stalls for all living merchants."""
    from engine.models import Building, NPC, Resource

    # Find the market building
    market = db.query(Building).filter(Building.building_type == 'market').first()
    if not market:
        return 0

    # Find all living merchants
    merchants = db.query(NPC).filter(
        NPC.role == 'merchant',
        NPC.is_dead == 0
    ).all()

    stall_count = 0
    for merchant in merchants:
        stall = Resource(
            name=f"stall_{merchant.name}",
            quantity=1,
            building_id=market.id
        )
        db.add(stall)
        stall_count += 1

    db.commit()
    return stall_count


def upgrade_building_capacity(db: Session, building_id: int) -> int | None:
    """Upgrade building capacity. Cost = capacity * 10 from Treasury. If affordable: capacity += 5. Create Event(event_type='capacity_upgrade'). Return new capacity or None."""
    from engine.models import Building, Treasury, Event, WorldState
    from datetime import datetime, timezone
    
    building = db.query(Building).filter(Building.id == building_id).first()
    if not building:
        return None
    
    treasury = db.query(Treasury).filter(Treasury.building_id == building_id).first()
    if not treasury:
        return None
    
    cost = building.capacity * 10
    if treasury.gold_stored < cost:
        return None
    
    treasury.gold_stored -= cost
    building.capacity += 5
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        world_state = WorldState(tick=0)
        db.add(world_state)
        db.flush()
    
    event = Event(
        event_type='capacity_upgrade',
        description=f'Building {building.name} capacity upgraded to {building.capacity}',
        tick=world_state.tick,
        severity='info',
        affected_building_id=building_id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(event)
    db.commit()
    
    return building.capacity


def calculate_network_effects(db: Session) -> dict:
    """Calculate network effects for all buildings based on proximity."""
    from engine.models import Building
    
    buildings = db.query(Building).all()
    result: dict = {}
    
    for building in buildings:
        adjacent_count = 0
        for other in buildings:
            if building.id == other.id:
                continue
            distance = abs(building.x - other.x) + abs(building.y - other.y)
            if distance <= 5:
                adjacent_count += 1
        
        result[building.id] = {
            "adjacent": adjacent_count,
            "has_bonus": adjacent_count >= 3
        }
    
    return result


def repair_buildings(db: Session) -> int:
    """Repair damaged buildings where capacity < 10 if builders/blacksmiths work there."""
    from sqlalchemy.orm import Session
    from engine.models import Building, NPC, Event
    
    repair_count = 0
    
    # Get all damaged buildings (capacity < 10)
    damaged_buildings = db.query(Building).filter(Building.capacity < 10).all()
    
    for building in damaged_buildings:
        # Check if at least one NPC with role in ('builder', 'blacksmith') works here
        workers = db.query(NPC).filter(
            NPC.work_building_id == building.id,
            NPC.role.in_(['builder', 'blacksmith'])
        ).first()
        
        if workers:
            # Increase capacity by 1, cap at 10
            if building.capacity < 10:
                building.capacity += 1
                repair_count += 1
                
                # Create repair event
                event = Event(
                    event_type='building_repaired',
                    building_id=building.id,
                    description=f"Building {building.name} repaired (capacity now {building.capacity})"
                )
                db.add(event)
    
    return repair_count


def get_level_multiplier(building_level: int) -> float:
    """Calculate production multiplier based on building level.
    
    Args:
        building_level: The level of the building (1-5)
    
    Returns:
        float: Production multiplier (1.0 for level 1, up to 2.0 for level 5)
    
    Formula: 1.0 + (level - 1) * 0.25
    """
    return 1.0 + (building_level - 1) * 0.25


def check_housing_crisis(db: Session) -> int:
    """Check for housing crisis and apply effects to homeless NPCs."""
    from engine.models import NPC, Event, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Count homeless NPCs (home_building_id is None and not dead)
    homeless_count = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.home_building_id == None
    ).count()
    
    # Count total living NPCs
    total_population = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    # If homeless > 25% of population, create crisis event
    if total_population > 0 and homeless_count > 0.25 * total_population:
        # Create housing crisis event with required description
        event = Event(
            event_type='housing_crisis',
            description='Housing crisis detected - over 25% of population is homeless',
            severity='high',
            tick=current_tick
        )
        db.add(event)
        
        # Apply happiness penalty to all homeless NPCs
        homeless_npcs = db.query(NPC).filter(
            NPC.is_dead == 0,
            NPC.home_building_id == None
        ).all()
        
        for npc in homeless_npcs:
            npc.happiness = max(0, npc.happiness - 5)
    
    return homeless_count


def check_market_exists(db: Session) -> bool:
    """Check if any market building exists in the world."""
    from engine.models import Building
    from sqlalchemy import func
    
    count = db.query(func.count(Building.id)).filter(
        Building.building_type == 'market'
    ).scalar()
    
    return count > 0


def update_building_efficiency(db: Session) -> dict:
    """Update building efficiency based on worker count."""
    from engine.models import Building, NPC
    
    result = {}
    
    # Get all buildings
    buildings = db.query(Building).all()
    
    for building in buildings:
        # Count NPCs working at this building
        worker_count = db.query(NPC).filter(NPC.work_building_id == building.id).count()
        result[building.id] = worker_count
        
        # If no workers, mark as idle (only if not already marked)
        if worker_count == 0:
            if not building.name.lower().startswith("idle"):
                building.name = f"idle {building.name}"
        
        # If 3+ workers, building gets +2 effective capacity for production
        # This is tracked for production calculations (handled in production.py)
        if worker_count >= 3:
            # Production logic will apply the bonus
            pass
    
    db.commit()
    return result


def apply_crime_penalty(db: Session) -> int:
    """Apply crime penalty to buildings when crime is high."""
    from engine.models import Crime, Building, Event, WorldState
    
    # Count unresolved crimes (Postgres compatibility: use == 0, not == False)
    unresolved_crimes = db.query(Crime).filter(Crime.resolved == 0).count()
    
    if unresolved_crimes <= 5:
        return 0
    
    # Get all buildings with level > 1
    buildings = db.query(Building).filter(Building.level > 1).all()
    
    downgraded_count = 0
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    for building in buildings:
        # 5% chance to downgrade
        if random.random() < 0.05:
            building.level -= 1
            downgraded_count += 1
            
            # Create event for the damage
            event = Event(
                event_type="crime_damage",
                description="High crime damaged building infrastructure",
                tick=current_tick
            )
            db.add(event)
    
    return downgraded_count


def check_housing_pressure(db: Session) -> dict:
    """Check if population exceeds housing capacity."""
    from engine.models import NPC, Building, Event, WorldState
    
    # Count living NPCs (is_dead == 0 per Postgres compatibility)
    npc_count = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    # Sum capacity of residential buildings
    total_capacity = db.query(func.coalesce(func.sum(Building.capacity), 0)).filter(
        Building.building_type == "residential"
    ).scalar() or 0
    
    pressure = npc_count > total_capacity
    
    # Create event if there's pressure
    if pressure:
        # Get current tick from WorldState
        world_state = db.query(WorldState).first()
        current_tick = world_state.tick if world_state else 0
        
        event = Event(
            event_type="housing_pressure",
            description=f"{npc_count} residents but only {total_capacity} housing capacity",
            tick=current_tick
        )
        db.add(event)
        db.commit()
    
    return {
        "population": npc_count,
        "capacity": total_capacity,
        "pressure": pressure
    }


def trigger_rebuilding_boom(db: Session) -> int:
    """Fire triggers rebuilding boom - rebuild destroyed buildings."""
    from engine.models import Building, Treasury, Event, WorldState
    
    # Find destroyed buildings (capacity == 0)
    destroyed = db.query(Building).filter(Building.capacity == 0).all()
    
    rebuilt_count = 0
    for building in destroyed:
        # Rebuild the building
        building.capacity = 5
        building.level = 1
        
        # Deduct 30 gold from first Treasury
        treasury = db.query(Treasury).first()
        if treasury and treasury.gold >= 30:
            treasury.gold -= 30
        
        # Get current tick from WorldState
        world_state = db.query(WorldState).first()
        current_tick = world_state.tick if world_state else 0
        
        # Create rebuilding event
        event = Event(
            event_type="rebuilding",
            description=f"Rebuilt {building.name}",
            tick=current_tick,
            affected_building_id=building.id
        )
        db.add(event)
        
        rebuilt_count += 1
    
    return rebuilt_count


def apply_adjacency_bonus(db: Session) -> dict:
    """Calculate adjacency bonuses for all buildings.
    
    For each building, count other buildings within Manhattan distance 3.
    Returns dict mapping building name to neighbor count.
    """
    from engine.models import Building
    
    buildings = db.query(Building).all()
    result = {}
    
    for building in buildings:
        neighbor_count = 0
        for other in buildings:
            if other.id != building.id:
                distance = abs(building.x - other.x) + abs(building.y - other.y)
                if distance <= 3:
                    neighbor_count += 1
        result[building.name] = neighbor_count
    
    return result


def adjust_farm_output(db: Session) -> dict:
    """Adjust farm output based on season."""
    from engine.models import Building, Resource, WorldState
    
    # Get current season from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return {}
    
    day = world_state.day
    season = (day % 96) // 24
    
    # Seasonal multipliers
    multipliers = {
        0: 1.2,  # Spring
        1: 1.5,  # Summer
        2: 1.0,  # Autumn
        3: 0.5   # Winter
    }
    
    multiplier = multipliers.get(season, 1.0)
    
    # Find all food buildings
    food_buildings = db.query(Building).filter(Building.building_type == "food").all()
    
    result = {}
    for building in food_buildings:
        # Find Resource named "Food" at this building
        resource = db.query(Resource).filter(
            Resource.name == "Food",
            Resource.building_id == building.id
        ).first()
        
        if resource:
            new_quantity = int(resource.quantity * multiplier)
            resource.quantity = new_quantity
            result[building.name] = new_quantity
    
    return result


def check_mine_depletion(db: Session) -> int:
    """Check and process mine depletion for all mines."""
    from engine.models import Building, Resource, Event, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find all mine buildings
    mines = db.query(Building).filter(Building.building_type == "mine").all()
    
    depleted_count = 0
    
    for mine in mines:
        # Find Resource "Ore" at this building
        ore_resource = db.query(Resource).filter(
            Resource.resource_name == "Ore",
            Resource.building_id == mine.id
        ).first()
        
        if ore_resource and ore_resource.quantity > 0:
            # Reduce quantity by 1 (natural depletion)
            ore_resource.quantity -= 1
            
            # Check if depleted
            if ore_resource.quantity == 0:
                # Create depletion event
                event = Event(
                    event_type="mine_depleted",
                    description=f"{mine.name} ore deposits exhausted",
                    tick=current_tick,
                    affected_building_id=mine.id
                )
                db.add(event)
                depleted_count += 1
    
    return depleted_count


def collect_maintenance(db: Session) -> int:
    """Collect maintenance costs for all buildings with level > 1."""
    from engine.models import Building, Treasury
    
    buildings = db.query(Building).filter(Building.level > 1).all()
    treasury = db.query(Treasury).first()
    
    total_spent = 0
    
    for building in buildings:
        cost = building.level * 5
        
        if treasury and treasury.gold_stored >= cost:
            treasury.gold_stored -= cost
            total_spent += cost
        else:
            # Cannot pay maintenance, building decays
            if building.level > 1:
                building.level -= 1
                
    return total_spent


def accumulate_knowledge(db: Session) -> int:
    """Accumulate books in all libraries.
    
    For each library building, find or create a Books resource and increment
    its quantity by 1 per tick, capped at 100. Returns total books across all libraries.
    """
    from engine.models import Building, Resource
    
    total_books = 0
    
    # Find all library buildings
    libraries = db.query(Building).filter(Building.building_type == "library").all()
    
    for library in libraries:
        # Find existing Books resource for this library
        books_resource = db.query(Resource).filter(
            Resource.name == "Books",
            Resource.building_id == library.id
        ).first()
        
        if books_resource:
            # Increment quantity, cap at 100
            if books_resource.quantity < 100:
                books_resource.quantity += 1
            total_books += books_resource.quantity
        else:
            # Create new Books resource
            new_books = Resource(
                name="Books",
                building_id=library.id,
                quantity=1
            )
            db.add(new_books)
            total_books += 1
    
    db.commit()
    return total_books


def process_rehabilitation(db: Session) -> int:
    """Process prison rehabilitation for unresolved crimes."""
    from engine.models import Building, Crime, Event, WorldState
    
    rehabilitation_count = 0
    prisons = db.query(Building).filter(Building.building_type == "prison").all()
    
    for prison in prisons:
        unresolved_crimes = db.query(Crime).filter(Crime.resolved == 0).limit(3).all()
        
        for crime in unresolved_crimes:
            import random
            if random.random() < 0.2:
                crime.resolved = 1
                tick = db.query(WorldState).first().tick if db.query(WorldState).first() else 0
                
                event = Event(
                    event_type="rehabilitation",
                    description=f"Criminal rehabilitated at {prison.name}",
                    tick=tick,
                    affected_building_id=prison.id
                )
                db.add(event)
                rehabilitation_count += 1
    
    return rehabilitation_count


def apply_memorial_effect(db: Session) -> int:
    """Apply memorial effect from graveyards to nearby living NPCs."""
    from engine.models import Building, NPC
    import math
    
    affected_count = 0
    
    # Find all graveyard buildings
    graveyards = db.query(Building).filter(Building.building_type == "graveyard").all()
    
    if not graveyards:
        return 0
    
    # Get all living NPCs (is_dead == 0)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    if not living_npcs:
        return 0
    
    for graveyard in graveyards:
        for npc in living_npcs:
            # Calculate distance
            distance = math.sqrt((graveyard.x - npc.x) ** 2 + (graveyard.y - npc.y) ** 2)
            
            if distance <= 8:
                # Apply happiness bonus (max 100)
                npc.happiness = min(npc.happiness + 2, 100)
                affected_count += 1
    
    return affected_count


def detect_crimes_from_watchtower(db: Session) -> int:
    """Detect and resolve crimes from watchtowers."""
    from engine.models import Building, NPC, Crime
    import random
    
    resolved_count = 0
    
    # Find all watchtower buildings
    watchtowers = db.query(Building).filter(
        Building.building_type.in_(["watchtower", "guard_tower"])
    ).all()
    
    # Find all unresolved crimes
    unresolved_crimes = db.query(Crime).filter(Crime.resolved == 0).all()
    
    for watchtower in watchtowers:
        # Check if there's a guard NPC working at this watchtower
        guard = db.query(NPC).filter(
            NPC.work_building_id == watchtower.id,
            NPC.is_dead == 0
        ).first()
        
        if guard:
            # 30% chance per crime to resolve it
            for crime in unresolved_crimes:
                if random.random() < 0.30:
                    if crime.resolved == 0:
                        crime.resolved = 1
                        resolved_count += 1
    
    return resolved_count


def apply_windmill_bonus(db: Session) -> int:
    """Apply windmill grain bonus to nearby farms.
    
    Finds all windmill buildings, then finds all food/farm buildings within
    distance 5. For each nearby farm, adds 3 Wheat resources (grinding bonus).
    Returns total bonus wheat produced.
    """
    from engine.models import Building, Resource
    from sqlalchemy import func
    
    total_bonus = 0
    
    # Find all windmills
    windmills = db.query(Building).filter(Building.building_type == "windmill").all()
    
    for windmill in windmills:
        # Find all food/farm buildings within distance 5
        farms = db.query(Building).filter(
            (Building.building_type == "food") | (Building.building_type == "farm")
        ).all()
        
        for farm in farms:
            # Calculate distance (Euclidean)
            dx = windmill.x - farm.x
            dy = windmill.y - farm.y
            distance = (dx**2 + dy**2)**0.5
            
            if distance <= 5:
                # Find Wheat resource at this farm
                wheat_resource = db.query(Resource).filter(
                    Resource.building_id == farm.id,
                    Resource.resource_name == "Wheat"
                ).first()
                
                if wheat_resource:
                    # Add 3 wheat
                    wheat_resource.quantity = (wheat_resource.quantity or 0) + 3
                    total_bonus += 3
                else:
                    # Create new Wheat resource if it doesn't exist
                    new_wheat = Resource(
                        building_id=farm.id,
                        resource_name="Wheat",
                        quantity=3
                    )
                    db.add(new_wheat)
                    total_bonus += 3
    
    return total_bonus


def harvest_gardens(db: Session) -> int:
    """Harvest gardens and distribute food to nearby NPCs.
    
    For each garden building:
    - Find or create a Herbs resource
    - Add 2 quantity per garden
    - Reduce hunger by 5 for living NPCs within distance 5
    
    Returns count of gardens harvested.
    """
    from engine.models import Building, Resource, NPC
    from sqlalchemy import func
    
    # Find all garden buildings
    gardens = db.query(Building).filter(Building.building_type == "garden").all()
    
    for garden in gardens:
        # Find or create Herbs resource for this garden
        herb_resource = db.query(Resource).filter(
            Resource.name == "Herbs",
            Resource.building_id == garden.id
        ).first()
        
        if herb_resource is None:
            herb_resource = Resource(
                name="Herbs",
                building_id=garden.id,
                quantity=0
            )
            db.add(herb_resource)
        
        # Add 2 quantity per garden
        herb_resource.quantity += 2
        
        # Find nearby living NPCs (distance <= 5)
        nearby_npcs = db.query(NPC).filter(
            NPC.is_dead == 0,
            func.sqrt(
                func.pow(NPC.x - garden.x, 2) + 
                func.pow(NPC.y - garden.y, 2)
            ) <= 5
        ).all()
        
        # Reduce hunger for nearby NPCs (min 0)
        for npc in nearby_npcs:
            npc.hunger = max(0, npc.hunger - 5)
    
    return len(gardens)


def apply_warehouse_bonus(db: Session) -> int:
    """Apply production bonus for nearby buildings based on warehouse storage."""
    from engine.models import Building, Resource
    
    total_bonus_added = 0
    
    # Find all warehouses
    warehouses = db.query(Building).filter(Building.building_type == "warehouse").all()
    
    for warehouse in warehouses:
        # Count resources at this warehouse
        warehouse_resources = db.query(Resource).filter(Resource.building_id == warehouse.id).all()
        total_quantity = sum(r.quantity for r in warehouse_resources)
        
        if total_quantity > 50:
            # Find nearby buildings (distance <= 5)
            nearby_buildings = db.query(Building).filter(
                Building.id != warehouse.id
            ).all()
            
            for building in nearby_buildings:
                dx = building.x - warehouse.x
                dy = building.y - warehouse.y
                distance_sq = dx*dx + dy*dy
                
                if distance_sq <= 25:  # 5^2
                    # Find resources for this building and add bonus
                    building_resources = db.query(Resource).filter(Resource.building_id == building.id).all()
                    for res in building_resources:
                        bonus = int(res.quantity * 0.1)
                        if bonus > 0:
                            res.quantity += bonus
                            total_bonus_added += bonus
    
    db.commit()
    return total_bonus_added
