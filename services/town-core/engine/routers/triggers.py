from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from typing import Dict

from engine.db import get_db
from engine.simulation import apply_triggered_event
from fastapi import Depends

router = APIRouter(prefix="/api/trigger", tags=["triggers"])

# In-memory rate limiting: IP -> last request timestamp
_rate_limit_store: Dict[str, float] = {}
_RATE_LIMIT_INTERVAL = 60  # 1 minute in seconds


def _check_rate_limit(ip_address: str) -> bool:
    """Check if IP is rate limited. Returns True if request is allowed."""
    import time
    
    current_time = time.time()
    last_request = _rate_limit_store.get(ip_address, 0)
    
    if current_time - last_request < _RATE_LIMIT_INTERVAL:
        return False
    
    _rate_limit_store[ip_address] = current_time
    return True


def _get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


SUPPORTED_EVENTS = ["thunderstorm", "festival", "gold_rush", "baby_boom"]


@router.post("/{event_type}")
def trigger_event(
    event_type: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Trigger a game event with immediate effects."""
    # Validate event type
    if event_type not in SUPPORTED_EVENTS:
        raise HTTPException(status_code=404, detail="Invalid event type")
    
    # Check rate limit
    client_ip = _get_client_ip(request)
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Apply the triggered event
    apply_triggered_event(db, event_type)
    
    return {"status": "success", "event": event_type}