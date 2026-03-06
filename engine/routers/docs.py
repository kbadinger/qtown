from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from fastapi import Request

from engine.db import get_db

router = APIRouter(prefix="/api-docs", tags=["docs"])

templates = Jinja2Templates(directory="engine/templates")

# Define API documentation structure manually to ensure human-readable output
API_ENDPOINTS = [
    {
        "method": "GET",
        "path": "/api/world",
        "description": "Returns the current world state including tick, day, weather, and economic status.",
        "auth_required": False,
        "example_response": {
            "tick": 120,
            "day": 5,
            "time_of_day": "morning",
            "weather": "sunny",
            "economic_status": "normal"
        }
    },
    {
        "method": "GET",
        "path": "/api/buildings",
        "description": "Lists all buildings in the town.",
        "auth_required": False,
        "example_response": [
            {"id": 1, "name": "Town Hall", "building_type": "civic", "x": 0, "y": 0}
        ]
    },
    {
        "method": "POST",
        "path": "/api/buildings",
        "description": "Creates a new building. Requires admin authentication.",
        "auth_required": True,
        "parameters": {
            "name": "string (required)",
            "building_type": "string (required)",
            "x": "integer (required)",
            "y": "integer (required)"
        },
        "example_response": {"id": 2, "name": "New Bakery", "building_type": "bakery", "x": 5, "y": 5}
    },
    {
        "method": "GET",
        "path": "/api/npcs",
        "description": "Lists all NPCs in the town.",
        "auth_required": False,
        "example_response": [
            {"id": 1, "name": "John", "role": "farmer", "gold": 50}
        ]
    },
    {
        "method": "GET",
        "path": "/api/features",
        "description": "Lists all feature requests submitted by users.",
        "auth_required": False,
        "example_response": [
            {"id": 1, "title": "Add a park", "status": "submitted", "vote_count": 5}
        ]
    },
    {
        "method": "POST",
        "path": "/api/features",
        "description": "Submits a new feature request.",
        "auth_required": False,
        "parameters": {
            "title": "string (required)",
            "description": "string (optional)"
        },
        "example_response": {"id": 2, "title": "Add a park", "status": "submitted"}
    },
    {
        "method": "POST",
        "path": "/api/features/{feature_id}/vote",
        "description": "Votes for a specific feature request.",
        "auth_required": False,
        "example_response": {"feature_id": 1, "vote_count": 6}
    },
    {
        "method": "GET",
        "path": "/api/economy",
        "description": "Returns current economic metrics including inflation and tax rates.",
        "auth_required": False,
        "example_response": {
            "inflation_rate": 0.02,
            "tax_rate": 0.10,
            "base_wage": 10
        }
    }
]

@router.get("/")
def get_api_docs(request: Request, db: Session = Depends(get_db)):
    """
    Returns a human-readable API documentation page.
    Lists all endpoints, parameters, and example responses.
    """
    return templates.TemplateResponse(
        "api_docs.html",
        {"request": request, "endpoints": API_ENDPOINTS}
    )