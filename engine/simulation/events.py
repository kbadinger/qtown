"""Event triggers — disasters, cascading effects, etc."""

from sqlalchemy.orm import Session

from engine.models import WorldState, Event


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
    from engine.models import NPC
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    
    # Create plague event
    plague_event = Event(
        event_type="plague",
        description="A plague has spread through the town, increasing illness severity",
        tick=world_state.tick if world_state else 0,
        severity="high"
    )
    db.add(plague_event)
    
    # Increase illness for all NPCs
    npcs = db.query(NPC).all()
    for npc in npcs:
        npc.illness_severity = min(100, npc.illness_severity + 20)
        npc.illness = npc.illness_severity
        if npc.illness_severity >= 100:
            npc.is_dead = 1
    
    db.commit()
