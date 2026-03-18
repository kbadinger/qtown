"""Event triggers — disasters, cascading effects, etc."""

from sqlalchemy.orm import Session

from engine.models import WorldState, Event
import random
from engine.simulation.constants import PLAGUE_OVERWHELM_THRESHOLD
import json
from datetime import datetime
from sqlalchemy import desc
from typing import Optional
from engine.simulation.weather import get_season
from engine.models import Building
from engine.models import NPC
from sqlalchemy import func


def trigger_drought(db: Session) -> None:
    """Trigger a drought event that reduces resource production."""
    from engine.models import Event, WorldState
    from engine.simulation.constants import DROUGHT_FAMINE_THRESHOLD
    
    # Get world state
    world_state = db.query(WorldState).first()
    if not world_state:
        world_state = WorldState(tick=0, day=1, time_of_day="morning", weather="clear")
        db.add(world_state)
        db.commit()
    
    current_tick = world_state.tick
    
    # Set drought active flag in WorldState
    world_state.drought_active = 1
    
    # Check for prolonged drought (cascading to famine)
    drought_events = db.query(Event).filter(
        Event.event_type == "drought"
    ).all()
    
    # Count drought events in the last DROUGHT_FAMINE_THRESHOLD ticks
    recent_drought_count = sum(
        1 for evt in drought_events 
        if current_tick - evt.tick < DROUGHT_FAMINE_THRESHOLD
    )
    
    # Create drought event
    drought_event = Event(
        event_type="drought",
        description="A severe drought has begun, reducing resource production by 50%",
        tick=current_tick,
        severity="high"
    )
    db.add(drought_event)
    
    # Check if drought has lasted long enough to trigger famine
    if recent_drought_count >= DROUGHT_FAMINE_THRESHOLD:
        # Create famine event (cascading effect)
        famine_event = Event(
            event_type="famine",
            description="Drought has cascaded into famine! NPC hunger increases by 15 per tick",
            tick=current_tick,
            severity="critical"
        )
        db.add(famine_event)
    
    db.commit()


