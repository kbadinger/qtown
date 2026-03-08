"""NPC movement, needs, decisions, lifecycle, and relationships."""

import json
import random
from sqlalchemy.orm import Session

from engine.models import NPC, Building, Resource, WorldState, Relationship, Treasury
from engine.simulation.init import _generate_personality
from engine.models import Loan
from typing import List
import heapq
from sqlalchemy import func
from engine.models import Dialogue, NPC, Event, WorldState


def move_npc_toward_target(db: Session, npc: NPC) -> None:
    """Move an NPC one step closer to its target position.
    
    If target_x/target_y are set, move 1 step closer per tick.
    If x < target_x, x += 1. If x > target_x, x -= 1. Same for y.
    Clamp to 0-49. Clear target when reached.
    """
    if npc.target_x is None or npc.target_y is None:
        return
    
    # Move towards target_x
    if npc.x < npc.target_x:
        npc.x += 1
    elif npc.x > npc.target_x:
        npc.x -= 1
    
    # Move towards target_y
    if npc.y < npc.target_y:
        npc.y += 1
    elif npc.y > npc.target_y:
        npc.y -= 1
    
    # Clamp to grid bounds (0-49)
    npc.x = max(0, min(49, npc.x))
    npc.y = max(0, min(49, npc.y))
    
    # Check if reached target
    if npc.x == npc.target_x and npc.y == npc.target_y:
        npc.target_x = None
        npc.target_y = None


def assign_homes(db: Session) -> None:
    """Assign homes to NPCs without one.

    For each NPC without a home_building_id, find a residential building
    with capacity > current occupants and assign it.
    """
    homeless_npcs = db.query(NPC).filter(NPC.home_building_id == None).all()
    residential_buildings = db.query(Building).filter(
        Building.building_type == "residential"
    ).all()

    occupancy = {}
    for building in residential_buildings:
        occupancy[building.id] = (
            db.query(NPC).filter(NPC.home_building_id == building.id).count()
        )

    for npc in homeless_npcs:
        for building in residential_buildings:
            if occupancy.get(building.id, 0) < building.capacity:
                npc.home_building_id = building.id
                occupancy[building.id] += 1
                break

    db.commit()


def assign_work(db: Session) -> None:
    """Assign work buildings to NPCs without one.

    For each NPC without a work_building_id, find a non-residential building
    matching their role and assign it.
    """
    role_mapping = {
        "farmer": "food",
        "baker": "food",
        "guard": "guard",
        "merchant": "market",
        "priest": "religious",
    }

    unemployed_npcs = db.query(NPC).filter(NPC.work_building_id == None).all()

    for npc in unemployed_npcs:
        target_type = role_mapping.get(npc.role)
        if not target_type:
            continue

        building = db.query(Building).filter(
            Building.building_type == target_type,
            Building.building_type != "residential",
        ).first()

        if building:
            npc.work_building_id = building.id

    db.commit()


def eat(db: Session, npc_id: int) -> bool:
    """Allow an NPC to eat food.

    Reduces hunger by 30 (minimum 0). Costs 5 gold.
    Returns False if NPC not found or insufficient gold.
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    if npc.gold < 5:
        return False

    npc.gold -= 5
    npc.hunger = max(0, npc.hunger - 30)
    db.commit()
    return True


def sleep_npc(db: Session, npc_id: int) -> bool:
    """Allow an NPC to sleep.

    Restores energy by 40, capped at 100.
    Returns False if NPC not found.
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False

    npc.energy = min(100, npc.energy + 40)
    db.commit()
    return True


def buy_food(db: Session, npc_id: int) -> bool:
    """Allow an NPC to buy food from any building.
    
    NPC spends 5 gold, hunger decreases by 30 (min 0).
    Requires a Food resource with quantity >= 1 at any building.
    Decrements food quantity by 1.
    Returns False if no food or insufficient gold.
    """
    # Get the NPC
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    # Check if NPC has enough gold
    if npc.gold < 5:
        return False
    
    # Find a Food resource with quantity >= 1 at any building
    food_resource = db.query(Resource).filter(
        Resource.name == 'Food',
        Resource.quantity >= 1
    ).first()
    
    if not food_resource:
        return False
    
    # Execute the purchase
    npc.gold -= 5
    npc.hunger = max(0, npc.hunger - 30)
    food_resource.quantity -= 1
    
    db.commit()
    return True


def buy_fish(db: Session, npc_id: int) -> bool:
    """Allow an NPC to buy Fish, reducing hunger by 25 and gold by 3."""
    from engine.models import NPC, Resource, Building
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    # Check if NPC has enough gold
    if npc.gold < 3:
        return False
    
    # Find available Fish resources (from any fishing dock)
    fish_resources = db.query(Resource).filter(
        Resource.name == 'Fish',
        Resource.quantity > 0
    ).all()
    
    if not fish_resources:
        return False
    
    # Find the first available fish resource
    fish = fish_resources[0]
    
    # Deduct gold from NPC
    npc.gold -= 3
    
    # Reduce hunger by 25 (but not below 0)
    npc.hunger = max(0, npc.hunger - 25)
    
    # Reduce fish quantity by 1
    fish.quantity -= 1
    if fish.quantity <= 0:
        db.delete(fish)
    
    db.commit()
    return True


def buy_art(db: Session, npc_id: int) -> bool:
    """NPC buys Art for 15 gold, gaining +20 happiness.
    
    Art is a luxury: only bought when hunger < 30 and energy > 60.
    Returns True if purchase succeeded, False otherwise.
    """
    from engine.models import NPC, Resource, Building
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    # Luxury condition: only buy when hunger < 30 and energy > 60
    if npc.hunger >= 30 or npc.energy <= 60:
        return False
    
    # Check if NPC can afford Art (15 gold)
    if npc.gold < 15:
        return False
    
    # Find available Art resources (any theater with Art in stock)
    art_resources = db.query(Resource).filter(
        Resource.name == "Art",
        Resource.quantity > 0
    ).all()
    
    if not art_resources:
        return False
    
    # Find the first theater with Art
    theater_id = art_resources[0].building_id
    theater = db.query(Building).filter(Building.id == theater_id).first()
    if not theater:
        return False
    
    # Complete the transaction
    npc.gold -= 15
    npc.happiness = min(100, npc.happiness + 20)
    
    # Reduce Art quantity
    art = db.query(Resource).filter(
        Resource.name == "Art",
        Resource.building_id == theater_id
    ).first()
    
    if art and art.quantity > 0:
        art.quantity -= 1
    
    db.commit()
    return True


