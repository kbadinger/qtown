"""All simulation logic — pure functions that take db session and modify game state."""

import random
from sqlalchemy.orm import Session, joinedload

from engine.models import NPC, Building, WorldState, Tile, Resource, Treasury, Transaction, Event


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
    """Seed starter buildings into the town.

    Creates 3 buildings:
    - Town Hall (building_type='civic', x=25, y=25)
    - Farm (building_type='food', x=10, y=10)
    - House (building_type='residential', x=30, y=30)

    Idempotent: calling twice will not duplicate buildings.
    """
    existing = db.query(Building).count()
    if existing > 0:
        return

    buildings_data = [
        {"name": "Town Hall", "building_type": "civic", "x": 25, "y": 25},
        {"name": "Farm", "building_type": "food", "x": 10, "y": 10},
        {"name": "House", "building_type": "residential", "x": 30, "y": 30},
    ]

    for data in buildings_data:
        db.add(Building(**data))
    db.commit()


def seed_npcs(db: Session) -> None:
    """Seed starter NPCs into the town.

    Creates 5 NPCs with names and roles at valid grid positions.
    Idempotent: calling twice will not duplicate NPCs.
    """
    existing = db.query(NPC).count()
    if existing > 0:
        return

    npcs_data = [
        {"name": "Tom", "role": "farmer", "x": 12, "y": 12},
        {"name": "Sarah", "role": "baker", "x": 15, "y": 15},
        {"name": "Jake", "role": "guard", "x": 20, "y": 20},
        {"name": "Lily", "role": "merchant", "x": 22, "y": 22},
        {"name": "Father Mike", "role": "priest", "x": 27, "y": 27},
    ]

    for data in npcs_data:
        db.add(NPC(**data))
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


