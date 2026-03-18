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
from engine.models import Policy, NPC
import random


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


def detect_corruption(db: Session) -> bool | None:
    """Detect corruption by checking if mayor has excessive gold.
    
    Finds the latest Election winner (mayor). If mayor.gold > 2 * avg gold:
    creates Event(event_type='corruption_detected'). Returns True/False.
    Returns None if no mayor.
    """
    # Find latest election with a winner
    latest_election = db.query(Election).filter(Election.winner_npc_id != None).order_by(Election.id.desc()).first()
    
    if not latest_election:
        return None
    
    # Get the mayor NPC (must be alive)
    mayor = db.query(NPC).filter(NPC.id == latest_election.winner_npc_id, NPC.is_dead == 0).first()
    
    if not mayor:
        return None
    
    # Calculate average gold of all living NPCs
    avg_gold = db.query(NPC).filter(NPC.is_dead == 0).with_entities(func.avg(NPC.gold)).scalar() or 0
    
    if avg_gold == 0:
        return None
    
    # Check if mayor has excessive gold
    if mayor.gold > 2 * avg_gold:
        # Get current tick from world state
        world_state = db.query(WorldState).first()
        
        # Create corruption event
        event = Event(
            event_type='corruption_detected',
            description=f'Mayor {mayor.name} has excessive gold: {mayor.gold} vs avg {avg_gold}',
            tick=world_state.tick if world_state else 0
        )
        db.add(event)
        return True
    
    return False


def enforce_curfew(db: Session) -> int:
    """Enforce town curfew - send NPCs home at night.
    
    If WorldState.tick % 24 >= 20 (nighttime), for each living NPC with home_building_id,
    set their target to home coords.
    
    Returns count of NPCs sent home.
    """
    from engine.models import Building
    
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    
    # Check if it's curfew time (tick % 24 >= 20 means evening/night)
    if world_state.tick % 24 < 20:
        return 0
    
    # Find all living NPCs with a home building
    npcs = db.query(NPC).filter(NPC.is_dead == 0, NPC.home_building_id != None).all()
    
    count = 0
    for npc in npcs:
        # Get the home building coordinates
        home_building = db.query(Building).filter(Building.id == npc.home_building_id).first()
        if home_building:
            npc.target_x = home_building.x
            npc.target_y = home_building.y
            count += 1
    
    return count


def give_public_speech(db: Session) -> int | None:
    """Mayor gives a public speech, boosting happiness for all living NPCs."""
    from engine.models import Election, NPC, Dialogue, Event, WorldState
    
    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find latest election winner (order by id since tick may not exist on Election)
    latest_election = db.query(Election).order_by(Election.id.desc()).first()
    if not latest_election or not latest_election.winner_npc_id:
        return None
    
    mayor_id = latest_election.winner_npc_id
    
    # Check if mayor is alive
    mayor = db.query(NPC).filter(NPC.id == mayor_id, NPC.is_dead == 0).first()
    if not mayor:
        return None
    
    # Boost happiness for all living NPCs
    db.query(NPC).filter(NPC.is_dead == 0).update({NPC.happiness: NPC.happiness + 2})
    
    # Create dialogue record
    dialogue = Dialogue(
        speaker_npc_id=mayor_id,
        listener_npc_id=None,
        message="A public speech was given!",
        tick=current_tick
    )
    db.add(dialogue)
    
    # Create event record
    event = Event(
        event_type='public_speech',
        description=f"Mayor {mayor.name} gave a public speech",
        tick=current_tick
    )
    db.add(event)
    
    db.commit()
    return mayor_id


def identify_opposition_leader(db: Session) -> dict | None:
    """Find the opposition leader (second-place candidate in latest election)."""
    from engine.models import Election, Vote
    
    # Find latest election
    latest_election = db.query(Election).order_by(Election.id.desc()).first()
    if not latest_election:
        return None
    
    # Count votes per candidate for this election
    vote_counts = db.query(
        Vote.candidate_npc_id,
        func.count(Vote.id).label('vote_count')
    ).filter(
        Vote.election_id == latest_election.id
    ).group_by(
        Vote.candidate_npc_id
    ).all()
    
    # Need at least 2 candidates
    if len(vote_counts) < 2:
        return None
    
    # Sort by vote count descending
    sorted_votes = sorted(vote_counts, key=lambda x: x.vote_count, reverse=True)
    
    # Second place is opposition leader
    opposition = sorted_votes[1]
    return {
        "opposition_npc_id": opposition.candidate_npc_id,
        "votes": opposition.vote_count
    }


