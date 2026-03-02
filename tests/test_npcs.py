"""Tests for NPC stories: 003, 005, 010-011, 018-019, 040."""


def test_s003_npc_model_exists(db):
    """Story 003: NPC model should exist with required fields."""
    from engine.models import NPC

    npc = NPC(name="Alice", role="farmer", x=10, y=10)
    db.add(npc)
    db.commit()
    assert npc.id is not None
    assert npc.name == "Alice"
    assert npc.role == "farmer"


def test_s005_seed_npcs(db):
    """Story 005: seed_npcs() should create starter NPCs."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    from engine.models import NPC

    count = db.query(NPC).count()
    assert count >= 5, f"Expected at least 5 seed NPCs, got {count}"


def test_s005_seed_npcs_on_valid_tiles(db):
    """Story 005: Seeded NPCs must be on valid grid coordinates."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    from engine.models import NPC

    for npc in db.query(NPC).all():
        assert 0 <= npc.x < 50, f"NPC {npc.name} x={npc.x} out of range"
        assert 0 <= npc.y < 50, f"NPC {npc.name} y={npc.y} out of range"


def test_s010_get_npcs_api(client):
    """Story 010: GET /api/npcs returns list of NPCs."""
    resp = client.get("/api/npcs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_s011_create_npc_api(client, admin_headers):
    """Story 011: POST /api/npcs creates an NPC (admin only)."""
    resp = client.post(
        "/api/npcs",
        json={"name": "Bob", "role": "baker", "x": 5, "y": 5},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "Bob"


def test_s018_npc_home_assignment(db):
    """Story 018: assign_homes() gives NPCs a home_building_id."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs, assign_homes

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    assign_homes(db)
    from engine.models import NPC

    assigned = db.query(NPC).filter(NPC.home_building_id.isnot(None)).count()
    total = db.query(NPC).count()
    assert assigned > 0, "No NPCs assigned homes"


def test_s019_npc_work_assignment(db):
    """Story 019: assign_work() gives NPCs a work_building_id."""
    from engine.simulation import init_grid, seed_buildings, seed_npcs, assign_work

    init_grid(db)
    seed_buildings(db)
    seed_npcs(db)
    assign_work(db)
    from engine.models import NPC

    assigned = db.query(NPC).filter(NPC.work_building_id.isnot(None)).count()
    assert assigned > 0, "No NPCs assigned work"


def test_s040_npc_personality_traits(db):
    """Story 040: NPCs should have personality traits."""
    from engine.models import NPC

    npc = NPC(name="Trait Test", role="farmer", x=0, y=0)
    db.add(npc)
    db.commit()
    # Personality traits should exist as a field
    assert hasattr(npc, "personality")
