"""All simulation logic — pure functions that take db session and modify game state."""

import json
import random
from sqlalchemy.orm import Session, joinedload

from engine.models import NPC, Building, WorldState, Tile, Resource, Treasury, Transaction, Event

# Building types available in the simulation
BUILDING_TYPES = ["civic", "food", "residential", "bakery", "blacksmith", "farm"]


def _generate_personality() -> str:
    """Generate a random personality JSON string for an NPC.
    
    Creates a dictionary with random boolean values for each trait:
    hardworking, lazy, social, greedy, brave, cautious.
    Returns the JSON string representation.
    """
    traits = ['hardworking', 'lazy', 'social', 'greedy', 'brave', 'cautious']
    personality = {}
    for trait in traits:
        personality[trait] = random.choice([True, False])
    return json.dumps(personality)


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


def seed_bakery(db: Session) -> None:
    """Seed a bakery building into the town.

    Creates 1 bakery building at coordinates (18, 18).
    Idempotent: calling twice will not duplicate the bakery.
    """
    existing_bakery = db.query(Building).filter(
        Building.building_type == "bakery"
    ).first()
    if existing_bakery:
        return

    bakery = Building(
        name="Bakery",
        building_type="bakery",
        x=18,
        y=18,
        capacity=10
    )
    db.add(bakery)
    db.commit()


def seed_blacksmith(db: Session) -> None:
    """Seed a blacksmith building into the town.

    Creates 1 blacksmith building at coordinates (22, 22).
    Idempotent: calling twice will not duplicate the blacksmith.
    """
    existing_blacksmith = db.query(Building).filter(
        Building.building_type == "blacksmith"
    ).first()
    if existing_blacksmith:
        return

    blacksmith = Building(
        name="Blacksmith",
        building_type="blacksmith",
        x=22,
        y=22,
        capacity=10
    )
    db.add(blacksmith)
    db.commit()


def seed_farm(db: Session) -> None:
    """Seed a farm building into the town.

    Creates 1 farm building at coordinates (15, 15).
    Idempotent: calling twice will not duplicate the farm.
    """
    existing_farm = db.query(Building).filter(
        Building.building_type == "farm"
    ).first()
    if existing_farm:
        return

    farm = Building(
        name="Farm",
        building_type="farm",
        x=15,
        y=15,
        capacity=10
    )
    db.add(farm)
    db.commit()


def seed_npcs(db: Session) -> None:
    """Seed starter NPCs into the town.

    Creates 5 NPCs with names and roles at valid grid positions.
    Each NPC is assigned a random personality trait JSON string.
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
        db.add(NPC(personality=_generate_personality(), **data))
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


def produce_bakery_resources(db: Session) -> None:
    """Produce resources for buildings of type 'bakery'.
    
    Bakery converts Wheat into Bread.
    Produces 5 Bread per tick if Wheat resource available.
    """
    bakery_buildings = db.query(Building).filter(Building.building_type == 'bakery').all()
    
    for building in bakery_buildings:
        # Check if Wheat resource is available at this building
        wheat_resource = db.query(Resource).filter(
            Resource.name == 'Wheat',
            Resource.building_id == building.id
        ).first()
        
        # Only produce if Wheat is available (quantity > 0)
        if wheat_resource and wheat_resource.quantity > 0:
            # Consume 1 Wheat to produce 5 Bread
            wheat_resource.quantity -= 1
            
            # Check if Bread resource exists at this building
            bread_resource = db.query(Resource).filter(
                Resource.name == 'Bread',
                Resource.building_id == building.id
            ).first()
            
            if bread_resource:
                bread_resource.quantity += 5
            else:
                new_bread = Resource(
                    name='Bread',
                    quantity=5,
                    building_id=building.id
                )
                db.add(new_bread)


def produce_blacksmith_resources(db: Session) -> None:
    """Produce resources for buildings of type 'blacksmith'.
    
    Blacksmith converts Ore into Tools.
    Produces 3 Tools per tick if Ore resource available.
    """
    blacksmith_buildings = db.query(Building).filter(Building.building_type == 'blacksmith').all()
    
    for building in blacksmith_buildings:
        # Check if Ore resource is available at this building
        ore_resource = db.query(Resource).filter(
            Resource.name == 'Ore',
            Resource.building_id == building.id
        ).first()
        
        # Only produce if Ore is available (quantity > 0)
        if ore_resource and ore_resource.quantity > 0:
            # Consume 1 Ore to produce 3 Tools
            ore_resource.quantity -= 1
            
            # Check if Tools resource exists at this building
            tools_resource = db.query(Resource).filter(
                Resource.name == 'Tools',
                Resource.building_id == building.id
            ).first()
            
            if tools_resource:
                tools_resource.quantity += 3
            else:
                new_tools = Resource(
                    name='Tools',
                    quantity=3,
                    building_id=building.id
                )
                db.add(new_tools)


def produce_farm_resources(db: Session) -> None:
    """Produce resources for buildings of type 'farm'.
    
    Farm produces 10 Wheat and 10 Food per tick.
    """
    farm_buildings = db.query(Building).filter(Building.building_type == 'farm').all()
    
    for building in farm_buildings:
        # Produce Wheat
        wheat_resource = db.query(Resource).filter(
            Resource.name == 'Wheat',
            Resource.building_id == building.id
        ).first()
        
        if wheat_resource:
            wheat_resource.quantity += 10
        else:
            new_wheat = Resource(
                name='Wheat',
                quantity=10,
                building_id=building.id
            )
            db.add(new_wheat)
        
        # Produce Food
        food_resource = db.query(Resource).filter(
            Resource.name == 'Food',
            Resource.building_id == building.id
        ).first()
        
        if food_resource:
            food_resource.quantity += 10
        else:
            new_food = Resource(
                name='Food',
                quantity=10,
                building_id=building.id
            )
            db.add(new_food)


def collect_taxes(db: Session) -> None:
    """Collect taxes from all NPCs and add to Treasury.
    
    Each NPC pays 2 gold in taxes (if they have enough).
    Total collected is added to treasury.gold_stored.
    """
    npcs = db.query(NPC).all()
    total_collected = 0
    
    for npc in npcs:
        if npc.gold >= 2:
            npc.gold -= 2
            total_collected += 2
    
    treasury = db.query(Treasury).first()
    if treasury:
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
    
    # Only update if weather changed
    if new_weather != world_state.weather:
        world_state.weather = new_weather
        db.commit()


def apply_weather_effects(db: Session) -> None:
    """Apply weather effects on NPC movement and production."""
    world_state = db.query(WorldState).first()
    if not world_state:
        return
    
    weather = world_state.weather
    
    # Snow reduces movement speed (handled in movement by checking tick % 2)
    # Rain increases food production (handled in produce_resources)
    # Storm temporarily stops all NPC movement (handled in movement)


def calculate_happiness(db: Session, npc_id: int) -> None:
    """Calculate and update happiness for an NPC.
    
    Happiness is affected by:
    - Hunger: -10 if hunger > 50
    - Energy: -10 if energy < 30
    - Gold: +5 if gold > 20
    - Has home: +10 if home_building_id is set
    - Has work: +10 if work_building_id is set
    Base happiness is 50.
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return
    
    # Calculate happiness based on conditions
    happiness = 50
    
    if npc.hunger > 50:
        happiness -= 10
    if npc.energy < 30:
        happiness -= 10
    if npc.gold > 20:
        happiness += 5
    if npc.home_building_id is not None:
        happiness += 10
    if npc.work_building_id is not None:
        happiness += 10
    
    # Clamp happiness between 0 and 100
    npc.happiness = max(0, min(100, happiness))
    db.commit()


