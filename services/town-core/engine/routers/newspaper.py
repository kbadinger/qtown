from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/newspaper", tags=["newspaper"])

@router.get("/")
def get_latest_newspaper(db: Session = Depends(get_db)):
    """Get the latest newspaper entry."""
    from engine.models import Newspaper
    
    latest = db.query(Newspaper).order_by(Newspaper.tick.desc()).first()
    if latest:
        return {
            "id": latest.id,
            "day": latest.day,
            "headline": latest.headline,
            "body": latest.body,
            "author_npc_id": latest.author_npc_id,
            "tick": latest.tick
        }
    return {"error": "No newspaper entries found"}