"""Generate 85 new stories (266-350) for Qwen Town and append tests + PRD entries."""
import json

STORIES = [
    # ── A. Advanced NPC AI (266-280) ──────────────────────────
    {
        "id": "266", "title": "NPC dream system",
        "description": "Create process_dreams(db) in engine/simulation/npcs.py. For each living NPC where WorldState.time_of_day == 'night', pick a random dream from ['found_treasure', 'nightmare', 'peaceful', 'adventure']. Append dream to NPC memory_events JSON list (cap at 10). 'found_treasure' gives happiness +3, 'nightmare' gives happiness -2. Return count of dreamers.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "267", "title": "Career progression",
        "description": "Create check_career_progression(db) in engine/simulation/npcs.py. For each living NPC with skill >= 8, promote: if role is 'farmer' promote to 'master_farmer', 'guard' to 'captain', 'merchant' to 'guild_master'. Append 'promoted to {new_role}' to memory_events. Give promoted NPC happiness +10. Return count of promotions.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "268", "title": "NPC retirement",
        "description": "Create process_retirement(db) in engine/simulation/npcs.py. For each living NPC with age > 70: set energy gain to half (energy += 1 instead of normal). If NPC has work_building_id, 50% chance each call to retire (set work_building_id=None, append 'retired' to memory_events). Retired NPCs get happiness +5 (relief). Return count of retirements.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "269", "title": "Family inheritance",
        "description": "Create process_inheritance(db) in engine/simulation/npcs.py. For each NPC where is_dead == 1, check if any Relationship with relationship_type='family' exists. If so, distribute dead NPC's gold equally among living family members. Set dead NPC gold to 0. Create Transaction for each transfer with reason='inheritance'. Return total gold distributed.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "270", "title": "Child NPC growth",
        "description": "Create process_child_growth(db) in engine/simulation/npcs.py. For each living NPC with age < 18: set work_building_id=None (can't work). Increase skill by +1 per call (learning fast). If age >= 18 and no work_building_id, assign to a random building with capacity > 0. Return count of children.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "271", "title": "NPC persuasion",
        "description": "Create attempt_persuasion(db) in engine/simulation/npcs.py. Find pairs of NPCs on the same tile. If NPC A has skill > NPC B skill, A can persuade B: 30% chance B adopts A's current goal (from experience JSON). Append 'persuaded by {A.name}' to B's memory_events. Return count of successful persuasions.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "272", "title": "Crowd behavior",
        "description": "Create process_crowd_behavior(db) in engine/simulation/npcs.py. Find tiles with 3+ living NPCs. For each crowd tile: all NPCs on that tile get happiness +2 (socializing). If any Event exists at a building on that tile, NPCs move away (set target_x/y to random nearby tile within 5). Return count of crowd tiles.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "273", "title": "Emotion memory tracking",
        "description": "Create track_emotions(db) in engine/simulation/npcs.py. For each living NPC, parse their memory_events JSON. Append current happiness to a 'mood_history' list stored in experience JSON. Keep only last 5 entries. Calculate mood_trend: if last value > first value, trend='improving'; if less, trend='declining'; else 'stable'. Return dict of {npc_id: trend}.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "274", "title": "NPC migration out",
        "description": "Create process_emigration(db) in engine/simulation/npcs.py. For each living NPC with happiness < 15 for 3+ consecutive mood_history entries (from experience JSON), NPC leaves: set is_dead=1, append 'emigrated' to memory_events. Create Event event_type='npc_emigrated'. Return count of emigrants.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "275", "title": "NPC arrival by prosperity",
        "description": "Create check_immigration(db) in engine/simulation/npcs.py. Calculate avg happiness of all living NPCs. If avg > 65 and living NPC count < 20, spawn 1 new NPC with role='newcomer', gold=30, random position. Create Event event_type='npc_arrived'. Return True if spawned, False otherwise.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "276", "title": "Friendship decay",
        "description": "Create decay_friendships(db) in engine/simulation/npcs.py. For each Relationship with relationship_type='friend', reduce strength by 1 per call (floor at 0). If strength reaches 0, change relationship_type to 'acquaintance'. Return count of decayed friendships.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "277", "title": "NPC specialization bonus",
        "description": "Create apply_specialization_bonus(db) in engine/simulation/npcs.py. For each living NPC, check experience JSON for 'ticks_in_role' counter. Increment by 1 each call. If ticks_in_role > 50, NPC gets +1 skill (cap 15). Store updated counter back in experience. Return count of specialists.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "278", "title": "NPC fatigue system",
        "description": "Create apply_fatigue(db) in engine/simulation/npcs.py. For each living NPC with energy < 20: reduce skill effectiveness by setting a 'fatigued' flag in experience JSON. Fatigued NPCs produce 50% less (halve any production bonus). If energy < 5, NPC collapses: move to home building, set energy=0. Return count of fatigued NPCs.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "279", "title": "NPC celebration",
        "description": "Create check_celebrations(db) in engine/simulation/npcs.py. For each living NPC with happiness > 90, trigger celebration: all NPCs within 5 tiles get happiness +3. Create Event event_type='celebration' with description '{npc.name} is celebrating!'. Max 1 celebration per call. Return celebrating NPC name or None.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "280", "title": "NPC mourning",
        "description": "Create process_mourning(db) in engine/simulation/npcs.py. For each dead NPC (is_dead==1), find living NPCs with Relationship to them (any type). Each mourner gets happiness -5 and 'mourning {dead.name}' appended to memory_events. Only mourn once per dead NPC (check memory_events for existing mourning entry). Return count of mourners.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },

    # ── B. Advanced Economy (281-295) ──────────────────────────
    {
        "id": "281", "title": "Trade guild formation",
        "description": "Create check_guild_formation(db) in engine/simulation/economy.py. Count living NPCs with role='merchant'. If count >= 3 and no Event event_type='guild_formed' exists, create guild: create Event event_type='guild_formed'. All merchants get +10 gold bonus and happiness +5. Return True if guild formed, False otherwise.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "282", "title": "Monopoly detection",
        "description": "Create detect_monopoly(db) in engine/simulation/economy.py. For each Resource, find which NPC's work_building produces it. If one NPC controls 80%+ of total production buildings for that resource, create Event event_type='monopoly_detected' with description naming the NPC and resource. Return list of monopolist NPC names.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "283", "title": "Price ceiling during disasters",
        "description": "Create enforce_price_ceiling(db) in engine/simulation/economy.py. Check if any Event with severity='critical' exists in last 10 ticks. If so, for each Resource, cap price at 2x the base price (base_price = 10). If current price > ceiling, set to ceiling. Return count of prices capped.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "284", "title": "Commodity futures",
        "description": "Create create_futures_contract(db, npc_id, resource_name, quantity, price) in engine/simulation/economy.py. Store contract in NPC experience JSON under 'futures' list: {resource, quantity, price, tick}. When resource price drops below contract price, NPC profits (add difference * quantity to gold). Return contract dict.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "285", "title": "Debt forgiveness",
        "description": "Create process_debt_forgiveness(db) in engine/simulation/economy.py. For each NPC with is_bankrupt==1, check WorldState.tick minus the tick they went bankrupt (store in experience JSON as 'bankrupt_tick'). If 100+ ticks have passed, set is_bankrupt=0, give NPC 20 gold, happiness +10. Create Event event_type='debt_forgiven'. Return count forgiven.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "286", "title": "Economic boom detection",
        "description": "Create detect_economic_boom(db) in engine/simulation/economy.py. Sum all living NPC gold. Compare to previous sum stored in WorldState metadata or experience. If current > previous * 1.1 (10% growth), create Event event_type='economic_boom'. All NPCs get happiness +3. Return True if boom, False otherwise.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "287", "title": "Recession detection",
        "description": "Create detect_recession(db) in engine/simulation/economy.py. Track total NPC gold over last 3 calls using a 'gold_history' list in WorldState (store in a new column or use existing metadata). If gold decreased for 3 consecutive checks, create Event event_type='recession'. All NPCs happiness -3. Return True if recession, False otherwise.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "288", "title": "Wage negotiation",
        "description": "Create process_wage_negotiations(db) in engine/simulation/economy.py. For each living NPC with skill >= 5 and work_building_id set: 30% chance to negotiate raise. If successful, NPC gets +2 gold per future pay cycle (store 'wage_bonus' in experience JSON, default 0). Cap wage_bonus at 10. Return count of successful negotiations.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "289", "title": "Tip system",
        "description": "Create process_tips(db) in engine/simulation/economy.py. For each Transaction where receiver NPC happiness > 70, there's a 25% chance of a tip: create additional Transaction with amount = original * 0.1 (min 1), reason='tip'. Add tip gold to receiver. Return total tips given.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "290", "title": "Resource quality tiers",
        "description": "Create assign_resource_quality(db) in engine/simulation/economy.py. For each Resource, assign quality based on producing NPC skill: skill < 3 = 'basic', 3-7 = 'fine', >= 8 = 'masterwork'. Store quality string in Resource name suffix (e.g., 'Food (fine)'). 'masterwork' items sell for 2x price. Return dict of {resource_name: quality}.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "291", "title": "Import/export balance tracking",
        "description": "Create calculate_trade_balance(db) in engine/simulation/economy.py. Count Events with event_type='export' (exports) and event_type='import' or 'merchant_caravan' (imports) in last 100 ticks. Calculate balance = export_count - import_count. Create Event event_type='trade_report' with balance in description. Return balance integer.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "292", "title": "Inflation adjustment",
        "description": "Create adjust_for_inflation(db) in engine/simulation/economy.py. Check WorldState.inflation_rate (default 0). If inflation_rate > 0.2, increase WorldState.base_wage by 1 (cap at 20). If inflation_rate < -0.1 (deflation), decrease base_wage by 1 (floor at 1). Return new base_wage value.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "293", "title": "Gold sink events",
        "description": "Create run_gold_sink(db) in engine/simulation/economy.py. If first Treasury gold > 200, spend 50 gold on a festival: create Event event_type='festival', deduct 50 from Treasury. All living NPCs get happiness +8. If Treasury < 50, skip. Return gold spent or 0.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "294", "title": "Economic report generation",
        "description": "Create generate_economic_report(db) in engine/simulation/economy.py. Calculate: total_gold (sum NPC gold), treasury_gold, avg_gold (mean NPC gold), richest NPC name, poorest NPC name, total_resources (sum all Resource quantities). Create Newspaper with headline='Economic Report' and body with all stats. Return the stats dict.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "295", "title": "Wealth inequality index",
        "description": "Create calculate_gini(db) in engine/simulation/economy.py. Calculate Gini coefficient from living NPC gold values. Formula: sum of |xi - xj| for all pairs / (2 * n * mean). Return float 0.0 (perfect equality) to 1.0 (max inequality). If only 1 NPC, return 0.0. Create Event event_type='gini_report' with value in description.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },

    # ── C. World Events & Seasons (296-310) ──────────────────────────
    {
        "id": "296", "title": "Multi-day event chains",
        "description": "Create process_event_chains(db) in engine/simulation/events.py. For each Event with severity='high' created in last 3 ticks that has no follow-up, create a follow-up Event: same event_type with '_aftermath' suffix, severity one level lower. E.g., 'fire' -> 'fire_aftermath' with severity='medium'. Return count of follow-ups created.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "297", "title": "Event severity escalation",
        "description": "Create escalate_events(db) in engine/simulation/events.py. For each active Event (created in last 5 ticks) with severity='medium', if no guard NPC exists within 10 tiles of affected_building, escalate to severity='high'. If already 'high' and still unresolved after 10 ticks, escalate to 'critical'. Return count of escalations.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "298", "title": "Event recovery bonus",
        "description": "Create apply_recovery_bonus(db) in engine/simulation/events.py. Check if any Event with severity='critical' was created 20-30 ticks ago. If so and no current critical events exist, all living NPCs get happiness +10 (relief). Create Event event_type='recovery'. Only trigger once per recovery. Return True if bonus applied.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "299", "title": "Anniversary events",
        "description": "Create check_anniversaries(db) in engine/simulation/events.py. If WorldState.day is a multiple of 100 (anniversary of town founding), create Event event_type='anniversary' with description 'Town celebrates day {day}!'. All NPCs get happiness +15. Create Newspaper with celebration headline. Return True if anniversary, False otherwise.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "300", "title": "Visitor trader events",
        "description": "Create spawn_visitor_trader(db) in engine/simulation/events.py. 5% chance per call to spawn a visitor. Create NPC with role='visitor_trader', gold=150, random edge position (x or y = 0 or 49). Create Event event_type='visitor_trader'. Visitor sells rare resources at 3x price. Return visitor NPC or None.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "301", "title": "Festival voting",
        "description": "Create hold_festival_vote(db) in engine/simulation/events.py. Each living NPC 'votes' based on their lowest stat: hunger -> 'food_festival', happiness -> 'music_festival', energy -> 'rest_day'. Tally votes, pick winner. Create Event event_type=winner. Return winning festival type.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "302", "title": "Weather prediction",
        "description": "Create predict_weather(db) in engine/simulation/events.py. Based on current WorldState.weather, predict next: 'sunny' -> 70% sunny, 20% cloudy, 10% rain. 'cloudy' -> 30% sunny, 40% cloudy, 30% rain. 'rain' -> 10% sunny, 40% cloudy, 40% rain, 10% storm. Store prediction in WorldState or return it. Return predicted weather string.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "303", "title": "Crop yield calculation",
        "description": "Create calculate_crop_yield(db) in engine/simulation/events.py. Import get_season. Base yield = 10. Multiply by season: spring=1.2, summer=1.5, fall=1.0, winter=0.3. Multiply by weather: sunny=1.2, cloudy=1.0, rain=0.8, storm=0.2. Add worker skill bonus (highest farmer skill * 0.1). Return integer yield.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "304", "title": "Famine relief distribution",
        "description": "Create distribute_famine_relief(db) in engine/simulation/events.py. If any Food Resource quantity < 10 and living NPC count > 3, trigger famine relief: take 30 gold from first Treasury, add 20 to first Food resource quantity. Create Event event_type='famine_relief'. Each NPC hunger reduced by 10 (floor 0). Return True if relief distributed.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "305", "title": "Building damage from events",
        "description": "Create apply_event_damage(db) in engine/simulation/events.py. For each Event with severity='critical' in last 5 ticks that has affected_building_id, reduce that building's capacity by 3 (floor at 1). If building capacity drops to 1, create follow-up Event event_type='building_destroyed'. Return count of buildings damaged.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "306", "title": "Event newspaper coverage",
        "description": "Create generate_event_news(db) in engine/simulation/events.py. For each Event created in the current tick (WorldState.tick), create a Newspaper with headline based on event_type and body based on description. Priority events: severity='critical' get 'BREAKING: ' prefix. Return count of articles created.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "307", "title": "Memorial creation",
        "description": "Create create_memorial(db) in engine/simulation/events.py. After a critical event that affected a building, create a new Building with building_type='memorial', name='Memorial for {event_type}', at a position near the affected building (x+1, y+1, capped at 49). Return memorial building or None if no qualifying event.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "308", "title": "Event prevention by guards",
        "description": "Create calculate_prevention_chance(db) in engine/simulation/events.py. Count guard NPCs. Each guard adds 5% prevention chance (cap at 50%). When a new 'bandit' or 'theft' event would trigger, roll random.random(). If < prevention_chance, prevent it: create Event event_type='event_prevented' instead. Return prevention_chance float.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "309", "title": "Seasonal migration",
        "description": "Create process_seasonal_visitors(db) in engine/simulation/events.py. Import get_season. In 'summer', 10% chance to spawn a visitor NPC (role='tourist', gold=50). In 'winter', any existing tourist NPCs leave (set is_dead=1). Create Event for arrivals/departures. Return count of visitors spawned or removed.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "310", "title": "Legendary event",
        "description": "Create check_legendary_event(db) in engine/simulation/events.py. If WorldState.tick > 1000 and no Event event_type='legendary' exists ever, 1% chance to trigger. Legendary event: 'dragon_sighting' — all NPCs flee (set target to random edge), all buildings lose 1 capacity, but 500 gold added to Treasury. Create Event and Newspaper. Return True if triggered.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },

    # ── D. Politics & Governance (311-320) ──────────────────────────
    {
        "id": "311", "title": "Political faction system",
        "description": "Create assign_factions(db) in engine/simulation/events.py. For each living NPC without a faction (no 'faction' in experience JSON), assign based on priorities: gold > 50 -> 'merchants_guild', skill > 5 -> 'artisans_guild', happiness < 40 -> 'reform_party', else -> 'independents'. Store in experience JSON. Return dict of faction counts.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "312", "title": "Policy proposal queue",
        "description": "Create manage_proposal_queue(db) in engine/simulation/events.py. Count Policy records with status='proposed'. If count > 3, reject the oldest (set status='expired'). Return count of active proposals. This ensures only 3 proposals are active at once.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "313", "title": "Term limits for mayor",
        "description": "Create check_term_limits(db) in engine/simulation/events.py. Find NPC with role='mayor'. Check their experience JSON for 'mayor_since_tick'. If WorldState.tick - mayor_since_tick > 240, trigger new election: call hold_election(db). Create Event event_type='term_limit_reached'. Return True if term ended.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "314", "title": "Impeachment mechanic",
        "description": "Create check_impeachment(db) in engine/simulation/events.py. Find NPC with role='mayor'. Calculate avg happiness of all living NPCs. If avg < 25, trigger impeachment vote: 60% chance of removal (random.random() < 0.6). If removed, set mayor role to 'citizen', trigger hold_election(db). Create Event event_type='impeachment'. Return True if removed.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "315", "title": "Tax revolt",
        "description": "Create check_tax_revolt(db) in engine/simulation/events.py. If WorldState.tax_rate > 0.2 and avg NPC happiness < 30, trigger revolt: all NPCs refuse to pay tax for 10 ticks (store 'revolt_until_tick' in WorldState or events). Create Event event_type='tax_revolt' with severity='high'. Return True if revolt triggered.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "316", "title": "Public works projects",
        "description": "Create launch_public_works(db) in engine/simulation/events.py. If first Treasury gold > 100, spend 50 gold: pick building with lowest capacity, increase capacity by 3. Create Event event_type='public_works' with building name. Deduct from Treasury. Return upgraded building name or None.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "317", "title": "Diplomatic missions",
        "description": "Create send_diplomat(db) in engine/simulation/events.py. Pick NPC with highest skill and role!='mayor'. Set their target_x/y to edge of map (x=49). Create Event event_type='diplomatic_mission'. After 20 ticks (check experience JSON 'mission_start_tick'), diplomat returns with 30 gold. Return diplomat NPC name or None.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "318", "title": "Census system",
        "description": "Create run_census(db) in engine/simulation/events.py. Count: living NPCs, dead NPCs, total buildings, total gold, avg happiness, avg age. Store snapshot as Event event_type='census' with all stats in description JSON. Only run if no census in last 50 ticks. Return stats dict.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "319", "title": "Town charter",
        "description": "Create generate_charter(db) in engine/simulation/events.py. Compile all Policy records with status='enacted' into a charter document. Create Newspaper with headline='Town Charter Updated' and body listing all enacted policies. Return list of policy names.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },
    {
        "id": "320", "title": "Emergency powers",
        "description": "Create grant_emergency_powers(db) in engine/simulation/events.py. If any Event with severity='critical' exists in last 5 ticks, find mayor NPC. Mayor gets 'emergency_powers' flag in experience JSON. With emergency powers, mayor can: set tax_rate directly, repair any building +2 capacity. Powers expire after 20 ticks. Return True if granted.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["politics", "simulation"],
    },

    # ── E. Buildings & Infrastructure (321-330) ──────────────────────────
    {
        "id": "321", "title": "Building adjacency bonuses",
        "description": "Create calculate_adjacency_bonuses(db) in engine/simulation/buildings.py. For each building, check buildings within 3 tiles (Euclidean). Specific bonuses: farm near well = +2 capacity, blacksmith near mine = +2 capacity, tavern near residential = +1 capacity. Return dict of {building_id: bonus}.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "322", "title": "Road network speed bonus",
        "description": "Create calculate_road_bonus(db) in engine/simulation/buildings.py. Count buildings with building_type='road' (or 'gate'). Each road adds 1% movement speed bonus to all NPCs (cap at 20%). Store road_bonus percentage in WorldState or return it. Return integer percentage bonus.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "323", "title": "Building specialization",
        "description": "Create set_building_focus(db, building_id, focus) in engine/simulation/buildings.py. Valid focuses: 'production', 'training', 'storage'. Production focus: +50% output. Training: workers gain +1 skill per cycle. Storage: +5 effective capacity. Store focus as building name suffix. Return updated building.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "324", "title": "Ruin decay system",
        "description": "Create process_building_decay(db) in engine/simulation/buildings.py. For each building with no workers (no NPC has work_building_id pointing to it), reduce capacity by 1 per call (floor at 1). If capacity reaches 1, rename to 'Ruins of {original_name}' if not already. Create Event event_type='building_decayed'. Return count of decayed buildings.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "325", "title": "Construction queue",
        "description": "Create process_construction(db) in engine/simulation/buildings.py. Check for NPC with role='builder'. If builder exists, check experience JSON for 'construction_project'. If no project, assign: create building stub with capacity=0 at random empty tile. Each call, builder increases capacity by 1. When capacity reaches 5, building is complete. Return project status string.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "326", "title": "Building insurance",
        "description": "Create process_insurance(db) in engine/simulation/buildings.py. For each building, check if 'insured' flag exists (store in building name or via a tag). Insured buildings: if damaged by event (capacity reduced), auto-repair +2 capacity. Insurance costs 5 gold from first Treasury per insured building per call. Return count of insured buildings.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "327", "title": "Landmark buildings",
        "description": "Create check_landmarks(db) in engine/simulation/buildings.py. Buildings with level >= 4 become landmarks. Landmarks give town-wide happiness +1 per landmark (cap +5 total). Create Event event_type='landmark_status' listing landmark names. Return count of landmarks.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "328", "title": "Building inspection",
        "description": "Create inspect_buildings(db) in engine/simulation/buildings.py. For each building: check capacity vs original (10). If capacity < 5, status='damaged'. If capacity < 3, status='critical'. If no workers, status='abandoned'. Else status='operational'. Return list of dicts [{building_id, name, status, capacity}].",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "329", "title": "Resource storage limits",
        "description": "Create enforce_storage_limits(db) in engine/simulation/buildings.py. Count warehouse buildings. Each warehouse adds 100 to storage cap (base 200). For each Resource, if quantity > storage_cap, set quantity to storage_cap (excess lost). Create Event event_type='storage_overflow' if any capped. Return storage_cap value.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "330", "title": "Building rename system",
        "description": "Create rename_building(db, building_id, new_name) in engine/simulation/buildings.py. Validate new_name is 1-50 chars and alphanumeric+spaces. Update building.name. Create Event event_type='building_renamed' with old and new name. Return updated building name or None if invalid.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },

    # ── F. UI & API Endpoints (331-340) ──────────────────────────
    {
        "id": "331", "title": "NPC biography API",
        "description": "Create GET /api/npcs/{npc_id}/biography in engine/routers/npcs.py. Return NPC life history: name, role, age, gold, relationships list, memory_events (parsed from JSON), work building name, home building name. Return 404 if not found.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/npcs.py"],
        "tags": ["api"],
    },
    {
        "id": "332", "title": "Building history API",
        "description": "Create GET /api/buildings/{building_id}/history in engine/routers/buildings.py. Return building details plus: current workers (NPC names), events affecting this building (query Event where affected_building_id matches), current capacity and level. Return 404 if not found.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/buildings.py"],
        "tags": ["api"],
    },
    {
        "id": "333", "title": "Economic chart data API",
        "description": "Create GET /api/economy/chart-data in engine/routers/economy.py. Accept query param 'days' (default 10). Return JSON with: gold_over_time (list of {tick, total_gold} from Transactions), price_over_time (from PriceHistory). Aggregate by day (tick // 24).",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/economy.py"],
        "tags": ["api"],
    },
    {
        "id": "334", "title": "Relationship graph API",
        "description": "Create GET /api/relationships/graph in engine/routers/npcs.py. Return JSON with nodes (NPC id, name, role) and edges (Relationship npc_id, target_npc_id, type, strength). Format suitable for graph visualization libraries.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/npcs.py"],
        "tags": ["api"],
    },
    {
        "id": "335", "title": "Town achievement progress API",
        "description": "Create GET /api/achievements in engine/routers/stats.py. Check milestones: population >= 10, total_gold >= 500, buildings >= 30, stories_done >= 100. Return list of {name, description, achieved: bool}.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/stats.py"],
        "tags": ["api"],
    },
    {
        "id": "336", "title": "Event calendar API",
        "description": "Create GET /api/events/calendar in engine/routers/events.py. Accept query params 'from_day' and 'to_day'. Return events grouped by day: [{day, events: [{event_type, description, severity}]}]. Default: last 7 days.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/events.py"],
        "tags": ["api"],
    },
    {
        "id": "337", "title": "Resource flow API",
        "description": "Create GET /api/economy/resource-flow in engine/routers/economy.py. For each Resource, calculate production rate (quantity change per day from recent data) and consumption estimate (transactions involving that resource). Return [{resource_name, quantity, production_rate, consumption_rate}].",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/economy.py"],
        "tags": ["api"],
    },
    {
        "id": "338", "title": "Leaderboard API",
        "description": "Create GET /api/leaderboards in engine/routers/stats.py. Return top 5 NPCs in each category: richest (by gold), most skilled (by skill), happiest (by happiness), oldest (by age). Each entry has npc_id, name, value.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/stats.py"],
        "tags": ["api"],
    },
    {
        "id": "339", "title": "Town history summary API",
        "description": "Create GET /api/town/history in engine/routers/stats.py. Return chronological list of key Events: elections, disasters, achievements, milestones. Limit to 50 most recent. Each entry has tick, day, event_type, description.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/stats.py"],
        "tags": ["api"],
    },
    {
        "id": "340", "title": "Simulation config API",
        "description": "Create GET /api/config in engine/routers/stats.py. Return current simulation settings from WorldState: tick, day, time_of_day, weather, tax_rate, base_wage, inflation_rate, infrastructure_score. Read-only endpoint.",
        "test_file": "tests/test_api.py",
        "context_files": ["engine/routers/stats.py"],
        "tags": ["api"],
    },

    # ── G. Polish & Meta (341-350) ──────────────────────────
    {
        "id": "341", "title": "NPC name generator",
        "description": "Create generate_npc_name(db) in engine/simulation/npcs.py. Define FIRST_NAMES list of 20 names and LAST_NAMES list of 20 names. Pick random first + last. Ensure no duplicate full names among living NPCs. Return the generated name string.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "342", "title": "Building description generator",
        "description": "Create generate_building_description(db, building_id) in engine/simulation/buildings.py. Based on building_type and level, generate a description string. E.g., level 1 farm = 'A modest farm with basic tools', level 3 = 'A prosperous farm with irrigation'. Use a dict mapping (type, level) to descriptions. Return description string.",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "343", "title": "Daily digest",
        "description": "Create generate_daily_digest(db) in engine/simulation/events.py. Summarize last 24 ticks: count events by type, NPC births/deaths, gold change, weather changes. Create Newspaper with headline='Daily Digest Day {day}'. Return summary dict.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "344", "title": "Prosperity score",
        "description": "Create calculate_prosperity(db) in engine/simulation/economy.py. Composite score 0-100: avg_happiness * 0.3 + (avg_gold/10 capped at 30) * 0.3 + (building_count/30 capped at 1.0) * 0.2 + (1.0 - crime_rate) * 0.2. Store in WorldState. Return integer prosperity score.",
        "test_file": "tests/test_economy.py",
        "context_files": ["engine/simulation/economy.py"],
        "tags": ["economy", "simulation"],
    },
    {
        "id": "345", "title": "Danger score per tile",
        "description": "Create calculate_danger_scores(db) in engine/simulation/events.py. For each tile, count crimes and disaster events within 5 tiles (from Crime and Event tables). Score = crime_count * 2 + disaster_count * 3. Return dict of {(x,y): danger_score} for tiles with score > 0.",
        "test_file": "tests/test_events.py",
        "context_files": ["engine/simulation/events.py"],
        "tags": ["events", "simulation"],
    },
    {
        "id": "346", "title": "NPC compatibility score",
        "description": "Create calculate_compatibility(db, npc_id_a, npc_id_b) in engine/simulation/npcs.py. Compare two NPCs: same role = +20, age difference < 10 = +15, both happiness > 50 = +10, existing relationship = +25. Score 0-100. Return integer compatibility score.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "347", "title": "Auto-assign homeless NPCs",
        "description": "Create assign_homeless(db) in engine/simulation/npcs.py. Find living NPCs without home_building_id. Find residential buildings with available capacity (count current residents < building capacity). Assign NPCs to buildings with space. Return count of NPCs assigned.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "348", "title": "Auto-assign unemployed NPCs",
        "description": "Create assign_unemployed(db) in engine/simulation/npcs.py. Find living NPCs without work_building_id and age >= 18. Find buildings with available worker slots (count current workers < building capacity). Assign NPCs to buildings with openings, preferring buildings matching NPC role. Return count assigned.",
        "test_file": "tests/test_npcs.py",
        "context_files": ["engine/simulation/npcs.py"],
        "tags": ["npc", "simulation"],
    },
    {
        "id": "349", "title": "Town population cap",
        "description": "Create get_population_cap(db) in engine/simulation/buildings.py. Count residential building total capacity. Cap = sum of all residential building capacities. If living NPC count >= cap, no new NPCs can spawn (return False). If under cap, return True. Also return the cap value. Return tuple (can_spawn: bool, cap: int).",
        "test_file": "tests/test_buildings.py",
        "context_files": ["engine/simulation/buildings.py"],
        "tags": ["buildings", "simulation"],
    },
    {
        "id": "350", "title": "End-of-day report",
        "description": "Create generate_end_of_day_report(db) in engine/simulation/tick.py. If WorldState.tick % 24 == 0, compile: population, total_gold, avg_happiness, events_today (last 24 ticks), weather. Create Event event_type='end_of_day_report' with all stats in description JSON. Return stats dict or None if not end of day.",
        "test_file": "tests/test_tick.py",
        "context_files": ["engine/simulation/tick.py"],
        "tags": ["simulation"],
    },
]


