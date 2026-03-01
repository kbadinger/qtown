"""Tests for API stories: 006-007, 037-038."""


def test_get_world(client):
    """Story 006: GET /api/world returns world state."""
    resp = client.get("/api/world")
    assert resp.status_code == 200
    data = resp.json()
    assert "tiles" in data or "grid" in data


def test_get_world_includes_buildings(client, admin_headers):
    """Story 006: World state includes buildings."""
    # Seed some data first
    client.post(
        "/api/buildings",
        json={"name": "Hall", "building_type": "civic", "x": 25, "y": 25},
        headers=admin_headers,
    )
    resp = client.get("/api/world")
    data = resp.json()
    assert "buildings" in data


def test_get_world_includes_npcs(client):
    """Story 006: World state includes NPCs."""
    resp = client.get("/api/world")
    data = resp.json()
    assert "npcs" in data


def test_post_tick(client, admin_headers):
    """Story 007: POST /api/tick advances simulation by one tick."""
    resp = client.post("/api/tick", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tick" in data or "world_tick" in data or "status" in data


def test_post_tick_requires_admin(client):
    """Story 007: POST /api/tick requires admin key."""
    resp = client.post("/api/tick")
    assert resp.status_code in (401, 422)


def test_events_api(client):
    """Story 037: GET /api/events returns event list."""
    resp = client.get("/api/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_stats_api(client):
    """Story 038: GET /api/stats returns simulation statistics."""
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    # Should have some kind of stats
    assert isinstance(data, dict)