def buy_books(db: Session, npc_id: int) -> bool:
    """NPC buys Books for 10 gold (+15 happiness, +5 skill)."""
    from engine.models import NPC, Resource, Building

    npc = db.query(NPC).filter_by(id=npc_id).first()
    if not npc:
        return False

    # Check conditions: hunger < 30 and energy > 60
    if npc.hunger >= 30 or npc.energy <= 60:
        return False

    # Check gold
    if npc.gold < 10:
        return False

    # Find available Books (from any Library)
    libraries = db.query(Building).filter_by(building_type="library").all()
    book_resource = None
    for lib in libraries:
        res = db.query(Resource).filter_by(name="Books", building_id=lib.id).first()
        if res and res.quantity > 0:
            book_resource = res
            break

    if not book_resource:
        return False

    # Execute purchase
    npc.gold -= 10
    npc.happiness += 15
    npc.skill += 5
    book_resource.quantity -= 1

    db.commit()
    return True


def buy_medicine(db: Session, npc_id: int) -> bool:
    """NPC buys Medicine for 8 gold if available."""
    from engine.models import Resource, Building, NPC
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return False
    
    if npc.gold < 8:
        return False
    
    hospitals = db.query(Building).filter(Building.building_type == 'hospital').all()
    
    for hospital in hospitals:
        medicine = db.query(Resource).filter(
            Resource.name == 'Medicine',
            Resource.building_id == hospital.id,
            Resource.quantity > 0
        ).first()
        
        if medicine:
            medicine.quantity -= 1
            npc.gold -= 8
            npc.illness_severity = 0
            db.commit()
            return True
    
    return False


def calculate_happiness(db: Session, npc_id: int) -> None:
    """Calculate and update happiness for an NPC.
    
    Happiness is affected by:
    - Hunger: -10 if hunger > 50
    - Energy: -10 if energy < 30
    - Gold: +5 if gold > 20
    - Has home: +10 if home_building_id is set
    - Has work: +10 if work_building_id is set
    Base happiness is 50.
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return
    
    # Calculate happiness based on conditions
    happiness = 50
    
    if npc.hunger > 50:
        happiness -= 10
    if npc.energy < 30:
        happiness -= 10
    if npc.gold > 20:
        happiness += 5
    if npc.home_building_id is not None:
        happiness += 10
    if npc.work_building_id is not None:
        happiness += 10
    
    # Clamp happiness between 0 and 100
    npc.happiness = max(0, min(100, happiness))
    db.commit()


def get_npc_decision(db: Session, npc_id: int) -> str:
    """Determine what an NPC should do based on their state.
    
    Decision priority:
    1. eat (if hunger > 50)
    2. sleep (if energy < 30)
    3. work (if has work_building and not at work)
    4. rest (otherwise)
    5. memory-based decisions (if memory influences choice)
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return "rest"
    
    # Check basic needs first
    if npc.hunger > 50:
        return "eat"
    elif npc.energy < 30:
        return "sleep"
    elif npc.work_building_id is not None:
        work_building = db.query(Building).filter(Building.id == npc.work_building_id).first()
        if work_building and (npc.x != work_building.x or npc.y != work_building.y):
            return "work"
    
    # Check memory for influencing decisions
    # If NPC remembers a favorite building, they might visit it
    memories = recall_memory(db, npc_id, "favorite")
    if memories and npc.happiness < 70:
        return "visit_favorite"
    
    # If NPC remembers danger, they might avoid certain areas
    danger_memories = recall_memory(db, npc_id, "danger")
    if danger_memories:
        return "avoid_danger"
    
    return "rest"


def update_relationships(db: Session) -> None:
    """Update relationships between NPCs based on proximity and competition."""
    from engine.models import NPC, Building
    
    # Get all NPCs with their work buildings
    npcs = db.query(NPC).all()
    
    # Group NPCs by work building
    building_npcs: dict[int, list[NPC]] = {}
    for npc in npcs:
        if npc.work_building_id:
            if npc.work_building_id not in building_npcs:
                building_npcs[npc.work_building_id] = []
            building_npcs[npc.work_building_id].append(npc)
    
    # Process friendships (same building)
    for building_id, building_npc_list in building_npcs.items():
        for i, npc1 in enumerate(building_npc_list):
            for npc2 in building_npc_list[i+1:]:
                # Create or update friendship
                rel = db.query(Relationship).filter(
                    Relationship.npc_id == npc1.id,
                    Relationship.target_npc_id == npc2.id
                ).first()
                
                if not rel:
                    rel = Relationship(
                        npc_id=npc1.id,
                        target_npc_id=npc2.id,
                        relationship_type="friend",
                        strength=5
                    )
                    db.add(rel)
                else:
                    rel.strength = min(100, rel.strength + 5)
                
                # Also create reverse relationship
                rel_reverse = db.query(Relationship).filter(
                    Relationship.npc_id == npc2.id,
                    Relationship.target_npc_id == npc1.id
                ).first()
                
                if not rel_reverse:
                    rel_reverse = Relationship(
                        npc_id=npc2.id,
                        target_npc_id=npc1.id,
                        relationship_type="friend",
                        strength=5
                    )
                    db.add(rel_reverse)
                else:
                    rel_reverse.strength = min(100, rel_reverse.strength + 5)
    
    # Process rivalries (competing for same resource)
    # Group NPCs by building type
    building_type_npcs: dict[str, list[NPC]] = {}
    for npc in npcs:
        if npc.work_building_id:
            building = db.query(Building).filter(Building.id == npc.work_building_id).first()
            if building:
                building_type = building.building_type
                if building_type not in building_type_npcs:
                    building_type_npcs[building_type] = []
                building_type_npcs[building_type].append(npc)
    
    # Process rivalries for resource-producing buildings
    resource_buildings = ['mine', 'lumber_mill', 'fishing_dock', 'farm']
    
    for building_type in resource_buildings:
        if building_type in building_type_npcs:
            npc_list = building_type_npcs[building_type]
            for i, npc1 in enumerate(npc_list):
                for npc2 in npc_list[i+1:]:
                    # Skip if they're at the same building (already friends)
                    if npc1.work_building_id == npc2.work_building_id:
                        continue
                    
                    # Create or update rivalry
                    rel = db.query(Relationship).filter(
                        Relationship.npc_id == npc1.id,
                        Relationship.target_npc_id == npc2.id
                    ).first()
                    
                    if not rel:
                        rel = Relationship(
                            npc_id=npc1.id,
                            target_npc_id=npc2.id,
                            relationship_type="rival",
                            strength=5
                        )
                        db.add(rel)
                    else:
                        rel.strength = min(100, rel.strength + 5)
                    
                    # Also create reverse relationship
                    rel_reverse = db.query(Relationship).filter(
                        Relationship.npc_id == npc2.id,
                        Relationship.target_npc_id == npc1.id
                    ).first()
                    
                    if not rel_reverse:
                        rel_reverse = Relationship(
                            npc_id=npc2.id,
                            target_npc_id=npc1.id,
                            relationship_type="rival",
                            strength=5
                        )
                        db.add(rel_reverse)
                    else:
                        rel_reverse.strength = min(100, rel_reverse.strength + 5)
    
    db.commit()


