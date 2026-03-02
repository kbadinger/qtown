from sqlalchemy.orm import Session


def init_grid(db: Session) -> None:
    """Initialize the 50x50 tile grid."""
    from engine.models import Tile

    # Idempotency check: do nothing if grid exists
    if db.query(Tile).count() > 0:
        return

    tiles = []
    for x in range(50):
        for y in range(50):
            tiles.append(Tile(x=x, y=y, terrain="grass"))

    db.add_all(tiles)
    db.commit()