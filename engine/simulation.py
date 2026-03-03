"""All simulation logic — pure functions that take db session and modify game state."""

from sqlalchemy.orm import Session

from engine.models import WorldState


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
    from engine.models import Tile
    
    existing = db.query(Tile).count()
    if existing > 0:
        return  # Already initialized
    
    for x in range(50):
        for y in range(50):
            db.add(Tile(x=x, y=y, terrain="grass"))
    db.commit()


def process_tick(db: Session) -> None:
    """Advance the simulation by one tick."""
    # 1. Update world state (time, weather)
    # 2. Process NPC needs (hunger, energy decay)
    # 3. Process NPC decisions (eat, sleep, work, move)
    # 4. Process production (farms, workshops)
    # 5. Process economy (trades, wages, taxes)
    # 6. Log events
    pass