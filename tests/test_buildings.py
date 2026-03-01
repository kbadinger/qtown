"""Tests for building stories: 002, 004, 008-009, 031."""


def test_building_model_exists(db):
    """Story 002: Building model should exist with required fields."""
    from engine.models import Building

    b = Building(name="Town Hall", building_type="civic", x=25, y=25)
    db.add(b)
    db.commit()
    assert b.id is not None
    assert b.name == "Town Hall"
    assert b.building_type == "civic"
    assert b.x == 25
    assert b.y == 25


def test_seed_buildings(db):
    """Story 004: seed_buildings() should create starter buildings."""
    from engine.simulation import init_grid, seed_buildings

    init_grid(db)
    seed_buildings(db)
    from engine.models import Building

    count = db.query(Building).count()
    assert count >= 3, f"Expected at least 3 seed buildings, got {count}"


def test_seed_buildings_on_valid_tiles(db):
    """Story 004: Seeded buildings must be on valid grid coordinates."""
    from engine.simulation import init_grid, seed_buildings

    init_grid(db)
    seed_buildings(db)
    from engine.models import Building

    for b in db.query(Building).all():
        assert 0 <= b.x < 50, f"Building {b.name} x={b.x} out of range"
        assert 0 <= b.y < 50, f"Building {b.name} y={b.y} out of range"


def test_get_buildings_api(client, admin_headers):
    """Story 008: GET /api/buildings returns list of buildings."""
    resp = client.get("/api/buildings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_building_api(client, admin_headers):
    """Story 009: POST /api/buildings creates a building (admin only)."""
    resp = client.post(
        "/api/buildings",
        json={"name": "Bakery", "building_type": "food", "x": 10, "y": 10},
        headers=admin_headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "Bakery"


def test_create_building_requires_admin(client):
    """Story 009: POST /api/buildings without admin key returns 401/422."""
    resp = client.post(
        "/api/buildings",
        json={"name": "Bakery", "building_type": "food", "x": 10, "y": 10},
    )
    assert resp.status_code in (401, 422)


def test_build_building_via_simulation(db):
    """Story 031: build_building() should deduct resources and create building."""
    from engine.simulation import init_grid, build_building

    init_grid(db)
    result = build_building(db, name="Market", building_type="commerce", x=15, y=15)
    assert result is not None
    from engine.models import Building

    assert db.query(Building).filter_by(name="Market").first() is not None
