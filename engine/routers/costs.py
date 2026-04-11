from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db
import json
import os
from pathlib import Path
from pydantic import BaseModel, Field

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
    return templates.TemplateResponse(request=request, name="costs.html")


class StoryProposal(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    phase: str = Field(default="development", min_length=1)


def _get_prd_path() -> Path:
    """Get the path to prd.json."""
    # Try current working directory, then project root
    if os.path.exists("prd.json"):
        return Path("prd.json")
    if os.path.exists("engine/prd.json"):
        return Path("engine/prd.json")
    # Default to current dir
    return Path("prd.json")


def _load_prd() -> dict:
    """Load prd.json, returning default structure if missing."""
    path = _get_prd_path()
    if not path.exists():
        return {"stories": []}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"stories": []}


def _save_prd(data: dict) -> None:
    """Save data to prd.json."""
    path = _get_prd_path()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


@router.post("/admin/propose-story", status_code=201)


def propose_story(
    proposal: StoryProposal,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Create a new story proposal and append to prd.json."""
    prd = _load_prd()
    stories = prd.get("stories", [])
    
    # Calculate next ID
    if not stories:
        next_id = 1
    else:
        # Extract numeric IDs if they are strings like "171"
        existing_ids = []
        for s in stories:
            try:
                existing_ids.append(int(s.get("id", 0)))
            except (ValueError, TypeError):
                pass
        next_id = (max(existing_ids) if existing_ids else 0) + 1
    
    new_story = {
        "id": str(next_id),
        "title": proposal.title,
        "description": proposal.description,
        "phase": proposal.phase,
        "status": "new"
    }
    
    stories.append(new_story)
    prd["stories"] = stories
    _save_prd(prd)
    
    return new_story
