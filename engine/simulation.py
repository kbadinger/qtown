"""All simulation logic — pure functions that take db session and modify game state."""

from sqlalchemy.orm import Session

from engine.models import NPC, Building, WorldState, Tile


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
    """Seed the world with initial buildings for testing."""
    existing = db.query(Building).count()
    if existing > 0:
        return  # Already seeded
    
    buildings = [
        Building(name="Town Hall", building_type="town_hall", x=25, y=25, capacity=10),
        Building(name="Bakery", building_type="bakery", x=10, y=10, capacity=5),
        Building(name="House 1", building_type="house", x=5, y=5, capacity=4),
        Building(name="House 2", building_type="house", x=15, y=15, capacity=4),
    ]
    
    for building in buildings:
        db.add(building)
    db.commit()


def seed_npcs(db: Session) -> None:
    """Seed the world with initial NPCs for testing."""
    existing = db.query(NPC).count()
    if existing > 0:
        return  # Already seeded
    
    npcs = [
        NPC(name="Alice", role="merchant", x=5, y=5, gold=100, hunger=20, energy=80),
        NPC(name="Bob", role="farmer", x=10, y=10, gold=50, hunger=30, energy=90),
        NPC(name="Charlie", role="worker", x=15, y=15, gold=75, hunger=10, energy=100),
    ]
    
    for npc in npcs:
        db.add(npc)
    db.commit()


def move_npc_toward_target(db: Session, npc: NPC) -> None:
    """Move an NPC one step closer to its target position.
    
    If target_x/target_y are set, move 1 step closer per tick.
    If x < target_x, x += 1. If x > target_x, x -= 1. Same for y.
    Clamp to 0-49. Clear target when reached.
    """
    if npc.target_x is None or npc.target_y is None:
        return
    
    # Move towards target_x
    if npc.x < npc.target_x:
        npc.x += 1
    elif npc.x > npc.target_x:
        npc.x -= 1
    
    # Move towards target_y
    if npc.y < npc.target_y:
        npc.y += 1
    elif npc.y > npc.target_y:
        npc.y -= 1
    
    # Clamp to grid bounds (0-49)
    npc.x = max(0, min(49, npc.x))
    npc.y = max(0, min(49, npc.y))
    
    # Check if reached target
    if npc.x == npc.target_x and npc.y == npc.target_y:
        npc.target_x = None
        npc.target_y = None


def process_tick(db: Session) -> None:
    """Advance the simulation by one tick."""
    # 1. Update world state (time, weather)
    world_state = db.query(WorldState).first()
    if world_state:
        world_state.tick += 1
    
    # 2. Process NPC needs (hunger, energy decay)
    npcs = db.query(NPC).all()
    for npc in npcs:
        # Hunger increases by 1 per tick
        npc.hunger = min(100, npc.hunger + 1)
        # Energy decreases by 1 per tick
        npc.energy = max(0, npc.energy - 1)
    
    # 3. Process NPC decisions (eat, sleep, work, move)
    # Movement is handled here
    for npc in npcs:
        move_npc_toward_target(db, npc)
    
    # 4. Process production (farms, workshops)
    # 5. Process economy (trades, wages, taxes)
    # 6. Log events
    
    db.commit()