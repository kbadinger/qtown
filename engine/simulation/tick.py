"""Main simulation tick orchestrator."""

from sqlalchemy.orm import Session

from engine.models import NPC, WorldState
from engine.simulation.init import init_world_state, assign_work_and_homes
from engine.simulation.buildings import seed_all_buildings
from engine.simulation.weather import update_weather, apply_weather_effects
from engine.simulation.npcs import (
    eat, sleep_npc, calculate_happiness, move_npc_toward_target, wander,
    update_relationships, check_marriage, check_population_growth, age_npcs,
)
from engine.simulation.production import (
    produce_resources, produce_bakery_resources, produce_blacksmith_resources,
    produce_farm_resources, produce_library_resources,
    produce_mine_resources, produce_lumber_mill_resources,
    produce_fishing_dock_resources, produce_guard_tower_resources,
    produce_gate_resources, produce_well_resources,
    produce_warehouse_resources, produce_bank_resources,
    produce_theater_resources, produce_art,
)
from engine.simulation.effects import (
    process_hospital, process_tavern, process_school_skill_gain,
    apply_church_effects, apply_fountain_effects,
)
from engine.simulation.economy import (
    process_work, collect_taxes, track_inflation,
)
import json
from sqlalchemy import func
from engine.models import Event
from engine.models import Election


def process_tick(db: Session) -> None:
    """Advance the simulation by one tick.
    
    Processes all game systems in order:
    1. World State — time, weather
    2. NPC Needs — hunger, energy decay
    3. NPC Decisions — eat, sleep, work, move
    4. Movement — NPCs move toward targets
    5. Production — buildings produce resources
    6. Economy — wages, trades, tax collection
    7. Population — births, deaths, aging
    8. Events — log notable events
    """
    # 0. Ensure all building types are seeded and NPCs assigned (idempotent)
    seed_all_buildings(db)
    assign_work_and_homes(db)

    # 1. Update world state (time, weather)
    world_state = db.query(WorldState).first()
    if not world_state:
        init_world_state(db)
        world_state = db.query(WorldState).first()
    
    world_state.tick += 1
    
    # Advance time of day
    time_order = ['morning', 'afternoon', 'evening', 'night']
    current_time_idx = time_order.index(world_state.time_of_day)
    world_state.time_of_day = time_order[(current_time_idx + 1) % 4]
    
    # Change day every 4 ticks
    if world_state.time_of_day == 'morning':
        world_state.day += 1
    
    # 2. Process weather
    update_weather(db)
    apply_weather_effects(db)
    
    # 3. Process NPC needs (hunger, energy decay)
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    for npc in npcs:
        npc.hunger = min(100, npc.hunger + 5)
        npc.energy = max(0, npc.energy - 3)
    
    # 4. Process NPC decisions (eat, sleep, work, move)
    for npc in npcs:
        # Decide based on needs
        if npc.hunger > 50:
            # Try to eat
            if npc.gold >= 5:
                eat(db, npc.id)
        elif npc.energy < 30:
            # Try to sleep
            sleep_npc(db, npc.id)
        
        # Calculate happiness
        calculate_happiness(db, npc.id)
    
    # 5. Wander + movement (snow halves movement - every other tick)
    weather = world_state.weather
    if weather != 'snow' or world_state.tick % 2 == 0:
        # Re-query NPCs fresh to avoid stale session state from earlier commits
        npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
        for npc in npcs:
            wander(db, npc)
            move_npc_toward_target(db, npc)
    
    # 6. Process production
    produce_resources(db, weather)
    produce_bakery_resources(db)  # Bakery production
    produce_blacksmith_resources(db)  # Blacksmith production
    produce_farm_resources(db)  # Farm production
    produce_library_resources(db)  # Library production
    produce_mine_resources(db)  # Mine production
    produce_lumber_mill_resources(db)  # Lumber Mill production
    produce_fishing_dock_resources(db)  # Fishing Dock production
    produce_guard_tower_resources(db)  # Guard Tower production
    produce_gate_resources(db)  # Gate production
    produce_well_resources(db)  # Well production
    produce_warehouse_resources(db)  # Warehouse production
    produce_bank_resources(db)  # Bank production
    produce_theater_resources(db)  # Theater production
    produce_art(db)  # Art production from Theater
    process_hospital(db)  # Hospital healing
    process_tavern(db)  # Tavern effects
    
    # 7. Process economy (wages, trades, tax collection)
    process_work(db)
    
    # Collect taxes every 10 ticks
    if world_state.tick % 10 == 0:
        collect_taxes(db)
    
    # Track inflation every 10 ticks
    if world_state.tick % 10 == 0:
        track_inflation(db)
    
    # 8. Process population (births, deaths, aging)
    check_population_growth(db)
    
    # Age NPCs every 100 ticks
    if world_state.tick % 100 == 0:
        age_npcs(db)
    
    # 9. Log events (notable events)
    # Events are logged throughout other functions
    
    # Process school skill gains every 5 ticks
    if world_state.tick % 5 == 0:
        process_school_skill_gain(db)
    
    # Apply church effects
    apply_church_effects(db)
    
    # Apply fountain effects
    apply_fountain_effects(db)
    
    # Update relationships
    update_relationships(db)
    
    # Check for marriages every 50 ticks
    if world_state.tick % 50 == 0:
        check_marriage(db)
    
    # Hold mayoral election every 500 ticks
    if world_state.tick % 500 == 0:
        from engine.simulation.events import hold_election
        hold_election(db)
    
    db.commit()


