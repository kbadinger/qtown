"""All simulation logic — pure functions that take db session and modify game state."""

import json
import random
import math
from sqlalchemy.orm import Session, joinedload

from engine.models import NPC, Building, WorldState, Tile, Resource, Treasury, Transaction, Event
from sqlalchemy.orm import Session
from engine.models import (
Tile, NPC, Building, Resource, WorldState, Treasury, Event, Transaction
)
from engine.models import Relationship

# Building types available in the simulation
BUILDING_TYPES = [
    'residential',
    'food',
    'guard',
    'market',
    'religious',
    'school',
    'hospital',
    'tavern',
    'library',
    'bakery',
    'blacksmith',
    'farm',
    'church',
    'mine',
    'lumber_mill',
    'fishing_dock',
    'guard_tower',
    'wall',
    'gate',
    'fountain',
    'well',
    'warehouse',
    'bank',
    'theater',
    'arena',
    'prison',
    'graveyard',
    'garden',
    'watchtower',
    'health',
    'entertainment',
    'economic',
    'infrastructure',
    'windmill',
]


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


def seed_all_buildings(db: Session) -> None:
    """Call every seed_* function in this module. All are idempotent.

    Auto-discovers functions matching seed_*(db) so new building types
    added by Qwen are picked up without editing this function.
    """
    import sys
    module = sys.modules[__name__]
    for name in sorted(dir(module)):
        if name.startswith("seed_") and name != "seed_all_buildings":
            fn = getattr(module, name)
            if callable(fn):
                fn(db)


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


def seed_church(db: Session) -> None:
    """Seed a church building into the town.

    Creates 1 church building at coordinates (35, 35).
    Idempotent: calling twice will not duplicate the church.
    """
    existing_church = db.query(Building).filter(
        Building.building_type == "church"
    ).first()
    if existing_church:
        return

    church = Building(
        name="Church",
        building_type="church",
        x=35,
        y=35,
        capacity=10
    )
    db.add(church)
    db.commit()


def seed_school(db: Session) -> None:
    """Seed school building idempotently.
    
    Creates one school if none exists.
    """
    existing = db.query(Building).filter(Building.building_type == "school").first()
    if existing:
        return
    
    db.add(Building(name="School", building_type="school", x=25, y=35, capacity=30))
    db.commit()


def seed_hospital(db: Session) -> None:
    """Seed a hospital building into the town.

    Creates 1 hospital building at coordinates (28, 28).
    Idempotent: calling twice will not duplicate the hospital.
    """
    existing_hospital = db.query(Building).filter(
        Building.building_type == "hospital"
    ).first()
    if existing_hospital:
        return

    hospital = Building(
        name="Hospital",
        building_type="hospital",
        x=28,
        y=28,
        capacity=10
    )
    db.add(hospital)
    db.commit()


def seed_tavern(db: Session) -> None:
    """Seed a tavern building into the town.

    Creates 1 tavern building at coordinates (40, 40).
    Idempotent: calling twice will not duplicate the tavern.
    """
    existing_tavern = db.query(Building).filter(
        Building.building_type == "tavern"
    ).first()
    if existing_tavern:
        return

    tavern = Building(
        name="Tavern",
        building_type="tavern",
        x=40,
        y=40,
        capacity=10
    )
    db.add(tavern)
    db.commit()