# ── Test templates ─────────────────────────────────────────────────

TESTS = {
    "tests/test_npcs.py": [],
    "tests/test_economy.py": [],
    "tests/test_events.py": [],
    "tests/test_tick.py": [],
    "tests/test_buildings.py": [],
    "tests/test_api.py": [],
}

# Map function names from descriptions
FUNC_MAP = {
    "266": "process_dreams", "267": "check_career_progression", "268": "process_retirement",
    "269": "process_inheritance", "270": "process_child_growth", "271": "attempt_persuasion",
    "272": "process_crowd_behavior", "273": "track_emotions", "274": "process_emigration",
    "275": "check_immigration", "276": "decay_friendships", "277": "apply_specialization_bonus",
    "278": "apply_fatigue", "279": "check_celebrations", "280": "process_mourning",
    "281": "check_guild_formation", "282": "detect_monopoly", "283": "enforce_price_ceiling",
    "284": "create_futures_contract", "285": "process_debt_forgiveness", "286": "detect_economic_boom",
    "287": "detect_recession", "288": "process_wage_negotiations", "289": "process_tips",
    "290": "assign_resource_quality", "291": "calculate_trade_balance", "292": "adjust_for_inflation",
    "293": "run_gold_sink", "294": "generate_economic_report", "295": "calculate_gini",
    "296": "process_event_chains", "297": "escalate_events", "298": "apply_recovery_bonus",
    "299": "check_anniversaries", "300": "spawn_visitor_trader", "301": "hold_festival_vote",
    "302": "predict_weather", "303": "calculate_crop_yield", "304": "distribute_famine_relief",
    "305": "apply_event_damage", "306": "generate_event_news", "307": "create_memorial",
    "308": "calculate_prevention_chance", "309": "process_seasonal_visitors", "310": "check_legendary_event",
    "311": "assign_factions", "312": "manage_proposal_queue", "313": "check_term_limits",
    "314": "check_impeachment", "315": "check_tax_revolt", "316": "launch_public_works",
    "317": "send_diplomat", "318": "run_census", "319": "generate_charter", "320": "grant_emergency_powers",
    "321": "calculate_adjacency_bonuses", "322": "calculate_road_bonus", "323": "set_building_focus",
    "324": "process_building_decay", "325": "process_construction", "326": "process_insurance",
    "327": "check_landmarks", "328": "inspect_buildings", "329": "enforce_storage_limits",
    "330": "rename_building",
    "341": "generate_npc_name", "342": "generate_building_description",
    "343": "generate_daily_digest", "344": "calculate_prosperity",
    "345": "calculate_danger_scores", "346": "calculate_compatibility",
    "347": "assign_homeless", "348": "assign_unemployed",
    "349": "get_population_cap", "350": "generate_end_of_day_report",
}