def generate_end_of_day_report(db: Session) -> dict | None:
    """Generate end-of-day report every 24 ticks.
    
    Compiles: population, total_gold, avg_happiness, events_today (last 24 ticks), weather.
    Creates Event event_type='end_of_day_report' with all stats in description JSON.
    Returns stats dict or None if not end of day.
    """
    from engine.models import WorldState, NPC
    
    world_state = db.query(WorldState).first()
    if not world_state:
        return None
    
    # Check if it's end of day (every 24 ticks)
    if world_state.tick % 24 != 0:
        return None
    
    # Compile stats
    population = db.query(NPC).filter(NPC.is_dead == 0).count()
    total_gold = db.query(NPC).filter(NPC.is_dead == 0).with_entities(func.sum(NPC.gold)).scalar() or 0
    avg_happiness = db.query(NPC).filter(NPC.is_dead == 0).with_entities(func.avg(NPC.happiness)).scalar() or 0
    
    # Get events from last 24 ticks
    events_today = db.query(Event).filter(Event.tick >= world_state.tick - 24).all()
    events_list = [{"id": e.id, "event_type": e.event_type, "description": e.description} for e in events_today]
    
    stats = {
        "population": population,
        "total_gold": total_gold,
        "avg_happiness": avg_happiness,
        "events_today": events_list,
        "weather": world_state.weather
    }
    
    # Create Event with stats in description JSON
    event = Event(
        event_type='end_of_day_report',
        description=json.dumps(stats),
        tick=world_state.tick
    )
    db.add(event)
    
    return stats


def calculate_approval_rating(db: Session) -> dict | None:
    """Calculate political approval rating for the current mayor.
    
    Finds the latest Election with a winner_npc_id.
    Returns None if no election exists.
    Returns dict with mayor_npc_id, approval (avg happiness of living NPCs), population.
    """
    # Find latest election with a winner (order by id descending)
    latest_election = db.query(Election).filter(Election.winner_npc_id != None).order_by(Election.id.desc()).first()
    
    if not latest_election:
        return None
    
    # Calculate approval as average happiness of living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    if not living_npcs:
        return None
    
    total_happiness = sum(npc.happiness for npc in living_npcs)
    population = len(living_npcs)
    approval = total_happiness / population
    
    return {
        "mayor_npc_id": latest_election.winner_npc_id,
        "approval": approval,
        "population": population
    }
