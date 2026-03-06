from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from engine.db import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/about", tags=["about"])

templates = Jinja2Templates(directory="engine/templates")

@router.get("")
def about_page(request: Request, db: Session = Depends(get_db)):
    """Render the About page with project description and tech stack."""
    return templates.TemplateResponse(
        "about.html",
        {"request": request}
    )