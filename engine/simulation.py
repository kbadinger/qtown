"""Simulation logic — pure functions that modify game state via the database."""

from sqlalchemy.orm import Session

from engine.models import Tile, Building, NPC, WorldState, Transaction


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
    Updates all NPC hunger (+5, max 100) and energy (-3, min 0).
    Creates WorldState if it doesn't exist.
    """
    # Get or create world state
    world_state = db.query(WorldState).first()
    if not world_state:
        world_state = WorldState(tick=0)
        db.add(world_state)
    
    world_state.tick += 1
    
    # Update all NPC hunger and energy
    npcs = db.query(NPC).all()
    for npc in npcs:
        npc.hunger = min(100, npc.hunger + 5)
        npc.energy = max(0, npc.energy - 3)
    
    db.commit()
    
    return world_state.tick


def transfer_gold(db: Session, sender_id: int, receiver_id: int, amount: int) -> bool:
    """Transfer gold from sender to receiver.
    
    Deducts amount from sender's gold, adds to receiver's gold.
    Returns True on success, False if sender has insufficient funds.
    Also creates a Transaction record.
    
    Args:
        db: Database session
        sender_id: ID of the sender NPC
        receiver_id: ID of the receiver NPC
        amount: Amount of gold to transfer (must be positive)
    
    Returns:
        True if transfer succeeded, False otherwise
    """
    # Validate amount is positive
    if amount <= 0:
        return False
    
    # Get sender and receiver
    sender = db.query(NPC).filter(NPC.id == sender_id).first()
    receiver = db.query(NPC).filter(NPC.id == receiver_id).first()
    
    # Check if both NPCs exist
    if not sender or not receiver:
        return False
    
    # Check if sender has sufficient funds
    if sender.gold < amount:
        return False
    
    # Perform the transfer
    sender.gold -= amount
    receiver.gold += amount
    
    # Create transaction record
    transaction = Transaction(
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount
    )
    db.add(transaction)
    
    db.commit()
    
    return True


def assign_homes(db: Session) -> None:
    """Assign homes to NPCs without one.
    
    For each NPC without a home_building_id, find a residential building 
    with capacity > current occupants and assign it.
    """
    # Find homeless NPCs
    homeless_npcs = db.query(NPC).filter(NPC.home_building_id == None).all()
    
    # Find residential buildings
    residential_buildings = db.query(Building).filter(Building.building_type == 'residential').all()
    
    # Calculate current occupancy for each residential building
    occupancy = {}
    for building in residential_buildings:
        occupancy[building.id] = db.query(NPC).filter(NPC.home_building_id == building.id).count()
    
    # Assign homes
    for npc in homeless_npcs:
        for building in residential_buildings:
            if occupancy.get(building.id, 0) < building.capacity:
                npc.home_building_id = building.id
                occupancy[building.id] += 1
                break
    
    db.commit()