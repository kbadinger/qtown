"""Shared test fixtures — fresh DB per test, FastAPI TestClient, admin key."""

import os

os.environ["QTOWN_ADMIN_KEY"] = "test-admin-key"
os.environ["QTOWN_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_town.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from engine.db import Base, get_db
from engine.main import app

TEST_DB_URL = "sqlite:///./test_town.db"


@pytest.fixture()
def db():
    """Fresh SQLite database per test."""
    test_engine = create_engine(
        TEST_DB_URL, connect_args={"check_same_thread": False}
    )

    @event.listens_for(test_engine, "connect")
    def _set_wal(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db):
    """FastAPI TestClient wired to the test database."""

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    # Disable rate limiting in tests
    app.state.limiter.enabled = False

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    app.state.limiter.enabled = True


@pytest.fixture()
def admin_key():
    """Returns the test admin key."""
    return "test-admin-key"


@pytest.fixture()
def admin_headers(admin_key):
    """Returns headers dict with admin key."""
    return {"X-Admin-Key": admin_key}


def enrich_world(db):
    """Add extra building types and NPC roles needed by stories 500+.

    Call AFTER seed_buildings/seed_npcs so we don't duplicate the base set.
    Idempotent — safe to call multiple times.
    """
    from engine.models import Building, NPC

    # -- extra buildings --------------------------------------------------
    extra_buildings = [
        "arena", "church", "tavern", "theater", "barracks", "mine",
        "lumber_mill", "fishing_dock", "hospital", "school", "library",
        "bank", "blacksmith", "warehouse", "market", "prison",
        "watchtower", "windmill", "well", "graveyard", "garden",
    ]
    existing_types = {b.building_type for b in db.query(Building).all()}
    for i, bt in enumerate(extra_buildings):
        if bt not in existing_types:
            db.add(Building(name=bt.replace("_", " ").title(),
                            building_type=bt, x=30 + i, y=30))

    # -- extra NPCs -------------------------------------------------------
    extra_npcs = [
        ("Rex", "miner"), ("Elara", "explorer"), ("Gwen", "lumberjack"),
        ("Finn", "fisherman"), ("Rosa", "artist"), ("Benny", "bard"),
        ("Dirk", "blacksmith"), ("Nora", "builder"), ("Ivy", "journalist"),
        ("Cal", "thief"),
    ]
    existing_names = {n.name for n in db.query(NPC).all()}
    for name, role in extra_npcs:
        if name not in existing_names:
            db.add(NPC(name=name, role=role, x=35, y=35, gold=50))

    db.commit()
