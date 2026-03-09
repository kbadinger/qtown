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
    from engine.models import Building
    
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
    """Trigger a harvest festival event that increases NPC happiness."""
    from engine.models import NPC, WorldState
    
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
    
    db.commit()


def trigger_bandit_raid(db: Session) -> None:
    """Trigger a bandit raid that steals gold from Treasury and NPCs."""
    from engine.models import Treasury, NPC, Building, Event, WorldState
    from engine.simulation.constants import JUSTICE_RESPONSE_GUARD_THRESHOLD
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Count guards to reduce theft (5% reduction per guard)
    guard_buildings = db.query(Building).filter(
        Building.building_type.in_(['guard', 'guard_tower'])
    ).all()
    num_guards = len(guard_buildings)
    
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


def trigger_earthquake(db: Session) -> None:
    """Trigger an earthquake event that damages all buildings."""
    from engine.models import Building, Event, WorldState
    import random
    
    # Get world state for tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create earthquake event
    earthquake_event = Event(
        event_type="earthquake",
        description="An earthquake has shaken the town, damaging buildings",
        tick=current_tick,
        severity="high"
    )
    db.add(earthquake_event)
    
    # Damage all buildings
    buildings = db.query(Building).all()
    stone_building_types = ['wall', 'gate', 'guard_tower', 'watchtower']
    
    for building in buildings:
        if building.building_type in stone_building_types:
            # Stone buildings take less damage (10-25%)
            damage_percent = random.uniform(0.10, 0.25)
        else:
            # Regular buildings take more damage (10-50%)
            damage_percent = random.uniform(0.10, 0.50)
        
        new_capacity = int(building.capacity * (1 - damage_percent))
        building.capacity = max(1, new_capacity)  # Ensure capacity stays at least 1
    
    db.commit()


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
        resolved=0
    )
    db.add(event)
    
    db.flush()

    return visitor


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