def check_marriage(db: Session) -> None:
    """Check for NPCs that can marry and process marriages.
    
    Two NPCs with friendship strength > 80 and no existing spouse may marry.
    They move to the same home.
    """
    from engine.models import Relationship, NPC
    
    # Find all friend relationships with strength > 80
    friend_relationships = db.query(Relationship).filter(
        Relationship.relationship_type == 'friend',
        Relationship.strength > 80
    ).all()
    
    for rel in friend_relationships:
        # Check if npc1 already has a spouse
        npc1_has_spouse = db.query(Relationship).filter(
            ((Relationship.npc_id == rel.npc_id) | (Relationship.target_npc_id == rel.npc_id)) &
            (Relationship.relationship_type == 'spouse')
        ).first()
        
        # Check if npc2 already has a spouse
        npc2_has_spouse = db.query(Relationship).filter(
            ((Relationship.npc_id == rel.target_npc_id) | (Relationship.target_npc_id == rel.target_npc_id)) &
            (Relationship.relationship_type == 'spouse')
        ).first()
        
        # Only marry if neither has a spouse
        if not npc1_has_spouse and not npc2_has_spouse:
            # Update relationship to spouse
            rel.relationship_type = 'spouse'
            
            # Get both NPCs
            npc1 = db.query(NPC).filter(NPC.id == rel.npc_id).first()
            npc2 = db.query(NPC).filter(NPC.id == rel.target_npc_id).first()
            
            if npc1 and npc2:
                # Move to the same home
                if npc1.home_building_id:
                    npc2.home_building_id = npc1.home_building_id
                elif npc2.home_building_id:
                    npc1.home_building_id = npc2.home_building_id


def age_npcs(db: Session) -> None:
    """Age all NPCs by 1 year. Mark NPCs as dead when they reach max_age."""
    from engine.models import NPC
    
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        npc.age += 1
        if npc.age >= npc.max_age:
            npc.is_dead = 1
    
    db.commit()


def process_inheritance(db: Session) -> int:
    """Process inheritance for all dead NPCs."""
    from engine.models import NPC, Relationship, Treasury
    
    total_gold_distributed = 0
    
    # Get all dead NPCs who still have gold
    dead_npcs = db.query(NPC).filter(NPC.is_dead == 1).filter(NPC.gold > 0).all()
    
    for dead_npc in dead_npcs:
        gold = dead_npc.gold
        
        # Find children (Relationship where npc_id is dead_npc and target_npc_id is child)
        children = db.query(NPC).join(
            Relationship, Relationship.target_npc_id == NPC.id
        ).filter(
            Relationship.npc_id == dead_npc.id,
            Relationship.relationship_type == "child"
        ).all()
        
        if children:
            # Split gold equally among children
            share = gold // len(children)
            remainder = gold % len(children)
            for i, child in enumerate(children):
                amount = share + (1 if i < remainder else 0)
                child.gold += amount
                total_gold_distributed += amount
        else:
            # Find spouse
            spouse = db.query(NPC).join(
                Relationship, Relationship.target_npc_id == NPC.id
            ).filter(
                Relationship.npc_id == dead_npc.id,
                Relationship.relationship_type == "spouse"
            ).first()
            
            if spouse:
                # Spouse gets all gold
                spouse.gold += gold
                total_gold_distributed += gold
            else:
                # Treasury gets all gold
                treasury = db.query(Treasury).first()
                if treasury:
                    treasury.gold_stored += gold
                    total_gold_distributed += gold
        
        # Clear dead NPC's gold
        dead_npc.gold = 0
    
    db.commit()
    return total_gold_distributed


def check_population_growth(db: Session) -> None:
    """Spawn a new NPC if conditions are right.

    Throttled: only checks every 100 ticks with a 25% chance.
    Requires avg happiness > 60 and living population < 20.
    """
    from engine.models import WorldState
    ws = db.query(WorldState).first()
    if not ws or ws.tick % 100 != 0:
        return

    if random.random() > 0.25:
        return

    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    if not npcs:
        return

    avg_happiness = sum(npc.happiness for npc in npcs) / len(npcs)

    if avg_happiness > 60 and len(npcs) < 20:
        names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank",
                 "Grace", "Henry", "Ivy", "Jack"]
        roles = ["farmer", "baker", "guard", "merchant", "priest"]

        new_npc = NPC(
            name=random.choice(names),
            role=random.choice(roles),
            x=random.randint(5, 45),
            y=random.randint(5, 45),
            gold=0,
            hunger=0,
            energy=100,
            happiness=50,
            personality=_generate_personality(),
        )
        db.add(new_npc)
        db.commit()