def trigger_flood(db: Session) -> None:
    """Trigger a flood event that damages all buildings and causes price spike."""
    from engine.models import Building, NPC, WorldState, Event
    
    # Create flood event
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    flood_event = Event(
        event_type="flood",
        description="A severe flood has damaged all buildings in the town",
        tick=current_tick,
        severity="high"
    )
    db.add(flood_event)
    
    # Damage all buildings by reducing their capacity
    buildings = db.query(Building).all()
    for building in buildings:
        building.capacity = max(1, building.capacity // 2)
    
    # Reduce energy for living NPCs in flooded zone (y < 5)
    flooded_npcs = db.query(NPC).filter(NPC.y < 5, NPC.is_dead == 0).all()
    for npc in flooded_npcs:
        npc.energy = max(0, npc.energy - 20)
    
    # Cascade: trigger price spike event
    price_spike_event = Event(
        event_type="price_spike",
        description="Food prices triple due to crop destruction from flood",
        tick=current_tick,
        severity="high"
    )
    db.add(price_spike_event)
    
    db.commit()


def trigger_fire(db: Session) -> None:
    """Trigger a fire event that destroys a random building."""
    from engine.models import Building
    import random
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    
    # Select a random building to destroy
    buildings = db.query(Building).all()
    if not buildings:
        return  # No buildings to destroy
    
    affected_building = random.choice(buildings)
    
    # Create fire event
    fire_event = Event(
        event_type="fire",
        description=f"A fire has destroyed {affected_building.name}",
        tick=world_state.tick if world_state else 0,
        severity="high",
        affected_building_id=affected_building.id
    )
    db.add(fire_event)
    
    # Cascade: Trigger rebuilding boom
    rebuilding_event = Event(
        event_type="rebuilding_boom",
        description=f"Rebuilding effort initiated after fire at {affected_building.name}",
        tick=world_state.tick if world_state else 0,
        severity="medium",
        affected_building_id=affected_building.id
    )
    db.add(rebuilding_event)
    
    db.commit()


def trigger_plague(db: Session) -> None:
    """Trigger a plague event that increases NPC illness severity."""
    from engine.models import NPC, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create plague event
    plague_event = Event(
        event_type="plague",
        description="A plague has spread through the town, increasing illness severity",
        tick=current_tick,
        severity="high"
    )
    db.add(plague_event)
    
    # Increase illness for all NPCs
    npcs = db.query(NPC).all()
    sick_count = 0
    total_alive = 0
    
    for npc in npcs:
        # Skip already dead NPCs
        if npc.is_dead:
            continue
            
        total_alive += 1
        
        # Increase illness severity by 20
        npc.illness_severity = min(100, npc.illness_severity + 20)
        npc.illness = npc.illness_severity
        
        # Count as sick if illness_severity > 0
        if npc.illness_severity > 0:
            sick_count += 1
        
        # Kill NPC if severity reaches 100
        if npc.illness_severity >= 100:
            npc.is_dead = 1
    
    # Check for hospital overwhelmed cascade (50%+ sick)
    if total_alive > 0:
        sick_ratio = sick_count / total_alive
        if sick_ratio >= PLAGUE_OVERWHELM_THRESHOLD:
            # Create hospital_overwhelmed event
            overwhelmed_event = Event(
                event_type="hospital_overwhelmed",
                description=f"Hospital overwhelmed: {sick_count} of {total_alive} NPCs sick ({int(sick_ratio*100)}%)",
                tick=current_tick,
                severity="critical"
            )
            db.add(overwhelmed_event)
            
            # Reduce hospital healing by 75% - store in WorldState
            # We'll track this via a new field or use existing fields
            # For now, we create an event that can be read by effects system
            healing_reduction_event = Event(
                event_type="healing_reduced",
                description="Hospital healing capacity reduced by 75% due to plague",
                tick=current_tick,
                severity="warning"
            )
            db.add(healing_reduction_event)
    
    db.commit()


def trigger_harvest_festival(db: Session) -> None:
    """Trigger a harvest festival event that increases NPC happiness and doubles food."""
    from engine.models import NPC, WorldState, Resource

    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0

    # Create harvest festival event
    festival_event = Event(
        event_type="harvest_festival",
        description="A harvest festival has begun, boosting town happiness",
        tick=current_tick,
        severity="low"
    )
    db.add(festival_event)

    # Increase happiness for all NPCs (capped at 100)
    npcs = db.query(NPC).all()
    for npc in npcs:
        npc.happiness = min(100, npc.happiness + 20)

    # Double food/grain resources
    food_resources = db.query(Resource).filter(
        Resource.name.ilike("%food%") | Resource.name.ilike("%grain%")
    ).all()
    for resource in food_resources:
        resource.quantity *= 2

    db.commit()


def trigger_bandit_raid(db: Session) -> None:
    """Trigger a bandit raid that steals gold from Treasury and NPCs."""
    from engine.models import Treasury, NPC, Building, Event, WorldState
    from engine.simulation.constants import JUSTICE_RESPONSE_GUARD_THRESHOLD
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Count living NPCs with role="guard" to reduce theft (5% reduction per guard)
    guard_npcs = db.query(NPC).filter(
        NPC.role == "guard",
        NPC.is_dead == 0
    ).all()
    num_guards = len(guard_npcs)
    
    # Calculate theft reduction (5% per guard, capped at 100%)
    theft_reduction = min(num_guards * 0.05, 1.0)
    
    # Steal from Treasury (20% base, reduced by guards)
    treasuries = db.query(Treasury).all()
    total_stolen_from_treasury = 0
    for treasury in treasuries:
        base_theft = treasury.gold_stored * 0.20
        actual_theft = int(base_theft * (1 - theft_reduction))
        treasury.gold_stored = max(0, treasury.gold_stored - actual_theft)
        total_stolen_from_treasury += actual_theft
    
    # Steal from random NPCs (10% base, reduced by guards)
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    if npcs:
        # Select random NPCs to steal from (up to 20% of population)
        num_victims = max(1, len(npcs) // 5)
        victims = random.sample(npcs, min(num_victims, len(npcs)))
        
        for npc in victims:
            base_theft = npc.gold * 0.10
            actual_theft = int(base_theft * (1 - theft_reduction))
            npc.gold = max(0, npc.gold - actual_theft)
    
    # Create bandit raid event log
    raid_event = Event(
        event_type="bandit_raid",
        description=f"Bandits raided the town, stealing gold from treasury and citizens",
        tick=current_tick,
        severity="high"
    )
    db.add(raid_event)
    
    # Create justice response event (cascade effect)
    if num_guards > JUSTICE_RESPONSE_GUARD_THRESHOLD:
        justice_description = f"Guards ({num_guards}) pursue bandits. Bandits will be caught and imprisoned."
        severity = "medium"
    else:
        justice_description = f"Guards ({num_guards}) pursue bandits. Bandits will escape and raid again in 50 ticks."
        severity = "low"
    
    justice_event = Event(
        event_type="justice_response",
        description=justice_description,
        tick=current_tick,
        severity=severity
    )
    db.add(justice_event)
    
    db.commit()


def trigger_earthquake(db: Session) -> int:
    """Trigger an earthquake event that damages 1-3 random buildings."""
    from engine.models import Building, Event, WorldState, NPC
    import random
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create earthquake event
    earthquake_event = Event(
        event_type="earthquake",
        description="An earthquake has shaken the town, damaging buildings",
        tick=current_tick,
        severity=3
    )
    db.add(earthquake_event)
    
    # Pick 1-3 random buildings
    buildings = db.query(Building).all()
    if not buildings:
        db.commit()
        return 0
    
    num_to_damage = random.randint(1, min(3, len(buildings)))
    damaged_buildings = random.sample(buildings, num_to_damage)
    
    damaged_count = 0
    for building in damaged_buildings:
        if building.level > 1:
            building.level -= 1
        damaged_count += 1
    
    # Reduce all NPCs happiness by 5
    npcs = db.query(NPC).all()
    for npc in npcs:
        npc.happiness = max(0, npc.happiness - 5)
    
    db.commit()
    return damaged_count


def trigger_market_crash(db: Session) -> None:
    """Trigger a market crash event that reduces all resource prices by 60%."""
    from engine.models import Resource, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create market crash event
    market_crash_event = Event(
        event_type="market_crash",
        description="A market crash has occurred, reducing all resource prices by 60%",
        tick=current_tick,
        severity="high"
    )
    db.add(market_crash_event)
    
    # Reduce all resource prices by 60%
    resources = db.query(Resource).all()
    for resource in resources:
        if hasattr(resource, 'price') and resource.price is not None:
            resource.price = max(1, int(resource.price * 0.4))  # Reduce by 60%
    
    db.commit()


def trigger_baby_boom(db: Session) -> None:
    """Trigger a baby boom event that spawns 5-10 new NPCs."""
    from engine.models import NPC, Event, WorldState
    import random
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Determine number of babies to spawn (5-10)
    num_babies = random.randint(5, 10)
    
    # Spawn new NPCs
    roles = ['farmer', 'merchant', 'guard', 'builder', 'healer', 'scholar']
    for i in range(num_babies):
        baby = NPC(
            name=f"Baby {i+1}",
            role=random.choice(roles),
            x=random.randint(0, 49),
            y=random.randint(0, 49),
            gold=0,
            hunger=50,
            energy=100,
            happiness=100,
            age=0,
            max_age=80,
            is_dead=0,
            illness_severity=0,
            illness=0
        )
        db.add(baby)
    
    # Create baby boom event
    baby_boom_event = Event(
        event_type="baby_boom",
        description=f"A baby boom has occurred, {num_babies} new citizens have been born",
        tick=current_tick,
        severity="low"
    )
    db.add(baby_boom_event)
    db.commit()


def trigger_gold_rush(db: Session) -> None:
    """Trigger a gold rush event that doubles gold production."""
    from engine.models import Event, WorldState
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Set gold rush active flag in WorldState
    if world_state:
        world_state.gold_rush_active = 1
    
    # Create gold rush event
    gold_rush_event = Event(
        event_type="gold_rush",
        description="A gold rush has begun, doubling gold production for all workers",
        tick=current_tick,
        severity="medium"
    )
    db.add(gold_rush_event)
    db.commit()


def apply_priest_healing(db: Session) -> None:
    """Apply +5 healing to NPCs near priests at Church buildings."""
    from engine.models import NPC, Building
    
    # Find all Church buildings
    churches = db.query(Building).filter(
        Building.building_type == "church"
    ).all()
    
    # Find all priest NPCs
    priests = db.query(NPC).filter(
        NPC.role == "priest",
        NPC.is_dead == 0
    ).all()
    
    # For each priest, check if they're at a church
    for priest in priests:
        # Check if priest is at any church location
        at_church = False
        for church in churches:
            if priest.x == church.x and priest.y == church.y:
                at_church = True
                break
        
        if not at_church:
            continue
        
        # Find nearby NPCs (within 5 tiles)
        nearby_npcs = db.query(NPC).filter(
            NPC.is_dead == 0,
            NPC.id != priest.id,
            NPC.x.between(priest.x - 5, priest.x + 5),
            NPC.y.between(priest.y - 5, priest.y + 5)
        ).all()
        
        # Apply +5 healing to nearby NPCs
        for npc in nearby_npcs:
            # Reduce illness severity by 5 (healing effect)
            npc.illness_severity = max(0, npc.illness_severity - 5)
            npc.illness = npc.illness_severity
    
    db.commit()


def hold_election(db: Session) -> dict:
    """Hold a mayoral election.
    
    Every 500 ticks, NPCs vote for mayor. Highest vote count wins.
    Returns election data including winner_npc_id.
    """
    from engine.models import Election, NPC, WorldState
    
    # Get current tick
    world_state = db.query(WorldState).first()
    if not world_state:
        return {}
    
    current_tick = world_state.tick
    
    # Select candidates: NPCs who are alive, not dead, not bankrupt, and age >= 30
    candidates = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.is_bankrupt == 0,
        NPC.age >= 18
    ).all()
    
    if not candidates:
        # No eligible candidates, create a placeholder election
        election = Election(
            candidate_npc_ids='[]',
            votes='{}',
            winner_npc_id=None,
            tick_held=current_tick
        )
        db.add(election)
        db.commit()
        return {"winner_npc_id": None, "message": "No eligible candidates"}
    
    # Prepare candidate IDs
    candidate_ids = [c.id for c in candidates]
    
    # Simulate votes from all living NPCs
    voters = db.query(NPC).filter(NPC.is_dead == 0).all()
    votes = {c.id: 0 for c in candidates}
    
    for voter in voters:
        # Simple voting logic: random candidate weighted slightly by happiness
        # Higher happiness NPCs are more likely to vote for the "happiest" candidate
        # For simplicity in this simulation, we just pick a random candidate
        # but we can add bias later if needed.
        if random.random() < 0.8:  # 80% turnout
            chosen = random.choice(candidates)
            votes[chosen.id] += 1
    
    # Determine winner
    winner_id = max(votes, key=votes.get) if votes else None
    winner_votes = votes.get(winner_id, 0)
    
    # Create election record
    election = Election(
        candidate_npc_ids=json.dumps(candidate_ids),
        votes=json.dumps(votes),
        winner_npc_id=winner_id,
        tick_held=current_tick
    )
    db.add(election)
    
    # Update winner's role to "mayor"
    if winner_id:
        winner_npc = db.query(NPC).filter(NPC.id == winner_id).first()
        if winner_npc:
            winner_npc.role = "mayor"
    
    db.commit()
    
    return {
        "winner_npc_id": winner_id,
        "winner_votes": winner_votes,
        "total_votes": sum(votes.values()),
        "candidates": candidate_ids
    }


def propose_policy(db: Session, name: str, effect: dict) -> "Policy | None":
    """Mayor proposes a new policy. Returns Policy or None if no mayor."""
    from engine.models import Policy, Election, NPC

    election = db.query(Election).order_by(Election.tick_held.desc()).first()
    if not election or not election.winner_npc_id:
        return None

    mayor = db.query(NPC).filter(NPC.id == election.winner_npc_id).first()
    if not mayor:
        return None

    policy = Policy(
        name=name,
        description=f"Policy: {name}",
        effect=json.dumps(effect),
        proposed_by_npc_id=mayor.id,
    )
    db.add(policy)
    db.commit()
    return policy


def form_parties(db: Session) -> None:
    """Form political parties from NPCs with similar personalities. No-op placeholder."""
    from engine.models import NPC
    # Placeholder — Qwen will flesh out party logic in later stories
    db.commit()


def check_achievements(db: Session) -> None:
    """Check all achievements and unlock those whose conditions are met."""
    from engine.models import Achievement, Event, Building
    
    # Get all unachieved achievements
    achievements = db.query(Achievement).filter(Achievement.achieved == 0).all()
    
    for ach in achievements:
        # Parse condition (stored as JSON string)
        try:
            condition = json.loads(ach.condition)
        except (json.JSONDecodeError, TypeError):
            continue
        
        # Check building_count condition
        if "building_count" in condition:
            required_count = condition.get("building_count", 0)
            actual_count = db.query(Building).count()
            
            if actual_count >= required_count:
                ach.achieved = True
                ach.unlocked_at = datetime.now()
                
                # Create event
                event = Event(
                    event_type="achievement",
                    description=f"Achievement unlocked: {ach.name}",
                    tick=0  # Will be set by tick processor
                )
                db.add(event)
    
    db.commit()


def generate_newspaper(db: Session) -> None:
    """Generate a newspaper entry summarizing recent events."""
    from engine.models import Newspaper, Event, WorldState, NPC
    
    # Get current world state
    world_state = db.query(WorldState).first()
    if not world_state:
        world_state = WorldState(tick=0, day=1, time_of_day="morning")
        db.add(world_state)
        db.commit()
    
    # Query recent events (last 24 ticks)
    recent_events = db.query(Event).filter(
        Event.tick >= world_state.tick - 24
    ).order_by(desc(Event.tick)).limit(10).all()
    
    # Generate headline based on events
    if recent_events:
        headline = f"Town Updates: {len(recent_events)} Notable Events"
    else:
        headline = "Another Quiet Day in Town"
    
    # Generate body with event summaries
    body_parts = []
    for event in recent_events:
        body_parts.append(f"- {event.event_type}: {event.description}")
    
    if body_parts:
        body = "\n".join(body_parts)
    else:
        body = "No major events occurred this period."
    
    # Find an author NPC (preferably a journalist or town crier)
    author_npc = db.query(NPC).filter(
        NPC.role.in_(['journalist', 'town_crier', 'merchant'])
    ).first()
    
    # Create newspaper entry
    newspaper = Newspaper(
        day=world_state.day,
        headline=headline,
        body=body,
        author_npc_id=author_npc.id if author_npc else None,
        tick=world_state.tick
    )
    db.add(newspaper)
    db.commit()


def apply_triggered_event(db: Session, event_type: str) -> None:
    """Apply a triggered event with immediate effects."""
    from engine.models import WorldState, Event, NPC, Building
    from datetime import datetime
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create the event record
    event = Event(
        event_type=event_type,
        description=f"{event_type.replace('_', ' ').title()} triggered",
        tick=current_tick,
        severity="info",
        created_at=datetime.now()
    )
    db.add(event)
    
    # Apply immediate effects based on event type
    if event_type == "thunderstorm":
        # Set weather to storm for 5 ticks
        if world_state:
            world_state.weather = "storm"
            world_state.weather_duration = 5
    elif event_type == "festival":
        # Boost all NPC happiness by 20
        for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
            npc.happiness = min(100, npc.happiness + 20)
    elif event_type == "gold_rush":
        # Give all miners +50 gold
        for npc in db.query(NPC).filter(NPC.role == "miner", NPC.is_dead == 0).all():
            npc.gold = npc.gold + 50
    elif event_type == "baby_boom":
        # Spawn 3 new NPCs
        from engine.simulation.npcs import seed_npc
        for _ in range(3):
            seed_npc(db, role="citizen")
    
    db.commit()


def process_event_chains(db: Session) -> int:
    """Process multi-day event chains - create follow-up events for high severity events."""
    from engine.models import Event, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Query high severity events from last 3 ticks (current_tick - 2 to current_tick)
    high_events = db.query(Event).filter(
        Event.severity == 'high',
        Event.tick >= current_tick - 2,
        Event.tick <= current_tick
    ).all()
    
    follow_up_count = 0
    
    for event in high_events:
        # Check if follow-up already exists (same event_type + '_aftermath' at same tick)
        follow_up_type = event.event_type + '_aftermath'
        existing_follow_up = db.query(Event).filter(
            Event.event_type == follow_up_type,
            Event.tick == event.tick
        ).first()
        
        if not existing_follow_up:
            # Create follow-up event with '_aftermath' suffix and severity one level lower
            follow_up = Event(
                event_type=follow_up_type,
                severity='medium',
                tick=event.tick,
                description=f"Aftermath of {event.event_type}"
            )
            db.add(follow_up)
            follow_up_count += 1
    
    db.commit()
    return follow_up_count


def escalate_events(db: Session) -> int:
    """Escalate event severity based on guard presence and duration."""
    from sqlalchemy.orm import Session
    from sqlalchemy import func
    from engine.models import Event, NPC, Building, WorldState
    
    escalations = 0
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    
    current_tick = world_state.tick
    
    # Query medium severity events created in last 5 ticks
    medium_events = db.query(Event).filter(
        Event.severity == 'medium',
        Event.tick >= current_tick - 5
    ).all()
    
    for event in medium_events:
        if event.affected_building_id:
            building = db.query(Building).filter(
                Building.id == event.affected_building_id
            ).first()
            
            if building:
                # Check for guard NPCs within 10 tiles
                guards = db.query(NPC).filter(
                    NPC.role == 'guard',
                    NPC.is_dead == 0,
                    func.abs(NPC.x - building.x) <= 10,
                    func.abs(NPC.y - building.y) <= 10
                ).count()
                
                if guards == 0:
                    event.severity = 'high'
                    escalations += 1
    
    # Query high severity events created 10+ ticks ago (unresolved)
    high_events = db.query(Event).filter(
        Event.severity == 'high',
        Event.tick <= current_tick - 10
    ).all()
    
    for event in high_events:
        event.severity = 'critical'
        escalations += 1
    
    db.commit()
    return escalations


def apply_recovery_bonus(db: Session) -> bool:
    """Apply recovery bonus after critical events."""
    from engine.models import Event, NPC
    
    # Get current tick from latest event
    latest_event = db.query(Event).order_by(Event.tick.desc()).first()
    current_tick = latest_event.tick if latest_event else 0
    
    # Check for critical events 20-30 ticks ago
    old_critical = db.query(Event).filter(
        Event.severity == 'critical',
        Event.tick >= current_tick - 30,
        Event.tick <= current_tick - 20
    ).first()
    
    if not old_critical:
        return False
    
    # Check no current critical events (within last 20 ticks)
    current_critical = db.query(Event).filter(
        Event.severity == 'critical',
        Event.tick > current_tick - 20
    ).first()
    
    if current_critical:
        return False
    
    # Check if recovery already applied (within last 50 ticks)
    existing_recovery = db.query(Event).filter(
        Event.event_type == 'recovery',
        Event.tick > current_tick - 50
    ).first()
    
    if existing_recovery:
        return False
    
    # Apply happiness bonus to all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    for npc in living_npcs:
        npc.happiness = min(npc.happiness + 10, 100)
    
    # Create recovery event
    recovery_event = Event(
        event_type='recovery',
        severity='minor',
        tick=current_tick,
        description='Recovery bonus applied after critical event'
    )
    db.add(recovery_event)
    db.commit()
    
    return True


def check_anniversaries(db: Session) -> bool:
    """Check if current day is an anniversary and trigger events."""
    from sqlalchemy.orm import Session
    from sqlalchemy import update, func
    from engine.models import WorldState, Event, NPC, Newspaper
    
    world_state = db.query(WorldState).first()
    if not world_state:
        return False
    
    day = world_state.day
    if day % 100 == 0:
        # Create Event
        event = Event(
            name='Anniversary',
            event_type='anniversary',
            description=f'Town celebrates day {day}!',
            tick=world_state.tick
        )
        db.add(event)
        
        # Update NPC happiness
        db.execute(update(NPC).values(happiness=func.coalesce(NPC.happiness, 0) + 15))
        
        # Create Newspaper
        newspaper = Newspaper(
            day=day,
            headline='Anniversary Celebration!',
            body=f'Town celebrates day {day}!',
            author_npc_id=None,
            tick=world_state.tick
        )
        db.add(newspaper)
        
        db.commit()
        return True
    
    return False


def spawn_visitor_trader(db: Session) -> "Optional[NPC]":
    """Spawn a visitor trader NPC with 5% chance."""
    from engine.models import NPC, Event
    
    # 5% chance to spawn
    if random.random() >= 0.05:
        return None
    
    # Pick random edge position (x or y = 0 or 49)
    edge = random.choice(['left', 'right', 'top', 'bottom'])
    if edge == 'left':
        x, y = 0, random.randint(0, 49)
    elif edge == 'right':
        x, y = 49, random.randint(0, 49)
    elif edge == 'top':
        x, y = random.randint(0, 49), 0
    else:  # bottom
        x, y = random.randint(0, 49), 49
    
    # Create visitor trader NPC
    visitor = NPC(
        name=f"Trader {random.randint(1, 1000)}",
        role='visitor_trader',
        x=x,
        y=y,
        gold=150,
        hunger=50,
        energy=50,
        happiness=70,
        age=30,
        max_age=70,
        is_dead=0,
        is_bankrupt=0,
        illness_severity=0,
        illness=0,
        home_building_id=None,
        work_building_id=None,
        target_x=None,
        target_y=None,
        personality='outgoing',
        skill='trading',
        memory_events='[]',
        favorite_buildings='[]',
        avoided_areas='[]',
        experience='{}'
    )
    db.add(visitor)
    
    # Create event record
    event = Event(
        event_type='visitor_trader',
        description=f"Trader {visitor.name} has arrived at the edge of town",
        tick=db.query(Event).order_by(Event.id.desc()).first().id + 1 if db.query(Event).first() else 1,
    )
    db.add(event)
    
    db.flush()

    return visitor


def send_diplomat(db: Session):
    """Send the highest-skilled non-mayor NPC on a diplomatic mission."""
    from engine.models import NPC, Event

    living = db.query(NPC).filter(NPC.is_dead == 0).all()
    if not living:
        return None

    # Pick NPC with highest skill value, excluding mayor
    candidates = [n for n in living if n.role != "mayor"]
    if not candidates:
        return None

    diplomat = max(candidates, key=lambda n: len(n.skill or ""))

    # Set target to edge of map
    diplomat.target_x = 49
    diplomat.target_y = diplomat.y

    # Record mission in experience
    import json as _json
    try:
        exp = _json.loads(diplomat.experience or "{}")
    except (ValueError, TypeError):
        exp = {}
    if isinstance(exp, list):
        exp = {}
    exp["mission_start_tick"] = 0  # will be updated by tick
    diplomat.experience = _json.dumps(exp)

    # Create event
    evt = Event(
        event_type="diplomatic_mission",
        description=f"{diplomat.name} sent on diplomatic mission",
        tick=0,
    )
    db.add(evt)
    db.flush()

    return diplomat.name


def hold_festival_vote(db: Session) -> str:
    """Hold a festival vote based on NPC needs."""
    from engine.models import NPC, Event, WorldState
    from datetime import datetime
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Get all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    if not living_npcs:
        # No NPCs to vote, default to rest_day
        event = Event(
            event_type="rest_day",
            description="Town festival: Rest Day",
            tick=current_tick,
            severity="info",
            affected_npc_id=None,
            affected_building_id=None,
            created_at=datetime.now()
        )
        db.add(event)
        db.commit()
        return "rest_day"
    
    # Tally votes based on lowest stat (lowest value = highest need)
    # hunger -> food_festival, happiness -> music_festival, energy -> rest_day
    votes = {"food_festival": 0, "music_festival": 0, "rest_day": 0}
    
    for npc in living_npcs:
        # Find the lowest stat value
        stats = [npc.hunger, npc.happiness, npc.energy]
        min_val = min(stats)
        
        if npc.hunger == min_val:
            votes["food_festival"] += 1
        elif npc.happiness == min_val:
            votes["music_festival"] += 1
        else:
            votes["rest_day"] += 1
    
    # Pick winner (highest votes, with deterministic tiebreaker)
    winner = max(votes, key=lambda k: (votes[k], k))
    
    # Create event with proper tick value
    event = Event(
        event_type=winner,
        description=f"Town festival: {winner.replace('_', ' ').title()}",
        tick=current_tick,
        severity="info",
        affected_npc_id=None,
        affected_building_id=None,
        created_at=datetime.now()
    )
    db.add(event)
    db.commit()
    
    return winner


def predict_weather(db: Session) -> str:
    """
    Predict the next weather based on current WorldState.weather.
    
    Weather transition probabilities:
    - sunny: 70% sunny, 20% cloudy, 10% rain
    - cloudy: 30% sunny, 40% cloudy, 30% rain
    - rain: 10% sunny, 40% cloudy, 40% rain, 10% storm
    
    Returns: predicted weather string
    """
    from sqlalchemy.orm import Session
    
    # Get current weather from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return "sunny"  # Default if no world state exists
    
    current_weather = world_state.weather or "sunny"
    
    # Define weather transition probabilities
    weather_transitions = {
        "sunny": [
            ("sunny", 0.70),
            ("cloudy", 0.20),
            ("rain", 0.10),
        ],
        "cloudy": [
            ("sunny", 0.30),
            ("cloudy", 0.40),
            ("rain", 0.30),
        ],
        "rain": [
            ("sunny", 0.10),
            ("cloudy", 0.40),
            ("rain", 0.40),
            ("storm", 0.10),
        ],
    }
    
    # Get transition options for current weather (default to sunny if unknown)
    transitions = weather_transitions.get(current_weather, weather_transitions["sunny"])
    
    # Generate random number for probability selection
    roll = random.random()
    cumulative_probability = 0.0
    
    # Select weather based on cumulative probability
    for weather, probability in transitions:
        cumulative_probability += probability
        if roll <= cumulative_probability:
            predicted_weather = weather
            break
    else:
        predicted_weather = transitions[-1][0]  # Fallback to last option
    
    # Store prediction in WorldState (optional, for persistence)
    if hasattr(world_state, 'predicted_weather'):
        world_state.predicted_weather = predicted_weather
        db.commit()
    
    return predicted_weather


def calculate_crop_yield(db: Session) -> int:
    """Calculate crop yield based on season, weather, and worker skill."""
    from engine.models import NPC
    
    # Base yield
    yield_value = 10.0
    
    # Season multiplier
    season = get_season(db)
    season_multipliers = {
        "spring": 1.2,
        "summer": 1.5,
        "fall": 1.0,
        "winter": 0.3
    }
    yield_value *= season_multipliers.get(season, 1.0)
    
    # Weather multiplier
    from engine.models import WorldState
    ws = db.query(WorldState).first()
    weather = getattr(ws, 'weather', 'cloudy') if ws else 'cloudy'
    weather_multipliers = {
        "sunny": 1.2,
        "cloudy": 1.0,
        "rain": 0.8,
        "storm": 0.2
    }
    yield_value *= weather_multipliers.get(weather, 1.0)
    
    # Worker skill bonus (highest farmer skill * 0.1)
    farmers = db.query(NPC).filter(NPC.role == "farmer").all()
    if farmers:
        max_skill = max(farmer.skill for farmer in farmers if farmer.skill is not None)
        yield_value += max_skill * 0.1
    
    # Return as integer
    return int(yield_value)


def distribute_famine_relief(db: Session) -> bool:
    """Distribute famine relief when food is scarce and population is high."""
    from sqlalchemy.orm import Session
    from engine.models import Resource, Treasury, Event, NPC
    
    # Check if any Food Resource has quantity < 10
    food_resources = db.query(Resource).filter(Resource.name == "Food").all()
    food_low = any(r.quantity < 10 for r in food_resources)
    
    # Check if living NPC count > 3 (is_dead == 0 for Postgres compatibility)
    living_npc_count = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    if not food_low or living_npc_count <= 3:
        return False
    
    # Take 30 gold from first Treasury
    treasuries = db.query(Treasury).all()
    if treasuries:
        treasury = treasuries[0]
        treasury.gold = max(0, treasury.gold - 30)
    
    # Add 20 to first Food resource quantity
    if food_resources:
        food_resources[0].quantity += 20
    
    # Create Event with event_type='famine_relief'
    event = Event(event_type="famine_relief")
    db.add(event)
    
    # Reduce each NPC hunger by 10 (floor 0)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    for npc in living_npcs:
        npc.hunger = max(0, npc.hunger - 10)
    
    db.commit()
    return True


def apply_event_damage(db: Session) -> int:
    """Apply damage to buildings from critical events in the last 5 ticks.
    
    For each Event with severity='critical' in last 5 ticks that has affected_building_id:
    - Reduce that building's capacity by 3 (floor at 1)
    - If building capacity drops to 1, create follow-up Event event_type='building_destroyed'
    
    Returns count of buildings damaged.
    """
    from engine.models import Event, Building, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    current_tick = world_state.tick
    
    # Find all critical events in last 5 ticks with affected_building_id
    critical_events = db.query(Event).filter(
        Event.severity == 'critical',
        Event.affected_building_id != None,
        Event.tick >= current_tick - 5,
        Event.tick <= current_tick
    ).all()
    
    buildings_damaged = set()
    
    for event in critical_events:
        building = db.query(Building).filter(
            Building.id == event.affected_building_id,
            Building.capacity > 1
        ).first()
        
        if building:
            # Reduce capacity by 3, floor at 1
            building.capacity = max(1, building.capacity - 3)
            buildings_damaged.add(building.id)
            
            # If capacity drops to 1, create follow-up event
            if building.capacity == 1:
                destroyed_event = Event(
                    event_type='building_destroyed',
                    severity='critical',
                    affected_building_id=building.id,
                    tick=current_tick,
                    description=f"Building {building.name} destroyed"
                )
                db.add(destroyed_event)
    
    db.commit()
    return len(buildings_damaged)


def generate_event_news(db: Session) -> int:
    """Generate newspaper coverage for events created in the current tick."""
    from engine.models import Event, Newspaper, WorldState
    
    # Get current tick from world state
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    
    current_tick = world_state.tick
    
    # Find events created in current tick
    events = db.query(Event).filter(Event.tick == current_tick).all()
    
    article_count = 0
    for event in events:
        # Build headline with BREAKING prefix for critical events
        headline = f"BREAKING: {event.event_type}" if event.severity == 'critical' else f"{event.event_type}"
        body = event.description
        
        # Create newspaper article
        article = Newspaper(
            day=world_state.day,
            headline=headline,
            body=body,
            author_npc_id=None,  # System-generated
            tick=current_tick
        )
        db.add(article)
        article_count += 1
    
    db.commit()
    return article_count


def create_memorial(db: Session) -> Optional[Building]:
    """Create a memorial building after a critical event that affected a building."""
    from engine.models import Event
    
    # Find the most recent critical event that affected a building
    critical_event_types = ['fire', 'flood', 'earthquake', 'bandit_raid']
    event = db.query(Event).filter(
        Event.affected_building_id.isnot(None),
        Event.event_type.in_(critical_event_types)
    ).order_by(Event.tick.desc()).first()
    
    if not event:
        return None
    
    # Find the affected building
    affected_building = db.query(Building).filter(Building.id == event.affected_building_id).first()
    if not affected_building:
        return None
    
    # Calculate memorial position (near affected building, capped at 49)
    memorial_x = min(affected_building.x + 1, 49)
    memorial_y = min(affected_building.y + 1, 49)
    
    # Create memorial building
    memorial = Building(
        building_type='memorial',
        name=f'Memorial for {event.event_type}',
        x=memorial_x,
        y=memorial_y,
        capacity=1,
        level=1
    )
    db.add(memorial)
    db.commit()
    
    return memorial


def calculate_prevention_chance(db: Session) -> float:
    """Calculate event prevention chance based on guard NPCs.
    
    Each guard adds 5% prevention chance, capped at 50%.
    Only counts living guards (is_dead == 0).
    
    Args:
        db: SQLAlchemy database session
        
    Returns:
        float: Prevention chance between 0.0 and 0.5
    """
    guard_count = db.query(NPC).filter(NPC.role == 'guard', NPC.is_dead == 0).count()
    prevention_chance = guard_count * 0.05
    return min(prevention_chance, 0.5)


def process_seasonal_visitors(db: Session) -> int:
    """Process seasonal migration of tourists."""
    from engine.models import NPC, Event
    
    season = get_season(db)
    visitor_count = 0
    
    if season == 'summer':
        # 10% chance to spawn a visitor NPC
        import random
        if random.random() < 0.1:
            # Spawn a tourist NPC
            tourist = NPC(
                name=f"Tourist {db.query(NPC).count() + 1}",
                role='tourist',
                gold=50,
                hunger=50,
                energy=50,
                happiness=50,
                age=30,
                max_age=80,
                is_dead=0,
                is_bankrupt=0,
                illness_severity=0,
                illness=0,
                x=25,
                y=25,
                target_x=25,
                target_y=25,
                personality='friendly',
                skill='sightseeing',
                memory_events='[]',
                favorite_buildings='[]',
                avoided_areas='[]',
                experience='{}'
            )
            db.add(tourist)
            
            # Create event for arrival
            event = Event(
                event_type='visitor_arrival',
                description=f"A tourist has arrived in town",
                tick=db.query(Feature).filter_by(feature_name='current_tick').first().value if db.query(Feature).filter_by(feature_name='current_tick').first() else 0,
                resolved=0
            )
            db.add(event)
            
            visitor_count += 1
    
    elif season == 'winter':
        # Any existing tourist NPCs leave (set is_dead=1)
        tourists = db.query(NPC).filter_by(role='tourist').all()
        for tourist in tourists:
            tourist.is_dead = 1
            
            # Create event for departure
            event = Event(
                event_type='visitor_departure',
                description=f"{tourist.name} has left town for winter",
                tick=db.query(Feature).filter_by(feature_name='current_tick').first().value if db.query(Feature).filter_by(feature_name='current_tick').first() else 0,
                resolved=0
            )
            db.add(event)
            
            visitor_count += 1
    
    db.commit()
    return visitor_count


def check_legendary_event(db: Session) -> bool:
    """Check and trigger legendary event."""
    from engine.models import WorldState, Event, NPC, Building, Treasury, Newspaper
    import random

    world_state = db.query(WorldState).first()
    if not world_state or world_state.tick <= 1000:
        return False

    existing_legendary = db.query(Event).filter(Event.event_type == 'legendary').first()
    if existing_legendary:
        return False

    if random.random() >= 0.01:
        return False

    # Trigger legendary event
    # 1. All NPCs flee (set target to random edge)
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    for npc in npcs:
        # Random edge: x=0, x=49, y=0, or y=49
        if random.random() < 0.5:
            npc.target_x = random.choice([0, 49])
            npc.target_y = random.randint(0, 49)
        else:
            npc.target_x = random.randint(0, 49)
            npc.target_y = random.choice([0, 49])

    # 2. All buildings lose 1 capacity
    buildings = db.query(Building).all()
    for building in buildings:
        if building.capacity > 0:
            building.capacity -= 1

    # 3. 500 gold added to Treasury
    treasury = db.query(Treasury).first()
    if treasury:
        treasury.gold += 500

    # 4. Create Event
    new_event = Event(
        event_type='legendary',
        name='dragon_sighting',
        description='A dragon has been sighted!',
        tick=world_state.tick,
        resolved=0
    )
    db.add(new_event)

    # 5. Create Newspaper
    new_paper = Newspaper(
        day=world_state.tick,
        headline='Dragon Sighting!',
        body='A legendary dragon has been spotted near the town!',
        author_npc_id=None,
        tick=world_state.tick
    )
    db.add(new_paper)

    db.commit()
    return True


def assign_factions(db: Session) -> dict:
    """Assign political factions to NPCs based on their attributes."""
    from engine.models import NPC
    import json
    
    faction_counts = {
        'merchants_guild': 0,
        'artisans_guild': 0,
        'reform_party': 0,
        'independents': 0
    }
    
    # Get all living NPCs
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in npcs:
        # Parse experience JSON
        experience = {}
        if npc.experience:
            parsed = json.loads(npc.experience)
            experience = parsed if isinstance(parsed, dict) else {}
        
        # Skip if already has a faction
        if 'faction' in experience:
            continue
        
        # Assign faction based on priority
        if npc.gold > 50:
            faction = 'merchants_guild'
        elif npc.skill > 5:
            faction = 'artisans_guild'
        elif npc.happiness < 40:
            faction = 'reform_party'
        else:
            faction = 'independents'
        
        # Update experience with faction
        experience['faction'] = faction
        npc.experience = json.dumps(experience)
        
        # Count the faction
        faction_counts[faction] += 1
    
    db.commit()
    return faction_counts


def manage_proposal_queue(db: Session) -> int:
    """Manage the policy proposal queue - keep only 3 active proposals."""
    from engine.models import Policy
    
    # Find all active proposals
    active_proposals = db.query(Policy).filter(Policy.status == 'proposed').all()
    count = len(active_proposals)
    
    # If more than 3, reject the oldest
    if count > 3:
        # Find the oldest proposed policy
        oldest = db.query(Policy).filter(
            Policy.status == 'proposed'
        ).order_by(Policy.tick_proposed.asc()).first()
        
        if oldest:
            oldest.status = 'expired'
            db.commit()
            count = count - 1
    
    return count


def check_term_limits(db: Session) -> bool:
    """Check if mayor has reached term limit and trigger election if so."""
    from engine.models import NPC, WorldState, Event
    import json
    
    # Get current tick
    world_state = db.query(WorldState).first()
    if not world_state:
        return False
    
    current_tick = world_state.tick
    
    # Find mayor
    mayor = db.query(NPC).filter(
        NPC.role == 'mayor',
        NPC.is_dead == 0
    ).first()
    
    if not mayor:
        return False
    
    # Check experience for mayor_since_tick
    try:
        parsed = json.loads(mayor.experience)
        experience = parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError, AttributeError):
        experience = {}
    
    mayor_since_tick = experience.get('mayor_since_tick')
    
    if mayor_since_tick is None:
        return False
    
    # Check if term limit reached (> 240 ticks)
    if current_tick - mayor_since_tick > 240:
        # Trigger new election
        hold_election(db)
        
        # Create event
        event = Event(
            event_type='term_limit_reached',
            tick=current_tick
        )
        db.add(event)
        db.commit()
        
        return True
    
    return False


