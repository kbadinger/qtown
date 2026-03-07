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
- **Simulation**: `engine/simulation/` — game logic split into submodules:

| Submodule | What goes here |
|-----------|---------------|
| `constants.py` | BUILDING_TYPES, DEFAULT_BASE_PRICE, etc. |
| `init.py` | init_world_state, init_grid, seed_buildings, seed_npcs |
| `buildings.py` | seed_all_buildings, build_building, all seed_* functions |
| `production.py` | All produce_* functions |
| `effects.py` | Hospital, tavern, church, fountain, school effects |
| `npcs.py` | Movement, needs, decisions, lifecycle, relationships, buying |
| `economy.py` | process_work, pricing, trade, taxes, inflation, recession |
| `weather.py` | update_weather, apply_weather_effects |
| `events.py` | Event triggers (disasters, cascading effects) |
| `tick.py` | process_tick orchestrator |

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

## Simulation Package — Important

`engine/simulation/__init__.py` uses `from .events import *` (and similar for all submodules).
This means **any new function you add to a submodule is automatically importable** via
`from engine.simulation import your_new_function`. You do NOT need to modify `__init__.py`.
Never patch or write to `engine/simulation/__init__.py` — it is protected.

## File Blocklist — NEVER Modify These

You must NEVER create or modify these files:
- `tests/` — all test files (human-written)
- `ralph/` — the orchestrator (human-written)
- `engine/simulation/__init__.py` — auto-re-export facade (human-written)
- `engine/auth.py` — authentication (human-written, security-critical)
- `engine/main.py` — app setup (human-written, security-critical)
- `engine/models.py` — all models pre-added (human-written, BLOCKLISTED)
- `engine/db.py` — database setup (human-written)
- `engine/sprites.py` — sprite generation bridge (human-written)
- `engine/templates/dashboard.html` — progress dashboard (human-written)
- `docs/` — documentation (human-written)
- `HUMAN.md` — human intervention file
- `AGENTS.md` — this file
- `prd.json` — story backlog
- `.env` — environment secrets
- `.gitignore` — git config
- `requirements.txt` — Python dependencies

## What You CAN Modify

- `engine/simulation/*.py` — add/update simulation functions (NOT `__init__.py`)
- `engine/routers/*.py` — create new router files
- `engine/templates/*.html` — create templates
- `engine/static/*` — add static assets

**IMPORTANT: `engine/models.py` is BLOCKLISTED.** All models have been pre-added by the human scaffolder.
Do NOT try to modify, patch, or write to `engine/models.py`. All models you need already exist.
Just import them: `from engine.models import Newspaper, Milestone, Achievement` etc.

Available models (already in models.py):
- Tile, AdminUser, WorldState, Feature, Vote
- Building (has: id, name, building_type, x, y, capacity, level)
- NPC (has: id, name, role, x, y, gold, hunger, energy, happiness, age, max_age, is_dead, is_bankrupt, illness_severity, illness, home_building_id, work_building_id, target_x, target_y, personality, skill, memory_events, favorite_buildings, avoided_areas, experience)
- Transaction, Resource, Treasury, Event, Relationship
- PriceHistory (has: resource_name, price, supply, demand, tick)
- Cost, Loan, Election, Policy, Crime
- Newspaper (has: day, headline, body, author_npc_id, tick)
- Milestone (has: name, description, tick_achieved)
- Achievement (has: name, description, condition, condition_type, condition_value, achieved, unlocked_at)
- VisitorLog (has: npc_id, arrival_tick, greeted_by_npc_id)
- TownAnthem (has: lyrics, composed_by_npc_id, tick_composed)
- Dialogue (has: speaker_npc_id, listener_npc_id, message, tick)

### Which simulation submodule to patch

| Story type | Target file |
|-----------|-------------|
| New building type | `engine/simulation/buildings.py` (seed) + `engine/simulation/production.py` (produce) + `engine/simulation/constants.py` (BUILDING_TYPES) |
| New NPC behavior / buying | `engine/simulation/npcs.py` |
| Economy / trade / pricing | `engine/simulation/economy.py` |
| Events / disasters | `engine/simulation/events.py` |
| Building effects (heal, teach) | `engine/simulation/effects.py` |
| Weather changes | `engine/simulation/weather.py` |
| Tick orchestration changes | `engine/simulation/tick.py` |
| New constants | `engine/simulation/constants.py` |

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

## Sprite Generation (ComfyUI)

When your story adds a new building type or NPC role, generate a sprite for it:

```python
from engine.sprites import generate_building, generate_npc

# Generate a building sprite — returns path or None if ComfyUI is down
path = generate_building("bakery")

# Generate an NPC sprite
path = generate_npc("merchant")
```

- Call these in your router or simulation code whenever a new type/role is created
- They return `None` gracefully if ComfyUI is unavailable — never crash on sprite failure
- Generated sprites land in `assets/buildings/` and `assets/npcs/`
- The PixiJS renderer already serves files from `assets/`

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

Use **`### PATCH:`** for existing files and **`### FILE:`** for new files.

### Patching existing files (preferred)

For files that already exist (especially `engine/simulation/*.py`), output ONLY the new or changed
sections — do NOT rewrite the entire file:

```
### PATCH: engine/simulation/constants.py

### UPDATE CONSTANT: BUILDING_TYPES
BUILDING_TYPES = ["civic", "food", "tavern", "library", "mine"]

### PATCH: engine/simulation/buildings.py

### ADD FUNCTION
def seed_mine(db: Session) -> None:
    """Seed a mine building."""
    from engine.models import Building
    ...full function body...

### PATCH: engine/simulation/tick.py

### UPDATE FUNCTION: process_tick
def process_tick(db: Session) -> None:
    """Run one simulation tick."""
    ...full function body with new call added...
```

Section types:
- `### ADD IMPORT` — new import lines (duplicates are automatically ignored)
- `### ADD FUNCTION` — a completely new function (full body required)
- `### UPDATE FUNCTION: name` — replace an existing function (full body required)
- `### UPDATE CONSTANT: name` — replace a module-level constant (e.g. BUILDING_TYPES)

### Creating new files

For files that do not exist yet, use `### FILE:` with complete contents:

```
### FILE: engine/routers/mining.py
<complete file contents here>
```

Every `### FILE:` block must contain the full, working file content — never use `...` or
`# rest unchanged`.
