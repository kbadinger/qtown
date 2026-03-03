from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


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
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in buildings
    ]


@router.get("/{building_id}")
def get_building(building_id: int, db: Session = Depends(get_db)):
    from engine.models import Building
    from fastapi import HTTPException
    building = db.query(Building).filter_by(id=building_id).first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    return {
        "id": building.id,
        "name": building.name,
        "building_type": building.building_type,
        "x": building.x,
        "y": building.y,
        "capacity": building.capacity,
        "created_at": building.created_at.isoformat() if building.created_at else None,
    }


@router.post("/", status_code=201)
def create_building(
    name: str,
    building_type: str,
    x: int,
    y: int,
    capacity: int = 10,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    from engine.models import Building
    building = Building(
        name=name,
        building_type=building_type,
        x=x,
        y=y,
        capacity=capacity,
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
        "created_at": building.created_at.isoformat() if building.created_at else None,
    }


@router.delete("/{building_id}")
def delete_building(
    building_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    from engine.models import Building
    from fastapi import HTTPException
    building = db.query(Building).filter_by(id=building_id).first()
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    db.delete(building)
    db.commit()
    return {"message": "Building deleted"}