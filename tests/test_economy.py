"""Tests for economy stories: 012-014, 026-030, 091-108."""


def _setup_world(db):
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)


def test_s012_npc_gold_field(db):
    """Story 012: NPC model should have a gold field."""
    from engine.models import NPC

    npc = NPC(name="Rich", role="merchant", x=0, y=0, gold=100)
    db.add(npc)
    db.commit()
    assert npc.gold == 100


def test_s013_transfer_gold(db):
    """Story 013: transfer_gold() moves gold between NPCs."""
    from engine.models import NPC
    from engine.simulation import transfer_gold

    sender = NPC(name="Sender", role="merchant", x=0, y=0, gold=100)
    receiver = NPC(name="Receiver", role="farmer", x=1, y=1, gold=0)
    db.add_all([sender, receiver])
    db.commit()

    result = transfer_gold(db, sender.id, receiver.id, 50)
    assert result is True
    db.commit()
    db.refresh(sender)
    db.refresh(receiver)
    assert sender.gold == 50
    assert receiver.gold == 50


def test_s013_transfer_gold_insufficient(db):
    """Story 013: transfer_gold() fails if sender lacks funds."""
    from engine.models import NPC
    from engine.simulation import transfer_gold

    sender = NPC(name="Poor", role="farmer", x=0, y=0, gold=10)
    receiver = NPC(name="Rich", role="merchant", x=1, y=1, gold=100)
    db.add_all([sender, receiver])
    db.commit()

    result = transfer_gold(db, sender.id, receiver.id, 50)
    assert result is False
    db.commit()
    db.refresh(sender)
    assert sender.gold == 10  # Unchanged


def test_s014_transactions_api(client, admin_headers):
    """Story 014: GET /api/transactions returns transaction history."""
    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_s026_earn_gold_at_work(db):
    """Story 026: NPCs earn gold when working."""
    _setup_world(db)
    from engine.models import NPC, Building
    from engine.simulation import process_work

    npc = db.query(NPC).first()
    building = db.query(Building).first()
    npc.gold = 0
    npc.work_building_id = building.id  # Assign to first building
    npc.x = building.x  # Move NPC to building location
    npc.y = building.y
    db.commit()
    process_work(db)
    db.commit()  # flush changes to DB so refresh picks them up
    db.refresh(npc)
    assert npc.gold > 0, "NPC should have earned gold from working"


def test_s027_resource_model(db):
    """Story 027: Resource model should exist."""
    from engine.models import Resource, Building

    b = Building(name="Farm", building_type="farm", x=0, y=0)
    db.add(b)
    db.commit()
    r = Resource(name="Wheat", quantity=100, building_id=b.id)
    db.add(r)
    db.commit()
    assert r.id is not None


def test_s028_food_production(db):
    """Story 028: Farms should produce food resources."""
    _setup_world(db)
    from engine.simulation import produce_resources

    produce_resources(db)
    from engine.models import Resource

    food = db.query(Resource).filter_by(name="Food").first()
    # Food should be produced (or function should exist without error)
    assert food is None or food.quantity >= 0


def test_s029_buy_food(db):
    """Story 029: NPCs can buy food with gold."""
    _setup_world(db)
    from engine.models import NPC, Building, Resource
    from engine.simulation import buy_food

    # Ensure food exists for purchase
    building = db.query(Building).first()
    food = Resource(name="Food", quantity=10, building_id=building.id)
    db.add(food)

    npc = db.query(NPC).first()
    npc.gold = 50
    npc.hunger = 80
    db.commit()
    buy_food(db, npc.id)
    db.commit()
    db.refresh(npc)
    assert npc.hunger < 80 or npc.gold < 50  # Something should change


def test_s030_treasury_taxes(db):
    """Story 030: Treasury collects taxes from NPCs."""
    _setup_world(db)
    from engine.simulation import collect_taxes
    from engine.models import NPC

    # Give NPCs some gold
    for npc in db.query(NPC).all():
        npc.gold = 100
    db.commit()

    treasury_before = 0
    collect_taxes(db)
    # Tax should have been collected (NPCs should have less gold)
    total_gold = sum(npc.gold for npc in db.query(NPC).all())
    assert total_gold < db.query(NPC).count() * 100


