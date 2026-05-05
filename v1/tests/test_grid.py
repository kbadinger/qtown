"""Tests for Story 001: Initialize 50x50 grid."""


def test_s001_init_grid_creates_2500_tiles(db):
    """Story 001: init_grid() should create 2500 tiles (50x50)."""
    from engine.simulation import init_grid

    init_grid(db)
    from engine.models import Tile

    count = db.query(Tile).count()
    assert count == 2500, f"Expected 2500 tiles, got {count}"


def test_s001_init_grid_covers_full_range(db):
    """Story 001: Grid should cover x=0..49, y=0..49."""
    from engine.simulation import init_grid

    init_grid(db)
    from engine.models import Tile

    xs = {t.x for t in db.query(Tile).all()}
    ys = {t.y for t in db.query(Tile).all()}
    assert xs == set(range(50))
    assert ys == set(range(50))


def test_s001_init_grid_default_terrain(db):
    """Story 001: Most tiles should be grass, with terrain variety for special zones."""
    from engine.simulation import init_grid

    init_grid(db)
    from engine.models import Tile

    total = db.query(Tile).count()
    grass = db.query(Tile).filter(Tile.terrain == "grass").count()
    valid_terrains = {"grass", "water", "forest", "dirt", "sand", "stone"}
    all_terrains = {t.terrain for t in db.query(Tile).all()}
    assert all_terrains.issubset(valid_terrains), f"Unexpected terrains: {all_terrains - valid_terrains}"
    assert grass > total * 0.8, f"Expected mostly grass, got {grass}/{total}"


def test_s001_init_grid_idempotent(db):
    """Story 001: Calling init_grid() twice should not duplicate tiles."""
    from engine.simulation import init_grid

    init_grid(db)
    init_grid(db)
    from engine.models import Tile

    count = db.query(Tile).count()
    assert count == 2500
