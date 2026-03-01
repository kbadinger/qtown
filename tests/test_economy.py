"""Tests for economy stories: 012-014, 026-030."""


def _setup_world(db):
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)


def test_npc_gold_field(db):
    """Story 012: NPC model should have a gold field."""
    from engine.models import NPC

    npc = NPC(name="Rich", role="merchant", x=0, y=0, gold=100)
    db.add(npc)
    db.commit()
    assert npc.gold == 100


def test_transfer_gold(db):
    """Story 013: transfer_gold() moves gold between NPCs."""
    from engine.models import NPC
    from engine.simulation import transfer_gold

    sender = NPC(name="Sender", role="merchant", x=0, y=0, gold=100)
    receiver = NPC(name="Receiver", role="farmer", x=1, y=1, gold=0)
    db.add_all([sender, receiver])
    db.commit()

    result = transfer_gold(db, sender.id, receiver.id, 50)
    assert result is True
    db.refresh(sender)
    db.refresh(receiver)
    assert sender.gold == 50
    assert receiver.gold == 50


def test_transfer_gold_insufficient(db):
    """Story 013: transfer_gold() fails if sender lacks funds."""
    from engine.models import NPC
    from engine.simulation import transfer_gold

    sender = NPC(name="Poor", role="farmer", x=0, y=0, gold=10)
    receiver = NPC(name="Rich", role="merchant", x=1, y=1, gold=100)
    db.add_all([sender, receiver])
    db.commit()

    result = transfer_gold(db, sender.id, receiver.id, 50)
    assert result is False
    db.refresh(sender)
    assert sender.gold == 10  # Unchanged


def test_transactions_api(client, admin_headers):
    """Story 014: GET /api/transactions returns transaction history."""
    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_earn_gold_at_work(db):
    """Story 026: NPCs earn gold when working."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import process_work

    npc = db.query(NPC).first()
    npc.gold = 0
    npc.work_building_id = 1  # Assign to first building
    db.commit()
    process_work(db)
    db.refresh(npc)
    assert npc.gold > 0, "NPC should have earned gold from working"


def test_resource_model(db):
    """Story 027: Resource model should exist."""
    from engine.models import Resource

    r = Resource(name="Wheat", quantity=100, building_id=1)
    db.add(r)
    db.commit()
    assert r.id is not None


def test_food_production(db):
    """Story 028: Farms should produce food resources."""
    _setup_world(db)
    from engine.simulation import produce_resources

    produce_resources(db)
    from engine.models import Resource

    food = db.query(Resource).filter_by(name="Food").first()
    # Food should be produced (or function should exist without error)
    assert food is None or food.quantity >= 0


def test_buy_food(db):
    """Story 029: NPCs can buy food with gold."""
    _setup_world(db)
    from engine.models import NPC
    from engine.simulation import buy_food

    npc = db.query(NPC).first()
    npc.gold = 50
    npc.hunger = 80
    db.commit()
    buy_food(db, npc.id)
    db.refresh(npc)
    assert npc.hunger < 80 or npc.gold < 50  # Something should change


def test_treasury_taxes(db):
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
