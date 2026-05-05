from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/{npc_id}")
def get_npc_detail(npc_id: int, db: Session = Depends(get_db)):
    """Get full NPC details with relationships and building names."""
    from engine.models import NPC, Relationship, Building

    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    # Get relationships for this NPC (correct columns: npc_id, target_npc_id)
    relationships = db.query(Relationship).filter(
        (Relationship.npc_id == npc_id) | (Relationship.target_npc_id == npc_id)
    ).all()

    # Get home and work building names
    home_building = db.query(Building).filter(Building.id == npc.home_building_id).first()
    work_building = db.query(Building).filter(Building.id == npc.work_building_id).first()

    return {
        "id": npc.id,
        "name": npc.name,
        "role": npc.role,
        "x": npc.x,
        "y": npc.y,
        "gold": npc.gold,
        "hunger": npc.hunger,
        "energy": npc.energy,
        "happiness": npc.happiness,
        "age": npc.age,
        "max_age": npc.max_age,
        "is_dead": npc.is_dead,
        "is_bankrupt": npc.is_bankrupt,
        "illness_severity": npc.illness_severity,
        "illness": npc.illness,
        "home_building_id": npc.home_building_id,
        "home_building_name": home_building.name if home_building else None,
        "work_building_id": npc.work_building_id,
        "work_building_name": work_building.name if work_building else None,
        "target_x": npc.target_x,
        "target_y": npc.target_y,
        "personality": npc.personality,
        "skill": npc.skill,
        "memory_events": npc.memory_events,
        "favorite_buildings": npc.favorite_buildings,
        "avoided_areas": npc.avoided_areas,
        "experience": npc.experience,
        "relationships": [
            {
                "npc_id": r.npc_id,
                "target_npc_id": r.target_npc_id,
                "relationship_type": r.relationship_type,
                "strength": r.strength
            }
            for r in relationships
        ]
    }
