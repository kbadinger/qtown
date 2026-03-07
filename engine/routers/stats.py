from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from engine.db import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/")
def get_stats(db: Session = Depends(get_db)):
    from engine.models import NPC, Building, WorldState

    # Population count
    population = db.query(NPC).count()

    # Total gold (sum of all NPC gold)
    total_gold = db.query(func.sum(NPC.gold)).scalar() or 0

    # Average hunger
    avg_hunger = db.query(func.avg(NPC.hunger)).scalar() or 0.0

    # Average energy
    avg_energy = db.query(func.avg(NPC.energy)).scalar() or 0.0

    # Average happiness
    avg_happiness = db.query(func.avg(NPC.happiness)).scalar() or 0.0

    # Total buildings count
    total_buildings = db.query(Building).count()

    # Current tick and day from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    current_day = world_state.day if world_state else 1

    # World state details
    weather = world_state.weather if world_state else None
    time_of_day = world_state.time_of_day if world_state else "morning"
    economic_status = world_state.economic_status if world_state else "normal"
    tax_rate = world_state.tax_rate if world_state else 0.10
    inflation_rate = world_state.inflation_rate if world_state else 0.0

    # Treasury
    from engine.models import Treasury, Resource
    treasury_gold = db.query(func.sum(Treasury.gold_stored)).scalar() or 0

    # Resource totals
    resource_rows = (
        db.query(Resource.name, func.sum(Resource.quantity))
        .group_by(Resource.name)
        .all()
    )
    resources = {name: qty for name, qty in resource_rows}

    # Average age
    avg_age = db.query(func.avg(NPC.age)).scalar() or 0.0

    return {
        "population": population,
        "total_gold": total_gold,
        "avg_hunger": avg_hunger,
        "avg_energy": avg_energy,
        "avg_happiness": avg_happiness,
        "total_buildings": total_buildings,
        "current_tick": current_tick,
        "current_day": current_day,
        "weather": weather,
        "time_of_day": time_of_day,
        "economic_status": economic_status,
        "tax_rate": tax_rate,
        "inflation_rate": inflation_rate,
        "treasury_gold": treasury_gold,
        "resources": resources,
        "avg_age": avg_age,
    }