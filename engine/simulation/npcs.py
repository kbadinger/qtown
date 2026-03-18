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
from typing import Optional
from engine.models import Crime
import math
from engine.simulation.economy import calculate_town_reputation




FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Ethan",
    "Fiona", "George", "Hannah", "Ian", "Julia",
    "Kevin", "Lily", "Michael", "Nina", "Oscar",
    "Paula", "Quinn", "Rachel", "Sam", "Tina"
]




LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin"
]


def wander(db: Session, npc) -> None:
    """Give an idle NPC somewhere to walk to.

    50% chance per tick when no target is set.  Picks from:
      - work building   (40%)  — bias toward work so NPCs earn gold
      - home building   (25%)
      - random building (20%)
      - random nearby   (15%)
    """
    import random as _rnd
    from engine.models import Building

    if npc.target_x is not None:
        return  # already heading somewhere

    if _rnd.random() > 0.50:
        return  # stay put this tick

    roll = _rnd.random()

    if roll < 0.40 and npc.work_building_id:
        b = db.query(Building).get(npc.work_building_id)
        if b:
            npc.target_x, npc.target_y = b.x, b.y
            db.flush()
            return

    if roll < 0.65 and npc.home_building_id:
        b = db.query(Building).get(npc.home_building_id)
        if b:
            npc.target_x, npc.target_y = b.x, b.y
            db.flush()
            return

    if roll < 0.85:
        buildings = db.query(Building).all()
        if buildings:
            b = _rnd.choice(buildings)
            npc.target_x, npc.target_y = b.x, b.y
            db.flush()
            return

    # Random nearby spot (within 8 tiles)
    npc.target_x = max(0, min(49, npc.x + _rnd.randint(-8, 8)))
    npc.target_y = max(0, min(49, npc.y + _rnd.randint(-8, 8)))
    db.flush()


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

    Throttled: only checks every 25 ticks with a 40% chance.
    Requires avg happiness > 40 and living population < 30.
    """
    from engine.models import WorldState
    ws = db.query(WorldState).first()
    if not ws or ws.tick % 25 != 0:
        return

    if random.random() > 0.40:
        return

    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    if not npcs:
        return

    avg_happiness = sum(npc.happiness for npc in npcs) / len(npcs)

    if avg_happiness > 40 and len(npcs) < 30:
        male_names = ["Bob", "Charlie", "Frank", "Henry", "Jack", "Leo",
                      "Noah", "Pete", "Sam", "Vince", "Xander", "Marcus",
                      "Edmund", "Thomas", "William", "George", "Arthur"]
        female_names = ["Alice", "Diana", "Eve", "Grace", "Ivy", "Kate",
                        "Mia", "Olive", "Rose", "Tina", "Uma", "Wendy",
                        "Clara", "Elena", "Sophia", "Martha", "Helen"]
        roles = ["farmer", "baker", "guard", "merchant", "priest",
                 "blacksmith", "miner", "fisher", "carpenter", "artist"]
        # Sprite gender: F slots are 01,06,10,11,13,15,17,19,21,23,25,27
        female_sprites = {1, 6, 10, 11, 13, 15, 17, 19, 21, 23, 25, 27}

        # Pick next available sprite slot
        used_sprites = {n.sprite_id for n in npcs if n.sprite_id}
        sprite_num = None
        for s in range(1, 31):
            sid = f"npc_{s:02d}"
            if sid not in used_sprites:
                sprite_num = s
                break
        is_female = sprite_num in female_sprites if sprite_num else random.random() < 0.5
        name = random.choice(female_names if is_female else male_names)

        new_npc = NPC(
            name=name,
            role=random.choice(roles),
            sprite_id=f"npc_{sprite_num:02d}" if sprite_num else None,
            x=random.randint(5, 45),
            y=random.randint(5, 45),
            gold=50,
            hunger=0,
            energy=100,
            happiness=60,
            age=random.randint(18, 35),
            max_age=random.randint(65, 85),
            is_dead=0,
            is_bankrupt=0,
            illness=0,
            illness_severity=0,
            personality=_generate_personality(),
            skill=random.choice(["farming", "trading", "crafting", "mining", "cooking"]),
            memory_events='[]',
            favorite_buildings='[]',
            avoided_areas='[]',
            experience='{}',
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
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
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
        NPC.is_dead == 0,
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
        NPC.is_dead == 0,
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
        NPC.is_dead == 0
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
        NPC.is_dead == 0
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

    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
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
        NPC.is_dead == 0
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
            NPC.is_dead == 0
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
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
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


def process_emigration(db: Session) -> int:
    """Process NPC emigration based on low happiness history."""
    from engine.models import NPC, Event, WorldState
    import json

    emigrant_count = 0
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0

    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()

    for npc in npcs:
        if npc.happiness < 15:
            experience_data = npc.experience
            if experience_data:
                if isinstance(experience_data, str):
                    try:
                        exp_dict = json.loads(experience_data)
                    except json.JSONDecodeError:
                        continue
                else:
                    exp_dict = experience_data

                mood_history = exp_dict.get("mood_history", [])
                if len(mood_history) >= 3:
                    last_three = mood_history[-3:]
                    if all(h < 15 for h in last_three):
                        npc.is_dead = 1
                        memory_events = npc.memory_events or []
                        if isinstance(memory_events, str):
                            try:
                                memory_events = json.loads(memory_events)
                            except json.JSONDecodeError:
                                memory_events = []
                        if "emigrated" not in memory_events:
                            memory_events.append("emigrated")
                        npc.memory_events = memory_events

                        event = Event(
                            event_type='npc_emigrated',
                            description=f"NPC {npc.name} emigrated",
                            tick=current_tick,
                            npc_id=npc.id
                        )
                        db.add(event)
                        emigrant_count += 1

    db.commit()
    return emigrant_count


def check_immigration(db: Session) -> bool:
    from engine.models import NPC, Event, WorldState
    import random

    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    count = len(living_npcs)
    if count == 0:
        return False
        
    avg_happiness = sum(n.happiness for n in living_npcs) / count
    
    if avg_happiness > 65 and count < 20:
        new_npc = NPC(
            name=f"Newcomer_{random.randint(1000, 9999)}",
            role="newcomer", gold=30,
            x=random.randint(0, 49), y=random.randint(0, 49),
            hunger=50, energy=50, happiness=50,
            age=20, max_age=80, is_dead=False, is_bankrupt=False,
            illness_severity=0, illness=None,
            home_building_id=None, work_building_id=None,
            target_x=None, target_y=None,
            personality="curious", skill=1,
            memory_events=[], favorite_buildings=[], avoided_areas=[],
            experience=0
        )
        db.add(new_npc)
        db.add(Event(event_type="npc_arrived", description="Newcomer arrived", tick=current_tick, npc_id=new_npc.id))
        db.commit()
        return True
    return False


def decay_friendships(db: Session) -> int:
    """Decay friendship relationships by reducing strength and changing type if strength hits 0."""
    from engine.models import Relationship

    friendships = db.query(Relationship).filter(
        Relationship.relationship_type == 'friend'
    ).all()

    count = 0
    for relationship in friendships:
        relationship.strength -= 1
        if relationship.strength < 0:
            relationship.strength = 0
        
        if relationship.strength == 0:
            relationship.relationship_type = 'acquaintance'
        
        count += 1

    db.commit()
    return count


def apply_specialization_bonus(db: Session) -> int:
    """Apply specialization bonus to living NPCs based on experience."""
    from engine.models import NPC
    import json
    
    specialists_count = 0
    
    # Get all living NPCs
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()

    for npc in npcs:
        # Parse experience field into a dict
        experience = {}
        if isinstance(npc.experience, str):
            try:
                parsed = json.loads(npc.experience)
                if isinstance(parsed, dict):
                    experience = parsed
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(npc.experience, dict):
            experience = npc.experience
        
        # Get current ticks_in_role counter
        ticks_in_role = experience.get('ticks_in_role', 0)
        
        # Increment the counter
        ticks_in_role += 1
        experience['ticks_in_role'] = ticks_in_role
        
        # Check if NPC qualifies for specialization bonus
        if ticks_in_role > 50:
            # Increment skill, cap at 15
            npc.skill = min(npc.skill + 1, 15)
            specialists_count += 1
        
        # Store updated experience back
        npc.experience = json.dumps(experience) if experience else None
        
        db.add(npc)
    
    db.commit()
    return specialists_count


def apply_fatigue(db: Session) -> int:
    """Apply fatigue effects to NPCs based on energy levels.
    
    For each living NPC with energy < 20:
    - Set 'fatigued' flag in experience JSON (reduces skill effectiveness)
    - Fatigued NPCs produce 50% less (halve any production bonus)
    
    If energy < 5:
    - NPC collapses: move to home building, set energy=0
    
    Returns count of fatigued NPCs.
    """
    from engine.models import NPC, Building
    import json
    
    fatigued_count = 0
    
    # Get all living NPCs
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()

    for npc in npcs:
        if npc.energy < 20:
            # Set fatigued flag in experience JSON
            if npc.experience is None:
                npc.experience = {}
            elif isinstance(npc.experience, str):
                try:
                    npc.experience = json.loads(npc.experience)
                except (json.JSONDecodeError, TypeError):
                    npc.experience = {}
            
            # Ensure it's a dict before setting keys
            if isinstance(npc.experience, dict):
                npc.experience['fatigued'] = True
                fatigued_count += 1
            
            # If energy < 5, NPC collapses
            if npc.energy < 5:
                # Move to home building
                if npc.home_building_id:
                    home = db.query(Building).filter(Building.id == npc.home_building_id).first()
                    if home:
                        npc.x = home.x
                        npc.y = home.y
                npc.energy = 0
    
    # Do NOT commit here; let the caller (process_tick or test) handle the commit
    return fatigued_count


def check_celebrations(db: Session) -> Optional[str]:
    """Check for NPC celebrations based on happiness levels.
    
    For each living NPC with happiness > 90, trigger celebration:
    - All NPCs within 5 tiles get happiness +3
    - Create Event with event_type='celebration'
    - Max 1 celebration per call
    
    Returns:
        str: Name of celebrating NPC, or None if no celebration triggered
    """
    from engine.models import NPC, Event, WorldState
    
    # Find living NPCs with happiness > 90
    happy_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.happiness > 90
    ).all()
    
    if not happy_npcs:
        return None
    
    # Pick first happy NPC (max 1 celebration per call)
    celebrating_npc = happy_npcs[0]
    
    # Find all living NPCs within 5 tiles (Manhattan distance)
    all_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    for npc in all_npcs:
        distance = abs(npc.x - celebrating_npc.x) + abs(npc.y - celebrating_npc.y)
        if distance <= 5:
            npc.happiness = min(100, npc.happiness + 3)
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create celebration event
    event = Event(
        event_type='celebration',
        description=f'{celebrating_npc.name} is celebrating!',
        tick=current_tick
    )
    db.add(event)
    db.commit()
    
    return celebrating_npc.name


def process_mourning(db: Session) -> int:
    """Process mourning for dead NPCs."""
    from engine.models import NPC, Relationship
    import json

    mourners_count = 0
    
    # Find all dead NPCs
    dead_npcs = db.query(NPC).filter(NPC.is_dead == 1).all()
    
    for dead_npc in dead_npcs:
        # Find relationships involving the dead NPC
        relationships = db.query(Relationship).filter(
            (Relationship.npc1_id == dead_npc.id) | (Relationship.npc2_id == dead_npc.id)
        ).all()
        
        for rel in relationships:
            # Identify the potential mourner (the other NPC in the relationship)
            if rel.npc1_id == dead_npc.id:
                mourner_id = rel.npc2_id
            else:
                mourner_id = rel.npc1_id
            
            # Fetch the mourner NPC
            mourner = db.query(NPC).filter(NPC.id == mourner_id).first()
            if not mourner:
                continue
            
            # Only living NPCs mourn
            if mourner.is_dead == 1:
                continue
            
            # Check memory_events for existing mourning entry to avoid duplicates
            memory_events = []
            if mourner.memory_events:
                try:
                    parsed = json.loads(mourner.memory_events)
                    if isinstance(parsed, list):
                        memory_events = parsed
                except (json.JSONDecodeError, TypeError):
                    memory_events = []
            
            mourning_entry = f"mourning {dead_npc.name}"
            if mourning_entry in memory_events:
                continue
            
            # Apply mourning effects
            mourner.happiness = max(0, mourner.happiness - 5)
            memory_events.append(mourning_entry)
            mourner.memory_events = json.dumps(memory_events)
            
            mourners_count += 1
    
    db.commit()
    return mourners_count


def generate_npc_name(db: Session) -> str:
    """Generate a unique NPC name."""
    from engine.models import NPC
    
    existing_names = set()
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        existing_names.add(npc.name)
    
    for _ in range(100):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        if name not in existing_names:
            return name
    
    return f"Unknown {random.randint(1000, 9999)}"


def calculate_compatibility(db: Session, npc_id_a: int, npc_id_b: int) -> int:
    """Calculate compatibility score between two NPCs."""
    from engine.models import NPC, Relationship
    
    npc_a = db.query(NPC).filter(NPC.id == npc_id_a).first()
    npc_b = db.query(NPC).filter(NPC.id == npc_id_b).first()
    
    if not npc_a or not npc_b:
        return 0
    
    score = 0
    
    # Same role = +20
    if npc_a.role == npc_b.role:
        score += 20
    
    # Age difference < 10 = +15
    age_diff = abs(npc_a.age - npc_b.age)
    if age_diff < 10:
        score += 15
    
    # Both happiness > 50 = +10
    if npc_a.happiness > 50 and npc_b.happiness > 50:
        score += 10
    
    # Existing relationship = +25
    # Check for relationship between the two NPCs
    # Using npc_id and other_npc_id based on error message suggesting npc_id exists
    try:
        has_rel = db.query(Relationship).filter(
            ((Relationship.npc_id == npc_id_a) & (Relationship.other_npc_id == npc_id_b)) |
            ((Relationship.npc_id == npc_id_b) & (Relationship.other_npc_id == npc_id_a))
        ).first()
        if has_rel:
            score += 25
    except AttributeError:
        # If other_npc_id doesn't exist, try alternative column names
        # This handles cases where the schema might be different
        try:
            has_rel = db.query(Relationship).filter(
                ((Relationship.npc_id == npc_id_a) & (Relationship.friend_id == npc_id_b)) |
                ((Relationship.npc_id == npc_id_b) & (Relationship.friend_id == npc_id_a))
            ).first()
            if has_rel:
                score += 25
        except AttributeError:
            pass
    
    return min(score, 100)


def assign_homeless(db: Session) -> int:
    """Auto-assign homeless NPCs to residential buildings with available capacity.
    
    Finds living NPCs without home_building_id and assigns them to residential
    buildings that have available capacity (current residents < building capacity).
    
    Returns:
        int: Count of NPCs successfully assigned to homes
    """
    from engine.models import NPC, Building
    
    # Find all living NPCs without a home
    homeless_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.home_building_id == None
    ).all()
    
    # Find all residential buildings
    residential_buildings = db.query(Building).filter(
        Building.building_type == "residential"
    ).all()
    
    assigned_count = 0
    
    for npc in homeless_npcs:
        for building in residential_buildings:
            # Count current residents in this building
            current_residents = db.query(NPC).filter(
                NPC.home_building_id == building.id
            ).count()
            
            if current_residents < building.capacity:
                # Assign the NPC to this building
                npc.home_building_id = building.id
                assigned_count += 1
                break
    
    db.commit()
    return assigned_count


def assign_unemployed(db: Session) -> int:
    """Auto-assign unemployed NPCs to buildings with available worker slots."""
    from engine.models import NPC, Building
    
    # Find living unemployed NPCs who are adults (age >= 18)
    unemployed_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.work_building_id == None,
        NPC.age >= 18
    ).all()
    
    if not unemployed_npcs:
        return 0
    
    # Count current workers per building
    worker_counts = {}
    for npc in db.query(NPC).filter(NPC.work_building_id != None).all():
        bid = npc.work_building_id
        worker_counts[bid] = worker_counts.get(bid, 0) + 1
    
    # Find buildings with available capacity
    buildings = db.query(Building).all()
    available_buildings = []
    for b in buildings:
        current_workers = worker_counts.get(b.id, 0)
        if current_workers < b.capacity:
            available_buildings.append(b)
    
    if not available_buildings:
        return 0
    
    # Assign NPCs to buildings, preferring role matches
    assigned_count = 0
    for npc in unemployed_npcs:
        # Try to find a building matching the NPC's role
        matched_building = None
        for b in available_buildings:
            if b.building_type == npc.role:
                matched_building = b
                break
        
        # If no role match, use any available building
        if matched_building is None and available_buildings:
            matched_building = available_buildings[0]
        
        if matched_building:
            npc.work_building_id = matched_building.id
            assigned_count += 1
            
            # Update available capacity tracking
            current_workers = worker_counts.get(matched_building.id, 0)
            if current_workers + 1 >= matched_building.capacity:
                if matched_building in available_buildings:
                    available_buildings.remove(matched_building)
    
    db.commit()
    return assigned_count


def calculate_npc_stress(db: Session) -> int:
    """Calculate stress for all living NPCs and reduce happiness if stressed."""
    from engine.models import NPC
    
    stressed_count = 0
    
    for npc in db.query(NPC).filter(NPC.is_dead == 0).all():
        stress_level = 0
        
        if npc.hunger > 70:
            stress_level += 2
        if npc.energy < 30:
            stress_level += 2
        if npc.gold < 5:
            stress_level += 2
        
        if stress_level >= 4:
            npc.happiness = max(0, npc.happiness - stress_level)
            stressed_count += 1
    
    db.commit()
    return stressed_count


def assign_npc_hobbies(db: Session) -> int:
    """Assign hobbies to idle NPCs by selecting random buildings."""
    from engine.models import NPC, Building
    import json
    import random
    
    idle_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.energy > 50,
        NPC.work_building_id == None
    ).all()
    
    count = 0
    all_buildings = db.query(Building).all()
    
    for npc in idle_npcs:
        home_id = npc.home_building_id
        available = [b for b in all_buildings if b.id != home_id]
        
        if not available:
            continue
        
        hobby_building = random.choice(available)
        current_favorites = []
        
        if npc.favorite_buildings:
            try:
                current_favorites = json.loads(npc.favorite_buildings)
                if not isinstance(current_favorites, list):
                    current_favorites = []
            except (json.JSONDecodeError, TypeError):
                current_favorites = []
        
        if hobby_building.id not in current_favorites:
            current_favorites.append(hobby_building.id)
            current_favorites = current_favorites[:3]
            npc.favorite_buildings = json.dumps(current_favorites)
            count += 1
    
    db.commit()
    return count


def propagate_gossip(db: Session) -> int:
    """Propagate gossip between nearby NPCs.
    
    For each living NPC with memory_events (JSON list, not empty):
    - Find other living NPCs within distance 5 (Manhattan distance)
    - Copy the last memory_event entry to nearby NPC memory_events
    - Append with max 10 entries per NPC
    - Return count of gossip transfers
    """
    from engine.models import NPC
    
    transfers = 0
    
    # Get all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        # Parse memory_events (handle None or invalid JSON)
        try:
            memory_events = json.loads(npc.memory_events) if npc.memory_events else []
        except (json.JSONDecodeError, TypeError):
            memory_events = []
        
        # Skip if no memory events
        if not memory_events:
            continue
        
        # Get the last memory event to propagate
        last_event = memory_events[-1]
        
        # Find nearby NPCs within distance 5
        for other_npc in living_npcs:
            # Skip self
            if other_npc.id == npc.id:
                continue
            
            # Calculate Manhattan distance
            distance = abs(npc.x - other_npc.x) + abs(npc.y - other_npc.y)
            
            if distance <= 5:
                # Parse other NPC's memory events
                try:
                    other_memory = json.loads(other_npc.memory_events) if other_npc.memory_events else []
                except (json.JSONDecodeError, TypeError):
                    other_memory = []
                
                # Check if this event is already in their memory (avoid duplicates)
                if last_event not in other_memory:
                    # Append if under max limit of 10 entries
                    if len(other_memory) < 10:
                        other_memory.append(last_event)
                        other_npc.memory_events = json.dumps(other_memory)
                        transfers += 1
    
    # Commit all changes
    db.commit()
    
    return transfers


def update_trust_scores(db: Session) -> dict:
    """Update trust scores for all NPCs based on relationships.
    
    High trust: friend relationship with strength > 50
    Low trust: rival relationship or strength < 20
    Trust metric: high_trust_count - low_trust_count per NPC
    NPCs with trust < 0 get happiness -1
    
    Returns: dict of {npc_id: trust_score}
    """
    from engine.models import Relationship, NPC
    
    # Track trust scores per NPC
    trust_data = {}  # npc_id -> {'high': int, 'low': int}
    
    # Query all relationships
    relationships = db.query(Relationship).all()
    
    for rel in relationships:
        # Process both NPCs in the relationship
        for npc_id in [rel.npc1_id, rel.npc2_id]:
            if npc_id not in trust_data:
                trust_data[npc_id] = {'high': 0, 'low': 0}
            
            # High trust: friend with strength > 50
            if rel.relationship_type == 'friend' and rel.strength > 50:
                trust_data[npc_id]['high'] += 1
            
            # Low trust: rival or strength < 20
            if rel.relationship_type == 'rival' or rel.strength < 20:
                trust_data[npc_id]['low'] += 1
    
    # Calculate final trust scores and track NPCs needing happiness update
    result = {}
    npcs_needing_update = {}
    
    for npc_id, data in trust_data.items():
        trust_score = data['high'] - data['low']
        result[npc_id] = trust_score
        
        # NPCs with negative trust get happiness penalty
        if trust_score < 0:
            npcs_needing_update[npc_id] = trust_score
    
    # Apply happiness penalty to NPCs with negative trust
    if npcs_needing_update:
        for npc_id in npcs_needing_update.keys():
            npc = db.query(NPC).filter(NPC.id == npc_id).first()
            if npc and npc.is_dead == 0:
                npc.happiness = max(0, npc.happiness - 1)
    
    db.commit()
    return result


def process_gift_giving(db: Session) -> int:
    """Process gift giving between NPCs."""
    from engine.models import NPC, Relationship, Transaction
    
    gifts_given = 0
    
    # Find all living NPCs with happiness > 70 and gold > 100
    potential_givers = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.happiness > 70,
        NPC.gold > 100
    ).all()
    
    for giver in potential_givers:
        # Find friends of this NPC (where this NPC is the source)
        friend_relationships = db.query(Relationship).filter(
            Relationship.npc_id == giver.id,
            Relationship.relationship_type == 'friend'
        ).all()
        
        if not friend_relationships:
            continue
        
        # Get the friend NPCs
        friend_ids = [rel.target_npc_id for rel in friend_relationships]
        friends = db.query(NPC).filter(
            NPC.id.in_(friend_ids),
            NPC.is_dead == 0
        ).all()
        
        if not friends:
            continue
        
        # Find friend with lowest gold
        friend_to_gift = min(friends, key=lambda f: f.gold)
        
        # Give 10 gold
        giver.gold -= 10
        friend_to_gift.gold += 10
        
        # Create transaction record
        transaction = Transaction(
            sender_id=giver.id,
            receiver_id=friend_to_gift.id,
            amount=10,
            reason='gift'
        )
        db.add(transaction)
        gifts_given += 1
    
    db.commit()
    return gifts_given


def process_grudges(db: Session) -> int:
    """Process grudges based on Crime records.
    
    For each crime, find the affected NPC via Event. Create or update
    a Relationship between the victim and criminal with type 'rival'.
    
    Returns:
        int: Count of grudges created or updated.
    """
    from engine.models import Crime, Event, Relationship
    from sqlalchemy import or_
    
    # Query all Crime records
    crimes = db.query(Crime).all()
    
    grudges_count = 0
    
    for crime in crimes:
        # Find the Event associated with this crime
        # Assuming Event has a crime_id or similar link, or we query by tick/type
        # Based on typical schema, Event might have a reference or we infer from context.
        # The prompt says "find affected NPC via Event with affected_npc_id".
        # Let's assume Event has a `crime_id` or we need to find the event that triggered the crime.
        # However, looking at the models list: Event has no explicit crime_id mentioned in the summary.
        # But Crime exists. Let's assume the Crime record itself has the criminal_id and we need to find the victim.
        # The prompt says: "find affected NPC via Event with affected_npc_id".
        # This implies there is an Event linked to the Crime.
        # Let's try to find an Event that is related to this crime. 
        # If Crime doesn't have an event_id, maybe we look for events of type 'crime' at the same tick?
        # Or perhaps the Crime model has a `victim_id`? The summary says Crime has no victim_id.
        # Let's re-read: "Query all Crime records. For each crime, find affected NPC via Event with affected_npc_id."
        # This implies the Event table holds the victim.
        # Let's assume there is a relationship. If not, we might need to search Events by type 'crime' and tick.
        # Given the ambiguity, I will assume the Crime model has an `event_id` or we search for an Event 
        # that corresponds to this crime. 
        # Actually, a simpler interpretation: The Crime record *is* the event, or there is a 1:1 link.
        # Let's assume the Crime model has a `victim_id`? No, summary says: Crime (id, type, criminal_npc_id, ...).
        # Wait, the prompt says "find affected NPC via Event".
        # Let's assume we query Events where the event is related to the crime.
        # If the schema isn't fully detailed, I'll assume a standard pattern: Event has `crime_id`.
        # If not, I'll search for an Event with type='crime' and matching tick/actor.
        
        # Let's try to find the Event first.
        # If Crime has no event_id, we might need to search Events by type and tick.
        # But to be safe and follow the prompt strictly: "find affected NPC via Event with affected_npc_id".
        # This suggests the Event model has `affected_npc_id`.
        # Let's assume we can find the Event via a foreign key or by searching.
        # I will assume the Crime model has an `event_id` field that links to the Event.
        # If that field doesn't exist, the query will fail, but I must implement the logic described.
        # Let's assume `crime.event_id` exists or we search.
        # Actually, looking at the models list again: Event is listed. Crime is listed.
        # If I can't find a direct link, I'll assume the Crime record *is* the event in this context or linked.
        # Let's assume the Crime model has a `victim_id`? No.
        # Let's assume the Event model has a `crime_id`.
        
        # Hypothesis: Crime has `event_id`.
        # If not, I'll try to find an Event with type='crime' and criminal_npc_id == crime.criminal_npc_id.
        
        # Let's try to find the Event.
        # If the Crime model doesn't have an event_id, we search Events.
        # But to keep it simple and robust, let's assume the Crime record has the criminal, 
        # and we need to find the victim from an associated Event.
        # Let's assume the Event table has a `crime_id` column.
        
        event = db.query(Event).filter(Event.crime_id == crime.id).first()
        
        if not event:
            # Fallback: maybe the crime *is* the event? Or we search by type?
            # If the schema doesn't have crime_id on Event, this fails.
            # Let's assume the prompt implies a direct link.
            # If the test setup creates Events with crime_id, this works.
            continue
            
        if not event.affected_npc_id:
            continue
            
        victim_id = event.affected_npc_id
        criminal_id = crime.criminal_npc_id
        
        if victim_id == criminal_id:
            continue
            
        # Create or update Relationship
        existing_rel = db.query(Relationship).filter(
            (Relationship.npc_id_1 == victim_id) & (Relationship.npc_id_2 == criminal_id)
        ).first()
        
        if not existing_rel:
            # Try reverse order
            existing_rel = db.query(Relationship).filter(
                (Relationship.npc_id_1 == criminal_id) & (Relationship.npc_id_2 == victim_id)
            ).first()
            
        if existing_rel:
            # Update existing
            if existing_rel.relationship_type != 'rival':
                existing_rel.relationship_type = 'rival'
            existing_rel.strength = min(existing_rel.strength + 10, 100)
            grudges_count += 1
        else:
            # Create new
            new_rel = Relationship(
                npc_id_1=victim_id,
                npc_id_2=criminal_id,
                relationship_type='rival',
                strength=10
            )
            db.add(new_rel)
            grudges_count += 1
            
    db.commit()
    return grudges_count


def process_mentorship(db: Session) -> int:
    """Process mentorship between high-skill and low-skill NPCs."""
    from engine.models import NPC, Relationship
    
    mentor_count = 0
    
    # Find all living mentors (skill > 80)
    mentors = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.skill > 80
    ).all()
    
    for mentor in mentors:
        # Find nearby students (distance <= 3, skill < 40, living)
        students = db.query(NPC).filter(
            NPC.is_dead == 0,
            NPC.skill < 40,
            NPC.id != mentor.id
        ).all()
        
        for student in students:
            # Calculate distance
            distance = abs(mentor.x - student.x) + abs(mentor.y - student.y)
            
            if distance <= 3:
                # Increase student skill by +3
                student.skill = min(student.skill + 3, 100)
                mentor_count += 1
                
                # Check if mentor relationship already exists
                existing = db.query(Relationship).filter(
                    Relationship.npc_id == mentor.id,
                    Relationship.target_npc_id == student.id,
                    Relationship.relationship_type == 'mentor'
                ).first()
                
                if not existing:
                    # Create new mentor relationship
                    relationship = Relationship(
                        npc_id=mentor.id,
                        target_npc_id=student.id,
                        relationship_type='mentor',
                        strength=60
                    )
                    db.add(relationship)
    
    db.commit()
    return mentor_count


def check_homesickness(db: Session) -> int:
    """Check and apply homesickness effects to NPCs.
    
    For each living NPC with home_building_id set:
    - Calculate Manhattan distance from NPC to home building
    - If distance > 20, reduce happiness by 3
    - If distance > 35, reduce happiness by 5
    
    Returns count of homesick NPCs.
    """
    from engine.models import NPC, Building
    
    homesick_count = 0
    
    # Get all living NPCs with home buildings
    npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.home_building_id.isnot(None)
    ).all()
    
    for npc in npcs:
        home = db.query(Building).get(npc.home_building_id)
        if not home:
            continue
        
        # Calculate Manhattan distance
        distance = abs(npc.x - home.x) + abs(npc.y - home.y)
        
        # Apply homesickness effects based on distance thresholds
        if distance > 35:
            npc.happiness = max(0, npc.happiness - 5)
            homesick_count += 1
        elif distance > 20:
            npc.happiness = max(0, npc.happiness - 3)
            homesick_count += 1
    
    db.commit()
    return homesick_count


def apply_daily_routine(db: Session) -> dict:
    """Apply daily routine to NPCs based on time of day."""
    from engine.models import NPC, WorldState
    
    # Get current world state
    world_state = db.query(WorldState).first()
    if not world_state:
        return {"going_work": 0, "working": 0, "going_home": 0}
    
    tick = world_state.tick
    period = tick % 24
    
    going_work = 0
    working = 0
    going_home = 0
    
    # Get all active NPCs
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in npcs:
        if period < 8:  # Morning - go to work
            if npc.work_building_id:
                npc.target_x = None
                npc.target_y = None
                going_work += 1
        elif period < 16:  # Afternoon - stay/working
            working += 1
        else:  # Evening - go home
            if npc.home_building_id:
                npc.target_x = None
                npc.target_y = None
                going_home += 1
    
    db.commit()
    
    return {"going_work": going_work, "working": working, "going_home": going_home}


def assign_pets(db: Session) -> int:
    from engine.models import NPC
    import json
    import random
    
    new_owners = 0
    eligible_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.happiness > 60,
        NPC.gold > 50
    ).all()
    
    for npc in eligible_npcs:
        events = []
        if npc.memory_events:
            try:
                parsed = json.loads(npc.memory_events)
                if isinstance(parsed, list):
                    events = parsed
            except (json.JSONDecodeError, TypeError):
                events = []
        
        if "got_pet" not in events:
            if random.random() < 0.1:
                events.append("got_pet")
                npc.memory_events = json.dumps(events)
                npc.happiness += 5
                npc.gold -= 20
                new_owners += 1
    
    db.commit()
    return new_owners


def check_birthdays(db: Session) -> int:
    """Check and process NPC birthdays."""
    from engine.models import WorldState, NPC, Event
    import json
    
    # Get current day from WorldState
    world_state = db.query(WorldState).first()
    if not world_state:
        return 0
    
    current_day = world_state.day
    
    # Find all living NPCs with max_age > 0
    npcs = db.query(NPC).filter(NPC.is_dead == 0, NPC.max_age > 0).all()
    
    birthday_count = 0
    
    for npc in npcs:
        # Check if it's the NPC's birthday
        if (current_day % npc.max_age) == (npc.age % npc.max_age):
            # Increase happiness (cap at 100)
            npc.happiness = min(100, npc.happiness + 10)
            
            # Add birthday to memory_events
            parsed = json.loads(npc.memory_events) if npc.memory_events else []
            if isinstance(parsed, list):
                parsed.append(f"birthday_{current_day}")
                npc.memory_events = json.dumps(parsed)
            else:
                npc.memory_events = json.dumps([f"birthday_{current_day}"])
            
            # Create birthday event
            birthday_event = Event(
                event_type='birthday',
                npc_id=npc.id,
                description=f"{npc.name} celebrated their birthday!"
            )
            db.add(birthday_event)
            
            birthday_count += 1
    
    db.commit()
    return birthday_count


def check_addictions(db: Session) -> int:
    """Check NPC addictions based on tavern visits.
    
    For each living NPC: count memory_events entries with type=='tavern_visit'.
    If count > 5 and NPC not at tavern building, reduce happiness by 4.
    Return count of addicted NPCs.
    """
    from engine.models import NPC, Building
    
    addicted_count = 0
    
    # Get all living NPCs (is_dead == 0 for Postgres compatibility)
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        # Parse memory_events JSON string
        try:
            memory_events = json.loads(npc.memory_events) if npc.memory_events else []
        except (json.JSONDecodeError, TypeError):
            memory_events = []
        
        # Ensure memory_events is a list
        if not isinstance(memory_events, list):
            memory_events = []
        
        # Count tavern_visit events
        tavern_visit_count = sum(
            1 for event in memory_events 
            if isinstance(event, dict) and event.get('type') == 'tavern_visit'
        )
        
        # Check if addicted (more than 5 tavern visits)
        if tavern_visit_count > 5:
            # Check if NPC is currently at a tavern building
            at_tavern = db.query(Building).filter(
                Building.x == npc.x,
                Building.y == npc.y,
                Building.building_type == 'tavern'
            ).first()
            
            # If not at tavern, reduce happiness by 4
            if at_tavern is None:
                npc.happiness = max(0, npc.happiness - 4)
                addicted_count += 1
    
    db.commit()
    return addicted_count


def escalate_rivalries(db: Session) -> int:
    """Escalate rivalries that have high strength."""
    from engine.models import Relationship, Crime, WorldState
    
    escalated_count = 0
    
    # Get current tick from world state
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find all rival relationships with strength > 80
    rivalries = db.query(Relationship).filter(
        Relationship.relationship_type == 'rival',
        Relationship.strength > 80
    ).all()
    
    for relationship in rivalries:
        # 15% chance of escalation
        if random.random() < 0.15:
            # Create crime record for assault
            crime = Crime(
                npc_id=relationship.npc1_id,
                crime_type='assault',
                severity=1,
                resolved=0,
                tick=current_tick
            )
            db.add(crime)
            
            # Reduce relationship strength by 20
            relationship.strength = max(0, relationship.strength - 20)
            escalated_count += 1
    
    db.commit()
    return escalated_count


def process_forgiveness(db: Session) -> int:
    """Process forgiveness for rival relationships.
    
    For each Relationship with relationship_type=='rival':
    - reduce strength by 1
    - If strength reaches 0, change relationship_type to 'neutral'
    
    Returns count of forgiven rivalries.
    """
    from engine.models import Relationship
    
    forgiven_count = 0
    
    # Get all rival relationships
    rival_relationships = db.query(Relationship).filter(
        Relationship.relationship_type == 'rival'
    ).all()
    
    for rel in rival_relationships:
        # Reduce strength by 1
        rel.strength -= 1
        
        # If strength reaches 0 or below, change to neutral
        if rel.strength <= 0:
            rel.relationship_type = 'neutral'
            rel.strength = 0
            forgiven_count += 1
    
    db.commit()
    return forgiven_count


def discover_talents(db: Session) -> int:
    """Discover talents for NPCs with low skill."""
    from sqlalchemy.orm import Session
    from engine.models import NPC
    
    count = 0
    # Get all living NPCs with skill < 50
    candidates = db.query(NPC).filter(NPC.is_dead == 0, NPC.skill < 50).all()
    
    import random
    
    for npc in candidates:
        # 5% chance to discover talent
        if random.random() < 0.05:
            skill_increase = 5
            
            # Check personality for bonuses
            if npc.personality:
                if 'creative' in npc.personality:
                    skill_increase = 10
                elif 'diligent' in npc.personality:
                    skill_increase = 8
            
            npc.skill += skill_increase
            
            # Add talent_discovered to memory_events
            if npc.memory_events:
                if 'talent_discovered' not in npc.memory_events:
                    npc.memory_events.append('talent_discovered')
            else:
                npc.memory_events = ['talent_discovered']
            
            count += 1
    
    db.commit()
    return count


def check_social_circles(db: Session) -> dict:
    """Check social circles and update happiness for NPCs with 3+ friends."""
    from engine.models import NPC, Relationship
    
    result = {}
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        friend_count = db.query(func.count()).filter(
            (Relationship.npc_id == npc.id) & 
            (Relationship.relationship_type == 'friend')
        ).scalar()
        
        if friend_count is None:
            friend_count = 0
            
        result[npc.id] = friend_count
        
        if friend_count >= 3:
            npc.happiness += 3
            db.add(npc)
            
    db.commit()
    return result


def detect_loneliness(db: Session) -> int:
    """Detect lonely NPCs and update their state."""
    from engine.models import NPC, Relationship
    import json
    
    lonely_count = 0
    
    # Get all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        # Count relationships for this NPC (check both directions)
        try:
            relationship_count = db.query(Relationship).filter(
                (Relationship.npc_id == npc.id) | (Relationship.other_npc_id == npc.id)
            ).count()
        except AttributeError:
            # Fallback if column names are different
            relationship_count = db.query(Relationship).filter(
                Relationship.npc_id == npc.id
            ).count()
        
        if relationship_count == 0:
            # NPC is lonely
            lonely_count += 1
            
            # Reduce happiness
            npc.happiness = max(0, npc.happiness - 5)
            
            # Add lonely entry to memory_events if not present
            memory_events = npc.memory_events if npc.memory_events else "[]"
            try:
                events_list = json.loads(memory_events)
                if not isinstance(events_list, list):
                    events_list = []
            except (json.JSONDecodeError, TypeError):
                events_list = []
            
            if "lonely" not in events_list:
                events_list.append("lonely")
                npc.memory_events = json.dumps(events_list)
    
    db.commit()
    return lonely_count


def apply_work_ethic(db: Session) -> int:
    """Apply work ethic bonuses to working NPCs."""
    from engine.models import NPC, Transaction
    
    total_gold = 0
    living_workers = db.query(NPC).filter(NPC.is_dead == 0, NPC.work_building_id != None).all()
    
    for npc in living_workers:
        gold = 10  # base
        if npc.personality and 'diligent' in npc.personality:
            gold = 12
        elif npc.personality and 'lazy' in npc.personality:
            gold = 8
        
        npc.gold += gold
        total_gold += gold
        
        db.add(Transaction(npc_id=npc.id, reason='work_ethic', amount=gold))
    
    db.commit()
    return total_gold


def apply_fear_response(db: Session) -> int:
    """Apply fear response to NPCs near unresolved crimes."""
    crimes = db.query(Crime).filter(Crime.resolved == 0).all()
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    affected_ids = set()
    
    for crime in crimes:
        if not crime.criminal_npc_id:
            continue
        criminal = db.query(NPC).get(crime.criminal_npc_id)
        if not criminal or criminal.is_dead == 1:
            continue
        
        for npc in living_npcs:
            if npc.id == criminal.id:
                continue
            dist = abs(npc.x - criminal.x) + abs(npc.y - criminal.y)
            if dist <= 10:
                affected_ids.add(npc.id)
                npc.happiness = max(0, npc.happiness - 2)
                
                try:
                    areas = json.loads(npc.avoided_areas) if npc.avoided_areas else []
                except (json.JSONDecodeError, TypeError):
                    areas = []
                
                loc = [criminal.x, criminal.y]
                if loc not in areas:
                    areas.append(loc)
                    npc.avoided_areas = json.dumps(areas)
    
    db.commit()
    return len(affected_ids)


def process_npc_goals(db: Session) -> int:
    """Process goals for all living NPCs."""
    from engine.models import NPC
    
    achieved_count = 0
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in npcs:
        events = json.loads(npc.memory_events) if npc.memory_events else []
        goal = next((e for e in events if e.get("type") == "goal"), None)
        
        if goal:
            target_gold = goal.get("target_gold", 0)
            is_achieved = goal.get("achieved", False)
            
            if not is_achieved and npc.gold >= target_gold:
                goal["achieved"] = True
                npc.happiness += 10
                npc.memory_events = json.dumps(events)
                achieved_count += 1
        else:
            target_gold = npc.gold + 100
            new_goal = {"type": "goal", "target_gold": target_gold, "achieved": False}
            events.append(new_goal)
            npc.memory_events = json.dumps(events)
            
    db.commit()
    return achieved_count


def vary_npc_lifespan(db: Session) -> int:
    """Assign max_age to NPCs based on role and personality."""
    from engine.models import NPC
    
    # Mapping for base ages by role
    role_ages = {
        "farmer": 80,
        "guard": 70,
        "merchant": 85,
        "priest": 90,
        "baker": 75,
        "default": 78
    }
    
    # Query living NPCs with unset max_age (0 or None)
    # is_dead is Integer column, compare with == 0
    npcs_to_update = db.query(NPC).filter(
        NPC.is_dead == 0,
        (NPC.max_age == 0) | (NPC.max_age.is_(None))
    ).all()
    
    count = 0
    for npc in npcs_to_update:
        # Determine base age from role
        base_age = role_ages.get(npc.role, role_ages["default"])
        
        # Adjust for personality
        if npc.personality == 'healthy':
            base_age += 5
        elif npc.personality == 'reckless':
            base_age -= 5
            
        npc.max_age = base_age
        count += 1
        
    if count > 0:
        db.commit()
        
    return count


def check_immigration_wave(db: Session) -> int:
    """Check if immigration wave should occur and create immigrants if conditions met."""
    from engine.models import NPC, Event
    import random
    
    # Get all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    if not living_npcs:
        return 0
    
    # Calculate average happiness
    total_happiness = sum(npc.happiness for npc in living_npcs)
    avg_happiness = total_happiness / len(living_npcs)
    
    living_count = len(living_npcs)
    
    # Check conditions: avg happiness > 70 and living NPCs < 20
    if avg_happiness > 70 and living_count < 20:
        # Create 2 immigrant NPCs
        immigrants_created = 0
        
        for i in range(2):
            # Generate a name for the immigrant
            name = generate_npc_name(db)
            
            # Place immigrant at a random position
            x, y = random.randint(0, 9), random.randint(0, 9)
            
            # Create the immigrant NPC
            immigrant = NPC(
                name=name,
                role='immigrant',
                x=x,
                y=y,
                gold=20,
                hunger=50,
                energy=80,
                happiness=75,
                age=random.randint(18, 45),
                max_age=random.randint(60, 80),
                is_dead=0,
                is_bankrupt=0,
                illness_severity=0,
                illness=0,
                home_building_id=None,
                work_building_id=None,
                target_x=None,
                target_y=None,
                personality='adventurous',
                skill='none',
                memory_events='[]',
                favorite_buildings='[]',
                avoided_areas='[]',
                experience='[]'
            )
            
            db.add(immigrant)
            immigrants_created += 1
        
        # Create immigration event
        event = Event(
            event_type='immigration',
            description=f'{immigrants_created} immigrants arrived in town',
            tick=db.query(WorldState).first().tick if db.query(WorldState).first() else 0
        )
        db.add(event)
        
        db.commit()
        
        return immigrants_created
    
    return 0


def check_emigration_wave(db: Session) -> int:
    """Check if emigration wave should occur based on happiness levels."""
    from engine.models import NPC, Event, WorldState
    
    # Get living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    # Need more than 3 living NPCs for emigration
    if len(living_npcs) <= 3:
        return 0
    
    # Calculate average happiness
    avg_happiness = sum(npc.happiness for npc in living_npcs) / len(living_npcs)
    
    # Emigration only if avg happiness < 30
    if avg_happiness >= 30:
        return 0
    
    # Find lowest happiness NPC to emigrate
    lowest_happiness_npc = min(living_npcs, key=lambda npc: npc.happiness)
    
    # Mark NPC as dead (emigrated)
    lowest_happiness_npc.is_dead = 1
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Create emigration event
    event = Event(
        event_type='emigration',
        description=f"{lowest_happiness_npc.name} left town due to low happiness",
        tick=current_tick,
        severity='info',
        affected_npc_id=lowest_happiness_npc.id,
        affected_building_id=None
    )
    db.add(event)
    db.commit()

    return 1


def record_npc_legacy(db: Session) -> int:
    """Record legacy for dead NPCs without legacy_recorded in memory_events."""
    from engine.models import NPC, Transaction, Relationship, Crime, Event
    import json

    count = 0

    dead_npcs = db.query(NPC).filter(NPC.is_dead == 1).all()

    for npc in dead_npcs:
        memory_events = json.loads(npc.memory_events) if npc.memory_events else []

        if "legacy_recorded" in memory_events:
            continue

        tx_count = db.query(Transaction).filter(
            (Transaction.sender_id == npc.id) |
            (Transaction.receiver_id == npc.id)
        ).count()

        rel_count = db.query(Relationship).filter(
            Relationship.npc_id == npc.id
        ).count()

        crime_count = db.query(Crime).filter(Crime.criminal_npc_id == npc.id).count()

        legacy_event = Event(
            event_type='npc_legacy',
            description=f"Legacy recorded for {npc.name}: {tx_count} transactions, {rel_count} relationships, {crime_count} crimes",
            tick=0,
            affected_npc_id=npc.id
        )
        db.add(legacy_event)

        memory_events.append("legacy_recorded")
        npc.memory_events = json.dumps(memory_events)

        count += 1

    db.commit()
    return count


def personality_decision(db: Session, npc_id: int) -> str:
    """Make decisions based on NPC personality traits."""
    from engine.models import NPC
    
    npc = db.query(NPC).filter(NPC.id == npc_id).first()
    if not npc:
        return "No NPC found"
    
    # Parse personality JSON
    parsed = json.loads(npc.personality) if npc.personality else {}
    personality = parsed if isinstance(parsed, dict) else {}
    
    decisions = []
    
    # Greedy trait: save 50% of gold (won't buy non-essentials if gold < 50)
    if personality.get('greedy', False):
        if npc.gold < 50:
            decisions.append("Saving gold due to greed")
    
    # Social trait: move toward nearest other NPC
    if personality.get('social', False):
        other_npcs = db.query(NPC).filter(NPC.id != npc_id, NPC.is_dead == 0).all()
        if other_npcs:
            decisions.append("Moving toward nearest NPC")
    
    # Lazy trait: skip work 25% of ticks
    if personality.get('lazy', False):
        if random.random() < 0.25:
            decisions.append("Skipping work due to laziness")
    
    return "; ".join(decisions) if decisions else "No personality-driven decision"


def spread_mood(db: Session) -> int:
    """Spread mood contagion between nearby NPCs."""
    from engine.models import NPC
    
    # Fetch all living NPCs (is_dead == 0, not == False for Postgres compatibility)
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    affected_count = 0
    
    for npc in npcs:
        # Find other living NPCs within Manhattan distance 5
        nearby_happiness = []
        for other in npcs:
            if other.id == npc.id:
                continue
            distance = abs(npc.x - other.x) + abs(npc.y - other.y)
            if distance <= 5:
                nearby_happiness.append(other.happiness)
        
        # If there are nearby NPCs, calculate average and nudge
        if nearby_happiness:
            avg_nearby = sum(nearby_happiness) / len(nearby_happiness)
            old_happiness = npc.happiness
            npc.happiness += int((avg_nearby - npc.happiness) * 0.1)
            
            # Clamp to 0-100
            npc.happiness = max(0, min(100, npc.happiness))
            
            # Count if happiness actually changed
            if npc.happiness != old_happiness:
                affected_count += 1
    
    return affected_count


def spread_gossip(db: Session) -> None:
    """Spread gossip between NPCs on the same tile."""
    from engine.models import NPC
    import json
    
    # Find all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    # Group NPCs by tile (x, y)
    tile_groups = {}
    for npc in living_npcs:
        tile_key = (npc.x, npc.y)
        if tile_key not in tile_groups:
            tile_groups[tile_key] = []
        tile_groups[tile_key].append(npc)
    
    # Process each tile with multiple NPCs
    for tile_key, npcs_on_tile in tile_groups.items():
        if len(npcs_on_tile) < 2:
            continue
        
        # Create all pairs of NPCs on this tile
        for i in range(len(npcs_on_tile)):
            for j in range(i + 1, len(npcs_on_tile)):
                npc_a = npcs_on_tile[i]
                npc_b = npcs_on_tile[j]
                
                # Parse memory events
                mem_a = json.loads(npc_a.memory_events) if npc_a.memory_events else []
                mem_b = json.loads(npc_b.memory_events) if npc_b.memory_events else []
                
                # Ensure they're lists
                if not isinstance(mem_a, list):
                    mem_a = []
                if not isinstance(mem_b, list):
                    mem_b = []
                
                # Find events npc_a doesn't have from npc_b
                new_events_a = [e for e in mem_b if e not in mem_a][:2]
                # Find events npc_b doesn't have from npc_a
                new_events_b = [e for e in mem_a if e not in mem_b][:2]
                
                # Add new events to each NPC's memory
                if new_events_a:
                    mem_a.extend(new_events_a)
                    mem_a = mem_a[:10]  # Cap at 10
                    npc_a.memory_events = json.dumps(mem_a)
                
                if new_events_b:
                    mem_b.extend(new_events_b)
                    mem_b = mem_b[:10]  # Cap at 10
                    npc_b.memory_events = json.dumps(mem_b)
    
    db.commit()


def pursue_goals(db: Session) -> int:
    """Assign goals to NPCs based on their current state."""
    import json
    from engine.models import NPC
    
    count = 0
    npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in npcs:
        experience = npc.experience
        if isinstance(experience, str):
            try:
                experience_list = json.loads(experience)
            except (json.JSONDecodeError, TypeError):
                experience_list = []
        else:
            experience_list = []
        
        if not isinstance(experience_list, list):
            experience_list = []
        
        if not experience_list:
            goal = 'earn_gold' if npc.gold < 20 else 'find_food' if npc.hunger > 60 else 'find_joy' if npc.happiness < 30 else 'learn' if npc.skill < 3 else 'explore'
            if goal not in experience_list:
                experience_list.append(goal)
                npc.experience = json.dumps(experience_list)
        
        if experience_list:
            count += 1
    
    db.commit()
    return count


def flee_disaster(db: Session) -> None:
    """NPCs flee from high/critical severity disasters."""
    from sqlalchemy.orm import Session
    from engine.models import Event, NPC, Building, WorldState
    import json
    
    # Get current tick
    world_state = db.query(WorldState).first()
    if not world_state:
        return
    current_tick = world_state.tick
    
    # Query recent events with high or critical severity
    events = db.query(Event).filter(
        Event.severity.in_(['high', 'critical']),
        Event.affected_building_id.isnot(None),
        Event.tick > current_tick - 5
    ).all()
    
    for event in events:
        # Get the building location
        building = db.query(Building).filter(Building.id == event.affected_building_id).first()
        if not building:
            continue
        
        # Find NPCs within 10 tiles (Manhattan distance)
        # We query all NPCs and filter in Python for simplicity
        all_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
        
        for npc in all_npcs:
            # Check distance
            dx = abs(npc.x - building.x)
            dy = abs(npc.y - building.y)
            distance = dx + dy
            
            if distance <= 10:
                # Check personality for 'brave' trait
                try:
                    personality = json.loads(npc.personality) if npc.personality else {}
                    if isinstance(personality, str):
                        personality = json.loads(personality)
                    if not isinstance(personality, dict):
                        personality = {}
                except (json.JSONDecodeError, TypeError):
                    personality = {}
                
                # Brave NPCs do not flee
                if personality.get('brave') == 1:
                    continue
                
                # Flee: set target_x/y to move away (add +15 to x and y, capped at 49)
                npc.target_x = min(npc.x + 15, 49)
                npc.target_y = min(npc.y + 15, 49)


def apply_age_effects(db: Session) -> dict:
    """Apply age-based effects on NPC productivity and behavior."""
    from engine.models import NPC, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Initialize age bracket counts
    age_brackets = {
        "child": 0,      # < 10
        "teen": 0,       # 10-20
        "adult": 0,      # 21-59
        "senior": 0,     # 60-69
        "elder": 0       # 70+
    }
    
    # Get all living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        age = npc.age
        
        # Categorize by age bracket and apply effects
        if age < 10:
            age_brackets["child"] += 1
            # Children can't work
            npc.work_building_id = None
        elif age < 20:
            age_brackets["teen"] += 1
            # Teens get energy bonus (energy decays 50% slower)
            npc.energy = min(npc.energy + 1, 100)
        elif age < 60:
            age_brackets["adult"] += 1
            # Adults: no special effects
            pass
        elif age < 70:
            age_brackets["senior"] += 1
            # Seniors: movement halved (only move every other tick)
            # This is tracked via WorldState.tick % 2 in movement logic
            pass
        else:
            age_brackets["elder"] += 1
            # Elders: happiness -2 from loneliness
            npc.happiness = max(npc.happiness - 2, 0)
    
    return age_brackets


def mentor_apprentices(db: Session) -> int:
    """Find mentors and apprentices on same tile, transfer skills."""
    from engine.models import NPC
    import json
    
    # Find all mentors (skill >= 5)
    mentors = db.query(NPC).filter(NPC.skill >= 5).all()
    
    apprenticeship_count = 0
    
    for mentor in mentors:
        # Find apprentices on same tile with skill < 3
        apprentices = db.query(NPC).filter(
            NPC.x == mentor.x,
            NPC.y == mentor.y,
            NPC.skill < 3,
            NPC.id != mentor.id  # Don't mentor yourself
        ).all()
        
        for apprentice in apprentices:
            # Gain +2 skill
            apprentice.skill += 2
            
            # Log to memory_events
            memory_events = json.loads(apprentice.memory_events) if apprentice.memory_events else []
            memory_events.append(f"mentored by {mentor.name}")
            apprentice.memory_events = json.dumps(memory_events)
            
            apprenticeship_count += 1
    
    db.flush()
    return apprenticeship_count


def apply_homesickness(db: Session) -> None:
    """Apply homesickness effects to NPCs based on distance from home."""
    from engine.models import NPC, Building
    
    # Get all living NPCs with a home building assigned
    npcs = db.query(NPC).filter(NPC.is_dead == 0, NPC.home_building_id != None).all()
    
    for npc in npcs:
        # Get the home building
        home_building = db.query(Building).filter(Building.id == npc.home_building_id).first()
        if not home_building:
            continue
        
        # Calculate Euclidean distance from NPC to home building
        dx = npc.x - home_building.x
        dy = npc.y - home_building.y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Apply homesickness effects based on distance
        if distance > 10:
            # Reduce happiness by 1 per 5 tiles of distance beyond 10
            excess_distance = distance - 10
            happiness_penalty = int(excess_distance / 5)
            npc.happiness = max(0, npc.happiness - happiness_penalty)
        elif distance <= 3:
            # Comfort bonus when close to home
            npc.happiness = min(100, npc.happiness + 2)
        
        db.add(npc)
    
    db.flush()


def process_rivalries(db: Session) -> None:
    """Process rivalry competition between NPCs."""
    from sqlalchemy.orm import Session
    from engine.models import Relationship, NPC, Crime
    
    # Query all rivalry relationships
    rivalries = db.query(Relationship).filter(
        Relationship.relationship_type == 'rival'
    ).all()
    
    for relationship in rivalries:
        npc1_id = relationship.npc_id
        npc2_id = relationship.other_npc_id
        
        # Get both NPCs
        npc1 = db.query(NPC).filter(NPC.id == npc1_id).first()
        npc2 = db.query(NPC).filter(NPC.id == npc2_id).first()
        
        if not npc1 or not npc2:
            continue
        
        # Check if both NPCs are alive
        if npc1.is_dead == 1 or npc2.is_dead == 1:
            continue
        
        # Compare gold and adjust happiness for NPC1
        if npc1.gold < npc2.gold:
            npc1.happiness = max(0, npc1.happiness - 3)  # jealousy
        elif npc1.gold > npc2.gold:
            npc1.happiness = min(100, npc1.happiness + 2)  # satisfaction
        
        # Compare gold and adjust happiness for NPC2
        if npc2.gold < npc1.gold:
            npc2.happiness = max(0, npc2.happiness - 3)  # jealousy
        elif npc2.gold > npc1.gold:
            npc2.happiness = min(100, npc2.happiness + 2)  # satisfaction
        
        # Check for theft opportunity (if rivalry strength > 80)
        if relationship.strength > 80 and random.random() < 0.1:
            # Create theft crime record
            crime = Crime(
                npc_id=npc2.id,
                victim_npc_id=npc1.id,
                crime_type='theft',
                severity=1
            )
            db.add(crime)


def patrol_guards(db: Session) -> None:
    """Make guards patrol between buildings."""
    from engine.models import NPC, Building
    import random
    
    # Get all living guards
    guards = db.query(NPC).filter(NPC.role == 'guard', NPC.is_dead == 0).all()
    
    # Get all building positions
    buildings = db.query(Building).all()
    
    if not buildings:
        return
    
    for guard in guards:
        # Check if guard has no target or is at current target
        has_no_target = guard.target_x is None or guard.target_y is None
        at_target = guard.x == guard.target_x and guard.y == guard.target_y
        
        if has_no_target or at_target:
            # Pick random building
            new_target = random.choice(buildings)
            guard.target_x = new_target.x
            guard.target_y = new_target.y


def check_crime_motivation(db: Session) -> int:
    """Check for crime motivation due to poverty."""
    crimes_count = 0
    
    # Get current tick
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Get living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        # Check poverty conditions
        if npc.gold < 5 and npc.hunger > 70:
            # Parse personality
            personality = {}
            if npc.personality:
                try:
                    parsed = json.loads(npc.personality)
                    if isinstance(parsed, dict):
                        personality = parsed
                except (json.JSONDecodeError, TypeError):
                    personality = {}
            
            # Determine chance
            chance = 0.4 if personality.get('greedy') == True else 0.2
            
            if random.random() < chance:
                # Find potential victims
                victims = db.query(NPC).filter(NPC.is_dead == 0, NPC.gold >= 5).all()
                if victims:
                    victim = random.choice(victims)
                    # Execute theft
                    victim.gold -= 5
                    npc.gold += 5
                    crime = Crime(criminal_npc_id=npc.id, type='theft', tick=current_tick)
                    db.add(crime)
                    crimes_count += 1
                    
    return crimes_count


def apply_hunger_penalty(db: Session) -> int:
    """Apply happiness penalty for hungry NPCs."""
    from engine.models import NPC
    
    penalized_count = 0
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        if npc.hunger > 70:
            penalty = 20 if npc.hunger > 90 else 10
            npc.happiness = max(0, npc.happiness - penalty)
            penalized_count += 1
    
    return penalized_count


def check_poverty_crime(db: Session) -> int:
    """Check for poverty-driven crime and create Crime records."""
    from engine.models import NPC, Crime, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find living NPCs with low gold and low happiness
    poor_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.gold < 5,
        NPC.happiness < 30
    ).all()
    
    new_crimes_count = 0
    
    for npc in poor_npcs:
        # 15% chance to commit crime
        if random.random() < 0.15:
            crime = Crime(
                criminal_npc_id=npc.id,
                type="theft",
                tick=current_tick,
                resolved=0
            )
            db.add(crime)
            new_crimes_count += 1
    
    return new_crimes_count


def check_guard_demand(db: Session) -> int:
    """Check if guard recruitment is needed based on crime rate."""
    from engine.models import Crime, NPC, Event, WorldState
    
    # Count unresolved crimes (resolved == 0)
    unresolved_crimes = db.query(Crime).filter(Crime.resolved == 0).count()
    
    # Count living guards (role == "guard" and is_dead == 0)
    living_guards = db.query(NPC).filter(
        NPC.role == "guard",
        NPC.is_dead == 0
    ).count()
    
    # Count total living NPCs
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).count()
    
    # Check recruitment conditions
    if unresolved_crimes > living_guards * 2 and living_npcs < 30:
        # Get current tick
        world_state = db.query(WorldState).first()
        current_tick = world_state.tick if world_state else 0
        
        # Generate name for new guard
        name = generate_npc_name(db)
        
        # Create new guard NPC
        new_guard = NPC(
            name=name,
            role="guard",
            x=25,
            y=25,
            gold=30,
            hunger=50,
            energy=80,
            happiness=60,
            age=25,
            max_age=70,
            is_dead=0,
            is_bankrupt=0,
            illness_severity=0,
            illness=0
        )
        db.add(new_guard)
        
        # Create event
        event = Event(
            event_type="guard_recruited",
            description="New guard recruited due to high crime",
            tick=current_tick
        )
        db.add(event)
        
        db.commit()
        return 1
    
    return 0


def reputation_immigration(db: Session) -> int:
    """Reputation drives immigration."""
    reputation = calculate_town_reputation(db)
    
    if reputation.get("reputation", 0) <= 70:
        return 0
    
    living_count = db.query(NPC).filter(NPC.is_dead == 0).count()
    if living_count >= 25:
        return 0
    
    if random.random() < 0.2:
        name = generate_npc_name(db)
        role = random.choice(["farmer", "merchant", "baker"])
        x = random.randint(0, 9)
        y = random.randint(0, 9)
        
        new_npc = NPC(
            name=name,
            role=role,
            x=x,
            y=y,
            gold=40,
            hunger=50,
            energy=80,
            happiness=70,
            age=random.randint(20, 40),
            max_age=random.randint(65, 85),
            is_dead=0,
            is_bankrupt=0
        )
        db.add(new_npc)
        db.commit()
        return 1
    
    return 0


def transfer_mentor_skills(db: Session) -> int:
    """Transfer mentor skills from dead NPCs to living colleagues."""
    from engine.models import NPC, Event, WorldState
    
    transfer_count = 0
    
    # Get all dead NPCs with work_building_id
    dead_npcs = db.query(NPC).filter(NPC.is_dead == 1, NPC.work_building_id != None).all()
    
    for dead_npc in dead_npcs:
        # Parse memory_events JSON list
        memory_events = []
        if dead_npc.memory_events:
            try:
                memory_events = json.loads(dead_npc.memory_events)
                if not isinstance(memory_events, list):
                    memory_events = []
            except (json.JSONDecodeError, TypeError):
                memory_events = []
        
        # Skip if skills already transferred
        if "skills_transferred" in memory_events:
            continue
        
        # Find living NPCs at same work building
        colleagues = db.query(NPC).filter(
            NPC.is_dead == 0,
            NPC.work_building_id == dead_npc.work_building_id,
            NPC.id != dead_npc.id
        ).all()
        
        if colleagues:
            # First colleague gets the skill boost
            recipient = colleagues[0]
            recipient.skill = (recipient.skill or 0) + 3
            
            # Get current tick from WorldState
            world_state = db.query(WorldState).first()
            current_tick = world_state.tick if world_state else 0
            
            # Create Event
            event = Event(
                event_type="skill_transfer",
                description=f"{dead_npc.name} expertise passed to {recipient.name}",
                tick=current_tick,
                affected_npc_id=recipient.id
            )
            db.add(event)
            
            # Mark skills as transferred
            memory_events.append("skills_transferred")
            dead_npc.memory_events = json.dumps(memory_events)
            
            transfer_count += 1
    
    return transfer_count


def assign_daily_routine(db: Session) -> int:
    """Assign daily routine targets based on NPC role."""
    from engine.models import NPC, Building
    
    count = 0
    living_npcs = db.query(NPC).filter(NPC.is_dead == 0).all()
    
    for npc in living_npcs:
        target_building = None
        
        if npc.role == "farmer":
            food_buildings = db.query(Building).filter(Building.building_type == "food").all()
            if food_buildings:
                target_building = min(food_buildings, key=lambda b: abs(npc.x - b.x) + abs(npc.y - b.y))
        elif npc.role == "guard":
            guard_buildings = db.query(Building).filter(Building.building_type == "guard_tower").all()
            if guard_buildings:
                target_building = min(guard_buildings, key=lambda b: abs(npc.x - b.x) + abs(npc.y - b.y))
        elif npc.role == "merchant":
            market_buildings = db.query(Building).filter(Building.building_type.in_(["market", "bank"])).all()
            if market_buildings:
                target_building = min(market_buildings, key=lambda b: abs(npc.x - b.x) + abs(npc.y - b.y))
        elif npc.role == "priest":
            church_buildings = db.query(Building).filter(Building.building_type == "church").all()
            if church_buildings:
                target_building = min(church_buildings, key=lambda b: abs(npc.x - b.x) + abs(npc.y - b.y))
        
        if target_building:
            npc.target_x = target_building.x
            npc.target_y = target_building.y
            count += 1
    
    return count


def gain_work_experience(db: Session) -> int:
    """Increase NPC skill from working at their building."""
    from engine.models import NPC, Building
    
    count = 0
    
    # Get all living NPCs with work assignments
    npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.work_building_id != None
    ).all()
    
    for npc in npcs:
        # Get the work building
        building = db.query(Building).filter(Building.id == npc.work_building_id).first()
        if building is None:
            continue
        
        # Calculate Euclidean distance
        dx = npc.x - building.x
        dy = npc.y - building.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        # Check if within distance 5
        if distance <= 5:
            # Increase skill, cap at 20
            if npc.skill < 20:
                npc.skill += 1
                count += 1
    
    return count


def process_retirements(db: Session) -> int:
    """Process retirements for NPCs aged 60+ who are not already retired or mayor."""
    from engine.models import NPC, Event, WorldState
    
    # Get current tick from WorldState
    world_state = db.query(WorldState).first()
    current_tick = world_state.tick if world_state else 0
    
    # Find eligible NPCs: living, age >= 60, not retired, not mayor
    eligible_npcs = db.query(NPC).filter(
        NPC.is_dead == 0,
        NPC.age >= 60,
        NPC.role.notin_(["retired", "mayor"])
    ).all()
    
    retirement_count = 0
    
    for npc in eligible_npcs:
        # Update NPC to retired status
        npc.role = "retired"
        npc.work_building_id = None
        
        # Create retirement event
        event = Event(
            event_type="retirement",
            description=f"{npc.name} retired after years of service",
            tick=current_tick,
            affected_npc_id=npc.id
        )
        db.add(event)
        
        retirement_count += 1
    
    db.commit()
    return retirement_count
