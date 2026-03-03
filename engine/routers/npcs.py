from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db

router = APIRouter(prefix="/api/npcs", tags=["npcs"])


class NPCCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    role: str = Field(..., min_length=1, max_length=64)
    x: int
    y: int


class NPCResponse(BaseModel):
    id: int
    name: str
    role: str
    x: int
    y: int
    gold: int
    hunger: int
    energy: int
    home_building_id: int | None
    work_building_id: int | None
    target_x: int | None
    target_y: int | None

    class Config:
        from_attributes = True


@router.get("/")
def list_npcs(db: Session = Depends(get_db)):
    from engine.models import NPC
    npcs = db.query(NPC).all()
    return [
        {
            "id": n.id,
            "name": n.name,
            "role": n.role,
            "x": n.x,
            "y": n.y,
            "gold": n.gold,
            "hunger": n.hunger,
            "energy": n.energy,
            "home_building_id": n.home_building_id,
            "work_building_id": n.work_building_id,
            "target_x": n.target_x,
            "target_y": n.target_y,
        }
        for n in npcs
    ]


@router.post("/", status_code=201)
def create_npc(
    npc_data: NPCCreate,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    from engine.models import NPC
    npc = NPC(
        name=npc_data.name,
        role=npc_data.role,
        x=npc_data.x,
        y=npc_data.y,
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)
    return NPCResponse.model_validate(npc)