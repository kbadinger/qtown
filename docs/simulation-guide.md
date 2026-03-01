# Simulation Architecture Guide

How the Qwen Town simulation engine should be structured.

## Core File: `engine/simulation.py`

All simulation logic lives in `engine/simulation.py`. This file contains pure functions
that take a database session and modify game state.

## Function Patterns

Every simulation function takes `db: Session` as its first argument:

```python
from sqlalchemy.orm import Session
from engine.models import Tile, NPC, Building

def init_grid(db: Session):
    """Initialize the 50x50 tile grid."""
    existing = db.query(Tile).count()
    if existing > 0:
        return  # Already initialized
    for x in range(50):
        for y in range(50):
            db.add(Tile(x=x, y=y, terrain="grass"))
    db.commit()

def process_tick(db: Session):
    """Advance the simulation by one tick."""
    # 1. Update world state (time, weather)
    # 2. Process NPC needs (hunger, energy decay)
    # 3. Process NPC decisions (eat, sleep, work, move)
    # 4. Process production (farms, workshops)
    # 5. Process economy (trades, wages, taxes)
    # 6. Log events
    pass
```

## Adding New Entity Types

1. Add the model to `engine/models.py`
2. Add simulation functions to `engine/simulation.py`
3. Add API endpoints in a new router file `engine/routers/new_entity.py`
4. The model inherits from `Base` (imported from `engine.db`)

Example:
```python
# In engine/models.py
class Resource(Base):
    __tablename__ = "resources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    quantity = Column(Integer, default=0)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
```

## Tick Processing Order

The `process_tick()` function should process systems in this order:

1. **World State** — increment tick counter, advance time of day, change day
2. **Weather** — update weather, apply weather effects
3. **Needs Decay** — hunger increases, energy decreases for all NPCs
4. **NPC Decisions** — each NPC decides what to do based on needs + utility
5. **Movement** — NPCs move toward their targets
6. **Production** — buildings produce resources
7. **Economy** — wages, trades, tax collection
8. **Population** — births, deaths, aging
9. **Events** — log notable events that occurred this tick

## Key Rules

- **All state in SQLite** — no global variables, no in-memory caches
- **Idempotent seeding** — `init_grid()`, `seed_buildings()`, `seed_npcs()` should be safe to call multiple times
- **No imports from ralph/** — simulation is independent of the orchestrator
- **No imports from engine.main** — simulation doesn't know about FastAPI
- **Always commit** — every function that modifies data should `db.commit()` at the end