def check_impeachment(db: Session) -> bool:
    """Check if mayor should be impeached due to low public happiness.
    
    Finds the mayor, calculates average happiness of living NPCs.
    If avg < 25, 60% chance of removal. If removed, sets role to 'citizen',
    triggers election, creates impeachment event.
    Returns True if mayor was removed.
    """
    mayor = db.query(NPC).filter(NPC.role == 'mayor').first()
    if not mayor:
        return False
    
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    if not living_npcs:
        return False
    
    avg_happiness = sum(npc.happiness for npc in living_npcs) / len(living_npcs)
    
    if avg_happiness < 25 and random.random() < 0.6:
        mayor.role = 'citizen'
        hold_election(db)
        
        world_state = db.query(WorldState).first()
        current_tick = world_state.tick if world_state else 0
        
        event = Event(
            event_type='impeachment',
            description='Mayor impeached due to low public happiness',
            tick=current_tick
        )
        db.add(event)
        db.commit()
        return True
    
    return False


def check_tax_revolt(db: Session) -> bool:
    """Check if tax revolt should be triggered based on tax rate and NPC happiness."""
    from engine.models import WorldState, NPC, Event
    
    # Get current world state
    world = db.query(WorldState).first()
    if not world:
        return False
    
    # Check if tax rate is too high (> 20%)
    if world.tax_rate <= 0.2:
        return False
    
    # Calculate average NPC happiness (only living NPCs)
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    if not npcs:
        return False
    
    avg_happiness = sum(npc.happiness for npc in npcs) / len(npcs)
    
    # Check if average happiness is too low (< 30)
    if avg_happiness >= 30:
        return False
    
    # Trigger revolt - NPCs refuse to pay tax for 10 ticks
    revolt_until_tick = world.tick + 10
    
    # Update WorldState with revolt_until_tick
    world.revolt_until_tick = revolt_until_tick
    
    # Create Event for tax revolt
    event = Event(
        event_type='tax_revolt',
        severity='high',
        description='Tax revolt triggered due to high taxes and low happiness',
        tick=world.tick
    )
    db.add(event)
    db.commit()
    
    return True


