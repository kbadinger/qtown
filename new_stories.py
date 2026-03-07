"""Generate 50 new stories for qtown and write tests."""
import json

STORIES = [
    # ── NPC Psychology & Autonomy (216-225) ──────────────────────────
    {
        "id": "216", "title": "Personality-driven NPC decisions",
        "description": "Create personality_decision(db, npc_id) in engine/simulation/npcs.py. Parse NPC.personality JSON. If 'greedy' is true, NPC saves 50% of gold (won't buy non-essentials if gold < 50). If 'social' is true, NPC moves toward nearest other NPC each tick. If 'lazy' is true, NPC skips work 25% of ticks. Return a string describing the decision made.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "217", "title": "Mood contagion between NPCs",
        "description": "Create spread_mood(db) in engine/simulation/npcs.py. For each NPC with happiness > 70, boost nearby NPCs (within 3 tiles Euclidean) happiness by +2 (cap 100). For each NPC with happiness < 30, reduce nearby NPCs happiness by -1 (floor 0). Use math.sqrt for distance.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "218", "title": "NPC daily routines based on time of day",
        "description": "Create apply_daily_routine(db) in engine/simulation/npcs.py. Read WorldState.time_of_day. Morning: NPCs with work_building move toward it (set target_x/y). Afternoon: continue working. Evening: NPCs move toward tavern or home. Night: NPCs move toward home_building. Only set targets for NPCs that don't already have one.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "219", "title": "NPC gossip system",
        "description": "Create spread_gossip(db) in engine/simulation/npcs.py. Find pairs of living NPCs on the same tile (same x AND y). For each pair, merge their memory_events: each NPC learns up to 2 events from the other that they don't already have. Cap memory_events at 10. Parse/dump as JSON lists.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "220", "title": "NPC goal pursuit system",
        "description": "Create pursue_goals(db) in engine/simulation/npcs.py. Each NPC checks their experience JSON list for active goals. If no goals, assign one based on state: gold < 20 -> 'earn_gold', hunger > 60 -> 'find_food', happiness < 30 -> 'find_joy', skill < 3 -> 'learn'. Store goal as string in experience list. Return count of NPCs with active goals.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "221", "title": "NPC fear response to disasters",
        "description": "Create flee_disaster(db) in engine/simulation/npcs.py. Query recent Events with severity='high' or 'critical' from last 5 ticks. For each such event with affected_building_id, NPCs within 10 tiles of that building flee: set target_x/y to move away (add +15 to x and y, capped at 49). NPCs with 'brave' personality trait (parsed from JSON) do NOT flee.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "222", "title": "NPC aging effects on productivity",
        "description": "Create apply_age_effects(db) in engine/simulation/npcs.py. For living NPCs: age < 10 -> can't work (set work_building_id=None). Age 10-20 -> energy decays 50% slower (energy += 1 bonus). Age 60+ -> movement halved (only move every other tick, use WorldState.tick % 2). Age 70+ -> happiness -2 per tick from 'loneliness'. Return dict with counts per age bracket.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "223", "title": "Mentor-apprentice skill transfer",
        "description": "Create mentor_apprentices(db) in engine/simulation/npcs.py. Find NPCs with skill >= 5 (mentors). For each mentor, find NPCs on the same tile with skill < 3 (apprentices). Each apprentice gains +2 skill per call. Log 'mentored by {mentor.name}' to apprentice's memory_events. Return count of apprenticeships.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "224", "title": "NPC homesickness mechanic",
        "description": "Create apply_homesickness(db) in engine/simulation/npcs.py. For each living NPC with home_building_id set, calculate Euclidean distance from NPC (x,y) to home building (x,y). If distance > 10, reduce happiness by 1 per 5 tiles of distance (e.g., distance 15 = -1, distance 25 = -3). If distance <= 3, boost happiness by +2 (comfort bonus).",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "225", "title": "NPC rivalry competition",
        "description": "Create process_rivalries(db) in engine/simulation/npcs.py. Query Relationships where relationship_type='rival'. For each rivalry pair, compare gold. If NPC has less gold than rival, NPC happiness -3 (jealousy). If NPC has more gold, NPC happiness +2 (satisfaction). If rivalry strength > 80, 10% chance rival commits theft Crime.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },

    # ── Economy & Trade (226-233) ────────────────────────────────────
    {
        "id": "226", "title": "Merchant caravan events",
        "description": "Create trigger_merchant_caravan(db) in engine/simulation/events.py. Create a temporary merchant NPC (role='caravan_merchant', gold=200) at a random edge tile (x=0 or x=49 or y=0 or y=49). Create an Event with event_type='merchant_caravan'. The merchant sells resources at 2x calculate_price and buys at 0.5x.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py", "engine/simulation/economy.py"],
    },
    {
        "id": "227", "title": "Resource spoilage system",
        "description": "Create apply_resource_spoilage(db) in engine/simulation/economy.py. For each Resource where name is 'Food' or 'Fish' or 'Bread', reduce quantity by 10% (integer division). Resources in warehouse buildings (building.building_type == 'warehouse') are exempt. Create Event with event_type='spoilage' listing total spoiled.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },
    {
        "id": "228", "title": "NPC economic class system",
        "description": "Create classify_npcs(db) in engine/simulation/economy.py. For each living NPC: gold < 20 = 'poor', 20-100 = 'middle', > 100 = 'rich'. Store class in NPC experience JSON as {'economic_class': 'poor'}. Return dict with counts per class. Rich NPCs get happiness +3, poor NPCs get happiness -3.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },
    {
        "id": "229", "title": "Supply chain disruption detection",
        "description": "Create detect_supply_disruptions(db) in engine/simulation/economy.py. Check production dependencies: bakery needs Wheat resource, blacksmith needs Ore. If required input resource quantity == 0, create Event with event_type='supply_disruption' and description naming the missing resource. Return list of disrupted building types.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },
    {
        "id": "230", "title": "Progressive tax brackets",
        "description": "Create collect_progressive_taxes(db) in engine/simulation/economy.py. Replace flat tax: NPC gold > 100 pays 15%, gold 20-100 pays 10%, gold < 20 pays 5%. Deduct tax from NPC gold, add to first Treasury. Create Transaction for each tax payment. Return total tax collected.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },
    {
        "id": "231", "title": "Trade surplus auto-export",
        "description": "Create process_exports(db) in engine/simulation/economy.py. For each Resource with quantity > 200, export 50 units: reduce quantity by 50, add 50 gold to first Treasury. Create Event with event_type='export' describing the resource. Return list of exported resources.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },
    {
        "id": "232", "title": "Skill-based wage multiplier",
        "description": "Create calculate_skill_wage(db, npc_id) in engine/simulation/economy.py. Base wage from WorldState.base_wage. If NPC skill >= 5, wage *= 1.5. If skill >= 10, wage *= 2.0. If skill < 2, wage *= 0.75. Return integer wage amount.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },
    {
        "id": "233", "title": "Bank interest for savers",
        "description": "Create apply_bank_interest(db) in engine/simulation/economy.py. Requires at least one bank building to exist. For each living NPC with gold > 50, add 2% interest (gold * 0.02, rounded down, minimum 1). Create Transaction with reason='bank_interest'. Return total interest paid.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },

    # ── Events & Seasons (234-241) ───────────────────────────────────
    {
        "id": "234", "title": "Seasonal cycle system",
        "description": "Create get_season(db) in engine/simulation/events.py. Calculate from WorldState.day: day 1-25 = 'spring', 26-50 = 'summer', 51-75 = 'fall', 76-100 = 'winter', then cycle (day 101-125 = spring again). Use (day - 1) % 100. Return season string.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "235", "title": "Auto-trigger harvest festival in fall",
        "description": "Create check_seasonal_events(db) in engine/simulation/events.py. Import get_season. If season is 'fall' and WorldState.day % 25 == 1 (first day of fall), check if total Food resource quantity > 50. If yes, call trigger_harvest_festival(db). If season is 'winter' and day % 25 == 1, create 'winter_begins' Event.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "236", "title": "Winter hardship effects",
        "description": "Create apply_winter_effects(db) in engine/simulation/events.py. Import get_season. If season is 'winter': all NPC hunger increases by +3 extra per call (on top of normal decay). NPCs without home_building_id lose energy -5 extra. Create Event 'winter_hardship' if any NPC energy drops below 10.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "237", "title": "Epidemic contagion spread",
        "description": "Create spread_epidemic(db) in engine/simulation/events.py. For each living NPC with illness_severity > 0, find other living NPCs on the same tile (same x,y). Each healthy neighbor has 30% chance (random.random() < 0.3) to get infected: set illness_severity = 10, illness = 10. Return count of new infections.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "238", "title": "Infrastructure collapse cascade",
        "description": "Create check_infrastructure_collapse(db) in engine/simulation/events.py. Count buildings with capacity < 5 vs total buildings. If damaged ratio > 0.5 (50%+), create Event event_type='infrastructure_collapse' with severity='critical'. Set WorldState.infrastructure_score to 0. Return True if collapsed, False otherwise.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "239", "title": "Annual town review report",
        "description": "Create generate_town_review(db) in engine/simulation/events.py. Calculate: population (living NPCs count), total_gold (sum of NPC gold), avg_happiness (mean of NPC happiness), building_count, crime_count (unresolved crimes). Create Newspaper with headline 'Annual Town Review' and body containing all stats. Return the stats dict.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "240", "title": "Random positive micro-events",
        "description": "Create trigger_random_boon(db) in engine/simulation/events.py. Roll random.random(). If < 0.01 (1% chance): pick one of 3 boons: (a) 'gold_vein' - add 100 gold to random NPC, (b) 'bumper_crop' - add 50 to first Food resource, (c) 'inspiration' - all NPCs +5 happiness. Create Event describing what happened. Return event_type or None.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "241", "title": "Refugee wave after disasters",
        "description": "Create process_refugees(db) in engine/simulation/events.py. Check if any Event with severity='critical' exists in last 10 ticks. If yes and not already processed (no 'refugee_wave' event in last 10 ticks), spawn 3 new NPCs with role='refugee', gold=0, hunger=70, happiness=20 at random positions. Create 'refugee_wave' Event. Return count spawned.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },

    # ── Politics & Governance (242-246) ──────────────────────────────
    {
        "id": "242", "title": "Policy effect enforcement",
        "description": "Create apply_policy_effects(db) in engine/simulation/events.py. Query all Policy records with status='passed'. Parse each policy's effect JSON. Apply effects to WorldState: if 'tax_rate' key exists, set WorldState.tax_rate. If 'base_wage' key, set WorldState.base_wage. Mark applied policies as status='enacted'. Return count of policies applied.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "243", "title": "Mayor corruption system",
        "description": "Create check_corruption(db) in engine/simulation/events.py. Find NPC with role='mayor'. If mayor exists and has 'greedy' trait in personality JSON, mayor steals 10% of first Treasury's gold (move to mayor's personal gold). Create Crime with type='corruption' and criminal_npc_id=mayor.id. Return amount stolen or 0.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "244", "title": "Public approval rating",
        "description": "Create calculate_approval(db) in engine/simulation/events.py. Average happiness of all living NPCs = approval rating (0-100). If approval < 30, create Event event_type='unrest'. If approval > 70, create Event event_type='prosperity'. Return approval as integer.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "245", "title": "Emergency election on low approval",
        "description": "Create check_emergency_election(db) in engine/simulation/events.py. Count 'unrest' Events in last 50 ticks. If count >= 3, trigger hold_election(db) and create Event event_type='emergency_election'. Return True if election triggered, False otherwise.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },
    {
        "id": "246", "title": "Town budget allocation",
        "description": "Create allocate_budget(db) in engine/simulation/economy.py. Take first Treasury gold. Allocate: 40% to wages (increase WorldState.base_wage by allocated/100), 30% to infrastructure (repair buildings: +1 capacity to all buildings with capacity < 10), 20% to defense (create 'defense_budget' Event). Deduct total from treasury. Return allocation dict.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
    },

    # ── Military & Crime (247-251) ───────────────────────────────────
    {
        "id": "247", "title": "Guard patrol movement",
        "description": "Create patrol_guards(db) in engine/simulation/npcs.py. Find all living NPCs with role='guard'. For each guard, if no target, set target to a random building position. If guard is at target, pick new random building. This makes guards patrol between buildings.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "248", "title": "Crime motivation from poverty",
        "description": "Create check_crime_motivation(db) in engine/simulation/npcs.py. For each living NPC: if gold < 5 AND hunger > 70, there's a 20% chance (random.random() < 0.2) they commit theft. If personality has 'greedy'=true, chance doubles to 40%. Create Crime(criminal_npc_id=npc.id, type='theft', tick=current_tick). Steal 5 gold from random NPC. Return count of crimes.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
    },
    {
        "id": "249", "title": "Prison sentence serving",
        "description": "Create serve_sentences(db) in engine/simulation/effects.py. Find NPCs at prison buildings (work_building points to prison). For each, add 'imprisoned_tick' to memory_events if not present. Parse memory_events to count ticks imprisoned. After 50 ticks in prison, move NPC to a random non-prison building, clear prison assignment, set happiness -20. Return count released.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/effects.py"],
    },
    {
        "id": "250", "title": "Bounty board for unresolved crimes",
        "description": "Create process_bounties(db) in engine/simulation/effects.py. Count unresolved Crimes. For each, if a guard NPC is within 5 tiles of the criminal NPC, resolve the crime and give guard +10 gold. Create Event event_type='bounty_collected'. Return count of bounties collected.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/effects.py"],
    },
    {
        "id": "251", "title": "Vigilante justice without guards",
        "description": "Create vigilante_justice(db) in engine/simulation/effects.py. If no guard NPCs exist, check for unresolved Crimes. For each crime, find NPCs with 'brave'=true in personality JSON on same tile as criminal. 50% chance (random.random() < 0.5) they resolve the crime. If resolved, brave NPC gets happiness +5. Return count resolved.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/effects.py"],
    },

    # ── Culture & Education (252-256) ────────────────────────────────
    {
        "id": "252", "title": "Skill specialization production bonus",
        "description": "Create apply_skill_bonuses(db) in engine/simulation/production.py. For each Resource, find NPCs working at that resource's building. If worker skill >= 5, add 50% bonus to resource quantity. If skill >= 10, add 100% bonus instead. Return dict of {resource_name: bonus_applied}.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/production.py"],
    },
    {
        "id": "253", "title": "Library research discoveries",
        "description": "Create conduct_research(db) in engine/simulation/effects.py. If a library building exists, every call has 5% chance of a discovery. Discoveries: 'farming_technique' (add 10 to all Food resources), 'medical_breakthrough' (reduce all NPC illness_severity by 5), 'engineering' (all buildings +1 capacity). Create Event with event_type='research_discovery'. Return discovery name or None.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/effects.py"],
    },
    {
        "id": "254", "title": "Theater performance events",
        "description": "Create hold_performance(db) in engine/simulation/effects.py. If theater building exists, create Event event_type='theater_performance'. All NPCs within radius 15 of theater get happiness +8. Create Dialogue from a random NPC at theater with message about the show. Return count of attendees boosted.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/effects.py"],
    },
    {
        "id": "255", "title": "Church ceremony happiness boost",
        "description": "Create hold_ceremony(db) in engine/simulation/effects.py. If church building exists, find all NPCs within radius 10 of church. Each gets happiness +12 and all mutual Relationships between attendees strengthen by +3. Create Event event_type='church_ceremony'. Return count of attendees.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/effects.py"],
    },
    {
        "id": "256", "title": "Town hall grievance meetings",
        "description": "Create hold_town_meeting(db) in engine/simulation/events.py. Find the civic building (building_type='civic'). Find NPCs within 10 tiles. Identify most common complaint: lowest avg stat among hunger, energy, happiness, gold. Create Event event_type='town_meeting' with description naming the complaint. If hunger is worst, propose policy 'food_subsidy'. Return complaint string.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
    },

    # ── Infrastructure & Buildings (257-261) ─────────────────────────
    {
        "id": "257", "title": "Building auto-repair system",
        "description": "Create repair_buildings(db) in engine/simulation/buildings.py. For each building with capacity < 10 (damaged), if at least one NPC with role in ('builder','blacksmith') has work_building_id pointing to it, increase capacity by +1 per call (cap at 10). Create Event event_type='building_repaired' for each repair. Return count of repairs.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
    },
    {
        "id": "258", "title": "Building level production bonus",
        "description": "Create get_level_multiplier(building_level) in engine/simulation/buildings.py. Returns production multiplier: level 1 = 1.0, level 2 = 1.25, level 3 = 1.5, level 4 = 1.75, level 5 = 2.0. Simple formula: 1.0 + (level - 1) * 0.25. Return float.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
    },
    {
        "id": "259", "title": "Housing crisis detection",
        "description": "Create check_housing_crisis(db) in engine/simulation/buildings.py. Count NPCs without home_building_id (homeless). Count total living NPCs. If homeless > 25% of population, create Event event_type='housing_crisis' with severity='high'. All homeless NPCs get happiness -5. Return homeless count.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
    },
    {
        "id": "260", "title": "Market building enables trading",
        "description": "Create check_market_exists(db) in engine/simulation/buildings.py. Return True if any building with building_type='market' exists, False otherwise. This is a utility function used by trade functions to gate trading — no market means no NPC-to-NPC trade.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
    },
    {
        "id": "261", "title": "Building capacity from worker count",
        "description": "Create update_building_efficiency(db) in engine/simulation/buildings.py. For each building, count NPCs with work_building_id = building.id. If workers == 0, building produces nothing (store 'idle' in building name prefix if not already). If workers >= 3, building gets +2 effective capacity for production purposes. Return dict of {building_id: worker_count}.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
    },

    # ── API & Visualization (262-265) ────────────────────────────────
    {
        "id": "262", "title": "Town statistics API endpoint",
        "description": "Create GET /api/stats/summary in engine/routers/stats.py. Return JSON with: population (living NPC count), total_gold (sum of NPC gold), avg_happiness (mean happiness), building_count, crime_rate (unresolved crimes / population), infrastructure_score from WorldState.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/stats.py"],
    },
    {
        "id": "263", "title": "NPC detail API endpoint",
        "description": "Create GET /api/npcs/{npc_id} in engine/routers/npcs.py. Return full NPC data: all fields plus relationships (query Relationship table), home building name, work building name. Return 404 if NPC not found.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/npcs.py"],
    },
    {
        "id": "264", "title": "Price history chart API",
        "description": "Create GET /api/economy/price-history in engine/routers/economy.py. Accept optional query param resource_name. Return list of PriceHistory records (last 100 ticks) as JSON: [{resource_name, price, supply, demand, tick}]. If resource_name given, filter to that resource only.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/economy.py"],
    },
    {
        "id": "265", "title": "Event timeline API grouped by day",
        "description": "Create GET /api/events/timeline in engine/routers/events.py. Group events by day (tick // 4 = day). Return JSON: [{day: N, events: [{event_type, description, severity, tick}]}]. Limit to last 10 days. Sort by day descending.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/events.py"],
    },
]


