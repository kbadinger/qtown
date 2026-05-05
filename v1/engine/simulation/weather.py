"""Weather system."""

import random
from sqlalchemy.orm import Session

from engine.models import WorldState


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


def get_season(db: Session) -> str:
    """Get the current season from world state."""
    from engine.models import WorldState
    ws = db.query(WorldState).first()
    if not ws:
        return "spring"
    # Extract season from day_of_year or similar field
    # Assuming day_of_year exists and ranges 0-365
    day = getattr(ws, 'day_of_year', 0)
    if 0 <= day < 90:
        return "spring"
    elif 90 <= day < 180:
        return "summer"
    elif 180 <= day < 270:
        return "fall"
    else:
        return "winter"


def apply_winter_drain(db: Session) -> int:
    """Apply winter energy drain effects on NPCs when weather is snow.
    
    If WorldState.weather == "snow":
    - All living NPCs (is_dead == 0) energy -= 5 (min 0) and hunger += 5 (max 100)
    - NPCs with home_building_id not None get half penalty (energy -2, hunger +2)
    
    Returns count of affected NPCs.
    If weather is not snow, returns 0.
    """
    from engine.models import NPC, WorldState
    
    world_state = db.query(WorldState).first()
    if not world_state or world_state.weather != "snow":
        return 0
    
    # Get all living NPCs
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    affected_count = 0
    
    for npc in npcs:
        if npc.home_building_id is not None:
            # Half penalty for NPCs with home
            npc.energy = max(0, npc.energy - 2)
            npc.hunger = min(100, npc.hunger + 2)
        else:
            # Full penalty for NPCs without home
            npc.energy = max(0, npc.energy - 5)
            npc.hunger = min(100, npc.hunger + 5)
        affected_count += 1
    
    db.commit()
    return affected_count