def launch_public_works(db: Session) -> str | None:
    """Launch public works project: upgrade lowest capacity building."""
    from engine.models import Treasury, Building, Event, WorldState
    
    # Check Treasury gold
    treasury = db.query(Treasury).first()
    if not treasury or treasury.gold <= 100:
        return None
    
    # Find building with lowest capacity
    building = db.query(Building).order_by(Building.capacity).first()
    if not building:
        return None
    
    # Spend gold
    treasury.gold -= 50
    
    # Upgrade capacity
    building.capacity += 3
    
    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create Event
    event = Event(
        event_type='public_works',
        description=f"Public works upgraded {building.name}",
        tick=current_tick
    )
    db.add(event)
    
    db.commit()
    return building.name


def run_census(db: Session) -> dict | None:
    """Run a census of the town."""
    from sqlalchemy import func
    from engine.models import NPC, Building, Event, WorldState
    import json
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return None
    
    current_tick = world_state.tick
    
    # Check if census was run in last 50 ticks
    last_census = db.query(Event).filter(
        Event.event_type == 'census',
        Event.tick > current_tick - 50
    ).first()
    
    if last_census:
        return None
    
    # Count living NPCs (is_dead == 0)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    # Count dead NPCs (is_dead == 1)
    dead_npcs = db.query(NPC).filter(NPC.is_dead == 1).count()
    
    # Count total buildings
    total_buildings = db.query(Building).count()
    
    # Total gold (sum of all NPC gold)
    total_gold_result = db.query(func.sum(NPC.gold)).scalar()
    total_gold = total_gold_result if total_gold_result is not None else 0
    
    # Avg happiness
    avg_happiness_result = db.query(func.avg(NPC.happiness)).scalar()
    avg_happiness = avg_happiness_result if avg_happiness_result is not None else 0.0
    
    # Avg age
    avg_age_result = db.query(func.avg(NPC.age)).scalar()
    avg_age = avg_age_result if avg_age_result is not None else 0.0
    
    stats = {
        "living_npcs": living_npcs,
        "dead_npcs": dead_npcs,
        "total_buildings": total_buildings,
        "total_gold": total_gold,
        "avg_happiness": avg_happiness,
        "avg_age": avg_age,
        "tick": current_tick
    }
    
    # Store as Event
    new_event = Event(
        event_type='census',
        description=json.dumps(stats),
        tick=current_tick
    )
    db.add(new_event)
    db.commit()
    
    return stats