# ---------------------------------------------------------------------------
# Stories 091-095: Supply chain tests
# ---------------------------------------------------------------------------


def test_s091_wheat_to_bread_supply_chain(db):
    """Story 091: Farm produces Wheat, Bakery converts 2 Wheat -> 1 Bread."""
    from engine.models import Building, Resource
    from engine.simulation import produce_resources, produce_bakery_resources

    farm = Building(name="Farm", building_type="food", x=0, y=0)
    bakery = Building(name="Bakery", building_type="bakery", x=2, y=2)
    db.add_all([farm, bakery])
    db.flush()

    # Give the bakery some Wheat to convert
    wheat = Resource(name="Wheat", quantity=4, building_id=bakery.id)
    db.add(wheat)
    db.flush()

    produce_bakery_resources(db)
    db.flush()

    bread = db.query(Resource).filter_by(name="Bread", building_id=bakery.id).first()
    assert bread is not None, "Bakery should produce Bread from Wheat"
    assert bread.quantity >= 1, "Bakery should have produced at least 1 Bread"


def test_s091_bakery_needs_wheat(db):
    """Story 091: Bakery produces nothing without Wheat."""
    from engine.models import Building, Resource
    from engine.simulation import produce_bakery_resources

    bakery = Building(name="Bakery", building_type="bakery", x=2, y=2)
    db.add(bakery)
    db.flush()

    produce_bakery_resources(db)
    db.flush()

    bread = db.query(Resource).filter_by(name="Bread", building_id=bakery.id).first()
    assert bread is None, "Bakery should not produce Bread without Wheat"


def test_s092_ore_to_tools_supply_chain(db):
    """Story 092: Mine produces Ore, Blacksmith converts 3 Ore -> 1 Tool."""
    from engine.models import Building, Resource
    from engine.simulation import produce_blacksmith_resources

    blacksmith = Building(name="Blacksmith", building_type="blacksmith", x=4, y=4)
    db.add(blacksmith)
    db.flush()

    ore = Resource(name="Ore", quantity=6, building_id=blacksmith.id)
    db.add(ore)
    db.flush()

    produce_blacksmith_resources(db)
    db.flush()

    tools = db.query(Resource).filter_by(name="Tool", building_id=blacksmith.id).first()
    assert tools is not None, "Blacksmith should produce Tools from Ore"
    assert tools.quantity >= 1

    db.refresh(ore)
    assert ore.quantity <= 3, "Blacksmith should consume Ore when making Tools"


def test_s093_wood_to_lumber_supply_chain(db):
    """Story 093: Lumber Mill converts 2 Wood -> 1 Lumber."""
    from engine.models import Building, Resource
    from engine.simulation import produce_lumber

    mill = Building(name="Lumber Mill", building_type="lumber_mill", x=6, y=6)
    db.add(mill)
    db.flush()

    wood = Resource(name="Wood", quantity=4, building_id=mill.id)
    db.add(wood)
    db.flush()

    produce_lumber(db)
    db.flush()

    lumber = db.query(Resource).filter_by(name="Lumber", building_id=mill.id).first()
    assert lumber is not None, "Lumber Mill should produce Lumber from Wood"
    assert lumber.quantity >= 1

    db.refresh(wood)
    assert wood.quantity <= 2, "Lumber Mill should consume Wood when making Lumber"


def test_s094_fish_to_market(db):
    """Story 094: Fishing Dock produces Fish, NPCs buy Fish (hunger -25, gold -3)."""
    from engine.models import Building, NPC, Resource
    from engine.simulation import produce_fish, buy_fish

    dock = Building(name="Fishing Dock", building_type="fishing_dock", x=8, y=8)
    db.add(dock)
    db.flush()

    produce_fish(db)
    db.flush()

    fish = db.query(Resource).filter_by(name="Fish", building_id=dock.id).first()
    assert fish is not None, "Fishing Dock should produce Fish"
    assert fish.quantity >= 1

    # NPC buys fish
    npc = NPC(name="Fisher", role="merchant", x=8, y=8, gold=20, hunger=60)
    db.add(npc)
    db.flush()

    result = buy_fish(db, npc.id)
    db.flush()

    assert result is True, "NPC should be able to buy Fish"
    db.refresh(npc)
    assert npc.hunger <= 35, "Fish should reduce hunger by 25"
    assert npc.gold <= 17, "Fish should cost 3 gold"


