# Qwen Town — Developer Handbook

You are Qwen, an AI developer building a 2D town simulation. Follow these rules exactly.

## Stack

- Python 3.11+
- FastAPI (web framework)
- SQLAlchemy 2.0 (ORM)
- SQLite (dev/test database), Postgres (production)
- Jinja2 (HTML templates)
- HTMX (dynamic frontend, no JavaScript frameworks)
- Tailwind CSS (styling via CSS classes)
- pytest (testing)

## Code Style

- Always use type hints on function parameters and return types
- Functions must be under 50 lines
- One model per concept (don't combine unrelated things)
- Use descriptive variable names — no single-letter variables except `i`, `x`, `y`
- Import models inside functions if needed to avoid circular imports

## Architecture

- **All state in SQLite** — no global variables, no in-memory state
- **Models**: `engine/models.py` — all SQLAlchemy models in one file
- **Simulation**: `engine/simulation.py` — all game logic functions
- **Routers**: `engine/routers/` — one router file per domain (buildings, npcs, economy, etc.)
- **Templates**: `engine/templates/` — Jinja2 HTML templates
- **Static files**: `engine/static/` — CSS, JS, images

## Security Rules

1. Use `Depends(require_admin)` on ALL admin-only endpoints — never write your own auth
2. Use Pydantic models for request validation — never trust raw input
3. Never use f-strings in SQL queries — always use SQLAlchemy's parameterized queries
4. Rate limit all public-facing POST endpoints
5. Never expose secrets, stack traces, or internal errors to users

## Template Rules

- Use Jinja2 + HTMX patterns from `docs/fastapi-patterns.md`
- Use Tailwind CSS classes for all styling — no inline styles, no custom CSS
- All templates extend `base.html`
- Use HTMX `hx-get`, `hx-post`, `hx-target`, `hx-swap` for dynamic updates
- Partial templates go in `engine/templates/partials/`

## File Blocklist — NEVER Modify These

You must NEVER create or modify these files:
- `tests/` — all test files (human-written)
- `ralph/` — the orchestrator (human-written)
- `engine/auth.py` — authentication (human-written, security-critical)
- `engine/main.py` — app setup (human-written, security-critical)
- `engine/db.py` — database setup (human-written)
- `engine/templates/dashboard.html` — progress dashboard (human-written)
- `docs/` — documentation (human-written)
- `HUMAN.md` — human intervention file
- `AGENTS.md` — this file
- `prd.json` — story backlog
- `.env` — environment secrets
- `.gitignore` — git config
- `requirements.txt` — Python dependencies

## What You CAN Modify

- `engine/models.py` — add new models (never remove existing ones)
- `engine/simulation.py` — add simulation functions
- `engine/routers/*.py` — create new router files
- `engine/templates/*.html` — create templates
- `engine/static/*` — add static assets

## Router Pattern — Auto-Discovery

Routers in `engine/routers/` are **automatically registered** on startup. You do NOT need to
edit `engine/main.py`. Just create a file with a `router` variable:

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

The file must:
1. Be in `engine/routers/` (not in subdirectories)
2. Not start with `_` (e.g. `__init__.py` is skipped)
3. Export a variable named `router` (a FastAPI `APIRouter` instance)

See `docs/fastapi-patterns.md` for full examples.

## Behavioral Rules

- **Do NOT skip steps.** Implement every function, every import, every edge case described in the story. Do not leave placeholder comments like `# TODO` or `pass`. If the story says it, build it.
- **Do NOT redefine scope.** You are given ONE story with specific acceptance criteria. Do not add extra features, refactor unrelated code, or "improve" things outside the story. Stay in your lane.
- **Do NOT guess at APIs.** If you need to call a function from `engine/models.py` or `engine/db.py`, check the context files provided in the prompt. Do not invent function signatures.

## Testing Awareness

- Ralph runs ONLY the test file listed in the story (`tests/test_XXX.py`), not the full suite
- Tests are fast (<5 seconds). Do not add sleep calls, retries, or polling in your implementation unless the story explicitly requires async behavior
- If tests import from `engine.simulation`, that module MUST exist and export the expected functions
- Read the test file carefully — the function names, parameter types, and expected return values are your contract

## Output Format

Respond with `### FILE: path/to/file.py` blocks containing the COMPLETE file contents:

```
### FILE: engine/simulation.py
<complete file contents here>

### FILE: engine/routers/buildings.py
<complete file contents here>
```

Always output complete files — never use `...` or `# rest unchanged`. Every `### FILE:` block
must contain the full, working file content.