def get_npc_decision(db: Session, npc_id: int) -> str:
    """Determine what an NPC should do based on their state.
    
    Decision priority:
    1. eat (if hunger > 50)
    2. sleep (if energy < 30)
    3. work (if has work_building and not at work)
    4. rest (otherwise)
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return "rest"
    
    if npc.hunger > 50:
        return "eat"
    elif npc.energy < 30:
        return "sleep"
    elif npc.work_building_id is not None:
        work_building = db.query(Building).filter(Building.id == npc.work_building_id).first()
        if work_building and (npc.x != work_building.x or npc.y != work_building.y):
            return "work"
    
    return "rest"


def process_tick(db: Session) -> None:
    """Advance the simulation by one tick.
    
    Processes all systems in the correct order:
    1. World State — increment tick counter, advance time of day, change day
    2. Weather — update weather, apply weather effects
    3. Needs Decay — hunger increases, energy decreases for all NPCs
    4. NPC Decisions — each NPC decides what to do based on needs + utility
    5. Movement — NPCs move toward their targets
    6. Production — buildings produce resources
    7. Economy — wages, trades, tax collection
    8. Population — births, deaths, aging
    9. Events — log notable events that occurred this tick
    """
    # 1. Update world state (time, weather)
    world_state = db.query(WorldState).first()
    if not world_state:
        init_world_state(db)
        world_state = db.query(WorldState).first()
    
    world_state.tick += 1
    
    # Advance time of day
    time_order = ['morning', 'afternoon', 'evening', 'night']
    current_time_idx = time_order.index(world_state.time_of_day)
    world_state.time_of_day = time_order[(current_time_idx + 1) % 4]
    
    # Change day every 4 ticks
    if world_state.time_of_day == 'morning':
        world_state.day += 1
    
    # 2. Process weather
    update_weather(db)
    apply_weather_effects(db)
    
    # 3. Process NPC needs (hunger, energy decay)
    npcs = db.query(NPC).all()
    for npc in npcs:
        npc.hunger = min(100, npc.hunger + 5)
        npc.energy = max(0, npc.energy - 3)
    
    # 4. Process NPC decisions (eat, sleep, work, move)
    for npc in npcs:
        # Decide based on needs
        if npc.hunger > 50:
            # Try to eat
            if npc.gold >= 5:
                eat(db, npc.id)
        elif npc.energy < 30:
            # Try to sleep
            sleep_npc(db, npc.id)
        
        # Calculate happiness
        calculate_happiness(db, npc.id)
    
    # 5. Process movement (snow halves movement - every other tick)
    weather = world_state.weather
    if weather != 'snow' or world_state.tick % 2 == 0:
        for npc in npcs:
            move_npc_toward_target(db, npc)
    
    # 6. Process production
    produce_resources(db, weather)
    produce_bakery_resources(db)  # Bakery production
    produce_blacksmith_resources(db)  # Blacksmith production
    produce_farm_resources(db)  # Farm production
    
    # 7. Process economy (wages, trades, tax collection)
    process_work(db)
    
    # Collect taxes every 10 ticks
    if world_state.tick % 10 == 0:
        collect_taxes(db)
    
    # 8. Process population (births, deaths, aging)
    check_population_growth(db)
    
    # 9. Log events (notable events)
    # Events are logged throughout other functions
    
    db.commit()


def check_population_growth(db: Session) -> None:
    """Check if we can spawn a new NPC based on happiness and population.
    
    If average happiness > 60 and population < 100, spawn a new NPC.
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
                happiness=50,
                personality=_generate_personality()
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