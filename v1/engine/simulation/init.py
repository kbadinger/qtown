"""World initialization — seed buildings, NPCs, and grid."""

import json
import random
from sqlalchemy.orm import Session

from engine.models import NPC, Building, WorldState, Tile
from engine.db import Base


def _generate_personality() -> str:
    """Generate a random personality JSON string for an NPC."""
    traits = ['hardworking', 'lazy', 'social', 'greedy', 'brave', 'cautious']
    personality = {}
    for trait in traits:
        personality[trait] = random.choice([True, False])
    return json.dumps(personality)


def init_world_state(db: Session) -> WorldState:
    """Initialize the world state idempotently."""
    existing = db.query(WorldState).first()
    if existing:
        return existing

    world_state = WorldState(
        tick=0,
        day=1,
        time_of_day="morning",
        weather=None
    )
    db.add(world_state)
    db.commit()
    db.refresh(world_state)
    return world_state


def init_grid(db: Session) -> None:
    """Initialize the 50x50 tile grid."""
    from engine.models import Tile
    
    # Check if grid already exists
    existing_count = db.query(Tile).count()
    if existing_count > 0:
        return  # Already initialized
    
    # Create all tiles
    for x in range(50):
        for y in range(50):
            tile = Tile(x=x, y=y, terrain="grass")
            db.add(tile)
    
    db.commit()


def _terrain_for(x: int, y: int) -> str:
    """Determine terrain type based on position for natural variety."""
    # Pond near fishing dock (SW area)
    if (x - 4) ** 2 + (y - 44) ** 2 <= 6:
        return "water"
    # Small lake in the east
    if (x - 38) ** 2 + (y - 40) ** 2 <= 4:
        return "water"
    # Forest patches in corners (away from 0,0 and 49,49 to not block paths)
    if 2 <= x <= 6 and 2 <= y <= 6:
        return "forest"
    if 43 <= x <= 47 and 43 <= y <= 47:
        return "forest"
    if 44 <= x <= 48 and 2 <= y <= 5:
        return "forest"
    # Dirt roads connecting buildings (cross pattern through center)
    if x == 25 and 10 <= y <= 40:
        return "dirt"
    if y == 25 and 10 <= x <= 40:
        return "dirt"
    # Sandy area near fishing dock
    if x < 8 and y > 43:
        return "sand"
    # Stone quarry area near mine
    if 40 <= x <= 44 and 6 <= y <= 10:
        return "stone"
    # Everything else is grass
    return "grass"


def seed_buildings(db: Session) -> None:
    """Seed starter buildings into the town.

    Creates 3 core buildings spread around the town center.
    Idempotent: calling twice will not duplicate buildings.
    """
    existing = db.query(Building).count()
    if existing > 0:
        return

    buildings_data = [
        {"name": "Town Hall", "building_type": "civic", "x": 25, "y": 25},
        {"name": "Farm", "building_type": "food", "x": 10, "y": 15},
        {"name": "House", "building_type": "residential", "x": 26, "y": 20},
    ]

    for data in buildings_data:
        db.add(Building(**data))
    db.commit()


# Role -> building_type mapping for work assignment
_ROLE_WORK_BUILDING = {
    "farmer": "food",
    "baker": "bakery",
    "guard": "guard_tower",
    "merchant": "bank",
    "priest": "church",
    "miner": "mine",
    "lumberjack": "lumber_mill",
    "fisherman": "fishing_dock",
    "artist": "theater",
    "bard": "tavern",
}


def assign_work_and_homes(db: Session) -> None:
    """Assign work buildings and homes to NPCs that don't have them."""
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()

    # Find the residential building for homes
    home_building = db.query(Building).filter(
        Building.building_type.in_(["residential", "civic"])
    ).first()

    for npc in npcs:
        # Assign work building based on role
        if not npc.work_building_id:
            target_type = _ROLE_WORK_BUILDING.get(npc.role)
            if target_type:
                building = db.query(Building).filter(
                    Building.building_type == target_type
                ).first()
                if building:
                    npc.work_building_id = building.id
                    # Move NPC near their workplace if they have no target
                    if npc.target_x is None:
                        npc.target_x = building.x
                        npc.target_y = building.y

        # Assign home building
        if not npc.home_building_id and home_building:
            npc.home_building_id = home_building.id

    db.commit()


def seed_npcs(db: Session) -> None:
    """Seed starter NPCs into the town.

    Creates 5 NPCs with names, roles, starting gold, and positions
    scattered near their workplaces. Idempotent.
    """
    existing = db.query(NPC).count()
    if existing > 0:
        return

    npcs_data = [
        {"name": "Tom", "role": "farmer", "x": 11, "y": 16, "gold": 50},
        {"name": "Sarah", "role": "baker", "x": 28, "y": 23, "gold": 50},
        {"name": "Jake", "role": "guard", "x": 44, "y": 6, "gold": 50},
        {"name": "Lily", "role": "merchant", "x": 31, "y": 25, "gold": 100},
        {"name": "Father Mike", "role": "priest", "x": 23, "y": 31, "gold": 30},
    ]

    for data in npcs_data:
        db.add(NPC(personality=_generate_personality(), **data))
    db.commit()
