from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from engine.auth import require_admin
from engine.db import get_db

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


class BuildingCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    building_type: str = Field(..., min_length=1, max_length=64)
    x: int = Field(..., ge=0, le=49)
    y: int = Field(..., ge=0, le=49)


class BuildingResponse(BaseModel):
    id: int
    name: str
    building_type: str
    x: int
    y: int
    capacity: int
    created_at: str

    class Config:
        from_attributes = True


@router.get("/")
def list_buildings(db: Session = Depends(get_db)):
    from engine.models import Building
    buildings = db.query(Building).all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "building_type": b.building_type,
            "x": b.x,
            "y": b.y,
            "capacity": b.capacity,
            "created_at": b.created_at.isoformat()
        }
        for b in buildings
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_building(
    body: BuildingCreate,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    from engine.models import Building
    building = Building(
        name=body.name,
        building_type=body.building_type,
        x=body.x,
        y=body.y,
    )
    db.add(building)
    db.commit()
    db.refresh(building)
    return {
        "id": building.id,
        "name": building.name,
        "building_type": building.building_type,
        "x": building.x,
        "y": building.y,
        "capacity": building.capacity,
        "created_at": building.created_at.isoformat()
    }