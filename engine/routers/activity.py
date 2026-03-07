from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/")
def get_activity(db: Session = Depends(get_db)):
    """Unified activity feed: recent events + transactions, sorted by tick desc."""
    from engine.models import Event, Transaction, NPC

    items = []

    # Recent events
    events = db.query(Event).order_by(Event.tick.desc()).limit(20).all()
    for ev in events:
        items.append({
            "tick": ev.tick,
            "message": ev.description,
            "type": "event",
            "severity": ev.severity or "info",
            "event_type": ev.event_type,
        })

    # Recent transactions (resolve NPC names)
    txns = (
        db.query(Transaction, NPC.name.label("sender_name"))
        .join(NPC, Transaction.sender_id == NPC.id)
        .order_by(Transaction.id.desc())
        .limit(20)
        .all()
    )
    for txn, sender_name in txns:
        receiver = db.query(NPC.name).filter(NPC.id == txn.receiver_id).scalar()
        reason = txn.reason or "transfer"
        items.append({
            "tick": 0,  # transactions don't have tick, use created_at ordering
            "message": f"{sender_name} paid {receiver or '?'} {txn.amount}g ({reason})",
            "type": "transaction",
            "severity": "info",
            "event_type": "transaction",
        })

    # Sort by tick desc (events first since they have real ticks), limit 20
    items.sort(key=lambda x: x["tick"], reverse=True)
    return items[:20]
