"""World state endpoint — returns all tiles, buildings, and NPCs."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/world", tags=["world"])


def _tile_to_dict(tile) -> dict:
    return {
        "id": tile.id,
        "x": tile.x,
        "y": tile.y,
        "terrain": tile.terrain,
    }


def _building_to_dict(building) -> dict:
    return {
        "id": building.id,
        "name": building.name,
        "building_type": building.building_type,
        "x": building.x,
        "y": building.y,
        "capacity": building.capacity,
        "created_at": building.created_at.isoformat() if building.created_at else None,
    }


def _npc_to_dict(npc) -> dict:
    return {
        "id": npc.id,
        "name": npc.name,
        "role": npc.role,
        "x": npc.x,
        "y": npc.y,
        "gold": npc.gold,
        "hunger": npc.hunger,
        "energy": npc.energy,
        "home_building_id": npc.home_building_id,
        "work_building_id": npc.work_building_id,
        "target_x": npc.target_x,
        "target_y": npc.target_y,
        "created_at": npc.created_at.isoformat() if npc.created_at else None,
    }


@router.get("/")
def get_world_state(db: Session = Depends(get_db)):
    """Return complete world state including tiles, buildings, and NPCs."""
    from engine.models import Building, NPC, Tile

    tiles = db.query(Tile).all()
    buildings = db.query(Building).all()
    npcs = db.query(NPC).all()

    return {
        "tiles": [_tile_to_dict(t) for t in tiles],
        "buildings": [_building_to_dict(b) for b in buildings],
        "npcs": [_npc_to_dict(n) for n in npcs],
    }