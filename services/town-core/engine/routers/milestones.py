from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db
from engine.models import Milestone

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


@router.get("/")
def list_milestones(db: Session = Depends(get_db)):
    """Get all recorded milestones."""
    milestones = db.query(Milestone).order_by(Milestone.tick_achieved).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "tick_achieved": m.tick_achieved
        }
        for m in milestones
    ]