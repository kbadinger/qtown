"""Simulation logic for Qwen Town.

All game state changes happen here. Functions take a db session and modify state.
"""

from sqlalchemy.orm import Session

from engine.models import Tile


def init_grid(db: Session) -> None:
    """Initialize the 50x50 tile grid.

    Creates 2500 Tile rows with x=0..49, y=0..49, terrain='grass'.
    Idempotent: calling twice will not duplicate rows.
    """
    # Check if grid already exists
    existing_count = db.query(Tile).count()
    if existing_count > 0:
        return

    # Create 50x50 grid
    for x in range(50):
        for y in range(50):
            db.add(Tile(x=x, y=y, terrain="grass"))

    db.commit()