def generate_charter(db: Session) -> list[str]:
    """Generate town charter newspaper from enacted policies."""
    from engine.models import Policy, Newspaper, WorldState
    
    # Get current world state
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    current_day = world_state.day if world_state else 1
    
    # Fetch enacted policies
    policies = db.query(Policy).filter(Policy.status == 'enacted').all()
    policy_names = [policy.name for policy in policies]
    
    # Construct newspaper body
    if policy_names:
        body_lines = ["Town Charter Updated", "", "Enacted Policies:"]
        for name in policy_names:
            body_lines.append(f"- {name}")
        body = "\n".join(body_lines)
    else:
        body = "Town Charter Updated\n\nNo enacted policies found."
    
    # Create newspaper entry
    newspaper = Newspaper(
        day=current_day,
        headline="Town Charter Updated",
        body=body,
        author_npc_id=None,
        tick=current_tick
    )
    db.add(newspaper)
    db.commit()
    
    return policy_names


def grant_emergency_powers(db: Session) -> bool:
    """Grant emergency powers to mayor if critical events exist in last 5 ticks."""
    from engine.models import Event, NPC, WorldState
    
    # Get current tick
    world_state = db.query(WorldState).first()
    if not world_state:
        return False
    
    current_tick = world_state.tick
    
    # Check for critical events in last 5 ticks
    critical_events = db.query(Event).filter(
        Event.severity == 'critical',
        Event.tick >= current_tick - 5,
        Event.tick <= current_tick
    ).all()
    
    if not critical_events:
        return False
    
    # Find mayor NPC
    mayor = db.query(NPC).filter(NPC.role == 'mayor').first()
    if not mayor:
        return False
    
    # Parse experience JSON
    parsed = json.loads(mayor.experience) if mayor.experience else {}
    experience = parsed if isinstance(parsed, dict) else {}
    
    # Grant emergency powers with expiration tick
    experience['emergency_powers'] = True
    experience['emergency_powers_expires_at'] = current_tick + 20
    
    # Update NPC
    mayor.experience = json.dumps(experience)
    db.commit()
    
    return True


def generate_daily_digest(db: Session) -> dict:
    """Generate a daily digest summarizing the last 24 ticks."""
    from engine.models import WorldState, Event, NPC, Newspaper, Treasury
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return {"error": "No world state found"}
    
    current_tick = world_state.tick
    current_day = world_state.day
    start_tick = max(0, current_tick - 24)
    
    # Count events by type in last 24 ticks
    events = db.query(Event).filter(
        Event.tick >= start_tick,
        Event.tick <= current_tick
    ).all()
    
    events_by_type = {}
    for event in events:
        event_type = event.event_type if hasattr(event, 'event_type') else "unknown"
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
    
    # Count NPC births and deaths
    # Births: NPCs with age == 0 (newborns)
    # Deaths: NPCs with is_dead == 1
    all_npcs = db.query(NPC).all()
    
    births = 0
    deaths = 0
    
    for npc in all_npcs:
        # Check if NPC died (is_dead == 1)
        if npc.is_dead == 1:
            deaths += 1
        # Check if NPC is newborn (age == 0)
        if npc.age == 0:
            births += 1
    
    # Calculate gold change from Treasury
    gold_change = 0
    treasury = db.query(Treasury).first()
    if treasury:
        # Gold change is estimated from current treasury state
        # In a full implementation, we'd track historical gold values
        gold_change = treasury.gold
    
    # Count weather changes from Feature (if available)
    weather_changes = 0
    try:
        from engine.models import Feature
        weather_features = db.query(Feature).filter(
            Feature.tick >= start_tick,
            Feature.tick <= current_tick,
            Feature.feature_type == "weather"
        ).all()
        weather_changes = len(weather_features)
    except (AttributeError, TypeError):
        # Feature model may not have these fields
        weather_changes = 0
    
    # Create Newspaper entry for the daily digest
    headline = f"Daily Digest Day {current_day}"
    body = f"""
    Town Summary for Day {current_day}:
    - Events: {len(events)} total
    - Births: {births}, Deaths: {deaths}
    - Gold Change: {gold_change:+d}
    - Weather Changes: {weather_changes}
    
    Events by Type:
    {chr(10).join(f'  - {k}: {v}' for k, v in events_by_type.items())}
    """
    
    newspaper = Newspaper(
        day=current_day,
        headline=headline,
        body=body,
        author_npc_id=None,
        tick=current_tick
    )
    db.add(newspaper)
    db.commit()
    
    # Return summary dict
    summary = {
        "day": current_day,
        "tick": current_tick,
        "events_total": len(events),
        "events_by_type": events_by_type,
        "births": births,
        "deaths": deaths,
        "gold_change": gold_change,
        "weather_changes": weather_changes,
        "newspaper_id": newspaper.id
    }
    
    return summary


def calculate_danger_scores(db: Session) -> dict:
    """Calculate danger scores for each tile based on crimes and disasters within 5 tiles.
    
    Score = crime_count * 2 + disaster_count * 3
    Returns dict of {(x,y): danger_score} for tiles with score > 0.
    """
    from engine.models import Crime, Event
    
    crimes = db.query(Crime).all()
    events = db.query(Event).all()
    
    # Get all unique tile coordinates from crimes and events
    all_coords = set()
    for crime in crimes:
        if hasattr(crime, 'x') and hasattr(crime, 'y'):
            all_coords.add((crime.x, crime.y))
    for event in events:
        if hasattr(event, 'x') and hasattr(event, 'y'):
            all_coords.add((event.x, event.y))
    
    danger_scores = {}
    
    for tx, ty in all_coords:
        crime_count = 0
        disaster_count = 0
        
        for crime in crimes:
            if hasattr(crime, 'x') and hasattr(crime, 'y'):
                dx = abs(crime.x - tx)
                dy = abs(crime.y - ty)
                if dx <= 5 and dy <= 5:
                    crime_count += 1
        
        for event in events:
            if hasattr(event, 'x') and hasattr(event, 'y'):
                dx = abs(event.x - tx)
                dy = abs(event.y - ty)
                if dx <= 5 and dy <= 5:
                    disaster_count += 1
        
        score = crime_count * 2 + disaster_count * 3
        if score > 0:
            danger_scores[(tx, ty)] = score
    
    return danger_scores