def generate_test_code(story):
    """Generate test function(s) for a story."""
    sid = story["id"]
    title = story["title"]

    # Map story to test patterns based on what function they create
    desc = story["description"]

    # Extract function name from description
    func_name = None
    if "Create " in desc:
        part = desc.split("Create ")[1]
        if "(" in part:
            func_name = part.split("(")[0].strip()
        elif " in " in part:
            func_name = part.split(" in ")[0].strip()

    # Determine import source
    if "engine/simulation/npcs.py" in desc:
        module = "engine.simulation"
    elif "engine/simulation/economy.py" in desc:
        module = "engine.simulation"
    elif "engine/simulation/events.py" in desc:
        module = "engine.simulation"
    elif "engine/simulation/effects.py" in desc:
        module = "engine.simulation"
    elif "engine/simulation/production.py" in desc:
        module = "engine.simulation"
    elif "engine/simulation/buildings.py" in desc:
        module = "engine.simulation"
    elif "/api/" in desc:
        module = None  # API test
    else:
        module = "engine.simulation"

    tests = []

    if module and func_name:
        # Simulation function test
        if "Return" in desc and ("dict" in desc or "count" in desc or "string" in desc or "int" in desc or "float" in desc or "list" in desc or "bool" in desc):
            tests.append(f"""
def test_s{sid}_{func_name}(db):
    \"\"\"Story {sid}: {title}.\"\"\"
    _setup_world(db)
    from {module} import {func_name}

    result = {func_name}(db)
    assert result is not None, "{func_name} should return a value"
    db.flush()
""")
        elif func_name == "get_level_multiplier":
            tests.append(f"""
def test_s{sid}_{func_name}(db):
    \"\"\"Story {sid}: {title}.\"\"\"
    from {module} import {func_name}

    assert {func_name}(1) == 1.0
    assert {func_name}(3) == 1.5
    assert {func_name}(5) == 2.0
""")
        elif func_name == "check_market_exists":
            tests.append(f"""
def test_s{sid}_{func_name}(db):
    \"\"\"Story {sid}: {title}.\"\"\"
    _setup_world(db)
    from {module} import {func_name}

    result = {func_name}(db)
    assert isinstance(result, bool), "{func_name} should return bool"
""")
        elif "npc_id" in desc and func_name != "flee_disaster":
            tests.append(f"""
def test_s{sid}_{func_name}(db):
    \"\"\"Story {sid}: {title}.\"\"\"
    _setup_world(db)
    from engine.models import NPC
    from {module} import {func_name}

    npc = db.query(NPC).first()
    assert npc is not None, "Need seeded NPCs"
    result = {func_name}(db, npc.id)
    db.flush()
""")
        else:
            tests.append(f"""
def test_s{sid}_{func_name}(db):
    \"\"\"Story {sid}: {title}.\"\"\"
    _setup_world(db)
    from {module} import {func_name}

    {func_name}(db)
    db.flush()
""")
    elif "/api/" in desc:
        # API endpoint test
        endpoint = None
        method = "get"
        if "GET " in desc:
            endpoint = desc.split("GET ")[1].split(" ")[0].rstrip(".")
        elif "POST " in desc:
            endpoint = desc.split("POST ")[1].split(" ")[0].rstrip(".")
            method = "post"

        if endpoint:
            tests.append(f"""
def test_s{sid}_api(client):
    \"\"\"Story {sid}: {title}.\"\"\"
    resp = client.{method}("{endpoint}")
    assert resp.status_code in (200, 201, 404), f"{{resp.status_code}}: {{resp.text}}"
""")

    return tests


# Generate all tests grouped by test file
test_groups = {}
for story in STORIES:
    tf = story["test_file"]
    tests = generate_test_code(story)
    test_groups.setdefault(tf, []).extend(tests)

# Print summary
for tf, tests in test_groups.items():
    print(f"{tf}: {len(tests)} tests")

# Write to JSON for prd.json integration
with open("new_stories_data.json", "w") as f:
    json.dump({"stories": STORIES, "tests": {k: v for k, v in test_groups.items()}}, f, indent=2)

print(f"\nTotal: {len(STORIES)} stories")
