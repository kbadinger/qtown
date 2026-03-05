"""Wage management endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from engine.auth import require_admin
from engine.db import get_db
from engine.models import WorldState

router = APIRouter(prefix="/api/admin/wage", tags=["wages"])


class WageUpdateRequest(BaseModel):
    base_wage: int


class WageUpdateResponse(BaseModel):
    base_wage: int
    message: str


@router.post("/")
def update_base_wage(
    request: WageUpdateRequest,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> WageUpdateResponse:
    """Update the base wage for all NPCs."""
    world_state = db.query(WorldState).first()
    
    if not world_state:
        world_state = WorldState()
        db.add(world_state)
        db.commit()
        db.refresh(world_state)
    
    world_state.base_wage = request.base_wage
    db.commit()
    
    return WageUpdateResponse(
        base_wage=world_state.base_wage,
        message=f"Base wage updated to {world_state.base_wage}",
    )