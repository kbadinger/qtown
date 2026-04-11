from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/visitor-log", tags=["visitor-log"])

@router.get("/")
def get_visitor_logs(db: Session = Depends(get_db)):
    """Get all visitor logs."""
    from engine.models import VisitorLog
    
    logs = db.query(VisitorLog).all()
    return [
        {
            "id": log.id,
            "npc_id": log.npc_id,
            "arrival_tick": log.arrival_tick,
            "greeted_by_npc_id": log.greeted_by_npc_id,
        }
        for log in logs
    ]