"""Event triggers — disasters, cascading effects, etc."""

from sqlalchemy.orm import Session

from engine.models import WorldState, Event
import random


def trigger_drought(db: Session) -> None:
    """Trigger a drought event that reduces resource production."""
    # Set drought active flag in WorldState
    world_state = db.query(WorldState).first()
    if world_state:
        world_state.drought_active = 1
    
    # Create drought event
    drought_event = Event(
        event_type="drought",
        description="A severe drought has begun, reducing resource production by 50%",
        tick=world_state.tick if world_state else 0,
        severity="high"
    )
    db.add(drought_event)
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