def produce_resources(db: Session, weather: str = None) -> None:
    """Produce resources for buildings of type 'food'."""
    food_buildings = db.query(Building).filter(Building.building_type == 'food').all()
    
    # Determine production amount based on weather
    base_production = 10
    if weather == 'rain':
        base_production = 12  # +20% bonus
    
    for building in food_buildings:
        resource = db.query(Resource).filter(
            Resource.name == 'Food',
            Resource.building_id == building.id
        ).first()
        
        if resource:
            resource.quantity += base_production
        else:
            new_resource = Resource(
                name='Food',
                quantity=base_production,
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


def update_weather(db: Session) -> None:
    """Update the weather in WorldState with weighted random selection.
    
    Weather options with weights:
    - clear: 40%
    - rain: 25%
    - storm: 10%
    - snow: 10%
    - fog: 15%
    """
    world_state = db.query(WorldState).first()
    if not world_state:
        return
    
    weather_options = ['clear', 'rain', 'storm', 'snow', 'fog']
    weights = [40, 25, 10, 10, 15]
    
    new_weather = random.choices(weather_options, weights=weights, k=1)[0]
    world_state.weather = new_weather
    
    db.commit()


def apply_weather_effects(db: Session) -> None:
    """Apply weather-specific effects to the simulation.
    
    Rain: farms produce +20% (12 instead of 10)
    Storm: random building takes damage (create damage Event)
    Snow: NPC movement halved (move every other tick)
    """
    world_state = db.query(WorldState).first()
    if not world_state:
        return
    
    weather = world_state.weather
    tick = world_state.tick
    
    if weather == 'rain':
        # Rain effect is handled in produce_resources by passing weather parameter
        pass
    
    elif weather == 'storm':
        # Storm: random building takes damage (create damage Event)
        buildings = db.query(Building).all()
        if buildings:
            damaged_building = random.choice(buildings)
            damage_event = Event(
                event_type='damage',
                description=f"Building {damaged_building.name} took damage from storm",
                tick=tick,
                severity='warning',
                affected_building_id=damaged_building.id
            )
            db.add(damage_event)
            db.commit()
    
    elif weather == 'snow':
        # Snow: NPC movement halved (move every other tick)
        # This is handled in process_tick by checking tick parity before moving NPCs
        pass


def calculate_happiness(db: Session, npc_id: int) -> int:
    """Calculate and update happiness for an NPC.
    
    Formula: happiness = 100 - hunger + (energy/2) + min(gold, 50)/2
    Clamped to range 0-100.
    
    Returns the calculated happiness value.
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return 50
    
    # Calculate happiness using the formula
    happiness = 100 - npc.hunger + (npc.energy // 2) + min(npc.gold, 50) // 2
    
    # Clamp to 0-100
    happiness = max(0, min(100, happiness))
    
    # Update the NPC's happiness field
    npc.happiness = happiness
    
    return happiness


def process_tick(db: Session) -> None:
    """Advance the simulation by one tick."""
    # 1. Update world state (time, weather)
    world_state = db.query(WorldState).first()
    if world_state:
        world_state.tick += 1
    
    # 2. Update weather
    update_weather(db)
    
    # 3. Apply weather effects
    apply_weather_effects(db)
    
    # 4. Process NPC needs (hunger, energy decay)
    npcs = db.query(NPC).all()
    for npc in npcs:
        # Hunger increases by 1 per tick
        npc.hunger = min(100, npc.hunger + 1)
        # Energy decreases by 1 per tick
        npc.energy = max(0, npc.energy - 1)
    
    # 5. Auto-eat: NPCs with hunger > 70 and gold >= 5
    for npc in npcs:
        if npc.hunger > 70 and npc.gold >= 5:
            npc.gold -= 5
            npc.hunger = max(0, npc.hunger - 30)

    # 6. Auto-sleep: NPCs with energy < 20
    for npc in npcs:
        if npc.energy < 20:
            npc.energy = min(100, npc.energy + 40)
    
    # 7. Movement (with snow effect: move every other tick)
    world_state = db.query(WorldState).first()
    current_weather = world_state.weather if world_state else None
    current_tick = world_state.tick if world_state else 0
    
    if current_weather != 'snow' or current_tick % 2 == 0:
        for npc in npcs:
            move_npc_toward_target(db, npc)
    
    # 8. Process production (farms, workshops)
    produce_resources(db, weather=current_weather)

    # 9. Process economy (trades, wages, taxes)
    process_work(db)

    # 10. Collect taxes every 10 ticks
    if world_state and world_state.tick % 10 == 0:
        collect_taxes(db)
    
    # 11. Population growth every 20 ticks
    if world_state and world_state.tick % 20 == 0:
        check_population_growth(db)
    
    # 12. Calculate happiness for all NPCs
    for npc in npcs:
        calculate_happiness(db, npc.id)

    db.commit()


def check_population_growth(db: Session) -> None:
    """Check conditions for population growth and spawn new NPC if eligible.
    
    If average NPC happiness > 60 and total NPC count < 100,
    spawn a new NPC with random name and role at a random valid position.
    """
    npcs = db.query(NPC).all()
    
    if not npcs:
        return
    
    # Calculate average happiness
    total_happiness = sum(npc.happiness for npc in npcs)
    avg_happiness = total_happiness / len(npcs)
    
    # Check if we can spawn a new NPC
    if avg_happiness > 60 and len(npcs) < 100:
        names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry", "Ivy", "Jack"]
        roles = ["farmer", "baker", "guard", "merchant", "priest"]
        
        # Find valid positions (not occupied by existing NPCs)
        existing_positions = set((npc.x, npc.y) for npc in npcs)
        valid_positions = [(x, y) for x in range(50) for y in range(50) if (x, y) not in existing_positions]
        
        if valid_positions:
            new_x, new_y = random.choice(valid_positions)
            
            new_npc = NPC(
                name=random.choice(names),
                role=random.choice(roles),
                x=new_x,
                y=new_y,
                gold=0,
                hunger=0,
                energy=100,
                happiness=50
            )
            
            db.add(new_npc)
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


def transfer_gold(db: Session, sender_id: int, receiver_id: int, amount: int) -> bool:
    """Transfer gold from sender to receiver.

    Deducts amount from sender's gold, adds to receiver's gold.
    Returns True on success, False if sender has insufficient funds.
    Also creates a Transaction record.
    """
    if amount <= 0:
        return False

    sender = db.query(NPC).filter(NPC.id == sender_id).first()
    receiver = db.query(NPC).filter(NPC.id == receiver_id).first()

    if not sender or not receiver:
        return False
    if sender.gold < amount:
        return False

    sender.gold -= amount
    receiver.gold += amount

    transaction = Transaction(
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount,
    )
    db.add(transaction)
    db.commit()
    return True


def assign_homes(db: Session) -> None:
    """Assign homes to NPCs without one.

    For each NPC without a home_building_id, find a residential building
    with capacity > current occupants and assign it.
    """
    homeless_npcs = db.query(NPC).filter(NPC.home_building_id == None).all()
    residential_buildings = db.query(Building).filter(
        Building.building_type == "residential"
    ).all()

    occupancy = {}
    for building in residential_buildings:
        occupancy[building.id] = (
            db.query(NPC).filter(NPC.home_building_id == building.id).count()
        )

    for npc in homeless_npcs:
        for building in residential_buildings:
            if occupancy.get(building.id, 0) < building.capacity:
                npc.home_building_id = building.id
                occupancy[building.id] += 1
                break

    db.commit()


def assign_work(db: Session) -> None:
    """Assign work buildings to NPCs without one.

    For each NPC without a work_building_id, find a non-residential building
    matching their role and assign it.
    """
    role_mapping = {
        "farmer": "food",
        "baker": "food",
        "guard": "guard",
        "merchant": "market",
        "priest": "religious",
    }

    unemployed_npcs = db.query(NPC).filter(NPC.work_building_id == None).all()

    for npc in unemployed_npcs:
        target_type = role_mapping.get(npc.role)
        if not target_type:
            continue

        building = db.query(Building).filter(
            Building.building_type == target_type,
            Building.building_type != "residential",
        ).first()

        if building:
            npc.work_building_id = building.id

    db.commit()


def eat(db: Session, npc_id: int) -> bool:
    """Allow an NPC to eat food.

    Reduces hunger by 30 (minimum 0). Costs 5 gold.
    Returns False if NPC not found or insufficient gold.
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    if npc.gold < 5:
        return False

    npc.gold -= 5
    npc.hunger = max(0, npc.hunger - 30)
    db.commit()
    return True


def sleep_npc(db: Session, npc_id: int) -> bool:
    """Allow an NPC to sleep.

    Restores energy by 40, capped at 100.
    Returns False if NPC not found.
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False

    npc.energy = min(100, npc.energy + 40)
    db.commit()
    return True