def remember_event(db: Session, npc_id: int, event: str) -> None:
    """Store an event in NPC's memory_events JSON, keeping max 10."""
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return

    try:
        events = json.loads(npc.memory_events) if npc.memory_events else []
    except (json.JSONDecodeError, TypeError):
        events = []

    events.append(event)
    if len(events) > 10:
        events = events[-10:]

    npc.memory_events = json.dumps(events)
    db.commit()


def update_favorites(db: Session, npc_id: int) -> None:
    """Update NPC's favorite buildings based on visit history.
    
    Stores top 3 most-visited buildings as JSON string in favorite_buildings field.
    For now, uses home and work buildings as favorites (up to 3).
    """
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return
    
    favorites = []
    
    # Add home building if exists
    if npc.home_building_id:
        home_building = db.query(Building).filter(Building.id == npc.home_building_id).first()
        if home_building:
            favorites.append({
                "building_id": home_building.id,
                "name": home_building.name,
                "type": home_building.building_type,
                "visit_count": 1
            })
    
    # Add work building if exists and different from home
    if npc.work_building_id and npc.work_building_id != npc.home_building_id:
        work_building = db.query(Building).filter(Building.id == npc.work_building_id).first()
        if work_building:
            favorites.append({
                "building_id": work_building.id,
                "name": work_building.name,
                "type": work_building.building_type,
                "visit_count": 1
            })
    
    # Ensure max 3 favorites
    favorites = favorites[:3]
    
    # Sort by visit count (descending)
    favorites.sort(key=lambda x: x["visit_count"], reverse=True)
    
    # Store as JSON string
    npc.favorite_buildings = json.dumps(favorites)
    db.commit()


def mark_dangerous_area(db: Session, npc_id: int, x: int, y: int) -> None:
    """Mark a location as dangerous for an NPC."""
    from engine.models import NPC, WorldState
    
    # Get current tick from world state
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Get the NPC
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return
    
    # Load existing avoided areas
    avoided_areas = npc.avoided_areas
    if avoided_areas and isinstance(avoided_areas, str):
        try:
            avoided_list = json.loads(avoided_areas)
        except (json.JSONDecodeError, TypeError):
            avoided_list = []
    else:
        avoided_list = []
    
    # Add new dangerous area with tick information
    new_area = {
        "x": x,
        "y": y,
        "tick_added": current_tick
    }
    avoided_list.append(new_area)
    
    # Save back to NPC
    npc.avoided_areas = json.dumps(avoided_list)
    db.commit()


def get_friends(db: Session, npc_id: int) -> list[int]:
    """Return list of NPC IDs with friendship strength > 60."""
    from engine.models import Relationship

    relationships = db.query(Relationship).filter(
        Relationship.npc_id == npc_id,
        Relationship.strength > 60
    ).all()
    
    return [rel.target_npc_id for rel in relationships]


def learn(db: Session, npc_id: int, lesson: str) -> None:
    """Store a lesson in the NPC's experience field.
    
    Args:
        db: Database session
        npc_id: ID of the NPC to update
        lesson: Text description of the lesson learned
    """
    import json
    from engine.models import NPC
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return
    
    # Load existing experience
    experience = npc.experience
    if isinstance(experience, str):
        try:
            experience_list = json.loads(experience)
        except (json.JSONDecodeError, TypeError):
            experience_list = []
    else:
        experience_list = []
    
    # Ensure it's a list
    if not isinstance(experience_list, list):
        experience_list = []
    
    # Add the new lesson if not already present
    if lesson not in experience_list:
        experience_list.append(lesson)
    
    # Save back to database
    npc.experience = json.dumps(experience_list)
    db.commit()


def process_loans(db: Session) -> None:
    """Process banker NPCs offering loans to poor NPCs."""
    from sqlalchemy import func
    
    # Find all banker NPCs with sufficient gold to lend
    bankers = db.query(NPC).filter(
        NPC.role == "banker",
        NPC.gold >= 100  # Minimum gold to lend
    ).all()
    
    # Find all poor NPCs (gold < 10) who don't already have active loans
    poor_npcs = db.query(NPC).filter(
        NPC.gold < 10,
        NPC.is_dead == 0
    ).all()
    
    # Check which poor NPCs already have active loans
    existing_loan_borrowers = set()
    for loan in db.query(Loan).filter(Loan.status == "active").all():
        existing_loan_borrowers.add(loan.borrower_npc_id)
    
    # Create loans for poor NPCs without existing loans
    for banker in bankers:
        for borrower in poor_npcs:
            if borrower.id in existing_loan_borrowers:
                continue
            
            # Create a loan
            loan = Loan(
                lender_npc_id=banker.id,
                borrower_npc_id=borrower.id,
                amount=100,
                interest_rate=0.1,
                ticks_remaining=50,
                status="active"
            )
            db.add(loan)
            
            # Transfer gold from banker to borrower
            banker.gold -= 100
            borrower.gold += 100
            
            # Limit to one loan per banker per tick
            break
    
    # Process loan repayments
    active_loans = db.query(Loan).filter(
        Loan.status == "active",
        Loan.ticks_remaining > 0
    ).all()
    
    for loan in active_loans:
        # Decrement ticks remaining
        loan.ticks_remaining -= 1
        
        if loan.ticks_remaining == 0:
            # Loan is due - check if borrower can repay
            borrower = db.query(NPC).filter(NPC.id == loan.borrower_npc_id).first()
            lender = db.query(NPC).filter(NPC.id == loan.lender_npc_id).first()
            
            if borrower and lender:
                total_due = int(loan.amount * (1 + loan.interest_rate))
                
                if borrower.gold >= total_due:
                    # Successful repayment
                    borrower.gold -= total_due
                    lender.gold += total_due
                    loan.status = "repaid"
                    
                    # Log successful repayment event
                    from engine.models import Event
                    event = Event(
                        event_type="loan_repayment",
                        description=f"{borrower.name} repaid loan to {lender.name}",
                        tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                        severity="info",
                        affected_npc_id=borrower.id
                    )
                    db.add(event)
                else:
                    # Default - borrower can't repay
                    loan.status = "defaulted"
                    
                    # Log default event
                    from engine.models import Event
                    event = Event(
                        event_type="loan_default",
                        description=f"{borrower.name} defaulted on loan to {lender.name}",
                        tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0,
                        severity="warning",
                        affected_npc_id=borrower.id
                    )
                    db.add(event)
    
    db.commit()


