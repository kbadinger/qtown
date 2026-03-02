from sqlalchemy.orm import Session

from engine.models import Tile


def init_grid(db: Session) -> None:
    """Initialize the 50x50 tile grid."""
    # Idempotency check: if any tiles exist, grid is already initialized
    if db.query(Tile).count() > 0:
        return

    # Create 2500 tiles (50x50)
    for x in range(50):
        for y in range(50):
            db.add(Tile(x=x, y=y, terrain="grass"))

    db.commit()