def trigger_festival_of_lights(db: Session) -> int:
    """
    Trigger the Festival of Lights event.
    
    - Creates Event with event_type='festival_of_lights', severity=0
    - Increases happiness by 10 for all living NPCs
    - Adds 'festival_of_lights' to each NPC's memory_events
    - Returns count of NPCs affected
    """
    import json
    
    # Create the event record
    from engine.models import WorldState
    ws = db.query(WorldState).first()
    current_tick = ws.tick if ws else 0

    event = Event(
        event_type='festival_of_lights',
        description='The town celebrates the Festival of Lights!',
        tick=current_tick,
        severity=0
    )
    db.add(event)

    # Find all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    affected_count = 0
    
    for npc in living_npcs:
        # Increase happiness
        npc.happiness = min(100, npc.happiness + 10)
        
        # Add to memory_events
        try:
            memory_events = json.loads(npc.memory_events) if npc.memory_events else []
        except (json.JSONDecodeError, TypeError):
            memory_events = []
        
        if 'festival_of_lights' not in memory_events:
            memory_events.append('festival_of_lights')
            npc.memory_events = json.dumps(memory_events)
        
        affected_count += 1
    
    db.commit()
    
    return affected_count


def trigger_wedding_festival(db: Session) -> int:
    """Trigger a wedding festival event for all married couples."""
    from engine.models import NPC, Relationship, Event
    
    # Query all spouse relationships
    couples = db.query(Relationship).filter(
        Relationship.relationship_type == "spouse"
    ).all()
    
    if not couples:
        return 0
    
    # Get unique NPC IDs involved in marriages to avoid double counting happiness
    married_npc_ids = set()
    for rel in couples:
        married_npc_ids.add(rel.npc_id_1)
        married_npc_ids.add(rel.npc_id_2)
    
    # Increase happiness for all living married NPCs
    living_married = db.query(NPC).filter(
        NPC.id.in_(married_npc_ids),
        NPC.is_dead == 0
    ).all()
    
    for npc in living_married:
        npc.happiness = min(npc.happiness + 5, 100)
    
    # Create the event
    event = Event(
        event_type="wedding_festival",
        description="A town-wide wedding celebration!"
    )
    db.add(event)
    
    db.commit()
    
    return len(couples)


def trigger_talent_show(db: Session) -> Optional[int]:
    """Trigger a talent show event.
    
    Find living NPC with highest skill. Award 50 gold, happiness += 10.
    Create Event and Transaction(reason='talent_show_prize').
    Return winner NPC id or None.
    """
    from engine.models import NPC, Event, Transaction, WorldState
    
    # Find living NPC with highest skill
    winner = db.query(NPC).filter(
        NPC.is_dead == 0
    ).order_by(NPC.skill.desc()).first()
    
    if not winner:
        return None
    
    # Award prize - 50 gold
    winner.gold = winner.gold + 50
    
    # Increase happiness by 10 (cap at 100)
    winner.happiness = min(winner.happiness + 10, 100)
    
    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find or create a town representative NPC for the sender
    town_npc = db.query(NPC).filter(
        NPC.name == 'Town Treasury',
        NPC.is_dead == 0
    ).first()
    
    if not town_npc:
        # Create a town treasury NPC if it doesn't exist
        town_npc = NPC(
            name='Town Treasury',
            role='town',
            x=0,
            y=0,
            gold=0,
            hunger=0,
            energy=100,
            happiness=100,
            age=100,
            max_age=150,
            is_dead=0,
            is_bankrupt=0,
            illness_severity=0,
            illness=0,
            personality='[]',
            skill=0,
            memory_events='[]',
            favorite_buildings='[]',
            avoided_areas='[]',
            experience='{}'
        )
        db.add(town_npc)
        db.flush()
    
    # Create transaction for the prize
    transaction = Transaction(
        sender_id=town_npc.id,
        receiver_id=winner.id,
        amount=50,
        reason='talent_show_prize'
    )
    db.add(transaction)
    
    # Create event
    event = Event(
        event_type='talent_show',
        description=f'{winner.name} won the talent show!',
        tick=current_tick
    )
    db.add(event)
    
    db.commit()
    
    return winner.id


def trigger_trade_caravan(db: Session) -> int:
    """Trigger a trade caravan arrival event.
    
    Finds the market building. If it exists, adds 3 Resources with name='caravan_goods'
    and quantity=20. Creates an Event with event_type='trade_caravan'.
    Returns the count of resources added (3) or 0 if no market exists.
    """
    from sqlalchemy.orm import Session
    from engine.models import Building, Resource, Event
    
    # Find the market building
    market = db.query(Building).filter(Building.building_type == "market").first()
    
    if not market:
        return 0
    
    # Add 3 resources of type 'caravan_goods' with quantity 20
    resources_added = 0
    for _ in range(3):
        new_resource = Resource(
            name="caravan_goods",
            quantity=20,
            building_id=market.id
        )
        db.add(new_resource)
        resources_added += 1
    
    # Create the event
    new_event = Event(
        event_type="trade_caravan",
        description="A trade caravan has arrived at the market!"
    )
    db.add(new_event)
    
    db.commit()
    
    return resources_added


def trigger_miracle(db: Session) -> int | None:
    """
    Trigger a miracle event that heals a random sick NPC.
    
    Finds a living NPC with an illness, heals them completely,
    increases their happiness, and logs the event.
    
    Args:
        db: Database session
        
    Returns:
        Healed NPC id or None if no sick NPC found
    """
    # Find a living NPC with an illness (illness is not None and illness_severity > 0)
    sick_npc = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.illness != None,
        NPC.illness_severity > 0
    ).first()
    
    if sick_npc is None:
        return None
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Heal the NPC
    old_illness = sick_npc.illness
    sick_npc.illness = None
    sick_npc.illness_severity = 0
    
    # Increase happiness (cap at reasonable max)
    sick_npc.happiness = min(sick_npc.happiness + 15, 100)
    
    # Create the miracle event
    event = Event(
        event_type='miracle',
        description=f"A miracle occurred! {sick_npc.name} was healed from {old_illness}.",
        tick=current_tick,
        severity='info',
        affected_npc_id=sick_npc.id
    )
    db.add(event)
    
    db.commit()
    
    return sick_npc.id


def check_building_collapse(db: Session) -> int:
    """Check for building collapses (5% chance for level 1 buildings with capacity > 0)."""
    from engine.models import Building, NPC, Event
    import random
    
    collapse_count = 0
    
    # Find all buildings with level==1 and capacity > 0
    buildings = db.query(Building).filter(
        Building.level == 1,
        Building.capacity > 0
    ).all()
    
    for building in buildings:
        # 5% chance to collapse
        if random.random() < 0.05:
            # Set capacity to 0
            building.capacity = 0
            
            # Unassign workers from this building
            db.query(NPC).filter(NPC.work_building_id == building.id).update(
                {"work_building_id": None}
            )
            
            # Create event record
            event = Event(
                event_type='building_collapse',
                severity=4,
                building_id=building.id
            )
            db.add(event)
            collapse_count += 1
    
    db.commit()
    return collapse_count


def trigger_comet_sighting(db: Session) -> bool:
    """Trigger a comet sighting event with 2% random chance."""
    import random
    import json
    
    if random.random() < 0.02:
        from engine.models import NPC, Event
        
        # Get all living NPCs
        living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
        
        for npc in living_npcs:
            # Parse memory_events (stored as JSON string)
            memory_events = npc.memory_events or []
            if isinstance(memory_events, str):
                try:
                    memory_events = json.loads(memory_events)
                except (json.JSONDecodeError, TypeError):
                    memory_events = []
            if not isinstance(memory_events, list):
                memory_events = []
            
            # Add comet_sighting if not already present
            if 'comet_sighting' not in memory_events:
                memory_events.append('comet_sighting')
                npc.memory_events = json.dumps(memory_events)
            
            # Increase happiness by 3 (capped at 100)
            npc.happiness = min(100, npc.happiness + 3)
        
        # Create event record
        event = Event(event_type='comet_sighting')
        db.add(event)
        
        db.commit()
        return True
    
    return False


def trigger_drought_relief(db: Session) -> int:
    """Trigger drought relief event."""
    from engine.models import WorldState, Resource, Event
    
    # Check if drought is active and weather is rain
    world_state = db.query(WorldState).first()
    if not world_state or world_state.drought_active != 1 or world_state.weather != 'rain':
        return 0
    
    # Deactivate drought
    world_state.drought_active = 0
    
    # Double food resources
    food_resources = db.query(Resource).filter(Resource.name == 'food').all()
    count = 0
    for resource in food_resources:
        resource.quantity *= 2
        count += 1
    
    # Create event
    event = Event(event_type='drought_relief')
    db.add(event)
    
    db.commit()
    return count


def trigger_spring_bloom(db: Session) -> int:
    """Trigger spring bloom event."""
    from engine.models import WorldState, NPC, Event
    
    ws = db.query(WorldState).first()
    if not ws or ws.weather not in ('sunny', 'clear'):
        return 0
    
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    count = len(npcs)
    
    for npc in npcs:
        npc.happiness += 3
    
    event = Event(
        event_type='spring_bloom',
        description='Spring bloom brings joy to all living NPCs',
        tick=ws.tick if hasattr(ws, 'tick') else 0,
        severity='info'
    )
    db.add(event)
    db.commit()
    
    return count


def apply_seasonal_weather(db: Session) -> str:
    """Apply seasonal weather cycle based on day."""
    from engine.models import WorldState, Event
    
    # Get current world state
    world_state = db.query(WorldState).first()
    if not world_state:
        return "spring"  # Default
    
    # Calculate season (96-day cycle, 24 days per season)
    season_index = (world_state.day % 96) // 24
    
    # Map season index to name and weather
    season_map = {
        0: ("spring", "sunny"),
        1: ("summer", "hot"),
        2: ("autumn", "cloudy"),
        3: ("winter", "snow")
    }
    
    season_name, weather_type = season_map.get(season_index, ("spring", "sunny"))
    
    # Update weather if changed
    if world_state.weather != weather_type:
        world_state.weather = weather_type
        db.commit()
    
    # Create Event on season change (every 24 days)
    if world_state.day % 24 == 0:
        event = Event(
            name=f"Season Change: {season_name.capitalize()}",
            description=f"The season has changed to {season_name}.",
            tick=world_state.tick
        )
        db.add(event)
        db.commit()
    
    return season_name


