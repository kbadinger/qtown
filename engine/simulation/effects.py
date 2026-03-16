"""Building effect functions — hospital, tavern, church, fountain, school."""

import math
from sqlalchemy.orm import Session

from engine.models import NPC, Building, Resource, WorldState, Event
import json
import random
from engine.models import Crime


def process_hospital(db: Session) -> None:
    """Process hospital effects on NPCs.
    
    NPCs assigned to hospital buildings (work_building_id pointing to hospital)
    have their health improved (placeholder for future illness system).
    Currently increases happiness by 5 for NPCs at hospital.
    """
    hospitals = db.query(Building).filter(Building.building_type == "hospital").all()
    
    for hospital in hospitals:
        # Get NPCs assigned to this hospital
        patient_npcs = db.query(NPC).filter(NPC.work_building_id == hospital.id).all()
        
        for npc in patient_npcs:
            # Heal effect: increase happiness (placeholder for illness system)
            npc.happiness = min(100, npc.happiness + 5)
            
            # Log healing event
            event = Event(
                event_type="healing",
                description=f"{npc.name} received healing at {hospital.name}",
                tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                severity="info",
                affected_npc_id=npc.id,
                affected_building_id=hospital.id
            )
            db.add(event)
    
    db.commit()


def process_tavern(db: Session) -> None:
    """Process tavern effects on NPCs.
    
    NPCs assigned to tavern buildings (work_building_id pointing to tavern)
    gain energy and happiness.
    Increases energy by 20 and happiness by 10 for NPCs at tavern.
    """
    taverns = db.query(Building).filter(Building.building_type == "tavern").all()
    
    for tavern in taverns:
        # Get NPCs assigned to this tavern
        visitor_npcs = db.query(NPC).filter(NPC.work_building_id == tavern.id).all()
        
        for npc in visitor_npcs:
            # Tavern effect: increase energy and happiness
            npc.energy = min(100, npc.energy + 20)
            npc.happiness = min(100, npc.happiness + 10)
            
            # Log tavern visit event
            event = Event(
                event_type="tavern_visit",
                description=f"{npc.name} visited {tavern.name}",
                tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                severity="info",
                affected_npc_id=npc.id,
                affected_building_id=tavern.id
            )
            db.add(event)
    
    db.commit()


def visit_tavern(db: Session, npc_id: int) -> bool:
    """Allow an NPC to visit a tavern.
    
    NPC spends 3 gold, gains +20 energy (capped at 100) and +10 happiness.
    Requires a tavern building to exist.
    Returns False if no tavern or insufficient gold.
    """
    # Get the NPC
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    # Check if NPC has enough gold
    if npc.gold < 3:
        return False
    
    # Find a tavern
    tavern = db.query(Building).filter(Building.building_type == "tavern").first()
    if not tavern:
        return False
    
    # Execute the visit
    npc.gold -= 3
    npc.energy = min(100, npc.energy + 20)
    npc.happiness = min(100, npc.happiness + 10)
    
    # Log tavern visit event
    event = Event(
        event_type="tavern_visit",
        description=f"{npc.name} visited {tavern.name}",
        tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
        severity="info",
        affected_npc_id=npc.id,
        affected_building_id=tavern.id
    )
    db.add(event)
    
    db.commit()
    return True


def apply_church_effects(db: Session) -> None:
    """Apply church effects on NPC happiness.
    
    Increases happiness of NPCs within radius 10 of any church building by 5.
    """
    church_buildings = db.query(Building).filter(Building.building_type == 'church').all()
    
    for church in church_buildings:
        # Get all NPCs
        npcs = db.query(NPC).all()
        
        for npc in npcs:
            # Calculate Euclidean distance
            distance = math.sqrt((npc.x - church.x) ** 2 + (npc.y - church.y) ** 2)
            
            # If within radius 10, increase happiness
            if distance <= 10:
                npc.happiness = min(100, npc.happiness + 5)
    
    db.commit()


