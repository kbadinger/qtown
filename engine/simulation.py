"""Simulation logic — pure functions that modify game state via the database."""

from sqlalchemy.orm import Session

from engine.models import Tile, Building


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