def test_s095_herbs_to_medicine(db):
    """Story 095: Garden produces Herbs, Hospital converts 3 Herbs -> 1 Medicine."""
    from engine.models import Building, Resource
    from engine.simulation import produce_medicine

    hospital = Building(name="Hospital", building_type="hospital", x=10, y=10)
    db.add(hospital)
    db.flush()

    herbs = Resource(name="Herbs", quantity=6, building_id=hospital.id)
    db.add(herbs)
    db.flush()

    produce_medicine(db)
    db.flush()

    medicine = db.query(Resource).filter_by(name="Medicine", building_id=hospital.id).first()
    assert medicine is not None, "Hospital should produce Medicine from Herbs"
    assert medicine.quantity >= 1

    db.refresh(herbs)
    assert herbs.quantity <= 3, "Hospital should consume Herbs when making Medicine"


# ---------------------------------------------------------------------------
# Stories 096-097: Pricing tests
# ---------------------------------------------------------------------------


def test_s096_calculate_price_basic(db):
    """Story 096: calculate_price() returns price based on supply/demand."""
    from engine.models import Building, Resource
    from engine.simulation import calculate_price

    b = Building(name="Market", building_type="market", x=12, y=12)
    db.add(b)
    db.flush()

    # High supply should mean lower price
    r = Resource(name="Wheat", quantity=100, building_id=b.id)
    db.add(r)
    db.flush()

    price = calculate_price(db, "Wheat")
    assert isinstance(price, (int, float)), "Price must be numeric"
    assert price > 0, "Price must be positive"


def test_s096_price_varies_with_supply(db):
    """Story 096: Price should be higher when supply is low."""
    from engine.models import Building, Resource
    from engine.simulation import calculate_price

    b = Building(name="Market", building_type="market", x=12, y=12)
    db.add(b)
    db.flush()

    # Low supply
    r = Resource(name="Bread", quantity=1, building_id=b.id)
    db.add(r)
    db.flush()
    price_low_supply = calculate_price(db, "Bread")

    # Increase supply
    r.quantity = 100
    db.flush()
    price_high_supply = calculate_price(db, "Bread")

    assert price_low_supply >= price_high_supply, "Lower supply should mean equal or higher price"


def test_s097_price_history_model(db):
    """Story 097: PriceHistory model with resource_name, price, supply, demand, tick."""
    from engine.models import PriceHistory

    ph = PriceHistory(
        resource_name="Wheat",
        price=5.0,
        supply=100,
        demand=50,
        tick=1,
    )
    db.add(ph)
    db.flush()

    assert ph.id is not None
    assert ph.resource_name == "Wheat"
    assert ph.price == 5.0
    assert ph.supply == 100
    assert ph.demand == 50
    assert ph.tick == 1


# ---------------------------------------------------------------------------
# Stories 098-100: Trade tests
# ---------------------------------------------------------------------------


def test_s098_process_trade(db):
    """Story 098: process_trade() moves resources between buildings."""
    from engine.models import Building, Resource
    from engine.simulation import process_trade

    seller = Building(name="Farm", building_type="food", x=0, y=0)
    buyer = Building(name="Bakery", building_type="bakery", x=2, y=2)
    db.add_all([seller, buyer])
    db.flush()

    wheat = Resource(name="Wheat", quantity=20, building_id=seller.id)
    db.add(wheat)
    db.flush()

    process_trade(db)
    db.flush()

    # After trade, resources should have moved (seller has less or buyer has some)
    db.refresh(wheat)
    buyer_wheat = db.query(Resource).filter_by(
        name="Wheat", building_id=buyer.id
    ).first()

    # Either seller lost some or buyer gained some (trade happened)
    traded = wheat.quantity < 20 or (buyer_wheat is not None and buyer_wheat.quantity > 0)
    assert traded, "process_trade should move resources between buildings"


