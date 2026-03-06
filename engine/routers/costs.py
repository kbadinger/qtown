from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db

router = APIRouter(prefix="/api/costs", tags=["costs"])

templates = Jinja2Templates(directory="engine/templates")

@router.get("")
def get_costs(db: Session = Depends(get_db)):
    """Return all cost records for the comparison table."""
    from engine.models import Cost
    costs = db.query(Cost).order_by(Cost.created_at.desc()).all()
    return [
        {
            "story_id": c.story_id,
            "model": c.model,
            "tokens_in": c.tokens_in,
            "tokens_out": c.tokens_out,
            "cost": c.cost,
            "duration": c.duration,
        }
        for c in costs
    ]

@router.get("/page")
def costs_page(request: Request, db: Session = Depends(get_db)):
    """Render the cost comparison page."""
    return templates.TemplateResponse("costs.html", {"request": request})


@router_page.get("")
def cost_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("costs.html", {"request": request})
