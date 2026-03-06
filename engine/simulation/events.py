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
