"""Tests for voting/feature stories: 042-045."""


def test_submit_feature(client):
    """Story 042: POST /api/features submits a feature request."""
    resp = client.post(
        "/api/features",
        json={"title": "Add dragons", "description": "Fire-breathing ones"},
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["title"] == "Add dragons"
    assert data["status"] == "submitted"


def test_submit_feature_empty_title(client):
    """Story 042: Empty title should return 422."""
    resp = client.post(
        "/api/features",
        json={"title": "", "description": "No title"},
    )
    assert resp.status_code == 422


def test_list_features(client):
    """Story 042: GET /api/features lists all submitted features."""
    # Submit one first
    client.post(
        "/api/features",
        json={"title": "Test Feature", "description": "For listing"},
    )
    resp = client.get("/api/features")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_vote_for_feature(client):
    """Story 043: POST /api/features/{id}/vote registers a vote."""
    # Create feature
    create_resp = client.post(
        "/api/features",
        json={"title": "Voteable", "description": "Vote for me"},
    )
    feature_id = create_resp.json()["id"]

    # Vote
    vote_resp = client.post(f"/api/features/{feature_id}/vote")
    assert vote_resp.status_code == 200
    data = vote_resp.json()
    assert data["vote_count"] >= 1


def test_vote_dedup_by_ip(client):
    """Story 043: Same IP can only vote once per feature."""
    create_resp = client.post(
        "/api/features",
        json={"title": "Dedup Test", "description": "One vote per IP"},
    )
    feature_id = create_resp.json()["id"]

    # First vote succeeds
    client.post(f"/api/features/{feature_id}/vote")
    # Second vote should fail or be rejected
    resp2 = client.post(f"/api/features/{feature_id}/vote")
    assert resp2.status_code in (200, 409)
    # Vote count should still be 1
    feature = client.get("/api/features").json()
    target = [f for f in feature if f["id"] == feature_id][0]
    assert target["vote_count"] == 1


def test_admin_approve_feature(client, admin_headers):
    """Story 044: Admin can approve a feature."""
    create_resp = client.post(
        "/api/features",
        json={"title": "Approve Me", "description": "Needs approval"},
    )
    feature_id = create_resp.json()["id"]

    resp = client.post(
        f"/api/features/{feature_id}/approve",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_approve_requires_admin(client):
    """Story 044: Approving without admin key returns 401/422."""
    create_resp = client.post(
        "/api/features",
        json={"title": "No Auth", "description": "Should fail"},
    )
    feature_id = create_resp.json()["id"]

    resp = client.post(f"/api/features/{feature_id}/approve")
    assert resp.status_code in (401, 422)


def test_convert_to_prd(client, admin_headers):
    """Story 045: Admin can convert approved feature to PRD story."""
    # Create and approve
    create_resp = client.post(
        "/api/features",
        json={"title": "PRD Convert", "description": "Convert to story"},
    )
    feature_id = create_resp.json()["id"]
    client.post(f"/api/features/{feature_id}/approve", headers=admin_headers)

    # Convert to PRD
    resp = client.post(
        f"/api/features/{feature_id}/to-prd",
        json={
            "story_id": "999",
            "title": "PRD: Convert Feature",
            "description": "Converted from feature request",
            "test_file": "tests/test_converted.py",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "published"
    assert data["prd_story_id"] == "999"
