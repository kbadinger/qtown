from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("/effectiveness")
def get_policy_effectiveness(db: Session = Depends(get_db)):
    """GET /api/policies/effectiveness - Return policies with name, effect, status, enacted_tick."""
    from engine.models import Policy

    policies = db.query(Policy).all()
    return [
        {
            "name": p.name,
            "effect": p.effect,
            "status": p.status,
            "enacted_tick": p.enacted_tick,
        }
        for p in policies
    ]