def check_naming_ceremony(db: Session) -> str | None:
    """Check if town has reached a building threshold for naming ceremony.
    
    At building thresholds (10, 20, 30, 40, 50): create Milestone if not exists.
    Create Event(event_type='naming_ceremony'). Return milestone name or None.
    """
    from engine.models import Building, Milestone, Event
    
    thresholds = [10, 20, 30, 40, 50]
    building_count = db.query(Building).count()
    
    for threshold in thresholds:
        if building_count == threshold:
            milestone_name = f"Town Milestone: {threshold} Buildings"
            
            # Check if milestone already exists
            existing = db.query(Milestone).filter(
                Milestone.name == milestone_name
            ).first()
            
            if not existing:
                # Create milestone
                milestone = Milestone(
                    name=milestone_name,
                    description=f"The town has reached {threshold} buildings!",
                    tick_achieved=0
                )
                db.add(milestone)
                
                # Create event
                event = Event(
                    event_type='naming_ceremony',
                    description=milestone_name
                )
                db.add(event)
                
                db.commit()
                
                return milestone_name
    
    return None


def trigger_merchant_caravan(db: Session) -> None:
    """Trigger a merchant caravan event at a random edge tile."""
    from engine.models import NPC, Event, WorldState
    from engine.simulation.economy import calculate_price
    import random
    from datetime import datetime
    
    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Generate random edge position (x=0 or x=49 or y=0 or y=49)
    if random.random() < 0.5:
        # Horizontal edge (y=0 or y=49)
        x = random.randint(0, 49)
        y = 0 if random.random() < 0.5 else 49
    else:
        # Vertical edge (x=0 or x=49)
        x = 0 if random.random() < 0.5 else 49
        y = random.randint(0, 49)
    
    # Create merchant NPC with role='caravan_merchant', gold=200
    merchant = NPC(
        name=f"Caravan Merchant {current_tick}",
        role="caravan_merchant",
        x=x,
        y=y,
        gold=200,
        hunger=50,
        energy=50,
        happiness=50,
        age=30,
        max_age=80,
        is_dead=0,
        is_bankrupt=0,
        illness_severity=0,
        illness=0,
        home_building_id=None,
        work_building_id=None,
        target_x=x,
        target_y=y,
        personality="{'merchant': 0.9, 'friendly': 0.7}",
        skill="{'trading': 0.8, 'persuasion': 0.6}",
        memory_events='[]',
        favorite_buildings='[]',
        avoided_areas='[]',
        experience='{}'
    )
    db.add(merchant)
    
    # Create Event with event_type='merchant_caravan'
    event = Event(
        event_type="merchant_caravan",
        description="A merchant caravan has arrived at the town edge",
        tick=current_tick,
        severity="info",
        affected_npc_id=merchant.id,
        affected_building_id=None,
        created_at=datetime.now()
    )
    db.add(event)
    
    # Store merchant pricing info in event description for reference
    # Sells at 2x calculate_price, buys at 0.5x
    event.description = f"A merchant caravan has arrived at the town edge (sells at 2x, buys at 0.5x)"
    db.flush()


def check_seasonal_events(db: Session) -> None:
    """Check for seasonal events like harvest festival and winter begins."""
    from engine.models import Resource
    from sqlalchemy import func
    
    world_state = db.query(WorldState).first()
    if not world_state:
        return
    
    season = get_season(db)
    current_day = world_state.day
    
    # Check for fall harvest festival
    if season == 'fall' and current_day % 25 == 1:
        # Check total food resource quantity
        total_food = db.query(func.sum(Resource.quantity)).filter(
            Resource.name.ilike("%food%") | Resource.name.ilike("%grain%")
        ).scalar() or 0
        
        if total_food > 50:
            trigger_harvest_festival(db)
    
    # Check for winter begins
    if season == 'winter' and current_day % 25 == 1:
        winter_event = Event(
            event_type="winter_begins",
            description="Winter has begun",
            tick=world_state.tick,
            severity="low"
        )
        db.add(winter_event)
        db.commit()


def apply_winter_effects(db: Session) -> None:
    """Apply winter hardship effects to NPCs."""
    from engine.models import NPC, Event
    
    season = get_season(db)
    if season != 'winter':
        return
    
    # Get all living NPCs
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    has_hardship = False
    
    for npc in npcs:
        # Increase hunger by +3 extra for winter
        npc.hunger = min(100, npc.hunger + 3)
        
        # NPCs without home lose -5 energy extra
        if npc.home_building_id is None:
            npc.energy = max(0, npc.energy - 5)
        
        # Check if energy drops below 10 for hardship event
        if npc.energy < 10:
            has_hardship = True
    
    # Create winter_hardship event if any NPC is struggling
    if has_hardship:
        event = Event(
            event_type='winter_hardship',
            description='Winter hardship affecting the town',
            severity=1,
            resolved=0
        )
        db.add(event)


def spread_epidemic(db: Session) -> int:
    """Spread epidemic to healthy NPCs on the same tile as infected NPCs."""
    from engine.models import NPC
    
    # Get all living NPCs with illness_severity > 0 (infected)
    infected_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.illness_severity > 0
    ).all()
    
    new_infections = 0
    
    for infected in infected_npcs:
        # Find other living NPCs on the same tile who are healthy
        neighbors = db.query(NPC).filter(
            NPC.id != infected.id,
            NPC.is_dead == 0,
            NPC.x == infected.x,
            NPC.y == infected.y,
            NPC.illness_severity == 0
        ).all()
        
        for neighbor in neighbors:
            # 30% chance to get infected
            if random.random() < 0.3:
                neighbor.illness_severity = 10
                neighbor.illness = 10
                new_infections += 1
    
    return new_infections


def check_infrastructure_collapse(db: Session) -> bool:
    """Check if infrastructure has collapsed (50%+ buildings with capacity < 5)."""
    from engine.models import Building, Event, WorldState
    
    # Count total buildings and damaged buildings (capacity < 5)
    total_buildings = db.query(Building).count()
    
    if total_buildings == 0:
        return False
    
    damaged_buildings = db.query(Building).filter(Building.capacity < 5).count()
    
    damaged_ratio = damaged_buildings / total_buildings
    
    if damaged_ratio > 0.5:
        # Create infrastructure collapse event
        event = Event(
            event_type='infrastructure_collapse',
            severity='critical',
            description='Infrastructure collapse detected: over 50% of buildings damaged'
        )
        db.add(event)
        
        # Set infrastructure score to 0
        world_state = db.query(WorldState).first()
        if world_state:
            world_state.infrastructure_score = 0
        
        return True
    
    return False


def generate_town_review(db: Session) -> dict:
    """Generate an annual town review report with population, gold, happiness, buildings, and crime stats."""
    from sqlalchemy import func
    from engine.models import NPC, Building, Crime, Newspaper, WorldState
    
    # Calculate population (living NPCs)
    population = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    # Calculate total gold
    total_gold_result = db.query(func.sum(NPC.gold)).filter(NPC.is_dead == 0).scalar()
    total_gold = total_gold_result if total_gold_result else 0
    
    # Calculate average happiness
    happiness_result = db.query(func.avg(NPC.happiness)).filter(NPC.is_dead == 0).scalar()
    avg_happiness = float(happiness_result) if happiness_result is not None else 0.0
    
    # Calculate building count
    building_count = db.query(Building).count()
    
    # Calculate crime count (unresolved)
    crime_count = db.query(Crime).filter(Crime.resolved == 0).count()
    
    # Get current tick for the newspaper
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create the stats dict
    stats = {
        "population": population,
        "total_gold": total_gold,
        "avg_happiness": round(avg_happiness, 2),
        "building_count": building_count,
        "crime_count": crime_count
    }
    
    # Generate newspaper article
    body_text = (
        f"Annual Town Review Report\n\n"
        f"Population: {population}\n"
        f"Total Gold in Town: {total_gold}\n"
        f"Average Happiness: {stats['avg_happiness']}\n"
        f"Total Buildings: {building_count}\n"
        f"Unresolved Crimes: {crime_count}\n\n"
        f"The town continues to grow and prosper. "
        f"Residents report a happiness level of {stats['avg_happiness']}. "
        f"Local authorities are working to reduce the {crime_count} unresolved crimes."
    )
    
    newspaper = Newspaper(
        day=current_tick,
        headline="Annual Town Review",
        body=body_text,
        author_npc_id=None,
        tick=current_tick
    )
    
    db.add(newspaper)
    db.flush()
    
    return stats


def trigger_random_boon(db: Session) -> str | None:
    """Trigger random positive micro-events (1% chance per tick)."""
    from engine.models import Event, NPC, Resource
    from sqlalchemy import func
    
    if random.random() >= 0.01:
        return None
    
    # Pick one of 3 boons
    boon_type = random.choice(['gold_vein', 'bumper_crop', 'inspiration'])
    
    current_tick = db.query(func.max(Event.tick)).scalar() or 0
    
    if boon_type == 'gold_vein':
        # Add 100 gold to random NPC
        npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
        if npcs:
            npc = random.choice(npcs)
            npc.gold = npc.gold + 100
            event = Event(
                event_type='gold_vein',
                description=f'{npc.name} found a gold vein and gained 100 gold!',
                tick=current_tick
            )
            db.add(event)
            db.flush()
            return 'gold_vein'
    
    elif boon_type == 'bumper_crop':
        # Add 50 to first Food resource
        food_resource = db.query(Resource).filter(Resource.resource_name == 'Food').first()
        if food_resource:
            food_resource.amount = food_resource.amount + 50
            event = Event(
                event_type='bumper_crop',
                description='A bumper crop has increased food reserves by 50!',
                tick=current_tick
            )
            db.add(event)
            db.flush()
            return 'bumper_crop'
    
    elif boon_type == 'inspiration':
        # All NPCs +5 happiness
        npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
        for npc in npcs:
            npc.happiness = min(npc.happiness + 5, 100)
        event = Event(
            event_type='inspiration',
            description='A wave of inspiration has lifted the spirits of all townsfolk!',
            tick=current_tick
        )
        db.add(event)
        db.flush()
        return 'inspiration'
    
    return None


