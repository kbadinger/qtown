from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/")
def list_events(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from engine.models import Event

    events = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "description": e.description,
            "tick": e.tick,
            "severity": e.severity,
            "affected_building_id": e.affected_building_id,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]