def send_diplomatic_gift(db: Session) -> int:
    """Send diplomatic gifts to visitors."""
    from engine.models import NPC, Treasury, Transaction, WorldState
    
    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Get Treasury
    treasury = db.query(Treasury).first()
    if not treasury:
        return 0
    
    # Find visitors
    visitors = db.query(NPC).filter(NPC.role == 'visitor').all()
    
    count = 0
    for visitor in visitors:
        # Give 20 gold
        visitor.gold += 20
        treasury.gold -= 20
        
        # Create transaction
        tx = Transaction(reason='diplomatic_gift', amount=20, tick=current_tick)
        db.add(tx)
        count += 1
        
    db.commit()
    return count


def allocate_town_budget(db: Session) -> dict:
    """Allocate town budget from Treasury."""
    from engine.models import Treasury, Event, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state and world_state.tick is not None else 0
    
    # Get treasury gold
    treasury = db.query(Treasury).first()
    total_gold = treasury.gold_stored if treasury else 0
    
    # Calculate allocations (40% infrastructure, 30% defense, 20% welfare, 10% events)
    infrastructure = int(total_gold * 0.40)
    defense = int(total_gold * 0.30)
    welfare = int(total_gold * 0.20)
    events_allocation = int(total_gold * 0.10)
    
    # Create event
    event = Event(
        event_type='budget_allocation',
        description=f'Allocated {total_gold} gold: infrastructure={infrastructure}, defense={defense}, welfare={welfare}, events={events_allocation}',
        tick=current_tick,
        severity='info'
    )
    db.add(event)
    db.commit()
    
    return {
        'total': total_gold,
        'infrastructure': infrastructure,
        'defense': defense,
        'welfare': welfare,
        'events': events_allocation
    }


def review_policy_effectiveness(db: Session) -> list[dict]:
    """Review effectiveness of all enacted policies based on NPC happiness."""
    from engine.models import Policy, NPC
    from sqlalchemy import func
    
    # Query all enacted policies - try common column names
    policies = []
    try:
        # Try 'enacted' column first (most likely for Policy)
        policies = db.query(Policy).filter(Policy.enacted == 1).all()
    except AttributeError:
        try:
            # Fall back to 'is_enacted'
            policies = db.query(Policy).filter(Policy.is_enacted == 1).all()
        except AttributeError:
            try:
                # Fall back to 'active'
                policies = db.query(Policy).filter(Policy.active == 1).all()
            except AttributeError:
                # If no enactment column exists, return empty list
                policies = []
    
    # Calculate average NPC happiness
    avg_happiness = 0.0
    npc_count = db.query(NPC).filter(NPC.is_dead == 0).count()
    if npc_count > 0:
        total_happiness = db.query(func.sum(NPC.happiness)).filter(NPC.is_dead == 0).scalar() or 0
        avg_happiness = total_happiness / npc_count
    
    # Build result list
    results = []
    for policy in policies:
        is_effective = avg_happiness > 50
        results.append({
            "policy_id": policy.id,
            "name": policy.name,
            "effective": is_effective
        })
    
    return results


def hold_war_council(db: Session) -> dict | None:
    """Hold a war council if enough guards are present."""
    from engine.models import NPC, Event, Crime, WorldState
    
    # Count living guards (is_dead is Integer, compare with 0)
    guard_count = db.query(NPC).filter(
        NPC.role == 'guard',
        NPC.is_dead == 0
    ).count()

    if guard_count < 3:
        return None

    # Count crimes
    crime_count = db.query(Crime).count()

    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0

    # Create Event
    event = Event(
        event_type='war_council',
        tick=current_tick,
        description="War council held"
    )
    db.add(event)
    db.commit()

    return {
        "action": "war_council_held",
        "guard_count": guard_count,
        "crime_count": crime_count
    }


def hold_expansion_vote(db: Session) -> dict:
    """Hold a town expansion vote."""
    from engine.models import Building, NPC, Event, WorldState
    
    building_count = db.query(Building).count()
    living_npc_count = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    vote_passed = False
    if building_count < living_npc_count:
        vote_passed = random.random() < 0.6
    
    if vote_passed:
        current_tick = db.query(WorldState).first().tick if db.query(WorldState).first() else 0
        event = Event(
            event_type="expansion_vote",
            description="Town expansion vote passed! The town will grow.",
            tick=current_tick
        )
        db.add(event)
        db.commit()
    
    return {
        "vote": "passed" if vote_passed else "failed"
    }


