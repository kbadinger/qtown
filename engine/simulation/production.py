"""Resource production functions for all building types."""

from sqlalchemy.orm import Session

from engine.models import Building, Resource, PriceHistory, WorldState
from engine.simulation.constants import DEFAULT_BASE_PRICE, DEFAULT_DEMAND
from engine.simulation.economy import calculate_price


def produce_resources(db: Session, weather: str = None) -> None:
    """Produce resources for buildings of type 'food' and record price history."""
    food_buildings = db.query(Building).filter(Building.building_type == 'food').all()
    
    # Determine production amount based on weather
    base_production = 10
    
    # Check for drought - halve production if active
    world_state = db.query(WorldState).first()
    if world_state and world_state.drought_active:
        base_production = 5
    
    if weather == 'rain':
        base_production = 12  # +20% bonus
    
    # Track resources for price history
    resource_stats = {}

    for building in food_buildings:
        resource = db.query(Resource).filter(
            Resource.name == 'Food',
            Resource.building_id == building.id
        ).first()
        
        if resource:
            resource.quantity += base_production
            # Aggregate stats for this resource type
            if 'Food' not in resource_stats:
                resource_stats['Food'] = {'total_supply': 0, 'count': 0}
            resource_stats['Food']['total_supply'] += resource.quantity
            resource_stats['Food']['count'] += 1
        else:
            new_resource = Resource(
                name='Food',
                quantity=base_production,
                building_id=building.id
            )
            db.add(new_resource)
            if 'Food' not in resource_stats:
                resource_stats['Food'] = {'total_supply': 0, 'count': 0}
            resource_stats['Food']['total_supply'] += base_production
            resource_stats['Food']['count'] += 1

    # Record price history for all tracked resources
    current_tick = db.query(WorldState).first().tick if db.query(WorldState).first() else 0
    
    for resource_name, stats in resource_stats.items():
        avg_supply = stats['total_supply'] / stats['count'] if stats['count'] > 0 else 0
        demand = DEFAULT_DEMAND
        price = calculate_price(db, resource_name)
        
        # Check if entry already exists for this tick to avoid UNIQUE constraint violation
        existing_history = db.query(PriceHistory).filter(
            PriceHistory.resource_name == resource_name,
            PriceHistory.tick == current_tick
        ).first()
        
        if existing_history:
            # Update existing entry
            existing_history.price = price
            existing_history.supply = int(avg_supply)
            existing_history.demand = demand
        else:
            # Insert new entry
            history_entry = PriceHistory(
                resource_name=resource_name,
                price=price,
                supply=int(avg_supply),
                demand=demand,
                tick=current_tick
            )
            db.add(history_entry)
    
    db.commit()


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


def produce_art(db: Session) -> None:
    """Theater produces Art resource (2 per tick)."""
    from engine.models import Building, Resource
    
    theaters = db.query(Building).filter(Building.building_type == "theater").all()
    
    for theater in theaters:
        # Find existing Art resource for this theater or create new one
        art = db.query(Resource).filter(
            Resource.name == "Art",
            Resource.building_id == theater.id
        ).first()
        
        if art:
            art.quantity += 2
        else:
            db.add(Resource(
                name="Art",
                quantity=2,
                building_id=theater.id
            ))
    
    db.commit()


def produce_books(db: Session) -> None:
    """Produce Books resource in Libraries (2 per tick)."""
    from engine.models import Building, Resource

    libraries = db.query(Building).filter_by(building_type="library").all()
    for library in libraries:
        resource = db.query(Resource).filter_by(name="Books", building_id=library.id).first()
        if resource:
            resource.quantity += 2
        else:
            db.add(Resource(name="Books", quantity=2, building_id=library.id))
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
