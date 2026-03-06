"""Event triggers — disasters, cascading effects, etc."""

from sqlalchemy.orm import Session

from engine.models import WorldState, Event
import random


def trigger_drought(db: Session) -> None:
    """Trigger a drought event that reduces resource production."""
    from engine.models import Event, WorldState
    from engine.simulation.constants import DROUGHT_FAMINE_THRESHOLD
    
    # Get world state
    world_state = db.query(WorldState).first()
    if not world_state:
        world_state = WorldState(tick=0, day=1, time_of_day="morning", weather="clear")
        db.add(world_state)
        db.commit()
    
    current_tick = world_state.tick
    
    # Set drought active flag in WorldState
    world_state.drought_active = 1
    
    # Check for prolonged drought (cascading to famine)
    drought_events = db.query(Event).filter(
        Event.event_type == "drought"
    ).all()
    
    # Count drought events in the last DROUGHT_FAMINE_THRESHOLD ticks
    recent_drought_count = sum(
        1 for evt in drought_events 
        if current_tick - evt.tick < DROUGHT_FAMINE_THRESHOLD
    )
    
    # Create drought event
    drought_event = Event(
        event_type="drought",
        description="A severe drought has begun, reducing resource production by 50%",
        tick=current_tick,
        severity="high"
    )
    db.add(drought_event)
    
    # Check if drought has lasted long enough to trigger famine
    if recent_drought_count >= DROUGHT_FAMINE_THRESHOLD:
        # Create famine event (cascading effect)
        famine_event = Event(
            event_type="famine",
            description="Drought has cascaded into famine! NPC hunger increases by 15 per tick",
            tick=current_tick,
            severity="critical"
        )
        db.add(famine_event)
    
    db.commit()


