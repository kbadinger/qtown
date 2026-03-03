"""Tests for NPC needs stories: 015-016, 020, 022, 039."""


def test_s015_hunger_field(db):
    """Story 015: NPC model should have a hunger field (0-100)."""
    from engine.models import NPC

    npc = NPC(name="Hungry", role="farmer", x=0, y=0, hunger=50)
    db.add(npc)
    db.commit()
    assert npc.hunger == 50


def test_s016_energy_field(db):
    """Story 016: NPC model should have an energy field (0-100)."""
    from engine.models import NPC

    npc = NPC(name="Tired", role="farmer", x=0, y=0, energy=75)
    db.add(npc)
    db.commit()
    assert npc.energy == 75


def test_s020_eating_reduces_hunger(db):
    """Story 020: eat() should reduce NPC hunger."""
    from engine.models import NPC
    from engine.simulation import eat

    npc = NPC(name="Eater", role="farmer", x=0, y=0, hunger=80, gold=50)
    db.add(npc)
    db.commit()
    eat(db, npc.id)
    db.commit()
    db.refresh(npc)
    assert npc.hunger < 80


def test_s022_sleeping_restores_energy(db):
    """Story 022: sleep_npc() should restore NPC energy."""
    from engine.models import NPC
    from engine.simulation import sleep_npc

    npc = NPC(name="Sleeper", role="farmer", x=0, y=0, energy=20)
    db.add(npc)
    db.commit()
    sleep_npc(db, npc.id)
    db.commit()
    db.refresh(npc)
    assert npc.energy > 20


def test_s039_npc_happiness(db):
    """Story 039: NPC model should have a happiness field."""
    from engine.models import NPC

    npc = NPC(name="Happy", role="farmer", x=0, y=0)
    db.add(npc)
    db.commit()
    assert hasattr(npc, "happiness")


def test_s039_happiness_calculation(db):
    """Story 039: Happiness should be calculable from needs."""
    from engine.simulation import calculate_happiness
    from engine.models import NPC

    npc = NPC(name="Test", role="farmer", x=0, y=0, hunger=20, energy=80)
    db.add(npc)
    db.commit()
    happiness = calculate_happiness(db, npc.id)
    assert isinstance(happiness, (int, float))
    assert 0 <= happiness <= 100
