"""NPC travel protocol — manages NPCs moving between neighborhoods.

When an NPC crosses a zone boundary:
1. Town Core detects the boundary crossing
2. Validates the travel via Fortress
3. Serializes NPC state and emits to Kafka
4. Marks NPC as 'traveling' (excluded from local tick processing)
5. Waits for npc.travel.complete or timeout (60s)
"""
import asyncio
import json
import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from engine.models import NPC, Event, WorldState
from engine.neighborhoods import get_neighborhood, is_zone_boundary_crossing

logger = logging.getLogger("town-core.travel")

# Active travel timeouts: npc_id -> (destination, start_time, tick)
_active_travels: dict[int, tuple[str, float, int]] = {}

TRAVEL_TIMEOUT_SECONDS = 60


def serialize_npc_state(npc: NPC) -> dict:
    """Serialize NPC to a dict for cross-service transfer via Kafka/proto."""
    return {
        "id": npc.id,
        "name": npc.name,
        "role": npc.role,
        "gold": npc.gold,
        "hunger": npc.hunger,
        "energy": npc.energy,
        "happiness": npc.happiness,
        "age": npc.age,
        "x": npc.x,
        "y": npc.y,
        "personality": json.loads(npc.personality or "{}"),
        "skill": npc.skill,
        "inventory": [],  # v2: will carry items
    }


def check_npc_zone_crossing(db: Session, npc: NPC, new_x: int, new_y: int, tick: int) -> bool:
    """Check if NPC movement crosses a zone boundary. If so, initiate travel.
    
    Returns True if travel was initiated (NPC should NOT continue normal movement).
    Returns False if no crossing detected (NPC moves normally).
    """
    # Skip NPCs already traveling
    if getattr(npc, 'traveling', False):
        return True  # already traveling, skip this NPC
    
    crossing = is_zone_boundary_crossing(npc.x, npc.y, new_x, new_y)
    if crossing is None:
        return False
    
    from_zone, to_zone = crossing
    
    # Don't trigger travel for town_hall <-> town_core (same service)
    if {from_zone, to_zone} <= {"town_core", "town_hall"}:
        return False
    
    # Mark NPC as traveling
    npc.traveling = True
    npc.travel_destination = to_zone
    
    # Record the active travel for timeout monitoring
    _active_travels[npc.id] = (to_zone, time.time(), tick)
    
    # Log the departure event
    event = Event(
        event_type="npc_travel_depart",
        description=f"{npc.name} is traveling from {from_zone} to {to_zone}",
        tick=tick,
        severity="info",
        affected_npc_id=npc.id,
    )
    db.add(event)
    
    logger.info("NPC %d (%s) departing %s -> %s at tick %d",
                npc.id, npc.name, from_zone, to_zone, tick)
    
    return True


async def emit_travel_event(npc: NPC, from_zone: str, to_zone: str, tick: int) -> None:
    """Emit the Kafka travel event (called async after tick commit)."""
    from engine.kafka_producer import emit_npc_travel
    
    npc_state = serialize_npc_state(npc)
    await emit_npc_travel(
        tick=tick,
        npc_id=npc.id,
        from_neighborhood=from_zone,
        to_neighborhood=to_zone,
        npc_state=npc_state,
    )


def check_travel_timeouts(db: Session, current_tick: int) -> list[int]:
    """Check for timed-out travels. Returns list of NPC IDs that timed out."""
    timed_out = []
    now = time.time()
    
    for npc_id, (destination, start_time, tick) in list(_active_travels.items()):
        if now - start_time > TRAVEL_TIMEOUT_SECONDS:
            logger.warning("NPC %d travel to %s timed out after %ds",
                          npc_id, destination, TRAVEL_TIMEOUT_SECONDS)
            
            npc = db.query(NPC).filter(NPC.id == npc_id).first()
            if npc:
                npc.traveling = False
                npc.travel_destination = None
                
                # Log failure event
                event = Event(
                    event_type="travel_failed",
                    description=f"{npc.name} tried to travel to {destination} but the road was closed.",
                    tick=current_tick,
                    severity="low",
                    affected_npc_id=npc_id,
                )
                db.add(event)
            
            del _active_travels[npc_id]
            timed_out.append(npc_id)
    
    return timed_out


def complete_travel(npc_id: int) -> None:
    """Remove NPC from active travels (called when travel.complete is consumed)."""
    _active_travels.pop(npc_id, None)
