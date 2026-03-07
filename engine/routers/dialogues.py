from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db
from engine.models import Dialogue

router = APIRouter(prefix="/api/dialogues", tags=["dialogues"])

@router.get("/")
def get_dialogue_history(db: Session = Depends(get_db)):
    """Get dialogue history ordered by tick."""
    dialogues = db.query(Dialogue).order_by(Dialogue.tick.desc()).all()
    return [
        {
            "id": d.id,
            "speaker_npc_id": d.speaker_npc_id,
            "listener_npc_id": d.listener_npc_id,
            "message": d.message,
            "tick": d.tick
        }
        for d in dialogues
    ]