def get_tax_route(db: Session, npc_id: int) -> List[int]:
    """Get the tax collection route for a politician NPC.
    Returns building IDs ordered by gold amount (wealthy buildings first).
    """
    from engine.models import Building, Resource
    
    # Get all buildings that can be taxed
    buildings = db.query(Building).all()
    
    # Calculate gold for each building
    building_gold = []
    for building in buildings:
        # Sum all resources at this building
        total_gold = 0
        resources = db.query(Resource).filter(Resource.building_id == building.id).all()
        for resource in resources:
            total_gold += resource.quantity
        building_gold.append((building.id, total_gold))
    
    # Sort by gold descending (prioritize wealthy buildings)
    building_gold.sort(key=lambda x: x[1], reverse=True)
    
    # Return just the building IDs in order
    return [b[0] for b in building_gold]


def negotiate_trade(db: Session, npc_a_id: int, npc_b_id: int, resource: str, quantity: int) -> float:
    """Two merchant NPCs negotiate price. Final price = average of their offers."""
    from sqlalchemy.orm import Session
    from engine.models import NPC, Transaction
    import json
    
    npc_a = db.query(NPC).filter(NPC.id == npc_a_id).first()
    npc_b = db.query(NPC).filter(NPC.id == npc_b_id).first()
    
    if not npc_a or not npc_b:
        return None
    
    # Get personality traits (default to empty dict if None or invalid JSON)
    try:
        personality_a = json.loads(npc_a.personality) if npc_a.personality else {}
    except (json.JSONDecodeError, TypeError):
        personality_a = {}
    
    try:
        personality_b = json.loads(npc_b.personality) if npc_b.personality else {}
    except (json.JSONDecodeError, TypeError):
        personality_b = {}
    
    # Base price for the resource (simple lookup or default)
    base_price = 10.0  # default base price per unit
    
    # Greedy NPCs start higher (multiply by 1.5)
    # Social NPCs compromise faster (closer to base, multiply by 0.8)
    greedy_a = personality_a.get('greedy', False)
    social_a = personality_a.get('social', False)
    greedy_b = personality_b.get('greedy', False)
    social_b = personality_b.get('social', False)
    
    # Calculate offers based on personality
    if greedy_a:
        offer_a = base_price * 1.5
    elif social_a:
        offer_a = base_price * 0.8
    else:
        offer_a = base_price
    
    if greedy_b:
        offer_b = base_price * 1.5
    elif social_b:
        offer_b = base_price * 0.8
    else:
        offer_b = base_price
    
    # Final price is average of both offers
    final_price = (offer_a + offer_b) / 2
    
    # Ensure price is positive
    if final_price <= 0:
        final_price = base_price
    
    # Create transaction (total amount = price * quantity)
    total_amount = int(final_price * quantity)
    transaction = Transaction(
        sender_id=npc_a.id,
        receiver_id=npc_b.id,
        amount=total_amount,
        reason=f"Trade of {quantity} {resource} at {final_price:.2f} each"
    )
    db.add(transaction)
    db.commit()
    
    return final_price


def check_bankruptcy(db: Session) -> None:
    """Check for bankrupt NPCs and apply bankruptcy consequences.
    
    NPCs with gold < -50 go bankrupt:
    - is_bankrupt set to 1
    - happiness drops to 0
    - lose home and work assignments
    
    Recovery:
    - If is_bankrupt is 1 and gold > 0, they recover:
      - is_bankrupt set to 0
      - happiness restored to 50 (default)
    """
    from engine.models import NPC
    
    # 1. Handle new bankruptcies (gold < -50)
    bankrupt_npcs = db.query(NPC).filter(NPC.gold < -50).all()
    
    for npc in bankrupt_npcs:
        if not npc.is_bankrupt:
            npc.is_bankrupt = 1
            npc.happiness = 0
            npc.home_building_id = None
            npc.work_building_id = None
    
    # 2. Handle recovery (is_bankrupt == 1 and gold > 0)
    recovering_npcs = db.query(NPC).filter(NPC.is_bankrupt == 1, NPC.gold > 0).all()
    
    for npc in recovering_npcs:
        npc.is_bankrupt = 0
        npc.happiness = 50  # Restore happiness
    
    db.commit()


def publish_newspaper(db: Session) -> None:
    """Publish a newspaper entry summarizing recent events."""
    from engine.models import Newspaper, NPC, WorldState
    
    # Find a journalist NPC or any NPC to be the author
    author = db.query(NPC).filter(NPC.role == "journalist").first()
    if not author:
        author = db.query(NPC).first()
    
    if not author:
        return  # No NPCs available to author the newspaper
    
    # Get current tick from world state
    world_state = db.query(WorldState).first()
    tick = world_state.tick if world_state else 1
    
    # Create newspaper entry with headline referencing recent events
    newspaper = Newspaper(
        day=tick,
        headline="Town Updates",
        body="The town continues to grow and thrive with new developments.",
        author_npc_id=author.id,
        tick=tick
    )
    
    db.add(newspaper)
    db.commit()