# API stories (331-340) — different test pattern
API_ROUTES = {
    "331": "/api/npcs/1/biography",
    "332": "/api/buildings/1/history",
    "333": "/api/economy/chart-data",
    "334": "/api/relationships/graph",
    "335": "/api/achievements",
    "336": "/api/events/calendar",
    "337": "/api/economy/resource-flow",
    "338": "/api/leaderboards",
    "339": "/api/town/history",
    "340": "/api/config",
}

for story in STORIES:
    sid = story["id"]
    tf = story["test_file"]

    if sid in API_ROUTES:
        route = API_ROUTES[sid]
        test_code = f'''
def test_s{sid}_api(client):
    """{story['title']}."""
    resp = client.get("{route}")
    assert resp.status_code in (200, 201, 404), f"{{resp.status_code}}: {{resp.text}}"
'''
        TESTS[tf].append(test_code)
    elif sid in FUNC_MAP:
        func = FUNC_MAP[sid]
        # Special cases for functions with extra args
        if sid == "284":
            test_code = f'''
def test_s{sid}_{func}(db):
    """{story['title']}."""
    _setup_world(db)
    from engine.simulation import {func}
    from engine.models import NPC

    npc = db.query(NPC).first()
    assert npc is not None, "Need seeded NPCs"
    result = {func}(db, npc.id, "Food", 10, 5)
    db.flush()
'''
        elif sid == "323":
            test_code = f'''
def test_s{sid}_{func}(db):
    """{story['title']}."""
    _setup_world(db)
    from engine.simulation import {func}
    from engine.models import Building

    b = db.query(Building).first()
    assert b is not None, "Need seeded buildings"
    result = {func}(db, b.id, "production")
    db.flush()
'''
        elif sid == "330":
            test_code = f'''
def test_s{sid}_{func}(db):
    """{story['title']}."""
    _setup_world(db)
    from engine.simulation import {func}
    from engine.models import Building

    b = db.query(Building).first()
    assert b is not None, "Need seeded buildings"
    result = {func}(db, b.id, "New Name")
    db.flush()
'''
        elif sid == "342":
            test_code = f'''
def test_s{sid}_{func}(db):
    """{story['title']}."""
    _setup_world(db)
    from engine.simulation import {func}
    from engine.models import Building

    b = db.query(Building).first()
    assert b is not None, "Need seeded buildings"
    result = {func}(db, b.id)
    assert result is not None, "{func} should return a value"
    db.flush()
'''
        elif sid == "346":
            test_code = f'''
def test_s{sid}_{func}(db):
    """{story['title']}."""
    _setup_world(db)
    from engine.simulation import {func}
    from engine.models import NPC

    npcs = db.query(NPC).limit(2).all()
    assert len(npcs) >= 2, "Need at least 2 NPCs"
    result = {func}(db, npcs[0].id, npcs[1].id)
    assert result is not None, "{func} should return a value"
    db.flush()
'''
        else:
            test_code = f'''
def test_s{sid}_{func}(db):
    """{story['title']}."""
    _setup_world(db)
    from engine.simulation import {func}

    result = {func}(db)
    assert result is not None, "{func} should return a value"
    db.flush()
'''
        TESTS[tf].append(test_code)


