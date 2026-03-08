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
