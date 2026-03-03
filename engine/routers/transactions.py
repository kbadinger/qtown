"""Transaction history endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db
from engine.models import Transaction

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/")
def list_transactions(db: Session = Depends(get_db)):
    """Get all transactions."""
    transactions = db.query(Transaction).all()
    return [
        {
            "id": t.id,
            "sender_id": t.sender_id,
            "receiver_id": t.receiver_id,
            "amount": t.amount,
            "reason": t.reason,
            "created_at": t.created_at.isoformat(),
        }
        for t in transactions
    ]