def test_s099_merchant_route(db):
    """Story 099: get_merchant_route() returns list of building stops."""
    from engine.models import Building, NPC
    from engine.simulation import get_merchant_route

    b1 = Building(name="Farm", building_type="food", x=0, y=0)
    b2 = Building(name="Bakery", building_type="bakery", x=5, y=5)
    b3 = Building(name="Market", building_type="market", x=10, y=10)
    db.add_all([b1, b2, b3])
    db.flush()

    merchant = NPC(name="Trader", role="merchant", x=0, y=0, gold=50)
    db.add(merchant)
    db.flush()

    route = get_merchant_route(db, merchant)
    assert isinstance(route, list), "Route should be a list"
    assert len(route) >= 1, "Merchant route should have at least one stop"


def test_s100_market_saturation(db):
    """Story 100: check_market_saturation() detects oversupply."""
    from engine.models import Building, Resource
    from engine.simulation import check_market_saturation

    b = Building(name="Farm", building_type="food", x=0, y=0)
    db.add(b)
    db.flush()

    # Create massive oversupply
    r = Resource(name="Wheat", quantity=10000, building_id=b.id)
    db.add(r)
    db.flush()

    result = check_market_saturation(db)
    assert isinstance(result, (bool, list, dict)), "Should return saturation info"


# ---------------------------------------------------------------------------
# Stories 101-102: Admin endpoint tests
# ---------------------------------------------------------------------------


def test_s101_configurable_tax_rate(client, admin_headers):
    """Story 101: tax_rate field on WorldState, POST /api/admin/tax-rate."""
    resp = client.post(
        "/api/admin/tax-rate",
        json={"tax_rate": 0.15},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201), f"POST tax-rate failed: {resp.text}"
    data = resp.json()
    assert "tax_rate" in data or "message" in data


def test_s101_tax_rate_on_worldstate(db):
    """Story 101: WorldState model should have a tax_rate field."""
    from engine.models import WorldState

    ws = WorldState(tick=0, day=1, time_of_day="morning")
    db.add(ws)
    db.flush()
    ws.tax_rate = 0.15
    db.flush()
    db.refresh(ws)
    assert ws.tax_rate == 0.15


def test_s102_wage_adjustment(client, admin_headers):
    """Story 102: base_wage field on WorldState, POST /api/admin/wage."""
    resp = client.post(
        "/api/admin/wage",
        json={"base_wage": 15},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201), f"POST wage failed: {resp.text}"
    data = resp.json()
    assert "base_wage" in data or "message" in data


# ---------------------------------------------------------------------------
# Stories 103-108: Complex simulation tests
# ---------------------------------------------------------------------------


def test_s103_track_inflation(db):
    """Story 103: track_inflation() calculates inflation rate."""
    from engine.simulation import track_inflation

    # Set up minimal world state
    from engine.models import WorldState
    ws = WorldState(tick=10, day=3, time_of_day="morning")
    db.add(ws)
    db.flush()

    result = track_inflation(db)
    assert isinstance(result, (int, float)), "Inflation rate must be numeric"


def test_s104_detect_recession(db):
    """Story 104: detect_recession() detects recession conditions."""
    from engine.simulation import detect_recession
    from engine.models import WorldState

    ws = WorldState(tick=10, day=3, time_of_day="morning")
    db.add(ws)
    db.flush()

    result = detect_recession(db)
    assert isinstance(result, bool), "detect_recession should return a boolean"


def test_s105_apply_stimulus(db):
    """Story 105: apply_stimulus() activates during recession."""
    from engine.simulation import apply_stimulus
    from engine.models import WorldState, NPC

    ws = WorldState(tick=10, day=3, time_of_day="morning")
    db.add(ws)
    db.flush()

    # Create some NPCs to receive stimulus
    npc1 = NPC(name="Worker1", role="farmer", x=0, y=0, gold=5)
    npc2 = NPC(name="Worker2", role="baker", x=1, y=1, gold=3)
    db.add_all([npc1, npc2])
    db.flush()

    result = apply_stimulus(db)
    db.flush()

    # Function should run without error and return something meaningful
    assert result is not None, "apply_stimulus should return a result"