def seed_library(db: Session) -> None:
    """Seed a library building into the town.

    Creates 1 library building at coordinates (20, 20).
    Idempotent: calling twice will not duplicate the library.
    """
    existing_library = db.query(Building).filter(Building.building_type == "library").first()
    if existing_library:
        return

    db.add(Building(name="Library", building_type="library", x=20, y=20))
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
    For farmers, also produce 10 Food at their work building.
    For bakers, convert Wheat into Bread at Bakery buildings, producing 5 Bread per tick.
    For blacksmiths, convert Ore into Tools at Blacksmith buildings, producing 3 Tools per tick.
    For priests, increase happiness of all NPCs within radius 10 by 5.
    For miners, produce 8 Ore at their work building.
    For lumberjacks, produce 8 Wood at their work building.
    For fishermen, produce 6 Fish at their work building.
    For artists, produce 2 Art at Theater buildings and boost nearby happiness by 5.
    For bards, wander between Tavern and Theater, boosting happiness of nearby NPCs by 8 per tick.
    For thieves, steal 5-15 gold from random NPCs at night.
    """
    # Get current time of day
    world_state = db.query(WorldState).first()
    is_night = world_state.time_of_day == "night" if world_state else False
    
    npcs = db.query(NPC).options(joinedload(NPC.work_building)).filter(NPC.work_building_id.isnot(None)).all()
    
    for npc in npcs:
        building = npc.work_building
        if building and npc.x == building.x and npc.y == building.y:
            # All NPCs earn 10 gold at work
            npc.gold += 10
            
            # Thieves steal gold at night
            if npc.role == "thief" and is_night:
                # Find potential victims with gold (excluding the thief themselves)
                victims = db.query(NPC).filter(
                    NPC.id != npc.id,
                    NPC.gold > 0
                ).all()
                
                if victims:
                    # Pick a random victim
                    victim = random.choice(victims)
                    # Steal 5-15 gold (capped by victim's available gold)
                    steal_amount = random.randint(5, 15)
                    steal_amount = min(steal_amount, victim.gold)
                    
                    if steal_amount > 0:
                        victim.gold -= steal_amount
                        npc.gold += steal_amount
            
            # Farmers produce 10 Food at their work building
            if npc.role == "farmer":
                # Find existing Food resource at this building or create new one
                food = db.query(Resource).filter(
                    Resource.name == "Food",
                    Resource.building_id == building.id
                ).first()
                
                if food:
                    food.quantity += 10
                else:
                    db.add(Resource(
                        name="Food",
                        quantity=10,
                        building_id=building.id
                    ))
            
            # Bakers convert Wheat into Bread at Bakery buildings
            if npc.role == "baker" and building.building_type == "bakery":
                # Check if there's Wheat available at the bakery
                wheat = db.query(Resource).filter(
                    Resource.name == "Wheat",
                    Resource.building_id == building.id
                ).first()
                
                if wheat and wheat.quantity >= 5:
                    # Consume 5 Wheat to produce 5 Bread
                    wheat.quantity -= 5
                    
                    # Find existing Bread resource at this building or create new one
                    bread = db.query(Resource).filter(
                        Resource.name == "Bread",
                        Resource.building_id == building.id
                    ).first()
                    
                    if bread:
                        bread.quantity += 5
                    else:
                        db.add(Resource(
                            name="Bread",
                            quantity=5,
                            building_id=building.id
                        ))
            
            # Blacksmiths convert Ore into Tools at Blacksmith buildings
            if npc.role == "blacksmith" and building.building_type == "blacksmith":
                # Check if there's Ore available at the blacksmith
                ore = db.query(Resource).filter(
                    Resource.name == "Ore",
                    Resource.building_id == building.id
                ).first()
                
                if ore and ore.quantity >= 1:
                    # Consume 1 Ore to produce 3 Tools
                    ore.quantity -= 1
                    
                    # Find existing Tools resource at this building or create new one
                    tools = db.query(Resource).filter(
                        Resource.name == "Tools",
                        Resource.building_id == building.id
                    ).first()
                    
                    if tools:
                        tools.quantity += 3
                    else:
                        db.add(Resource(
                            name="Tools",
                            quantity=3,
                            building_id=building.id
                        ))
            
            # Priests increase happiness of all NPCs within radius 10
            if npc.role == "priest" and building.building_type == "church":
                # Load all NPCs to check distance in Python (SQLAlchemy doesn't support ** operator in filters)
                all_npcs = db.query(NPC).all()
                
                for nearby_npc in all_npcs:
                    # Calculate squared distance (avoid sqrt for efficiency)
                    distance_sq = (nearby_npc.x - building.x) ** 2 + (nearby_npc.y - building.y) ** 2
                    if distance_sq <= 100:  # radius 10 squared
                        nearby_npc.happiness += 5
            
            # Miners produce 8 Ore at their work building
            if npc.role == "miner" and building.building_type == "mine":
                # Find existing Ore resource at this building or create new one
                ore = db.query(Resource).filter(
                    Resource.name == "Ore",
                    Resource.building_id == building.id
                ).first()
                
                if ore:
                    ore.quantity += 8
                else:
                    db.add(Resource(
                        name="Ore",
                        quantity=8,
                        building_id=building.id
                    ))
            
            # Lumberjacks produce 8 Wood at their work building
            if npc.role == "lumberjack" and building.building_type == "lumber_mill":
                # Find existing Wood resource at this building or create new one
                wood = db.query(Resource).filter(
                    Resource.name == "Wood",
                    Resource.building_id == building.id
                ).first()
                
                if wood:
                    wood.quantity += 8
                else:
                    db.add(Resource(
                        name="Wood",
                        quantity=8,
                        building_id=building.id
                    ))
            
            # Fishermen produce 6 Fish at their work building
            if npc.role == "fisherman" and building.building_type == "fishing_dock":
                # Find existing Fish resource at this building or create new one
                fish = db.query(Resource).filter(
                    Resource.name == "Fish",
                    Resource.building_id == building.id
                ).first()
                
                if fish:
                    fish.quantity += 6
                else:
                    db.add(Resource(
                        name="Fish",
                        quantity=6,
                        building_id=building.id
                    ))
            
            # Artists produce 2 Art at Theater buildings and boost nearby happiness by 5
            if npc.role == "artist" and building.building_type == "theater":
                # Produce 2 Art at the theater
                art = db.query(Resource).filter(
                    Resource.name == "Art",
                    Resource.building_id == building.id
                ).first()
                
                if art:
                    art.quantity += 2
                else:
                    db.add(Resource(
                        name="Art",
                        quantity=2,
                        building_id=building.id
                    ))
                
                # Boost happiness of all NPCs within radius 10
                all_npcs = db.query(NPC).all()
                
                for nearby_npc in all_npcs:
                    # Calculate squared distance (avoid sqrt for efficiency)
                    distance_sq = (nearby_npc.x - building.x) ** 2 + (nearby_npc.y - building.y) ** 2
                    if distance_sq <= 100:  # radius 10 squared
                        nearby_npc.happiness += 5
            
            # Bards boost happiness of nearby NPCs by 8 when at Tavern or Theater
            if npc.role == "bard" and building.building_type in ("tavern", "theater"):
                # Load all NPCs to check distance in Python
                all_npcs = db.query(NPC).all()
                
                for nearby_npc in all_npcs:
                    # Calculate squared distance (avoid sqrt for efficiency)
                    distance_sq = (nearby_npc.x - building.x) ** 2 + (nearby_npc.y - building.y) ** 2
                    if distance_sq <= 100:  # radius 10 squared
                        nearby_npc.happiness += 8
    
    db.commit()


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


def produce_library_resources(db: Session) -> None:
    """Produce resources for buildings of type 'library'.
    
    Library produces 2 Books per tick.
    """
    library_buildings = db.query(Building).filter(Building.building_type == 'library').all()
    
    for building in library_buildings:
        # Produce Books
        books_resource = db.query(Resource).filter(
            Resource.name == 'Books',
            Resource.building_id == building.id
        ).first()
        
        if books_resource:
            books_resource.quantity += 2
        else:
            new_books = Resource(
                name='Books',
                quantity=2,
                building_id=building.id
            )
            db.add(new_books)


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


def process_hospital(db: Session) -> None:
    """Process hospital effects on NPCs.
    
    NPCs assigned to hospital buildings (work_building_id pointing to hospital)
    have their health improved (placeholder for future illness system).
    Currently increases happiness by 5 for NPCs at hospital.
    """
    hospitals = db.query(Building).filter(Building.building_type == "hospital").all()
    
    for hospital in hospitals:
        # Get NPCs assigned to this hospital
        patient_npcs = db.query(NPC).filter(NPC.work_building_id == hospital.id).all()
        
        for npc in patient_npcs:
            # Heal effect: increase happiness (placeholder for illness system)
            npc.happiness = min(100, npc.happiness + 5)
            
            # Log healing event
            event = Event(
                event_type="healing",
                description=f"{npc.name} received healing at {hospital.name}",
                tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                severity="info",
                affected_npc_id=npc.id,
                affected_building_id=hospital.id
            )
            db.add(event)
    
    db.commit()


def process_tavern(db: Session) -> None:
    """Process tavern effects on NPCs.
    
    NPCs assigned to tavern buildings (work_building_id pointing to tavern)
    gain energy and happiness.
    Increases energy by 20 and happiness by 10 for NPCs at tavern.
    """
    taverns = db.query(Building).filter(Building.building_type == "tavern").all()
    
    for tavern in taverns:
        # Get NPCs assigned to this tavern
        visitor_npcs = db.query(NPC).filter(NPC.work_building_id == tavern.id).all()
        
        for npc in visitor_npcs:
            # Tavern effect: increase energy and happiness
            npc.energy = min(100, npc.energy + 20)
            npc.happiness = min(100, npc.happiness + 10)
            
            # Log tavern visit event
            event = Event(
                event_type="tavern_visit",
                description=f"{npc.name} visited {tavern.name}",
                tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                severity="info",
                affected_npc_id=npc.id,
                affected_building_id=tavern.id
            )
            db.add(event)
    
    db.commit()


def visit_tavern(db: Session, npc_id: int) -> bool:
    """Allow an NPC to visit a tavern.
    
    NPC spends 3 gold, gains +20 energy (capped at 100) and +10 happiness.
    Requires a tavern building to exist.
    Returns False if no tavern or insufficient gold.
    """
    # Get the NPC
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    # Check if NPC has enough gold
    if npc.gold < 3:
        return False
    
    # Find a tavern
    tavern = db.query(Building).filter(Building.building_type == "tavern").first()
    if not tavern:
        return False
    
    # Execute the visit
    npc.gold -= 3
    npc.energy = min(100, npc.energy + 20)
    npc.happiness = min(100, npc.happiness + 10)
    
    # Log tavern visit event
    event = Event(
        event_type="tavern_visit",
        description=f"{npc.name} visited {tavern.name}",
        tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
        severity="info",
        affected_npc_id=npc.id,
        affected_building_id=tavern.id
    )
    db.add(event)
    
    db.commit()
    return True


def process_tick(db: Session) -> None:
    """Advance the simulation by one tick.
    
    Processes all game systems in order:
    1. World State — time, weather
    2. NPC Needs — hunger, energy decay
    3. NPC Decisions — eat, sleep, work, move
    4. Movement — NPCs move toward targets
    5. Production — buildings produce resources
    6. Economy — wages, trades, tax collection
    7. Population — births, deaths, aging
    8. Events — log notable events
    """
    # 0. Ensure all building types are seeded (idempotent)
    seed_all_buildings(db)

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
    npcs = db.query(NPC).filter(NPC.is_dead == False).all()
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
    produce_library_resources(db)  # Library production
    produce_mine_resources(db)  # Mine production
    produce_lumber_mill_resources(db)  # Lumber Mill production
    produce_fishing_dock_resources(db)  # Fishing Dock production
    produce_guard_tower_resources(db)  # Guard Tower production
    produce_gate_resources(db)  # Gate production
    produce_well_resources(db)  # Well production
    produce_warehouse_resources(db)  # Warehouse production
    produce_bank_resources(db)  # Bank production
    produce_theater_resources(db)  # Theater production
    process_hospital(db)  # Hospital healing
    process_tavern(db)  # Tavern effects
    
    # 7. Process economy (wages, trades, tax collection)
    process_work(db)
    
    # Collect taxes every 10 ticks
    if world_state.tick % 10 == 0:
        collect_taxes(db)
    
    # 8. Process population (births, deaths, aging)
    check_population_growth(db)
    
    # Age NPCs every 100 ticks
    if world_state.tick % 100 == 0:
        age_npcs(db)
    
    # 9. Log events (notable events)
    # Events are logged throughout other functions
    
    # Process school skill gains every 5 ticks
    if world_state.tick % 5 == 0:
        process_school_skill_gain(db)
    
    # Apply church effects
    apply_church_effects(db)
    
    # Apply fountain effects
    apply_fountain_effects(db)
    
    # Update relationships
    update_relationships(db)
    
    # Check for marriages every 50 ticks
    if world_state.tick % 50 == 0:
        check_marriage(db)
    
    db.commit()


def process_school_skill_gain(db: Session) -> None:
    """Process skill gain for NPCs assigned to school buildings.
    
    NPCs with work_building_id pointing to a school building gain +1 skill.
    """
    schools = db.query(Building).filter(Building.building_type == "school").all()
    
    for school in schools:
        # Get NPCs assigned to this school
        student_npcs = db.query(NPC).filter(NPC.work_building_id == school.id).all()
        
        for npc in student_npcs:
            # NPC gains +1 skill
            npc.skill += 1
            
            # Log skill gain event
            event = Event(
                event_type="skill_gain",
                description=f"{npc.name} gained skill at {school.name}",
                tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                severity="info",
                affected_npc_id=npc.id,
                affected_building_id=school.id
            )
            db.add(event)
    
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


def apply_church_effects(db: Session) -> None:
    """Apply church effects on NPC happiness.
    
    Increases happiness of NPCs within radius 10 of any church building by 5.
    """
    church_buildings = db.query(Building).filter(Building.building_type == 'church').all()
    
    for church in church_buildings:
        # Get all NPCs
        npcs = db.query(NPC).all()
        
        for npc in npcs:
            # Calculate Euclidean distance
            distance = math.sqrt((npc.x - church.x) ** 2 + (npc.y - church.y) ** 2)
            
            # If within radius 10, increase happiness
            if distance <= 10:
                npc.happiness = min(100, npc.happiness + 5)
    
    db.commit()


def seed_mine(db: Session) -> None:
    """Seed a mine building into the town.

    Creates 1 mine building at coordinates (45, 45).
    Idempotent - will not create if one already exists.
    """
    existing_mines = db.query(Building).filter(Building.building_type == 'mine').count()
    if existing_mines > 0:
        return
    
    # Create mine at (45, 45)
    mine = Building(
        name="Town Mine",
        building_type="mine",
        x=45,
        y=45,
        capacity=5
    )
    db.add(mine)
    db.commit()


def produce_mine_resources(db: Session) -> None:
    """Produce resources for buildings of type 'mine'.
    
    Mine produces 8 Ore per tick.
    """
    mine_buildings = db.query(Building).filter(Building.building_type == 'mine').all()

    for building in mine_buildings:
        # Check if Ore resource exists at this building
        ore_resource = db.query(Resource).filter(
            Resource.name == 'Ore',
            Resource.building_id == building.id
        ).first()

        if ore_resource:
            ore_resource.quantity += 8
        else:
            new_ore = Resource(
                name='Ore',
                quantity=8,
                building_id=building.id
            )
            db.add(new_ore)


def seed_lumber_mill(db: Session) -> None:
    """Seed a lumber mill building into the town.

    Creates 1 lumber mill building at coordinates (46, 46).
    Idempotent - will not create if one already exists.
    """
    existing_mills = db.query(Building).filter(Building.building_type == 'lumber_mill').count()
    if existing_mills > 0:
        return
    
    # Create lumber mill at (46, 46)
    lumber_mill = Building(
        name="Town Lumber Mill",
        building_type="lumber_mill",
        x=46,
        y=46,
        capacity=5
    )
    db.add(lumber_mill)
    db.commit()


def produce_lumber_mill_resources(db: Session) -> None:
    """Produce resources for buildings of type 'lumber_mill'.
    
    Lumber Mill produces 8 Wood per tick.
    """
    lumber_mill_buildings = db.query(Building).filter(Building.building_type == 'lumber_mill').all()
    
    for building in lumber_mill_buildings:
        # Check if Wood resource exists at this building
        wood_resource = db.query(Resource).filter(
            Resource.name == 'Wood',
            Resource.building_id == building.id
        ).first()
        
        if wood_resource:
            wood_resource.quantity += 8
        else:
            new_wood = Resource(
                name='Wood',
                quantity=8,
                building_id=building.id
            )
            db.add(new_wood)


def seed_fishing_dock(db: Session) -> None:
    """Seed a fishing dock building into the town.

    Creates 1 fishing dock building at coordinates (47, 47).
    Idempotent - will not create if one already exists.
    """
    existing_docks = db.query(Building).filter(Building.building_type == 'fishing_dock').count()
    if existing_docks > 0:
        return
    
    # Create fishing dock at (47, 47)
    fishing_dock = Building(
        name="Town Fishing Dock",
        building_type="fishing_dock",
        x=47,
        y=47,
        capacity=5
    )
    db.add(fishing_dock)
    db.commit()


def produce_fishing_dock_resources(db: Session) -> None:
    """Produce resources for buildings of type 'fishing_dock'.
    
    Fishing Dock produces 6 Fish per tick.
    """
    fishing_dock_buildings = db.query(Building).filter(Building.building_type == 'fishing_dock').all()
    
    for building in fishing_dock_buildings:
        # Check if Fish resource exists at this building
        fish_resource = db.query(Resource).filter(
            Resource.name == 'Fish',
            Resource.building_id == building.id
        ).first()
        
        if fish_resource:
            fish_resource.quantity += 6
        else:
            new_fish = Resource(
                name='Fish',
                quantity=6,
                building_id=building.id
            )
            db.add(new_fish)


def seed_guard_tower(db: Session) -> None:
    """Seed a guard tower building into the town.

    Creates 1 guard tower building at coordinates (48, 48).
    Idempotent - will not create if one already exists.
    """
    existing_towers = db.query(Building).filter(Building.building_type == 'guard_tower').count()
    if existing_towers > 0:
        return
    
    # Create guard tower at (48, 48)
    guard_tower = Building(
        name="Town Guard Tower",
        building_type="guard_tower",
        x=48,
        y=48,
        capacity=5
    )
    db.add(guard_tower)
    db.commit()


def produce_guard_tower_resources(db: Session) -> None:
    """Produce resources for buildings of type 'guard_tower'.
    
    Guard Tower produces 5 Defense per tick.
    """
    guard_tower_buildings = db.query(Building).filter(Building.building_type == 'guard_tower').all()
    
    for building in guard_tower_buildings:
        # Check if Defense resource exists at this building
        defense_resource = db.query(Resource).filter(
            Resource.name == 'Defense',
            Resource.building_id == building.id
        ).first()
        
        if defense_resource:
            defense_resource.quantity += 5
        else:
            new_defense = Resource(
                name='Defense',
                quantity=5,
                building_id=building.id
            )
            db.add(new_defense)


def seed_wall(db: Session) -> None:
    """Seed a wall building into the town.

    Creates 1 wall building at coordinates (49, 49).
    Idempotent - will not create if one already exists.
    """
    existing_walls = db.query(Building).filter(Building.building_type == 'wall').count()
    if existing_walls > 0:
        return
    
    # Create wall at (49, 49)
    wall = Building(
        name="Town Wall",
        building_type="wall",
        x=49,
        y=49,
        capacity=5
    )
    db.add(wall)
    db.commit()


def seed_gate(db: Session) -> None:
    """Seed a gate building into the town.

    Creates 1 gate building at coordinates (50, 50).
    Idempotent - will not create if one already exists.
    """
    existing_gates = db.query(Building).filter(Building.building_type == 'gate').count()
    if existing_gates > 0:
        return
    
    # Create gate at (50, 50)
    gate = Building(
        name="Town Gate",
        building_type="gate",
        x=50,
        y=50,
        capacity=5
    )
    db.add(gate)
    db.commit()


def produce_gate_resources(db: Session) -> None:
    """Produce resources for buildings of type 'gate'.
    
    Gate produces 3 Security per tick.
    """
    gate_buildings = db.query(Building).filter(Building.building_type == 'gate').all()
    
    for building in gate_buildings:
        # Check if Security resource exists at this building
        security_resource = db.query(Resource).filter(
            Resource.name == 'Security',
            Resource.building_id == building.id
        ).first()
        
        if security_resource:
            security_resource.quantity += 3
        else:
            new_security = Resource(
                name='Security',
                quantity=3,
                building_id=building.id
            )
            db.add(new_security)


def seed_fountain(db: Session) -> None:
    """Seed a fountain building into the town.

    Creates 1 fountain building at coordinates (40, 40).
    Idempotent - will not create if one already exists.
    """
    existing_fountains = db.query(Building).filter(Building.building_type == 'fountain').count()
    if existing_fountains > 0:
        return
    
    # Create fountain at (40, 40)
    fountain = Building(
        name="Town Fountain",
        building_type="fountain",
        x=40,
        y=40,
        capacity=5
    )
    db.add(fountain)
    db.commit()


def apply_fountain_effects(db: Session) -> None:
    """Apply fountain effects on NPC happiness.
    
    Increases happiness of NPCs within radius 8 of any fountain building by 3.
    """
    fountain_buildings = db.query(Building).filter(Building.building_type == 'fountain').all()
    
    for fountain in fountain_buildings:
        # Get all NPCs
        npcs = db.query(NPC).all()
        
        for npc in npcs:
            # Calculate Euclidean distance
            distance = math.sqrt((npc.x - fountain.x) ** 2 + (npc.y - fountain.y) ** 2)
            
            # If within radius 8, increase happiness
            if distance <= 8:
                npc.happiness = min(100, npc.happiness + 3)
    
    db.commit()


def seed_well(db: Session) -> None:
    """Seed a well building into the town.

    Creates 1 well building at coordinates (41, 41).
    Idempotent - will not create if one already exists.
    """
    existing_wells = db.query(Building).filter(Building.building_type == 'well').count()
    if existing_wells > 0:
        return
    
    # Create well at (41, 41)
    well = Building(
        name="Town Well",
        building_type="well",
        x=41,
        y=41,
        capacity=5
    )
    db.add(well)
    db.commit()


def produce_well_resources(db: Session) -> None:
    """Produce resources for buildings of type 'well'.
    
    Well produces 20 Water per tick.
    """
    well_buildings = db.query(Building).filter(Building.building_type == 'well').all()
    
    for building in well_buildings:
        # Check if Water resource exists at this building
        water_resource = db.query(Resource).filter(
            Resource.name == 'Water',
            Resource.building_id == building.id
        ).first()
        
        if water_resource:
            water_resource.quantity += 20
        else:
            new_water = Resource(
                name='Water',
                quantity=20,
                building_id=building.id
            )
            db.add(new_water)


def seed_warehouse(db: Session) -> None:
    """Seed a warehouse building into the town.

    Creates 1 warehouse building at coordinates (42, 42).
    Idempotent - will not create if one already exists.
    """
    existing_warehouses = db.query(Building).filter(Building.building_type == 'warehouse').count()
    if existing_warehouses > 0:
        return
    
    # Create warehouse at (42, 42)
    warehouse = Building(
        name="Town Warehouse",
        building_type="warehouse",
        x=42,
        y=42,
        capacity=5
    )
    db.add(warehouse)
    db.commit()


def produce_warehouse_resources(db: Session) -> None:
    """Produce resources for buildings of type 'warehouse'.
    
    Warehouse produces 10 Storage per tick.
    """
    warehouse_buildings = db.query(Building).filter(Building.building_type == 'warehouse').all()
    
    for building in warehouse_buildings:
        # Check if Storage resource exists at this building
        storage_resource = db.query(Resource).filter(
            Resource.name == 'Storage',
            Resource.building_id == building.id
        ).first()
        
        if storage_resource:
            storage_resource.quantity += 10
        else:
            new_storage = Resource(
                name='Storage',
                quantity=10,
                building_id=building.id
            )
            db.add(new_storage)


def seed_bank(db: Session) -> None:
    """Seed a bank building into the town.

    Creates 1 bank building at coordinates (51, 51).
    Idempotent - will not create if one already exists.
    """
    existing_banks = db.query(Building).filter(Building.building_type == 'bank').count()
    if existing_banks > 0:
        return
    
    # Create bank at (51, 51)
    bank = Building(
        name="Town Bank",
        building_type="bank",
        x=51,
        y=51,
        capacity=5
    )
    db.add(bank)
    db.commit()


def produce_bank_resources(db: Session) -> None:
    """Produce resources for buildings of type 'bank'.
    
    Bank produces 10 Gold per tick.
    """
    bank_buildings = db.query(Building).filter(Building.building_type == 'bank').all()
    
    for building in bank_buildings:
        # Check if Gold resource exists at this building
        gold_resource = db.query(Resource).filter(
            Resource.name == 'Gold',
            Resource.building_id == building.id
        ).first()
        
        if gold_resource:
            gold_resource.quantity += 10
        else:
            new_gold = Resource(
                name='Gold',
                quantity=10,
                building_id=building.id
            )
            db.add(new_gold)


def seed_theater(db: Session) -> None:
    """Seed a theater building into the town.

    Creates 1 theater building at coordinates (52, 52).
    Idempotent - will not create if one already exists.
    """
    existing_theaters = db.query(Building).filter(Building.building_type == 'theater').count()
    if existing_theaters > 0:
        return
    
    # Create theater at (52, 52)
    theater = Building(
        name="Town Theater",
        building_type="theater",
        x=52,
        y=52,
        capacity=5
    )
    db.add(theater)
    db.commit()


def produce_theater_resources(db: Session) -> None:
    """Produce resources for buildings of type 'theater'.
    
    Theater produces 2 Art per tick.
    """
    theater_buildings = db.query(Building).filter(Building.building_type == 'theater').all()
    
    for building in theater_buildings:
        # Check if Art resource exists at this building
        art_resource = db.query(Resource).filter(
            Resource.name == 'Art',
            Resource.building_id == building.id
        ).first()
        
        if art_resource:
            art_resource.quantity += 2
        else:
            new_art = Resource(
                name='Art',
                quantity=2,
                building_id=building.id
            )
            db.add(new_art)


def seed_arena(db: Session) -> None:
    """Seed an arena building into the town.

    Creates 1 arena building at coordinates (53, 53).
    Idempotent - will not create if one already exists.
    """
    existing_arenas = db.query(Building).filter(Building.building_type == 'arena').count()
    if existing_arenas > 0:
        return
    
    # Create arena at (53, 53)
    arena = Building(
        name="Town Arena",
        building_type="arena",
        x=53,
        y=53,
        capacity=5
    )
    db.add(arena)
    db.commit()


def produce_arena_resources(db: Session) -> None:
    """Produce resources for buildings of type 'arena'.
    
    Arena produces 3 Entertainment per tick.
    """
    arena_buildings = db.query(Building).filter(Building.building_type == 'arena').all()
    
    for building in arena_buildings:
        # Check if Entertainment resource exists at this building
        entertainment_resource = db.query(Resource).filter(
            Resource.name == 'Entertainment',
            Resource.building_id == building.id
        ).first()
        
        if entertainment_resource:
            entertainment_resource.quantity += 3
        else:
            new_entertainment = Resource(
                name='Entertainment',
                quantity=3,
                building_id=building.id
            )
            db.add(new_entertainment)


def seed_prison(db: Session) -> None:
    """Seed a prison building into the town.

    Creates 1 prison building at coordinates (54, 54).
    Idempotent - will not create if one already exists.
    """
    existing_prisons = db.query(Building).filter(Building.building_type == 'prison').count()
    if existing_prisons > 0:
        return
    
    # Create prison at (54, 54)
    prison = Building(
        name="Town Prison",
        building_type="prison",
        x=54,
        y=54,
        capacity=5
    )
    db.add(prison)
    db.commit()


def seed_graveyard(db: Session) -> None:
    """Seed a graveyard building into the town.

    Creates 1 graveyard building at coordinates (55, 55).
    Idempotent - will not create if one already exists.
    """
    existing_graveyards = db.query(Building).filter(Building.building_type == 'graveyard').count()
    if existing_graveyards > 0:
        return
    
    # Create graveyard at (55, 55)
    graveyard = Building(
        name="Town Graveyard",
        building_type="graveyard",
        x=55,
        y=55,
        capacity=5
    )
    db.add(graveyard)
    db.commit()


def seed_garden(db: Session) -> None:
    """Seed a garden building into the town.

    Creates 1 garden building at coordinates (56, 56).
    Idempotent - will not create if one already exists.
    """
    existing_gardens = db.query(Building).filter(Building.building_type == 'garden').count()
    if existing_gardens > 0:
        return
    
    # Create garden at (56, 56)
    garden = Building(
        name="Town Garden",
        building_type="garden",
        x=56,
        y=56,
        capacity=5
    )
    db.add(garden)
    db.commit()


def produce_garden_resources(db: Session) -> None:
    """Produce resources for buildings of type 'garden'.
    
    Garden produces 4 Herbs per tick.
    """
    garden_buildings = db.query(Building).filter(Building.building_type == 'garden').all()
    
    for building in garden_buildings:
        # Check if Herbs resource exists at this building
        herbs_resource = db.query(Resource).filter(
            Resource.name == 'Herbs',
            Resource.building_id == building.id
        ).first()
        
        if herbs_resource:
            herbs_resource.quantity += 4
        else:
            new_herbs = Resource(
                name='Herbs',
                quantity=4,
                building_id=building.id
            )
            db.add(new_herbs)


def seed_watchtower(db: Session) -> None:
    """Seed a watchtower building into the town.

    Creates 1 watchtower building at coordinates (57, 57).
    Idempotent - will not create if one already exists.
    """
    existing_watchtowers = db.query(Building).filter(Building.building_type == 'watchtower').count()
    if existing_watchtowers > 0:
        return
    
    # Create watchtower at (57, 57)
    watchtower = Building(
        name="Town Watchtower",
        building_type="watchtower",
        x=57,
        y=57,
        capacity=5
    )
    db.add(watchtower)
    db.commit()


def produce_watchtower_resources(db: Session) -> None:
    """Produce resources for buildings of type 'watchtower'.
    
    Watchtower produces 4 Defense per tick.
    """
    watchtower_buildings = db.query(Building).filter(Building.building_type == 'watchtower').all()
    
    for building in watchtower_buildings:
        # Check if Defense resource exists at this building
        defense_resource = db.query(Resource).filter(
            Resource.name == 'Defense',
            Resource.building_id == building.id
        ).first()
        
        if defense_resource:
            defense_resource.quantity += 4
        else:
            new_defense = Resource(
                name='Defense',
                quantity=4,
                building_id=building.id
            )
            db.add(new_defense)


def seed_windmill(db: Session) -> None:
    """Seed a windmill building into the town.

    Creates 1 windmill building at coordinates (58, 58).
    Idempotent - will not create if one already exists.
    """
    existing_windmills = db.query(Building).filter(Building.building_type == 'windmill').count()
    if existing_windmills > 0:
        return
    
    # Create windmill at (58, 58)
    windmill = Building(
        name="Town Windmill",
        building_type="windmill",
        x=58,
        y=58,
        capacity=5
    )
    db.add(windmill)
    db.commit()


def produce_windmill_resources(db: Session) -> None:
    """Produce resources for buildings of type 'windmill'.
    
    Windmill converts 1 Wheat to 8 Flour per tick if Wheat available.
    """
    windmill_buildings = db.query(Building).filter(Building.building_type == 'windmill').all()
    
    for building in windmill_buildings:
        # Check if Wheat resource exists at this building
        wheat_resource = db.query(Resource).filter(
            Resource.name == 'Wheat',
            Resource.building_id == building.id
        ).first()
        
        # Only produce if Wheat is available
        if wheat_resource and wheat_resource.quantity >= 1:
            # Consume 1 Wheat
            wheat_resource.quantity -= 1
            
            # Check if Flour resource exists at this building
            flour_resource = db.query(Resource).filter(
                Resource.name == 'Flour',
                Resource.building_id == building.id
            ).first()
            
            if flour_resource:
                flour_resource.quantity += 8
            else:
                new_flour = Resource(
                    name='Flour',
                    quantity=8,
                    building_id=building.id
                )
                db.add(new_flour)


def update_relationships(db: Session) -> None:
    """Update relationships between NPCs based on proximity and competition."""
    from engine.models import NPC, Building
    
    # Get all NPCs with their work buildings
    npcs = db.query(NPC).all()
    
    # Group NPCs by work building
    building_npcs: dict[int, list[NPC]] = {}
    for npc in npcs:
        if npc.work_building_id:
            if npc.work_building_id not in building_npcs:
                building_npcs[npc.work_building_id] = []
            building_npcs[npc.work_building_id].append(npc)
    
    # Process friendships (same building)
    for building_id, building_npc_list in building_npcs.items():
        for i, npc1 in enumerate(building_npc_list):
            for npc2 in building_npc_list[i+1:]:
                # Create or update friendship
                rel = db.query(Relationship).filter(
                    Relationship.npc_id == npc1.id,
                    Relationship.target_npc_id == npc2.id
                ).first()
                
                if not rel:
                    rel = Relationship(
                        npc_id=npc1.id,
                        target_npc_id=npc2.id,
                        relationship_type="friend",
                        strength=5
                    )
                    db.add(rel)
                else:
                    rel.strength = min(100, rel.strength + 5)
                
                # Also create reverse relationship
                rel_reverse = db.query(Relationship).filter(
                    Relationship.npc_id == npc2.id,
                    Relationship.target_npc_id == npc1.id
                ).first()
                
                if not rel_reverse:
                    rel_reverse = Relationship(
                        npc_id=npc2.id,
                        target_npc_id=npc1.id,
                        relationship_type="friend",
                        strength=5
                    )
                    db.add(rel_reverse)
                else:
                    rel_reverse.strength = min(100, rel_reverse.strength + 5)
    
    # Process rivalries (competing for same resource)
    # Group NPCs by building type
    building_type_npcs: dict[str, list[NPC]] = {}
    for npc in npcs:
        if npc.work_building_id:
            building = db.query(Building).filter(Building.id == npc.work_building_id).first()
            if building:
                building_type = building.building_type
                if building_type not in building_type_npcs:
                    building_type_npcs[building_type] = []
                building_type_npcs[building_type].append(npc)
    
    # Process rivalries for resource-producing buildings
    resource_buildings = ['mine', 'lumber_mill', 'fishing_dock', 'farm']
    
    for building_type in resource_buildings:
        if building_type in building_type_npcs:
            npc_list = building_type_npcs[building_type]
            for i, npc1 in enumerate(npc_list):
                for npc2 in npc_list[i+1:]:
                    # Skip if they're at the same building (already friends)
                    if npc1.work_building_id == npc2.work_building_id:
                        continue
                    
                    # Create or update rivalry
                    rel = db.query(Relationship).filter(
                        Relationship.npc_id == npc1.id,
                        Relationship.target_npc_id == npc2.id
                    ).first()
                    
                    if not rel:
                        rel = Relationship(
                            npc_id=npc1.id,
                            target_npc_id=npc2.id,
                            relationship_type="rival",
                            strength=5
                        )
                        db.add(rel)
                    else:
                        rel.strength = min(100, rel.strength + 5)
                    
                    # Also create reverse relationship
                    rel_reverse = db.query(Relationship).filter(
                        Relationship.npc_id == npc2.id,
                        Relationship.target_npc_id == npc1.id
                    ).first()
                    
                    if not rel_reverse:
                        rel_reverse = Relationship(
                            npc_id=npc2.id,
                            target_npc_id=npc1.id,
                            relationship_type="rival",
                            strength=5
                        )
                        db.add(rel_reverse)
                    else:
                        rel_reverse.strength = min(100, rel_reverse.strength + 5)
    
    db.commit()


def check_marriage(db: Session) -> None:
    """Check for NPCs that can marry and process marriages.
    
    Two NPCs with friendship strength > 80 and no existing spouse may marry.
    They move to the same home.
    """
    from engine.models import Relationship, NPC
    
    # Find all friend relationships with strength > 80
    friend_relationships = db.query(Relationship).filter(
        Relationship.relationship_type == 'friend',
        Relationship.strength > 80
    ).all()
    
    for rel in friend_relationships:
        # Check if npc1 already has a spouse
        npc1_has_spouse = db.query(Relationship).filter(
            ((Relationship.npc_id == rel.npc_id) | (Relationship.target_npc_id == rel.npc_id)) &
            (Relationship.relationship_type == 'spouse')
        ).first()
        
        # Check if npc2 already has a spouse
        npc2_has_spouse = db.query(Relationship).filter(
            ((Relationship.npc_id == rel.target_npc_id) | (Relationship.target_npc_id == rel.target_npc_id)) &
            (Relationship.relationship_type == 'spouse')
        ).first()
        
        # Only marry if neither has a spouse
        if not npc1_has_spouse and not npc2_has_spouse:
            # Update relationship to spouse
            rel.relationship_type = 'spouse'
            
            # Get both NPCs
            npc1 = db.query(NPC).filter(NPC.id == rel.npc_id).first()
            npc2 = db.query(NPC).filter(NPC.id == rel.target_npc_id).first()
            
            if npc1 and npc2:
                # Move to the same home
                if npc1.home_building_id:
                    npc2.home_building_id = npc1.home_building_id
                elif npc2.home_building_id:
                    npc1.home_building_id = npc2.home_building_id
                # If neither has a home, they keep their current home_building_id (None)


def age_npcs(db: Session) -> None:
    """Age all NPCs by 1 year. Mark NPCs as dead when they reach max_age."""
    from engine.models import NPC
    
    for npc in db.query(NPC).filter(NPC.is_dead == False).all():
        npc.age += 1
        if npc.age >= npc.max_age:
            npc.is_dead = True
    
    db.commit()


def process_inheritance(db: Session) -> None:
    """Process inheritance for all dead NPCs."""
    from engine.models import NPC, Relationship, Treasury
    
    # Get all dead NPCs who still have gold
    dead_npcs = db.query(NPC).filter(NPC.is_dead == 1).filter(NPC.gold > 0).all()
    
    for dead_npc in dead_npcs:
        gold = dead_npc.gold
        
        # Find children (Relationship where npc_id is dead_npc and target_npc_id is child)
        children = db.query(NPC).join(
            Relationship, Relationship.target_npc_id == NPC.id
        ).filter(
            Relationship.npc_id == dead_npc.id,
            Relationship.relationship_type == "child"
        ).all()
        
        if children:
            # Split gold equally among children
            share = gold // len(children)
            remainder = gold % len(children)
            for i, child in enumerate(children):
                child.gold += share + (1 if i < remainder else 0)
        else:
            # Find spouse
            spouse = db.query(NPC).join(
                Relationship, Relationship.target_npc_id == NPC.id
            ).filter(
                Relationship.npc_id == dead_npc.id,
                Relationship.relationship_type == "spouse"
            ).first()
            
            if spouse:
                # Spouse gets all gold
                spouse.gold += gold
            else:
                # Treasury gets all gold
                treasury = db.query(Treasury).first()
                if treasury:
                    treasury.gold_stored += gold
        
        # Clear dead NPC's gold
        dead_npc.gold = 0
    
    db.commit()


def produce_lumber(db: Session) -> None:
    """Lumber Mills convert 2 Wood -> 1 Lumber."""
    from engine.models import Building, Resource
    
    lumber_mills = db.query(Building).filter(Building.building_type == 'lumber_mill').all()
    
    for mill in lumber_mills:
        # Find Wood resource at this mill
        wood = db.query(Resource).filter(
            Resource.name == 'Wood',
            Resource.building_id == mill.id
        ).first()
        
        if wood and wood.quantity >= 2:
            # Calculate how much lumber we can produce (2 Wood = 1 Lumber)
            lumber_produced = wood.quantity // 2
            
            # Consume wood (2 per lumber)
            wood.quantity -= lumber_produced * 2
            
            # Create or update Lumber resource
            lumber = db.query(Resource).filter(
                Resource.name == 'Lumber',
                Resource.building_id == mill.id
            ).first()
            
            if lumber:
                lumber.quantity += lumber_produced
            else:
                new_lumber = Resource(
                    name='Lumber',
                    quantity=lumber_produced,
                    building_id=mill.id
                )
                db.add(new_lumber)
            
            db.commit()


def produce_fish(db: Session) -> None:
    """Produce Fish resources for fishing_dock buildings."""
    from engine.models import Building, Resource
    
    fishing_docks = db.query(Building).filter(Building.building_type == 'fishing_dock').all()
    
    for building in fishing_docks:
        resource = db.query(Resource).filter(
            Resource.name == 'Fish',
            Resource.building_id == building.id
        ).first()
        
        if resource:
            resource.quantity += 10
        else:
            new_resource = Resource(
                name='Fish',
                quantity=10,
                building_id=building.id
            )
            db.add(new_resource)
    
    db.commit()


def buy_fish(db: Session, npc_id: int) -> bool:
    """Allow an NPC to buy Fish, reducing hunger by 25 and gold by 3."""
    from engine.models import NPC, Resource, Building
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    # Check if NPC has enough gold
    if npc.gold < 3:
        return False
    
    # Find available Fish resources (from any fishing dock)
    fish_resources = db.query(Resource).filter(
        Resource.name == 'Fish',
        Resource.quantity > 0
    ).all()
    
    if not fish_resources:
        return False
    
    # Find the first available fish resource
    fish = fish_resources[0]
    
    # Deduct gold from NPC
    npc.gold -= 3
    
    # Reduce hunger by 25 (but not below 0)
    npc.hunger = max(0, npc.hunger - 25)
    
    # Reduce fish quantity by 1
    fish.quantity -= 1
    if fish.quantity <= 0:
        db.delete(fish)
    
    db.commit()
    return True


def produce_medicine(db: Session) -> None:
    """Hospital converts 3 Herbs to 1 Medicine."""
    hospitals = db.query(Building).filter(Building.building_type == 'hospital').all()
    
    for hospital in hospitals:
        herbs = db.query(Resource).filter(
            Resource.name == 'Herbs',
            Resource.building_id == hospital.id
        ).first()
        
        if herbs and herbs.quantity >= 3:
            medicine = db.query(Resource).filter(
                Resource.name == 'Medicine',
                Resource.building_id == hospital.id
            ).first()
            
            batches = herbs.quantity // 3
            
            if medicine:
                medicine.quantity += batches
            else:
                new_medicine = Resource(
                    name='Medicine',
                    quantity=batches,
                    building_id=hospital.id
                )
                db.add(new_medicine)
            
            herbs.quantity -= (batches * 3)