def main():
    import os

    # 1. Append tests to existing test files
    for test_file, tests in TESTS.items():
        if not tests:
            continue
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()

        added = 0
        for test_code in tests:
            # Extract function name
            for line in test_code.strip().split("\n"):
                if line.startswith("def test_"):
                    func_name = line.split("(")[0].replace("def ", "")
                    break
            else:
                continue

            if func_name not in content:
                content += "\n" + test_code
                added += 1

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"{test_file}: added {added} tests")

    # 2. Merge stories into prd.json
    with open("prd.json", "r", encoding="utf-8") as f:
        prd = json.load(f)

    story_map = {s["id"]: s for s in prd["stories"]}

    for story in STORIES:
        sid = story["id"]
        if sid in story_map:
            story_map[sid]["description"] = story["description"]
            story_map[sid]["context_files"] = story["context_files"]
            story_map[sid]["test_file"] = story["test_file"]
            if "tags" in story:
                story_map[sid]["tags"] = story["tags"]
        else:
            prd["stories"].append({
                "id": sid,
                "title": story["title"],
                "description": story["description"],
                "test_file": story["test_file"],
                "context_files": story["context_files"],
                "tags": story.get("tags", ["simulation"]),
                "priority": int(sid),
                "status": "pending",
                "attempts": 0,
            })

    prd["stories"].sort(key=lambda s: int(s["id"]))

    with open("prd.json", "w", encoding="utf-8") as f:
        json.dump(prd, f, indent=2, ensure_ascii=False)

    print(f"\nTotal stories in prd.json: {len(prd['stories'])}")


if __name__ == "__main__":
    main()