def apply_tax_exemption(db: Session) -> int:
    """Apply tax exemption to NPCs aged 5 or younger."""
    from engine.models import NPC
    import json
    
    exempted_count = 0
    living_children = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.age <= 5
    ).all()
    
    for npc in living_children:
        # Parse memory_events (JSON string)
        try:
            memory_events = json.loads(npc.memory_events) if npc.memory_events else []
        except (json.JSONDecodeError, TypeError):
            memory_events = []
        
        # Add tax_exempt if not present
        if 'tax_exempt' not in memory_events:
            memory_events.append('tax_exempt')
            npc.memory_events = json.dumps(memory_events)
            exempted_count += 1
    
    return exempted_count


def declare_public_holiday(db: Session) -> int:
    """Declare a public holiday.
    
    - Creates an Event with event_type='public_holiday'
    - All living NPCs: energy = min(100, energy+20), happiness += 5
    - target_x=None, target_y=None
    - Returns count of rested NPCs
    """
    from engine.models import NPC, Event, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create the event with the current tick
    event = Event(
        event_type="public_holiday", 
        description="Public Holiday Declared",
        tick=current_tick
    )
    db.add(event)
    
    # Update all living NPCs
    # Using == 0 for is_dead per Postgres compatibility rules
    rested_count = 0
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        npc.energy = min(100, npc.energy + 20)
        npc.happiness = min(100, npc.happiness + 5)
        npc.target_x = None
        npc.target_y = None
        rested_count += 1
    
    db.commit()
    return rested_count


def check_recall_election(db: Session) -> bool:
    """Check if a recall election should be held based on average happiness."""
    from engine.models import NPC, Election, Event
    
    # Calculate average happiness of living NPCs
    avg_happiness = db.query(func.avg(NPC.happiness)).filter(NPC.is_dead == 0).scalar()
    
    if avg_happiness is None or avg_happiness >= 30:
        return False
    
    # Get top 3 NPCs by skill (living NPCs only)
    top_candidates = db.query(NPC).filter(NPC.is_dead == 0).order_by(NPC.skill.desc()).limit(3).all()
    
    if len(top_candidates) < 3:
        return False
    
    # Create Election with top 3 candidates
    election = Election(
        candidates=[c.id for c in top_candidates]
    )
    db.add(election)
    
    # Create Event for recall election
    event = Event(
        event_type='recall_election'
    )
    db.add(event)
    
    db.commit()
    return True


def apply_emergency_tax(db: Session) -> int:
    """Apply emergency tax if disasters occurred in last 10 ticks."""
    from engine.models import Event, NPC, Treasury, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    
    current_tick = world_state.tick
    
    # Check for disaster events in last 10 ticks
    # Using like to catch variations of disaster event types
    disaster_events = db.query(Event).filter(
        Event.tick >= current_tick - 10,
        Event.event_type.like('%disaster%')
    ).all()
    
    if not disaster_events:
        return 0
    
    total_collected = 0
    treasury = db.query(Treasury).first()
    if not treasury:
        return 0
    
    # Get living NPCs (is_dead == 0 for Postgres compatibility)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        tax_amount = 5
        if npc.gold >= tax_amount:
            npc.gold -= tax_amount
            total_collected += tax_amount
        else:
            total_collected += npc.gold
            npc.gold = 0
    
    treasury.gold += total_collected
    
    # Log the tax event
    tax_event = Event(
        event_type='emergency_tax',
        tick=current_tick,
        description='Emergency tax collected due to recent disaster'
    )
    db.add(tax_event)
    
    db.commit()
    return total_collected


def expire_old_policies(db: Session) -> int:
    """Expire enacted policies older than 240 ticks."""
    from engine.models import Policy, Event, WorldState

    world_state = db.query(WorldState).first()
    if not world_state:
        return 0

    current_tick = world_state.tick
    count = 0

    enacted = db.query(Policy).filter(Policy.status == "enacted").all()
    for policy in enacted:
        if policy.enacted_tick is not None and current_tick - policy.enacted_tick > 240:
            policy.status = "expired"
            db.add(Event(
                event_type="policy_expired",
                tick=current_tick,
                description=f"Policy '{policy.name}' has expired after 240 ticks",
            ))
            count += 1

    if count:
        db.commit()
    return count


