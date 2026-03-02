"""Simulation logic — pure functions that modify game state via DB."""

from sqlalchemy.orm import Session


def init_grid(db: Session) -> None:
    """Initialize the 50x50 tile grid."""
    from engine.models import Tile

    existing_count = db.query(Tile).count()
    if existing_count > 0:
        return

    for x in range(50):
        for y in range(50):
            tile = Tile(x=x, y=y, terrain="grass")
            db.add(tile)

    db.commit()