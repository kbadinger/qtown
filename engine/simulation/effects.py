"""Building effect functions — hospital, tavern, church, fountain, school."""

import math
from sqlalchemy.orm import Session

from engine.models import NPC, Building, Resource, WorldState, Event


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