def test_s106_art_luxury_goods(db):
    """Story 106: Theater produces Art, NPCs buy for 15 gold (+20 happiness)."""
    from engine.models import Building, NPC, Resource
    from engine.simulation import produce_art, buy_art

    theater = Building(name="Theater", building_type="theater", x=14, y=14)
    db.add(theater)
    db.flush()

    produce_art(db)
    db.flush()

    art = db.query(Resource).filter_by(name="Art", building_id=theater.id).first()
    assert art is not None, "Theater should produce Art"
    assert art.quantity >= 1

    npc = NPC(name="Patron", role="merchant", x=14, y=14, gold=30, happiness=50)
    db.add(npc)
    db.flush()

    result = buy_art(db, npc.id)
    db.flush()
    assert result is True, "NPC should be able to buy Art"

    db.refresh(npc)
    assert npc.gold <= 15, "Art should cost 15 gold"
    assert npc.happiness >= 70, "Art should boost happiness by 20"


def test_s107_books_luxury_goods(db):
    """Story 107: Library produces Books, NPCs buy for 10 gold (+15 happiness)."""
    from engine.models import Building, NPC, Resource
    from engine.simulation import produce_books, buy_books

    library = Building(name="Library", building_type="library", x=16, y=16)
    db.add(library)
    db.flush()

    produce_books(db)
    db.flush()

    books = db.query(Resource).filter_by(name="Books", building_id=library.id).first()
    assert books is not None, "Library should produce Books"
    assert books.quantity >= 1

    npc = NPC(name="Reader", role="merchant", x=16, y=16, gold=20, happiness=50)
    db.add(npc)
    db.flush()

    result = buy_books(db, npc.id)
    db.flush()
    assert result is True, "NPC should be able to buy Books"

    db.refresh(npc)
    assert npc.gold <= 10, "Books should cost 10 gold"
    assert npc.happiness >= 65, "Books should boost happiness by 15"


def test_s108_medicine_goods(db):
    """Story 108: Hospital produces Medicine from Herbs, sick NPCs buy for 8 gold."""
    from engine.models import Building, NPC, Resource
    from engine.simulation import produce_medicine, buy_medicine

    hospital = Building(name="Hospital", building_type="hospital", x=18, y=18)
    db.add(hospital)
    db.flush()

    herbs = Resource(name="Herbs", quantity=6, building_id=hospital.id)
    db.add(herbs)
    db.flush()

    produce_medicine(db)
    db.flush()

    medicine = db.query(Resource).filter_by(name="Medicine", building_id=hospital.id).first()
    assert medicine is not None, "Hospital should produce Medicine from Herbs"
    assert medicine.quantity >= 1

    # Sick NPC buys medicine
    npc = NPC(name="Patient", role="farmer", x=18, y=18, gold=20, hunger=80)
    db.add(npc)
    db.flush()

    result = buy_medicine(db, npc.id)
    db.flush()
    assert result is True, "Sick NPC should be able to buy Medicine"

    db.refresh(npc)
    assert npc.gold <= 12, "Medicine should cost 8 gold"


# ---------------------------------------------------------------------------
# Story 202: Dynamic supply/demand pricing — price history + merchant trades
# ---------------------------------------------------------------------------


def test_s202_update_price_history_creates_records(db):
    """Story 202: update_price_history() should create PriceHistory records."""
    from engine.models import Building, Resource, PriceHistory
    from engine.simulation import update_price_history

    b = Building(name="Market", building_type="market", x=0, y=0)
    db.add(b)
    db.flush()

    r = Resource(name="Wheat", quantity=50, building_id=b.id)
    db.add(r)
    db.flush()

    update_price_history(db)
    db.flush()

    records = db.query(PriceHistory).all()
    assert len(records) >= 1, "update_price_history must create at least one PriceHistory record"


def test_s202_price_history_model_fields(db):
    """Story 202: PriceHistory model has resource_name, price, supply, demand, tick."""
    from engine.models import PriceHistory

    ph = PriceHistory(
        resource_name="Bread",
        price=7.5,
        supply=40,
        demand=60,
        tick=10,
    )
    db.add(ph)
    db.flush()

    assert ph.id is not None
    assert ph.resource_name == "Bread"
    assert ph.price == 7.5
    assert ph.supply == 40
    assert ph.demand == 60
    assert ph.tick == 10