def save_town_snapshot(db: Session) -> dict | None:
    """Save a town snapshot if tick % 100 == 0.
    
    Captures population, gold, happiness, buildings, weather.
    Stores as Event(event_type='town_snapshot').
    Returns snapshot dict or None.
    """
    from engine.models import WorldState, NPC, Building, Event
    from sqlalchemy import func
    
    ws = db.query(WorldState).first()
    if not ws or ws.tick % 100 != 0:
        return None
    
    # Population
    population = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    # Gold (sum of all NPC gold)
    total_gold = db.query(func.sum(NPC.gold)).filter(NPC.is_dead == 0).scalar() or 0
    
    # Happiness (average of all NPC happiness)
    avg_happiness = db.query(func.avg(NPC.happiness)).filter(NPC.is_dead == 0).scalar() or 0
    
    # Buildings (count by type)
    building_counts = {}
    for b in db.query(Building).all():
        building_counts[b.building_type] = building_counts.get(b.building_type, 0) + 1
    
    # Weather from WorldState
    weather = ws.weather if hasattr(ws, 'weather') else 'unknown'
    
    snapshot = {
        "tick": ws.tick,
        "population": population,
        "total_gold": total_gold,
        "avg_happiness": round(avg_happiness, 2),
        "buildings": building_counts,
        "weather": weather
    }
    
    # Store as Event
    snapshot_event = Event(
        event_type='town_snapshot',
        description=str(snapshot),
        tick=ws.tick
    )
    db.add(snapshot_event)
    db.commit()
    
    return snapshot


def generate_speed_report(db: Session) -> dict:
    """Generate simulation speed report with entity counts and complexity."""
    from engine.models import NPC, Building, Resource, Event, Transaction, WorldState
    
    total_npcs = db.query(NPC).count()
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).count()
    buildings = db.query(Building).count()
    resources = db.query(Resource).count()
    events = db.query(Event).count()
    transactions = db.query(Transaction).count()
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    tick = world_state.tick if world_state else 0
    
    complexity = total_npcs * buildings
    
    return {
        "tick": tick,
        "total_npcs": total_npcs,
        "living_npcs": living_npcs,
        "buildings": buildings,
        "resources": resources,
        "events": events,
        "transactions": transactions,
        "complexity": complexity
    }


def apply_corruption_penalty(db: Session) -> int:
    """Apply corruption penalty if mayor hoarding wealth."""
    from engine.models import NPC, Event, WorldState
    
    mayor = db.query(NPC).filter(NPC.role == "mayor", NPC.is_dead == 0).first()
    if not mayor:
        return 0
    
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0, NPC.id != mayor.id).all()
    if not living_npcs:
        return 0
    
    avg_gold = sum(npc.gold for npc in living_npcs) / len(living_npcs)
    
    if mayor.gold > avg_gold * 3:
        for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
            npc.happiness = max(0, npc.happiness - 8)
        
        world_state = db.query(WorldState).first()
        tick = world_state.tick if world_state else 0
        
        event = Event(
            event_type="corruption_scandal",
            description=f"Mayor {mayor.name} hoarding wealth! Public outrage.",
            tick=tick
        )
        db.add(event)
        
        return 1
    
    return 0


def run_periodic_checks(db: Session, tick: int) -> dict:
    """Run periodic interconnection checks based on tick schedule."""
    results = {}
    
    # Every 10 ticks
    if tick % 10 == 0:
        from engine.simulation.npcs import apply_hunger_penalty
        from engine.simulation.economy import apply_tax_mood
        
        results["apply_hunger_penalty"] = apply_hunger_penalty(db)
        results["apply_tax_mood"] = apply_tax_mood(db)
    
    # Every 25 ticks
    if tick % 25 == 0:
        from engine.simulation.economy import check_food_scarcity
        from engine.simulation.buildings import check_housing_pressure
        
        results["check_food_scarcity"] = check_food_scarcity(db)
        results["check_housing_pressure"] = check_housing_pressure(db)
    
    # Every 50 ticks
    if tick % 50 == 0:
        from engine.simulation.npcs import check_poverty_crime
        from engine.simulation.economy import check_economic_cycle
        
        results["check_poverty_crime"] = check_poverty_crime(db)
        results["check_economic_cycle"] = check_economic_cycle(db)
    
    # Every 100 ticks
    if tick % 100 == 0:
        from engine.simulation.npcs import check_guard_demand
        from engine.simulation.buildings import apply_crime_penalty
        
        results["check_guard_demand"] = check_guard_demand(db)
        results["apply_crime_penalty"] = apply_crime_penalty(db)
    
    return results
