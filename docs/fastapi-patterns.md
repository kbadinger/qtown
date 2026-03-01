# FastAPI Patterns for Qwen Town

Reference guide for writing routers, endpoints, and templates.

## Router Creation

```python
# engine/routers/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db

router = APIRouter(prefix="/api/example", tags=["example"])

@router.get("/")
def list_items(db: Session = Depends(get_db)):
    from engine.models import Item
    items = db.query(Item).all()
    return [{"id": i.id, "name": i.name} for i in items]

@router.post("/", status_code=201)
def create_item(
    name: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),  # Admin only
):
    from engine.models import Item
    item = Item(name=name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "name": item.name}
```

## Registering a Router — Auto-Discovery

Routers are **automatically discovered and registered** on app startup. You do NOT need to
edit `engine/main.py`. The auto-discovery system:

1. Scans `engine/routers/` for `.py` files (excluding `__init__.py` and files starting with `_`)
2. Imports each module and looks for a `router` attribute
3. Calls `app.include_router(router)` automatically

Just create your router file with the correct pattern and it works:
```python
# engine/routers/buildings.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.auth import require_admin
from engine.db import get_db

router = APIRouter(prefix="/api/buildings", tags=["buildings"])

@router.get("/")
def list_buildings(db: Session = Depends(get_db)):
    from engine.models import Building
    return [{"id": b.id, "name": b.name} for b in db.query(Building).all()]
```

**Requirements**:
- File must be directly in `engine/routers/` (not subdirectories)
- Must export a variable named exactly `router`
- Use `APIRouter(prefix="/api/...", tags=["..."])` for consistent URL namespacing

## Database Session Pattern

Always use `Depends(get_db)` — never create sessions manually:
```python
@router.get("/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item.id, "name": item.name}
```

## Admin Authentication

Use `Depends(require_admin)` on any admin-only endpoint:
```python
@router.delete("/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    ...
```

Never write your own auth logic. The `require_admin` dependency handles everything.

## Pydantic Schemas

```python
from pydantic import BaseModel, Field

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None

class ItemResponse(BaseModel):
    id: int
    name: str
    description: str | None

    class Config:
        from_attributes = True
```

## SQLAlchemy CRUD Patterns

```python
# Create
item = Item(name="Test")
db.add(item)
db.commit()
db.refresh(item)

# Read
item = db.query(Item).filter_by(id=item_id).first()
items = db.query(Item).filter(Item.status == "active").all()

# Update
item.name = "New Name"
db.commit()

# Delete
db.delete(item)
db.commit()

# Count
count = db.query(Item).count()

# Aggregate
from sqlalchemy import func
total = db.query(func.sum(Item.value)).scalar() or 0
```

## Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/public-endpoint")
@limiter.limit("10/minute")
def public_action(request: Request):
    ...
```

## Jinja2 Template Rendering

```python
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="engine/templates")

@router.get("/page")
def show_page(request: Request, db: Session = Depends(get_db)):
    items = db.query(Item).all()
    return templates.TemplateResponse(
        "page.html",
        {"request": request, "items": items}
    )
```

## HTMX Response Patterns

For partial updates (HTMX swaps):
```python
@router.post("/items/{item_id}/vote")
def vote(request: Request, item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter_by(id=item_id).first()
    item.votes += 1
    db.commit()
    # Return just the updated fragment
    return templates.TemplateResponse(
        "partials/vote_count.html",
        {"request": request, "item": item}
    )
```

Template fragment (`engine/templates/partials/vote_count.html`):
```html
<span id="vote-count-{{ item.id }}" class="text-lg font-bold">
    {{ item.votes }}
</span>
```

Button that triggers it:
```html
<button hx-post="/items/{{ item.id }}/vote"
        hx-target="#vote-count-{{ item.id }}"
        hx-swap="outerHTML"
        class="bg-blue-500 text-white px-4 py-2 rounded">
    Vote
</button>
```
