from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from engine.db import get_db
from engine.models import Dialogue

router = APIRouter(prefix="/api/dialogues", tags=["dialogues"])


@router.get("/")
def get_dialogue_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Recent NPC dialogue, newest first (with speaker/listener names when known)."""
    dialogues = (
        db.query(Dialogue)
        .order_by(Dialogue.tick.desc(), Dialogue.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": d.id,
            "speaker_npc_id": d.speaker_npc_id,
            "listener_npc_id": d.listener_npc_id,
            "speaker_name": d.speaker.name if d.speaker else None,
            "listener_name": d.listener.name if d.listener else None,
            "message": d.message,
            "tick": d.tick,
        }
        for d in dialogues
    ]
