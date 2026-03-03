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

    return {
        "population": population,
        "total_gold": total_gold,
        "avg_hunger": avg_hunger,
        "avg_energy": avg_energy,
        "avg_happiness": avg_happiness,
        "total_buildings": total_buildings,
        "current_tick": current_tick,
        "current_day": current_day
    }