def trigger_flood(db: Session) -> None:
    """Trigger a flood event that damages all buildings."""
    from engine.models import Building
    
    # Create flood event
    world_state = db.query(WorldState).first()
    flood_event = Event(
        event_type="flood",
        description="A severe flood has damaged all buildings in the town",
        tick=world_state.tick if world_state else 0,
        severity="high"
    )
    db.add(flood_event)
    
    # Damage all buildings by reducing their capacity
    buildings = db.query(Building).all()
    for building in buildings:
        building.capacity = max(1, building.capacity // 2)
    
    db.commit()


def trigger_fire(db: Session) -> None:
    """Trigger a fire event that destroys a random building."""
    from engine.models import Building
    import random
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    
    # Select a random building to destroy
    buildings = db.query(Building).all()
    if not buildings:
        return  # No buildings to destroy
    
    affected_building = random.choice(buildings)
    
    # Create fire event
    fire_event = Event(
        event_type="fire",
        description=f"A fire has destroyed {affected_building.name}",
        tick=world_state.tick if world_state else 0,
        severity="high",
        affected_building_id=affected_building.id
    )
    db.add(fire_event)
    
    # Cascade: Trigger rebuilding boom
    rebuilding_event = Event(
        event_type="rebuilding_boom",
        description=f"Rebuilding effort initiated after fire at {affected_building.name}",
        tick=world_state.tick if world_state else 0,
        severity="medium",
        affected_building_id=affected_building.id
    )
    db.add(rebuilding_event)
    
    db.commit()


def trigger_plague(db: Session) -> None:
    """Trigger a plague event that increases NPC illness severity."""
    from engine.models import NPC, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create plague event
    plague_event = Event(
        event_type="plague",
        description="A plague has spread through the town, increasing illness severity",
        tick=current_tick,
        severity="high"
    )
    db.add(plague_event)
    
    # Increase illness for all NPCs
    npcs = db.query(NPC).all()
    for npc in npcs:
        # Skip already dead NPCs
        if npc.is_dead:
            continue
            
        # Increase illness severity by 20
        npc.illness_severity = min(100, npc.illness_severity + 20)
        npc.illness = npc.illness_severity
        
        # Kill NPC if severity reaches 100
        if npc.illness_severity >= 100:
            npc.is_dead = 1
    
    db.commit()


def trigger_harvest_festival(db: Session) -> None:
    """Trigger a harvest festival event that increases NPC happiness."""
    from engine.models import NPC, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create harvest festival event
    festival_event = Event(
        event_type="harvest_festival",
        description="A harvest festival has begun, boosting town happiness",
        tick=current_tick,
        severity="low"
    )
    db.add(festival_event)
    
    # Increase happiness for all NPCs (capped at 100)
    npcs = db.query(NPC).all()
    for npc in npcs:
        npc.happiness = min(100, npc.happiness + 20)
    
    db.commit()


def trigger_bandit_raid(db: Session) -> None:
    """Trigger a bandit raid that steals gold from Treasury and NPCs."""
    from engine.models import Treasury, NPC, Building, Event, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Count guards to reduce theft (5% reduction per guard)
    guard_buildings = db.query(Building).filter(
        Building.building_type.in_(['guard', 'guard_tower'])
    ).all()
    num_guards = len(guard_buildings)
    
    # Calculate theft reduction (5% per guard, capped at 100%)
    theft_reduction = min(num_guards * 0.05, 1.0)
    
    # Steal from Treasury (20% base, reduced by guards)
    treasuries = db.query(Treasury).all()
    total_stolen_from_treasury = 0
    for treasury in treasuries:
        base_theft = treasury.gold_stored * 0.20
        actual_theft = int(base_theft * (1 - theft_reduction))
        treasury.gold_stored = max(0, treasury.gold_stored - actual_theft)
        total_stolen_from_treasury += actual_theft
    
    # Steal from random NPCs (10% base, reduced by guards)
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    if npcs:
        # Select random NPCs to steal from (up to 20% of population)
        num_victims = max(1, len(npcs) // 5)
        victims = random.sample(npcs, min(num_victims, len(npcs)))
        
        for npc in victims:
            base_theft = npc.gold * 0.10
            actual_theft = int(base_theft * (1 - theft_reduction))
            npc.gold = max(0, npc.gold - actual_theft)
    
    # Create event log
    event = Event(
        event_type="bandit_raid",
        description=f"Bandits raided the town, stealing gold from treasury and citizens",
        tick=current_tick,
        severity="high"
    )
    db.add(event)
    db.commit()


def trigger_earthquake(db: Session) -> None:
    """Trigger an earthquake event that damages all buildings."""
    from engine.models import Building, Event, WorldState
    import random
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create earthquake event
    earthquake_event = Event(
        event_type="earthquake",
        description="An earthquake has shaken the town, damaging buildings",
        tick=current_tick,
        severity="high"
    )
    db.add(earthquake_event)
    
    # Damage all buildings
    buildings = db.query(Building).all()
    stone_building_types = ['wall', 'gate', 'guard_tower', 'watchtower']
    
    for building in buildings:
        if building.building_type in stone_building_types:
            # Stone buildings take less damage (10-25%)
            damage_percent = random.uniform(0.10, 0.25)
        else:
            # Regular buildings take more damage (10-50%)
            damage_percent = random.uniform(0.10, 0.50)
        
        new_capacity = int(building.capacity * (1 - damage_percent))
        building.capacity = max(1, new_capacity)  # Ensure capacity stays at least 1
    
    db.commit()


def trigger_market_crash(db: Session) -> None:
    """Trigger a market crash event that reduces all resource prices by 60%."""
    from engine.models import Resource, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create market crash event
    market_crash_event = Event(
        event_type="market_crash",
        description="A market crash has occurred, reducing all resource prices by 60%",
        tick=current_tick,
        severity="high"
    )
    db.add(market_crash_event)
    
    # Reduce all resource prices by 60%
    resources = db.query(Resource).all()
    for resource in resources:
        if hasattr(resource, 'price') and resource.price is not None:
            resource.price = max(1, int(resource.price * 0.4))  # Reduce by 60%
    
    db.commit()


def trigger_baby_boom(db: Session) -> None:
    """Trigger a baby boom event that spawns 5-10 new NPCs."""
    from engine.models import NPC, Event, WorldState
    import random
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Determine number of babies to spawn (5-10)
    num_babies = random.randint(5, 10)
    
    # Spawn new NPCs
    roles = ['farmer', 'merchant', 'guard', 'builder', 'healer', 'scholar']
    for i in range(num_babies):
        baby = NPC(
            name=f"Baby {i+1}",
            role=random.choice(roles),
            x=random.randint(0, 49),
            y=random.randint(0, 49),
            gold=0,
            hunger=50,
            energy=100,
            happiness=100,
            age=0,
            max_age=80,
            is_dead=0,
            illness_severity=0,
            illness=0
        )
        db.add(baby)
    
    # Create baby boom event
    baby_boom_event = Event(
        event_type="baby_boom",
        description=f"A baby boom has occurred, {num_babies} new citizens have been born",
        tick=current_tick,
        severity="low"
    )
    db.add(baby_boom_event)
    db.commit()


def trigger_gold_rush(db: Session) -> None:
    """Trigger a gold rush event that doubles gold production."""
    from engine.models import Event, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Set gold rush active flag in WorldState
    if world_state:
        world_state.gold_rush_active = 1
    
    # Create gold rush event
    gold_rush_event = Event(
        event_type="gold_rush",
        description="A gold rush has begun, doubling gold production for all workers",
        tick=current_tick,
        severity="medium"
    )
    db.add(gold_rush_event)
    db.commit()
