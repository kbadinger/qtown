from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from engine.models import Achievement
from engine.db import get_db

router = APIRouter(prefix="/api/achievements", tags=["achievements"])

@router.get("/")
def list_achievements(db: Session = Depends(get_db)):
    """Get all achievements with their status."""
    achievements = db.query(Achievement).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "achieved": a.achieved,
            "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None
        }
        for a in achievements
    ]