def record_milestones(db: Session) -> None:
    """Record milestones based on current world state."""
    from engine.models import Milestone, Building, NPC, WorldState
    
    # Get current tick
    world_state = db.query(WorldState).first()
    if not world_state:
        return
    current_tick = world_state.tick
    
    # Check if first building milestone exists
    first_building = db.query(Milestone).filter(
        Milestone.name == "First building"
    ).first()
    if not first_building:
        building_count = db.query(Building).count()
        if building_count >= 1:
            db.add(Milestone(
                name="First building",
                description="The town built its first building.",
                tick_achieved=current_tick
            ))
            db.commit()
    
    # Check if 10th NPC milestone exists
    tenth_npc = db.query(Milestone).filter(
        Milestone.name == "10th NPC"
    ).first()
    if not tenth_npc:
        npc_count = db.query(NPC).count()
        if npc_count >= 10:
            db.add(Milestone(
                name="10th NPC",
                description="The town reached 10 NPCs.",
                tick_achieved=current_tick
            ))
            db.commit()
    
    # Check if first death milestone exists
    first_death = db.query(Milestone).filter(
        Milestone.name == "First death"
    ).first()
    if not first_death:
        dead_count = db.query(NPC).filter(NPC.is_dead == 1).count()
        if dead_count >= 1:
            db.add(Milestone(
                name="First death",
                description="The first NPC died.",
                tick_achieved=current_tick
            ))
            db.commit()


def log_visitor(db: Session, npc_id: int) -> None:
    """Log an NPC arriving in town."""
    from engine.models import VisitorLog, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create visitor log entry
    visitor_log = VisitorLog(
        npc_id=npc_id,
        arrival_tick=current_tick,
        greeted_by_npc_id=None,
    )
    
    db.add(visitor_log)
    db.commit()


def compose_anthem(db: Session) -> None:
    """Compose a town anthem if 1000 ticks have passed since last one."""
    from engine.models import TownAnthem, NPC, WorldState
    from engine.simulation.constants import ANTHEM_TICK_INTERVAL
    
    # Get current tick from world state
    world_state = db.query(WorldState).first()
    if not world_state:
        return
    
    current_tick = world_state.tick
    
    # Check if enough time has passed since last anthem
    last_anthem = db.query(TownAnthem).order_by(TownAnthem.tick_composed.desc()).first()
    if last_anthem and (current_tick - last_anthem.tick_composed) < ANTHEM_TICK_INTERVAL:
        return
    
    # Find a bard NPC to compose the anthem
    bard = db.query(NPC).filter(NPC.role == "bard").first()
    composer_id = bard.id if bard else None
    
    # Generate lyrics with town name
    town_name = getattr(world_state, 'town_name', 'Qwen Town')
    lyrics = f"Oh {town_name}, our home so bright, where day turns into night."
    
    # Create the anthem
    anthem = TownAnthem(
        lyrics=lyrics,
        composed_by_npc_id=composer_id,
        tick_composed=current_tick
    )
    db.add(anthem)
    db.commit()


def find_path(db: Session, start_x: int, start_y: int, end_x: int, end_y: int) -> list:
    """Find path using A* algorithm avoiding buildings and water tiles.
    
    Args:
        db: Database session
        start_x: Starting x coordinate
        start_y: Starting y coordinate
        end_x: Ending x coordinate
        end_y: Ending y coordinate
        
    Returns:
        List of (x, y) tuples representing the path, or empty list if no path exists
    """
    from engine.models import Building, Tile
    
    # Get all obstacle positions (buildings and water)
    obstacles = set()
    
    # Add building positions as obstacles
    buildings = db.query(Building).all()
    for building in buildings:
        obstacles.add((building.x, building.y))
    
    # Add water tiles as obstacles
    water_tiles = db.query(Tile).filter(Tile.terrain == "water").all()
    for tile in water_tiles:
        obstacles.add((tile.x, tile.y))
    
    # A* algorithm implementation
    def heuristic(x, y):
        """Manhattan distance heuristic."""
        return abs(end_x - x) + abs(end_y - y)
    
    def get_neighbors(x, y):
        """Get valid neighboring tiles (up, down, left, right)."""
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            # Check bounds (50x50 grid)
            if 0 <= nx < 50 and 0 <= ny < 50:
                if (nx, ny) not in obstacles:
                    neighbors.append((nx, ny))
        return neighbors
    
    # A* search
    start = (start_x, start_y)
    end = (end_x, end_y)
    
    # If start or end is an obstacle, no path possible
    if start in obstacles or end in obstacles:
        return []
    
    # Priority queue: (f_score, g_score, x, y, path)
    open_set = [(heuristic(start[0], start[1]), 0, start[0], start[1], [start])]
    open_set_dict = {start: (heuristic(start[0], start[1]), 0)}
    
    while open_set:
        # Get node with lowest f_score
        f_score, g_score, x, y, path = heapq.heappop(open_set)
        
        # Check if we reached the end
        if (x, y) == end:
            return path
        
        # Explore neighbors
        for nx, ny in get_neighbors(x, y):
            neighbor = (nx, ny)
            tentative_g = g_score + 1
            
            # Skip if we've found a better path to this neighbor
            if neighbor in open_set_dict:
                old_f, old_g = open_set_dict[neighbor]
                if tentative_g >= old_g:
                    continue
            
            # Found better path to neighbor
            f_score_neighbor = tentative_g + heuristic(nx, ny)
            open_set_dict[neighbor] = (f_score_neighbor, tentative_g)
            heapq.heappush(open_set, (f_score_neighbor, tentative_g, nx, ny, path + [neighbor]))
    
    # No path found
    return []


def update_memory(db: Session, npc_id: int, event: str) -> None:
    """Store an event in the NPC's memory_events JSON field.
    
    Memory is capped at 10 events (FIFO - oldest removed first).
    """
    import json
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return
    
    # Parse existing memory (handle both string and list)
    memory_events = npc.memory_events
    if memory_events is None:
        memory_events = []
    elif isinstance(memory_events, str):
        try:
            memory_events = json.loads(memory_events)
        except (json.JSONDecodeError, TypeError):
            memory_events = []
    elif not isinstance(memory_events, list):
        memory_events = []
    
    # Cap at 10 events (remove oldest if full)
    if len(memory_events) >= 10:
        memory_events = memory_events[1:]
    
    # Add new event
    memory_events.append(event)
    
    # Save back to database
    npc.memory_events = json.dumps(memory_events)
    db.commit()


