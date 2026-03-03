"""All simulation logic — pure functions that take db session and modify game state."""

from sqlalchemy.orm import Session, joinedload

from engine.models import NPC, Building, WorldState, Tile, Resource, Treasury


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
        NPC(name="Diana", role="guard", x=25, y=24, gold=30, hunger=15, energy=95),
        NPC(name="Erik", role="priest", x=27, y=27, gold=20, hunger=5, energy=85),
    ]
    
    for npc in npcs:
        db.add(npc)
    db.commit()


def build_building(db: Session, name: str, building_type: str, x: int, y: int) -> Building:
    """Build a new building at the specified coordinates.
    
    Validates x,y are in 0-49 range. Creates a Building row.
    Returns the new Building object.
    Raises ValueError if coordinates out of range or occupied.
    """
    # Validate coordinates are in range
    if x < 0 or x > 49 or y < 0 or y > 49:
        raise ValueError(f"Coordinates ({x}, {y}) out of valid range (0-49)")
    
    # Check if tile is already occupied by another building
    existing_building = db.query(Building).filter(Building.x == x, Building.y == y).first()
    if existing_building:
        raise ValueError(f"Tile ({x}, {y}) is already occupied by {existing_building.name}")
    
    # Create the new building
    new_building = Building(
        name=name,
        building_type=building_type,
        x=x,
        y=y,
        capacity=10
    )
    
    db.add(new_building)
    db.commit()
    db.refresh(new_building)
    
    return new_building


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


def process_work(db: Session) -> None:
    """Process work earnings for NPCs at their work building.
    
    For each NPC that has a work_building_id and is at the same (x,y)
    as their work building, add 10 gold.
    """
    npcs = db.query(NPC).options(joinedload(NPC.work_building)).filter(NPC.work_building_id.isnot(None)).all()
    
    for npc in npcs:
        building = npc.work_building
        if building and npc.x == building.x and npc.y == building.y:
            npc.gold += 10


def produce_resources(db: Session) -> None:
    """Produce resources for buildings of type 'food'."""
    food_buildings = db.query(Building).filter(Building.building_type == 'food').all()
    
    for building in food_buildings:
        resource = db.query(Resource).filter(
            Resource.name == 'Food',
            Resource.building_id == building.id
        ).first()
        
        if resource:
            resource.quantity += 10
        else:
            new_resource = Resource(
                name='Food',
                quantity=10,
                building_id=building.id
            )
            db.add(new_resource)


def collect_taxes(db: Session) -> None:
    """Collect 10% taxes from all NPCs and add to Treasury.
    
    Takes floor(10%) of each NPC's gold and adds it to the Treasury.
    If no Treasury exists, creates one linked to Town Hall.
    """
    # Find or create Treasury
    treasury = db.query(Treasury).first()
    if not treasury:
        # Find Town Hall building
        town_hall = db.query(Building).filter(Building.name == "Town Hall").first()
        if town_hall:
            treasury = Treasury(
                gold_stored=0,
                building_id=town_hall.id
            )
            db.add(treasury)
            db.commit()
            db.refresh(treasury)
        else:
            return  # No Town Hall, cannot create Treasury
    
    # Collect taxes from all NPCs
    npcs = db.query(NPC).all()
    total_collected = 0
    
    for npc in npcs:
        tax_amount = npc.gold // 10  # floor of 10%
        if tax_amount > 0:
            npc.gold -= tax_amount
            total_collected += tax_amount
    
    # Add collected taxes to Treasury
    if total_collected > 0:
        treasury.gold_stored += total_collected
    
    db.commit()


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
    produce_resources(db)
    
    # 5. Process economy (trades, wages, taxes)
    process_work(db)
    
    # 6. Collect taxes every 10 ticks
    if world_state and world_state.tick % 10 == 0:
        collect_taxes(db)
    
    # 7. Log events
    
    db.commit()


def buy_food(db: Session, npc_id: int) -> bool:
    """Allow an NPC to buy food from any building.
    
    NPC spends 5 gold, hunger decreases by 30 (min 0).
    Requires a Food resource with quantity >= 1 at any building.
    Decrements food quantity by 1.
    Returns False if no food or insufficient gold.
    """
    # Get the NPC
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    # Check if NPC has enough gold
    if npc.gold < 5:
        return False
    
    # Find a Food resource with quantity >= 1 at any building
    food_resource = db.query(Resource).filter(
        Resource.name == 'Food',
        Resource.quantity >= 1
    ).first()
    
    if not food_resource:
        return False
    
    # Execute the purchase
    npc.gold -= 5
    npc.hunger = max(0, npc.hunger - 30)
    food_resource.quantity -= 1
    
    db.commit()
    return True