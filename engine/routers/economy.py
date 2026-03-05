"""Economy API endpoints."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db
from engine.models import WorldState

router = APIRouter(prefix="/api/admin/economy", tags=["economy"])


class TaxRateRequest(BaseModel):
    tax_rate: float


class TaxRateResponse(BaseModel):
    tax_rate: float
    message: str


@router.post("/tax-rate")
def update_tax_rate(
    request: TaxRateRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(require_admin),
):
    """Update the world tax rate (admin only)."""
    if request.tax_rate < 0 or request.tax_rate > 1:
        raise HTTPException(status_code=400, detail="Tax rate must be between 0 and 1")
    
    world_state = db.query(WorldState).first()
    if not world_state:
        raise HTTPException(status_code=500, detail="World state not initialized")
    
    world_state.tax_rate = request.tax_rate
    db.commit()
    
    return TaxRateResponse(
        tax_rate=world_state.tax_rate,
        message=f"Tax rate updated to {world_state.tax_rate * 100:.1f}%"
    )