def recall_memory(db: Session, npc_id: int, keyword: str) -> list:
    """Search NPC memory_events for entries containing the keyword.
    
    Returns list of matching memory entries (empty list if none found).
    """
    import json
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return []
    
    # Parse memory
    memory_events = npc.memory_events
    if memory_events is None:
        return []
    elif isinstance(memory_events, str):
        try:
            memory_events = json.loads(memory_events)
        except (json.JSONDecodeError, TypeError):
            return []
    elif not isinstance(memory_events, list):
        return []
    
    # Search for keyword match (case-insensitive)
    keyword_lower = keyword.lower()
    matching_memories = [
        event for event in memory_events 
        if isinstance(event, str) and keyword_lower in event.lower()
    ]
    
    return matching_memories


def generate_dialogue(db: Session, speaker_id: int, listener_id: int) -> str:
    """Generate a dialogue string between two NPCs based on context."""
    # Fetch the NPCs
    speaker = db.query(NPC).filter(NPC.id == speaker_id).first()
    listener = db.query(NPC).filter(NPC.id == listener_id).first()
    
    if not speaker or not listener:
        return "Hello there!"
    
    # Get current weather from WorldState
    world_state = db.query(WorldState).first()
    weather = world_state.weather if world_state else "sunny"
    
    # Get recent events (last 10 ticks)
    current_tick = world_state.tick if world_state else 0
    recent_events = db.query(Event).filter(
        Event.tick > current_tick - 10
    ).limit(5).all()
    
    # Build dialogue based on context
    dialogue_parts = []
    
    # Weather reference
    if weather == "rainy":
        dialogue_parts.append("It's raining today,")
    elif weather == "sunny":
        dialogue_parts.append("What a beautiful day,")
    elif weather == "snowy":
        dialogue_parts.append("Brr, it's cold out,")
    elif weather == "stormy":
        dialogue_parts.append("The storm is fierce,")
    
    # NPC needs reference
    if speaker.hunger > 80:
        dialogue_parts.append(f"I'm starving, {listener.name}!")
    elif speaker.energy < 20:
        dialogue_parts.append(f"I'm so tired, {listener.name}!")
    elif speaker.happiness < 30:
        dialogue_parts.append(f"I'm feeling down, {listener.name}!")
    else:
        dialogue_parts.append(f"How are you doing, {listener.name}?")
    
    # Recent events reference
    if recent_events:
        event = recent_events[0]
        if "flood" in event.event_type.lower():
            dialogue_parts.append("That flood was terrible!")
        elif "fire" in event.event_type.lower():
            dialogue_parts.append("The fire was scary!")
        elif "festival" in event.event_type.lower():
            dialogue_parts.append("The festival was amazing!")
    
    # Combine dialogue
    dialogue = " ".join(dialogue_parts) if dialogue_parts else "Hello there!"
    
    # Save to Dialogue table
    dialogue_record = Dialogue(
        speaker_npc_id=speaker_id,
        listener_npc_id=listener_id,
        message=dialogue,
        tick=current_tick
    )
    db.add(dialogue_record)
    db.commit()
    
    return dialogue


def process_dreams(db: Session) -> int:
    """Process dreams for living NPCs at night."""
    from engine.models import NPC, WorldState
    import random
    
    # Check if it's night
    world_state = db.query(WorldState).first()
    if not world_state or world_state.time_of_day != 'night':
        return 0
    
    # Get all living NPCs
    npcs = db.query(NPC).filter(NPC.is_dead == False).all()
    
    dream_count = 0
    for npc in npcs:
        dream = random.choice(['found_treasure', 'nightmare', 'peaceful', 'adventure'])
        
        # Append dream to memory_events (cap at 10)
        if not npc.memory_events:
            npc.memory_events = []
        npc.memory_events.append(dream)
        if len(npc.memory_events) > 10:
            npc.memory_events = npc.memory_events[-10:]
        
        # Apply happiness effects
        if dream == 'found_treasure':
            npc.happiness = min(100, npc.happiness + 3)
        elif dream == 'nightmare':
            npc.happiness = max(0, npc.happiness - 2)
        
        dream_count += 1
    
    db.commit()
    return dream_count


def check_career_progression(db: Session) -> int:
    """Check and process career progression for eligible NPCs."""
    from engine.models import NPC
    
    promotion_map = {
        'farmer': 'master_farmer',
        'guard': 'captain',
        'merchant': 'guild_master'
    }
    
    promotions = 0
    
    # Get all living NPCs with skill >= 8
    eligible_npcs = db.query(NPC).filter(
        NPC.is_dead == False,
        NPC.skill >= 8
    ).all()
    
    for npc in eligible_npcs:
        if npc.role in promotion_map:
            new_role = promotion_map[npc.role]
            npc.role = new_role
            
            # Append to memory_events
            if npc.memory_events is None:
                npc.memory_events = []
            npc.memory_events.append(f'promoted to {new_role}')
            
            # Increase happiness
            npc.happiness = npc.happiness + 10
            
            promotions += 1
    
    db.commit()
    return promotions


def process_retirement(db: Session) -> int:
    """Process NPC retirement for living NPCs with age > 70.
    
    For each living NPC with age > 70:
    - If NPC has work_building_id, 50% chance to retire (set work_building_id=None)
    - Append 'retired' to memory_events
    - Retired NPCs get happiness +5 (relief)
    
    Returns count of retirements this tick.
    """
    from engine.models import NPC
    
    retirement_count = 0
    
    # Get all living NPCs with age > 70 who have a job
    eligible_npcs = db.query(NPC).filter(
        NPC.age > 70,
        NPC.is_dead == False,
        NPC.work_building_id != None
    ).all()
    
    for npc in eligible_npcs:
        # 50% chance to retire each call
        if random.random() < 0.5:
            # Set work_building_id to None (retire)
            npc.work_building_id = None
            
            # Append 'retired' to memory_events
            if npc.memory_events is None:
                npc.memory_events = []
            npc.memory_events.append('retired')
            
            # Retired NPCs get happiness +5 (relief)
            npc.happiness = min(npc.happiness + 5, 100)
            
            retirement_count += 1
    
    db.commit()
    return retirement_count


