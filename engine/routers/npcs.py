from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/npcs", tags=["npcs"])


@router.get("/")
def list_npcs(db: Session = Depends(get_db)):
    """Return all NPCs as a JSON list with all fields."""
    from engine.models import NPC

    npcs = db.query(NPC).all()
    return [
        {
            "id": npc.id,
            "name": npc.name,
            "role": npc.role,
            "x": npc.x,
            "y": npc.y,
            "gold": npc.gold,
            "hunger": npc.hunger,
            "energy": npc.energy,
            "home_building_id": npc.home_building_id,
            "work_building_id": npc.work_building_id,
            "target_x": npc.target_x,
            "target_y": npc.target_y,
            "created_at": npc.created_at.isoformat() if npc.created_at else None,
        }
        for npc in npcs
    ]