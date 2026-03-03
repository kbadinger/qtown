"""Simulation logic — pure functions that modify game state via the database."""

from sqlalchemy.orm import Session

from engine.models import Tile, Building, NPC, WorldState


def init_grid(db: Session) -> None:
    """Initialize the 50x50 tile grid.
    
    Creates 2500 Tile rows with x=0..49, y=0..49, terrain='grass'.
    Idempotent: calling twice will not duplicate rows.
    """
    # Check if grid already exists
    existing_count = db.query(Tile).count()
    if existing_count > 0:
        return

    # Create all 2500 tiles
    for x in range(50):
        for y in range(50):
            tile = Tile(x=x, y=y, terrain="grass")
            db.add(tile)
    
    db.commit()


def seed_buildings(db: Session) -> None:
    """Seed starter buildings into the town.
    
    Creates 3 buildings:
    - Town Hall (building_type='civic', x=25, y=25)
    - Farm (building_type='food', x=10, y=10)
    - House (building_type='residential', x=30, y=30)
    
    Idempotent: calling twice will not duplicate buildings.
    """
    # Check if buildings already exist
    existing_count = db.query(Building).count()
    if existing_count > 0:
        return

    # Create the 3 starter buildings
    buildings_data = [
        {"name": "Town Hall", "building_type": "civic", "x": 25, "y": 25},
        {"name": "Farm", "building_type": "food", "x": 10, "y": 10},
        {"name": "House", "building_type": "residential", "x": 30, "y": 30},
    ]

    for building_data in buildings_data:
        building = Building(**building_data)
        db.add(building)
    
    db.commit()


def seed_npcs(db: Session) -> None:
    """Seed starter NPCs into the town.
    
    Creates 5 NPCs with names and roles:
    - Farmer (role='farmer')
    - Baker (role='baker')
    - Guard (role='guard')
    - Merchant (role='merchant')
    - Priest (role='priest')
    
    Each NPC is placed at a valid grid position (0-49).
    Idempotent: calling twice will not duplicate NPCs.
    """
    # Check if NPCs already exist
    existing_count = db.query(NPC).count()
    if existing_count > 0:
        return

    # Create the 5 starter NPCs
    npcs_data = [
        {"name": "Tom", "role": "farmer", "x": 12, "y": 12},
        {"name": "Sarah", "role": "baker", "x": 15, "y": 15},
        {"name": "Jake", "role": "guard", "x": 20, "y": 20},
        {"name": "Lily", "role": "merchant", "x": 22, "y": 22},
        {"name": "Father Mike", "role": "priest", "x": 27, "y": 27},
    ]

    for npc_data in npcs_data:
        npc = NPC(**npc_data)
        db.add(npc)
    
    db.commit()


def process_tick(db: Session) -> int:
    """Advance the simulation by one tick.
    
    Increments WorldState.tick by 1 and returns the new tick number.
    Creates WorldState if it doesn't exist.
    """
    # Get or create world state
    world_state = db.query(WorldState).first()
    if not world_state:
        world_state = WorldState(tick=0)
        db.add(world_state)
    
    world_state.tick += 1
    db.commit()
    
    return world_state.tick