def apply_fountain_effects(db: Session) -> None:
    """Apply fountain effects on NPC happiness.
    
    Increases happiness of NPCs within radius 8 of any fountain building by 3.
    """
    fountain_buildings = db.query(Building).filter(Building.building_type == 'fountain').all()
    
    for fountain in fountain_buildings:
        # Get all NPCs
        npcs = db.query(NPC).all()
        
        for npc in npcs:
            # Calculate Euclidean distance
            distance = math.sqrt((npc.x - fountain.x) ** 2 + (npc.y - fountain.y) ** 2)
            
            # If within radius 8, increase happiness
            if distance <= 8:
                npc.happiness = min(100, npc.happiness + 3)
    
    db.commit()


def process_school_skill_gain(db: Session) -> None:
    """Process skill gain for NPCs assigned to school buildings.
    
    NPCs with work_building_id pointing to a school building gain +1 skill.
    """
    schools = db.query(Building).filter(Building.building_type == "school").all()
    
    for school in schools:
        # Get NPCs assigned to this school
        student_npcs = db.query(NPC).filter(NPC.work_building_id == school.id).all()
        
        for npc in student_npcs:
            # NPC gains +1 skill
            npc.skill += 1
            
            # Log skill gain event
            event = Event(
                event_type="skill_gain",
                description=f"{npc.name} gained skill at {school.name}",
                tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                severity="info",
                affected_npc_id=npc.id,
                affected_building_id=school.id
            )
            db.add(event)

    db.commit()


def enforce_laws(db: Session) -> None:
    """Guards detect crimes and arrest criminals. No-op if no crimes exist."""
    from engine.models import Crime
    crimes = db.query(Crime).filter(Crime.resolved == 0).all()
    for crime in crimes:
        crime.resolved = True
    db.commit()


def process_punishment(db: Session) -> None:
    """Process punishment for imprisoned NPCs. No-op if no crimes exist."""
    from engine.models import Crime
    crimes = db.query(Crime).filter(Crime.resolved == 1).all()
    # Placeholder — Qwen will flesh out sentence tracking in later stories
    db.commit()


def serve_sentences(db: Session) -> int:
    """Process prison sentences for NPCs."""
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    current_tick = world_state.tick
    
    prisons = db.query(Building).filter(Building.building_type == "prison").all()
    prison_ids = [p.id for p in prisons]
    if not prison_ids:
        return 0
    
    inmates = db.query(NPC).filter(NPC.work_building_id.in_(prison_ids), NPC.is_dead == 0).all()
    released_count = 0
    
    for npc in inmates:
        mem = {}
        if npc.memory_events:
            try:
                mem = json.loads(npc.memory_events)
                if isinstance(mem, list):
                    mem = {}
            except (json.JSONDecodeError, TypeError):
                pass
        
        if 'imprisoned_tick' not in mem:
            mem['imprisoned_tick'] = current_tick
        
        if current_tick - mem['imprisoned_tick'] >= 50:
            non_prisons = db.query(Building).filter(Building.building_type != "prison").all()
            if non_prisons:
                target = random.choice(non_prisons)
                npc.x, npc.y = target.x, target.y
            npc.work_building_id = None
            npc.happiness = max(0, npc.happiness - 20)
            if 'imprisoned_tick' in mem:
                del mem['imprisoned_tick']
            released_count += 1
        
        npc.memory_events = json.dumps(mem)
    
    db.commit()
    return released_count


