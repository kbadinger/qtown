from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db
from engine.simulation import process_tick

router = APIRouter(prefix="/api/tick", tags=["tick"])


@router.post("/")
def tick(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Process one simulation tick.
    
    Requires admin authentication. Increments the world tick counter
    and returns the new tick number.
    """
    tick_num = process_tick(db)
    return {"tick": tick_num, "status": "ok"}