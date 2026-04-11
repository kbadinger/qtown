from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
import json
import os

from engine.db import get_db

router = APIRouter(prefix="/api", tags=["dashboard"])

templates = Jinja2Templates(directory="engine/templates")

def _load_prd_json():
    """Load prd.json from the project root."""
    prd_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "prd.json")
    # Fallback to current dir if not found relative to engine
    if not os.path.exists(prd_path):
        prd_path = "prd.json"
    
    try:
        with open(prd_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"stories": []}

@router.get("/dashboard-data")
def get_dashboard_data(db: Session = Depends(get_db)):
    """Return dashboard statistics including stories completed."""
    prd_data = _load_prd_json()
    stories = prd_data.get("stories", [])
    
    completed_count = sum(1 for s in stories if s.get("status") == "completed")
    total_count = len(stories)
    
    # Fallback to 200 if prd.json is missing or empty, as per story description
    if total_count == 0:
        total_count = 200
        
    return {
        "stories": {
            "done": completed_count,
            "total": total_count
        }
    }

@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    """Serve the main index page."""
    prd_data = _load_prd_json()
    stories = prd_data.get("stories", [])
    
    completed_count = sum(1 for s in stories if s.get("status") == "completed")
    total_count = len(stories)
    
    if total_count == 0:
        total_count = 200

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "stories_done": completed_count,
            "stories_total": total_count,
        },
    )