def process_child_growth(db: Session) -> int:
    """Process child growth and transition to adulthood."""
    from engine.models import NPC, Building
    import random
    
    # Process children (age < 18)
    children = db.query(NPC).filter(
        NPC.age < 18,
        NPC.is_dead == False
    ).all()
    
    for child in children:
        # Children can't work
        child.work_building_id = None
        
        # Children learn fast (+1 skill per tick)
        child.skill = child.skill + 1
    
    # Count children for return value
    child_count = len(children)
    
    # Handle adults without jobs (age >= 18, no work_building_id)
    adults_without_jobs = db.query(NPC).filter(
        NPC.age >= 18,
        NPC.work_building_id == None,
        NPC.is_dead == False
    ).all()
    
    # Get available buildings with capacity > 0
    available_buildings = db.query(Building).filter(
        Building.capacity > 0
    ).all()
    
    for adult in adults_without_jobs:
        if available_buildings:
            building = random.choice(available_buildings)
            adult.work_building_id = building.id
    
    db.commit()
    return child_count


def attempt_persuasion(db: Session) -> int:
    """Find pairs of NPCs on the same tile and attempt persuasion."""
    from engine.models import NPC
    import random
    import json

    npcs = db.query(NPC).filter(NPC.is_dead == False).all()
    tiles: dict[tuple[int, int], list[NPC]] = {}
    for npc in npcs:
        tiles.setdefault((npc.x, npc.y), []).append(npc)

    count = 0
    for group in tiles.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(len(group)):
                if i == j:
                    continue
                npc_a = group[i]
                npc_b = group[j]
                if npc_a.skill > npc_b.skill:
                    if random.random() < 0.3:
                        if npc_a.experience:
                            npc_b.experience = npc_a.experience
                        mem = npc_b.memory_events
                        if mem is None:
                            mem = []
                        elif isinstance(mem, str):
                            try:
                                mem = json.loads(mem)
                            except Exception:
                                mem = []
                        if isinstance(mem, list):
                            mem.append(f"persuaded by {npc_a.name}")
                            npc_b.memory_events = mem
                            count += 1
                        else:
                            npc_b.memory_events = [f"persuaded by {npc_a.name}"]
                            count += 1
    db.commit()
    return count


def process_crowd_behavior(db: Session) -> int:
    """Process crowd behavior for NPCs on the same tile.
    
    Find tiles with 3+ living NPCs. For each crowd tile:
    - All NPCs on that tile get happiness +2 (socializing)
    - If any Event exists at a building on that tile, NPCs move away
      (set target_x/y to random nearby tile within 5)
    
    Returns count of crowd tiles.
    """
    from engine.models import NPC, Building, Event
    import random
    
    # Find tiles with 3+ living NPCs
    crowd_query = db.query(
        NPC.x, NPC.y, func.count(NPC.id).label('count')
    ).filter(
        NPC.is_dead == False
    ).group_by(
        NPC.x, NPC.y
    ).having(
        func.count(NPC.id) >= 3
    )
    
    crowd_tiles = crowd_query.all()
    crowd_tile_count = len(crowd_tiles)
    
    for crowd_x, crowd_y, count in crowd_tiles:
        # Get all living NPCs on this tile
        npcs_on_tile = db.query(NPC).filter(
            NPC.x == crowd_x,
            NPC.y == crowd_y,
            NPC.is_dead == False
        ).all()
        
        # Check if there's an Event at a building on this tile
        building_on_tile = db.query(Building).filter(
            Building.x == crowd_x,
            Building.y == crowd_y
        ).first()
        
        has_event = False
        if building_on_tile:
            has_event = db.query(Event).filter(
                Event.building_id == building_on_tile.id
            ).first() is not None
        
        for npc in npcs_on_tile:
            # Add happiness for socializing
            npc.happiness = min(100, npc.happiness + 2)
            
            # If there's an event at a building here, move away
            if has_event:
                # Find random nearby tile within 5 tiles
                max_distance = 5
                for _ in range(100):  # Try up to 100 times to find valid tile
                    new_x = crowd_x + random.randint(-max_distance, max_distance)
                    new_y = crowd_y + random.randint(-max_distance, max_distance)
                    # Ensure within bounds (0-49)
                    new_x = max(0, min(49, new_x))
                    new_y = max(0, min(49, new_y))
                    # Don't set target to current position
                    if new_x != crowd_x or new_y != crowd_y:
                        npc.target_x = new_x
                        npc.target_y = new_y
                        break
    
    db.commit()
    return crowd_tile_count


def track_emotions(db: Session) -> dict:
    """Track emotion history for all living NPCs."""
    from engine.models import NPC
    import json
    
    result = {}
    living_npcs = db.query(NPC).filter(NPC.is_dead == False).all()
    
    for npc in living_npcs:
        # Parse experience JSON (default to empty dict)
        experience = json.loads(npc.experience) if npc.experience else {}
        
        # Ensure experience is a dict
        if not isinstance(experience, dict):
            experience = {}
        
        # Initialize mood_history if not exists
        if 'mood_history' not in experience:
            experience['mood_history'] = []
        
        # Append current happiness
        experience['mood_history'].append(npc.happiness)
        
        # Keep only last 5 entries
        experience['mood_history'] = experience['mood_history'][-5:]
        
        # Calculate mood trend
        mood_history = experience['mood_history']
        if len(mood_history) >= 2:
            if mood_history[-1] > mood_history[0]:
                trend = 'improving'
            elif mood_history[-1] < mood_history[0]:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        result[npc.id] = trend
        
        # Update NPC experience
        npc.experience = json.dumps(experience)
    
    db.commit()
    return result
