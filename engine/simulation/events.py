"""Event triggers — disasters, cascading effects, etc."""

from sqlalchemy.orm import Session

from engine.models import WorldState, Event
import random
from engine.simulation.constants import PLAGUE_OVERWHELM_THRESHOLD
import json


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
        NPC.is_dead == False,
        NPC.is_bankrupt == False,
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
    voters = db.query(NPC).filter(NPC.is_dead == False).all()
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
