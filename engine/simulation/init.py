"""World initialization — seed buildings, NPCs, and grid."""

import json
import random
from sqlalchemy.orm import Session

from engine.models import NPC, Building, WorldState, Tile


def _generate_personality() -> str:
    """Generate a random personality JSON string for an NPC.
    
    Creates a dictionary with random boolean values for each trait:
    hardworking, lazy, social, greedy, brave, cautious.
    Returns the JSON string representation.
    """
    traits = ['hardworking', 'lazy', 'social', 'greedy', 'brave', 'cautious']
    personality = {}
    for trait in traits:
        personality[trait] = random.choice([True, False])
    return json.dumps(personality)


def init_world_state(db: Session) -> WorldState:
    """Initialize the world state idempotently.
    
    Creates exactly one WorldState row if none exists.
    Returns the existing or newly created WorldState.
    """
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
    existing = db.query(Tile).count()
    if existing > 0:
        return  # Already initialized
    
    for x in range(50):
        for y in range(50):
            db.add(Tile(x=x, y=y, terrain="grass"))
    db.commit()


def seed_buildings(db: Session) -> None:
    """Seed starter buildings into the town.

    Creates 3 buildings:
    - Town Hall (building_type='civic', x=25, y=25)
    - Farm (building_type='food', x=10, y=10)
    - House (building_type='residential', x=30, y=30)

    Idempotent: calling twice will not duplicate buildings.
    """
    existing = db.query(Building).count()
    if existing > 0:
        return

    buildings_data = [
        {"name": "Town Hall", "building_type": "civic", "x": 25, "y": 25},
        {"name": "Farm", "building_type": "food", "x": 10, "y": 10},
        {"name": "House", "building_type": "residential", "x": 30, "y": 30},
    ]

    for data in buildings_data:
        db.add(Building(**data))
    db.commit()


def seed_npcs(db: Session) -> None:
    """Seed starter NPCs into the town.

    Creates 5 NPCs with names and roles at valid grid positions.
    Each NPC is assigned a random personality trait JSON string.
    Idempotent: calling twice will not duplicate NPCs.
    """
    existing = db.query(NPC).count()
    if existing > 0:
        return

    npcs_data = [
        {"name": "Tom", "role": "farmer", "x": 12, "y": 12},
        {"name": "Sarah", "role": "baker", "x": 15, "y": 15},
        {"name": "Jake", "role": "guard", "x": 20, "y": 20},
        {"name": "Lily", "role": "merchant", "x": 22, "y": 22},
        {"name": "Father Mike", "role": "priest", "x": 27, "y": 27},
    ]

    for data in npcs_data:
        db.add(NPC(personality=_generate_personality(), **data))
    db.commit()