def process_bounties(db: Session) -> int:
    """Process bounty collection for unresolved crimes.
    
    For each unresolved crime, if a guard NPC is within 5 tiles of the criminal NPC,
    resolve the crime and give guard +10 gold. Creates Event event_type='bounty_collected'.
    Returns count of bounties collected.
    """
    # Get unresolved crimes (resolved == 0 for Postgres compatibility)
    unresolved_crimes = db.query(Crime).filter(Crime.resolved == 0).all()
    
    # Get all active guards
    guards = db.query(NPC).filter(NPC.role == 'guard', NPC.is_dead == 0).all()
    
    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    bounties_collected = 0
    
    for crime in unresolved_crimes:
        criminal = db.query(NPC).filter(NPC.id == crime.criminal_npc_id).first()
        if not criminal:
            continue
        
        # Find a guard within 5 tiles
        for guard in guards:
            distance = math.sqrt((guard.x - criminal.x) ** 2 + (guard.y - criminal.y) ** 2)
            if distance <= 5:
                # Resolve crime
                crime.resolved = 1
                
                # Reward guard
                guard.gold += 10
                
                # Create event
                event = Event(
                    event_type="bounty_collected",
                    description=f"{guard.name} collected bounty for {criminal.name}",
                    tick=current_tick,
                    severity="info",
                    affected_npc_id=guard.id,
                    affected_building_id=None
                )
                db.add(event)
                
                bounties_collected += 1
                break # One guard per crime
    
    db.commit()
    return bounties_collected


def vigilante_justice(db: Session) -> int:
    """Vigilante justice without guards."""
    import random
    import json
    from engine.models import NPC, Crime

    # Check if any guards exist (role='guard', is_dead==0)
    guards = db.query(NPC).filter(NPC.role == 'guard', NPC.is_dead == 0).all()
    if guards:
        return 0

    # Find unresolved crimes (resolved==0)
    crimes = db.query(Crime).filter(Crime.resolved == 0).all()
    
    count_resolved = 0
    
    for crime in crimes:
        # Get criminal NPC to find location
        criminal = db.query(NPC).filter(NPC.id == crime.criminal_npc_id).first()
        if not criminal:
            continue
            
        # Find brave NPCs on same tile (x, y)
        brave_npcs = db.query(NPC).filter(
            NPC.x == criminal.x,
            NPC.y == criminal.y,
            NPC.is_dead == 0
        ).all()
        
        for npc in brave_npcs:
            # Check personality for 'brave' == True
            try:
                personality = json.loads(npc.personality)
                if isinstance(personality, dict) and personality.get('brave') == True:
                    # 50% chance to resolve
                    if random.random() < 0.5:
                        # Resolve crime
                        crime.resolved = 1
                        # Increase happiness
                        npc.happiness += 5
                        count_resolved += 1
                        break # One resolution per crime
            except (json.JSONDecodeError, TypeError):
                continue
                
    return count_resolved


def conduct_research(db: Session) -> str | None:
    """Conduct research at a library building.
    
    If a library building exists, every call has 5% chance of a discovery.
    Discoveries: 'farming_technique', 'medical_breakthrough', 'engineering'.
    Creates Event with event_type='research_discovery'.
    Returns discovery name or None.
    """
    from engine.models import Building, Event, Resource, NPC
    
    # Check if library exists
    library = db.query(Building).filter(Building.building_type == 'library').first()
    if not library:
        return None
    
    # 5% chance of discovery
    if random.random() >= 0.05:
        return None
    
    # Randomly select discovery type
    discoveries = ['farming_technique', 'medical_breakthrough', 'engineering']
    discovery = random.choice(discoveries)
    
    # Apply discovery effects
    if discovery == 'farming_technique':
        # Add 10 to all Food resources
        db.query(Resource).filter(Resource.resource_name == 'Food').update({'amount': Resource.amount + 10})
    elif discovery == 'medical_breakthrough':
        # Reduce all NPC illness_severity by 5 (minimum 0)
        db.query(NPC).update({'illness_severity': db.func.GREATEST(NPC.illness_severity - 5, 0)})
    elif discovery == 'engineering':
        # All buildings +1 capacity
        db.query(Building).update({'capacity': Building.capacity + 1})
    
    # Create Event record
    event = Event(
        event_type='research_discovery',
        description=f'Discovery: {discovery}',
        tick=0
    )
    db.add(event)
    
    return discovery
