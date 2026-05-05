from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from engine.auth import require_admin
from engine.db import get_db
from engine.models import WorldState

router = APIRouter(prefix="/api/admin", tags=["admin"])

class TaxRateRequest(BaseModel):
    tax_rate: float

@router.post("/tax-rate")
def set_tax_rate(request: TaxRateRequest, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Set the configurable tax rate for the world."""
    world_state = db.query(WorldState).first()
    if not world_state:
        world_state = WorldState(tax_rate=request.tax_rate)
        db.add(world_state)
    else:
        world_state.tax_rate = request.tax_rate
    db.commit()
    return {"tax_rate": world_state.tax_rate}