def process_refugees(db: Session) -> int:
    """Process refugee wave after critical disasters."""
    from sqlalchemy import func
    from engine.models import Event, NPC
    import random

    current_tick = db.query(func.max(Event.tick)).scalar() or 0
    lookback_window = 10

    # Check for critical events in the last 10 ticks
    critical_events = db.query(Event).filter(
        Event.severity == 'critical',
        Event.tick > current_tick - lookback_window
    ).all()

    if not critical_events:
        return 0

    # Check if a refugee wave event already happened in the last 10 ticks
    existing_refugee_event = db.query(Event).filter(
        Event.name == 'refugee_wave',
        Event.tick > current_tick - lookback_window
    ).first()

    if existing_refugee_event:
        return 0

    # Spawn 3 new NPCs
    count = 0
    for _ in range(3):
        # Random position (0-100 range assumed based on typical grid)
        x = random.randint(0, 100)
        y = random.randint(0, 100)
        
        npc = NPC(
            name=f"Refugee_{db.query(NPC).count() + 1}",
            role='refugee',
            x=x,
            y=y,
            gold=0,
            hunger=70,
            energy=50,
            happiness=20,
            age=25,
            max_age=80,
            is_dead=0,
            is_bankrupt=0,
            illness_severity=0,
            illness=0,
            home_building_id=None,
            work_building_id=None,
            target_x=None,
            target_y=None,
            personality='fearful',
            skill='none',
            memory_events='[]',
            favorite_buildings='[]',
            avoided_areas='[]',
            experience='{}'
        )
        db.add(npc)
        count += 1

    # Create the 'refugee_wave' Event
    event = Event(
        name='refugee_wave',
        description='A wave of refugees has arrived seeking shelter.',
        severity='major',
        tick=current_tick,
        resolved=0
    )
    db.add(event)
    
    db.flush()
    return count


def apply_policy_effects(db: Session) -> int:
    """Apply effects from passed policies to WorldState and mark as enacted."""
    from engine.models import Policy, WorldState
    import json
    
    # Get all passed policies
    passed_policies = db.query(Policy).filter(Policy.status == 'passed').all()
    
    count = 0
    for policy in passed_policies:
        # Parse policy effects JSON
        effects = json.loads(policy.effect) if policy.effect else {}
        
        # Apply tax_rate if present
        if 'tax_rate' in effects:
            world_state = db.query(WorldState).first()
            if world_state:
                world_state.tax_rate = effects['tax_rate']
        
        # Apply base_wage if present
        if 'base_wage' in effects:
            world_state = db.query(WorldState).first()
            if world_state:
                world_state.base_wage = effects['base_wage']
        
        # Mark policy as enacted
        policy.status = 'enacted'
        count += 1
    
    db.commit()
    return count


def check_corruption(db: Session) -> float:
    """Check for mayor corruption and steal gold if greedy."""
    from engine.models import NPC, Treasury, Crime
    import json
    
    # Find mayor
    mayor = db.query(NPC).filter(NPC.role == 'mayor').first()
    
    if not mayor:
        return 0.0
    
    # Check personality for 'greedy' trait
    personality_data = {}
    if mayor.personality:
        try:
            parsed = json.loads(mayor.personality)
            if isinstance(parsed, dict):
                personality_data = parsed
        except (json.JSONDecodeError, TypeError):
            pass
    
    if 'greedy' not in personality_data:
        return 0.0
    
    # Find first Treasury
    treasury = db.query(Treasury).first()
    
    if not treasury:
        return 0.0
    
    # Get current treasury gold (handle potential None)
    treasury_gold = treasury.gold if treasury.gold else 0.0
    
    if treasury_gold <= 0:
        return 0.0
    
    # Calculate stolen amount (10%)
    stolen_amount = treasury_gold * 0.1
    
    # Move gold
    treasury.gold = treasury_gold - stolen_amount
    mayor.gold = (mayor.gold if mayor.gold else 0.0) + stolen_amount
    
    # Create Crime record
    crime = Crime(
        type='corruption',
        criminal_npc_id=mayor.id
    )
    db.add(crime)
    
    return stolen_amount


def calculate_approval(db: Session) -> int:
    """Calculate public approval rating based on NPC happiness."""
    from engine.models import NPC, Event, WorldState
    
    # Get current tick
    ws = db.query(WorldState).first()
    tick = ws.tick if ws else 0
    
    # Get living NPCs (is_dead == 0 for Postgres compatibility)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    if not living_npcs:
        approval = 0
    else:
        total_happiness = sum(npc.happiness for npc in living_npcs)
        approval = int(round(total_happiness / len(living_npcs)))
    
    # Ensure rating is within 0-100
    approval = max(0, min(100, approval))
    
    # Trigger events based on approval thresholds
    if approval < 30:
        db.add(Event(event_type='unrest', tick=tick))
    if approval > 70:
        db.add(Event(event_type='prosperity', tick=tick))
        
    return approval


def check_emergency_election(db: Session) -> bool:
    """Check if an emergency election should be held.
    
    Counts 'unrest' Events in the last 50 ticks.
    If count >= 3, triggers hold_election(db) and creates an Event with event_type='emergency_election'.
    Returns True if election triggered, False otherwise.
    """
    from engine.models import WorldState, Event
    
    # Get current tick
    world_state = db.query(WorldState).first()
    if not world_state:
        return False
    
    current_tick = world_state.tick
    start_tick = current_tick - 50
    
    # Count unrest events in the last 50 ticks
    unrest_count = db.query(Event).filter(
        Event.event_type == 'unrest',
        Event.tick >= start_tick,
        Event.tick <= current_tick
    ).count()
    
    if unrest_count >= 3:
        # Trigger the election
        hold_election(db)
        
        # Create the emergency election event
        emergency_event = Event(
            event_type='emergency_election',
            description=f"Emergency election triggered due to {unrest_count} unrest events.",
            tick=current_tick
        )
        db.add(emergency_event)
        db.commit()
        
        return True
    
    return False


def hold_town_meeting(db: Session) -> str:
    """Hold a town hall meeting to address grievances."""
    from engine.models import Building, NPC, Event, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find the civic building
    civic_building = db.query(Building).filter(Building.building_type == 'civic').first()
    if not civic_building:
        return "No civic building found"
    
    # Find NPCs within 10 tiles of the civic building (Manhattan distance)
    nearby_npcs = []
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        distance = abs(npc.x - civic_building.x) + abs(npc.y - civic_building.y)
        if distance <= 10:
            nearby_npcs.append(npc)
    
    if not nearby_npcs:
        return "No NPCs nearby"
    
    # Calculate average stats for each complaint type
    stats = ['hunger', 'energy', 'happiness', 'gold']
    stat_averages = {}
    
    for stat in stats:
        values = [getattr(npc, stat) for npc in nearby_npcs]
        stat_averages[stat] = sum(values) / len(values) if values else 0
    
    # Find the lowest average (worst complaint)
    complaint = min(stat_averages, key=stat_averages.get)
    
    # Create event description
    description = f"Town meeting: Primary concern is {complaint}"
    
    # Create the event
    event = Event(
        event_type='town_meeting',
        description=description,
        tick=current_tick,
        severity='info'
    )
    db.add(event)
    db.flush()
    
    # Propose policy if hunger is the worst complaint
    if complaint == 'hunger':
        propose_policy(db, 'food_subsidy', 'Provide food subsidies to residents')
    
    return complaint


def apply_drought_starvation(db: Session) -> int:
    """Apply starvation deaths during drought."""
    from engine.models import WorldState, NPC, Event
    
    ws = db.query(WorldState).first()
    if ws is None or ws.drought_active != 1:
        return 0
    
    death_count = 0
    tick = ws.tick if ws.tick else 0
    
    for npc in db.query(NPC).filter(NPC.is_dead == 0, NPC.hunger > 85).all():
        if random.random() < 0.1:
            npc.is_dead = 1
            db.flush()
            event = Event(
                event_type="starvation_death",
                description=f"{npc.name} died of starvation during drought",
                tick=tick,
                affected_npc_id=npc.id
            )
            db.add(event)
            death_count += 1
    
    return death_count


def check_plague_overwhelm(db: Session) -> int:
    """Check if plague overwhelms hospital capacity."""
    from engine.models import NPC, Building, Event, WorldState
    
    # Count sick living NPCs (is_dead == 0 for Postgres compatibility)
    sick_npcs = db.query(NPC).filter(NPC.is_dead == 0, NPC.illness_severity > 0).all()
    sick_count = len(sick_npcs)
    
    # Calculate total hospital capacity
    hospital_capacity_result = db.query(func.sum(Building.capacity)).filter(Building.building_type == "hospital").scalar()
    hospital_capacity = hospital_capacity_result if hospital_capacity_result else 0
    
    # Check overwhelm condition
    if sick_count > hospital_capacity * 2:
        # Increase illness severity for sick NPCs (cap at 100)
        for npc in sick_npcs:
            npc.illness_severity = min(100, npc.illness_severity + 10)
        
        # Create event
        world_state = db.query(WorldState).first()
        current_tick = world_state.tick if world_state else 0
        
        event = Event(
            event_type="hospital_overwhelmed",
            description=f"Hospital overwhelmed: {sick_count} sick, only {hospital_capacity} capacity",
            tick=current_tick
        )
        db.add(event)
        
    return sick_count


def apply_newspaper_mood(db: Session) -> int:
    """Apply newspaper headline effects on NPC happiness."""
    from engine.models import Newspaper, NPC
    
    # Get latest newspaper
    latest = db.query(Newspaper).order_by(Newspaper.id.desc()).limit(1).first()
    
    if not latest:
        return 0
    
    headline = latest.headline.lower()
    
    # Determine mood effect
    negative_words = ["death", "plague", "fire", "crime"]
    positive_words = ["celebration", "festival", "boom", "prosperity"]
    
    is_negative = any(word in headline for word in negative_words)
    is_positive = any(word in headline for word in positive_words)
    
    # Get living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    affected_count = 0
    
    for npc in living_npcs:
        if is_negative:
            npc.happiness = max(0, npc.happiness - 5)
            affected_count += 1
        elif is_positive:
            npc.happiness = min(100, npc.happiness + 5)
            affected_count += 1
    
    db.flush()
    
    return affected_count


def check_summer_festival(db: Session) -> int:
    """Check if summer festival conditions are met and apply effects."""
    from engine.models import NPC, Event, WorldState
    
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    
    day = world_state.day or 0
    tick = world_state.tick or 0
    
    # Calculate season: 0=spring, 1=summer, 2=autumn, 3=winter
    season = (day % 96) // 24
    
    # Check if summer (season==1) and mid-season day (day%24==12)
    if season != 1 or day % 24 != 12:
        return 0
    
    # Get all living NPCs (is_dead==0 per Postgres compatibility)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    affected_count = 0
    for npc in living_npcs:
        # Increase happiness (max 100)
        npc.happiness = min(100, npc.happiness + 10)
        # Increase energy (max 100)
        npc.energy = min(100, npc.energy + 5)
        affected_count += 1
    
    # Create event
    event = Event(
        event_type="summer_festival",
        description="The annual summer festival brings joy to all!",
        tick=tick
    )
    db.add(event)
    
    return affected_count
