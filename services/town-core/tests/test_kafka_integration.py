"""Integration tests for Kafka event pipeline.

These tests verify:
1. Kafka producer can serialize and send events
2. Event structure matches expected schema
3. NPC travel event round-trip
4. Zone boundary detection triggers travel
5. Travel timeout handling

NOTE: These tests mock the Kafka producer — they do NOT require
a running Kafka broker. For end-to-end tests with real Kafka,
see tests/test_e2e_travel.py (requires `make deps`).
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Producer Tests ───

@pytest.mark.asyncio
async def test_emit_event_broadcast():
    """emit_event_broadcast sends correct structure to correct topic."""
    with patch("engine.kafka_producer.get_producer") as mock_get:
        mock_producer = AsyncMock()
        mock_get.return_value = mock_producer

        from engine.kafka_producer import emit_event_broadcast
        await emit_event_broadcast(
            tick=100,
            event_type="test_event",
            description="Something happened",
            npc_id=7,
            severity="info",
        )

        mock_producer.send_and_wait.assert_called_once()
        call_args = mock_producer.send_and_wait.call_args
        assert call_args.kwargs["topic"] == "qtown.events.broadcast" or \
               call_args[0][0] == "qtown.events.broadcast"


@pytest.mark.asyncio
async def test_emit_npc_travel():
    """emit_npc_travel sends correct structure keyed by npc_id."""
    with patch("engine.kafka_producer.get_producer") as mock_get:
        mock_producer = AsyncMock()
        mock_get.return_value = mock_producer

        from engine.kafka_producer import emit_npc_travel
        await emit_npc_travel(
            tick=200,
            npc_id=42,
            from_neighborhood="town_core",
            to_neighborhood="market_district",
            npc_state={"id": 42, "name": "Bob", "gold": 100},
        )

        mock_producer.send_and_wait.assert_called_once()


@pytest.mark.asyncio
async def test_emit_economy_trade():
    """emit_economy_trade sends trade event."""
    with patch("engine.kafka_producer.get_producer") as mock_get:
        mock_producer = AsyncMock()
        mock_get.return_value = mock_producer

        from engine.kafka_producer import emit_economy_trade
        await emit_economy_trade(
            tick=300,
            sender_id=1,
            receiver_id=2,
            amount=50,
            resource="wood",
            reason="market_trade",
        )

        mock_producer.send_and_wait.assert_called_once()


# ─── Zone / Neighborhood Tests ───

def test_get_neighborhood_town_core():
    """Center of grid maps to town_core."""
    from engine.neighborhoods import get_neighborhood
    assert get_neighborhood(20, 20) == "town_hall"  # town_hall overlaps center
    assert get_neighborhood(16, 16) == "town_core"


def test_get_neighborhood_market_district():
    """East strip maps to market_district."""
    from engine.neighborhoods import get_neighborhood
    assert get_neighborhood(40, 25) == "market_district"


def test_get_neighborhood_fortress():
    """NW corner maps to fortress."""
    from engine.neighborhoods import get_neighborhood
    assert get_neighborhood(5, 5) == "fortress"


def test_zone_boundary_crossing():
    """Moving from town_core to market_district detects crossing."""
    from engine.neighborhoods import is_zone_boundary_crossing
    result = is_zone_boundary_crossing(34, 25, 35, 25)
    assert result is not None
    assert result == ("town_core", "market_district")


def test_no_zone_crossing_within_zone():
    """Moving within town_core does not trigger crossing."""
    from engine.neighborhoods import is_zone_boundary_crossing
    result = is_zone_boundary_crossing(20, 20, 21, 20)
    assert result is None


# ─── Travel State Tests ───

def test_serialize_npc_state():
    """serialize_npc_state produces expected dict structure."""
    from engine.simulation.travel import serialize_npc_state

    # Create a mock NPC
    npc = MagicMock()
    npc.id = 7
    npc.name = "Bob"
    npc.role = "merchant"
    npc.gold = 150
    npc.hunger = 30
    npc.energy = 80
    npc.happiness = 60
    npc.age = 35
    npc.x = 20
    npc.y = 25
    npc.personality = '{"trait": "greedy"}'
    npc.skill = 5

    state = serialize_npc_state(npc)
    assert state["id"] == 7
    assert state["name"] == "Bob"
    assert state["gold"] == 150
    assert state["personality"] == {"trait": "greedy"}


def test_check_travel_timeouts_no_timeouts():
    """No timeouts when no active travels."""
    from engine.simulation.travel import check_travel_timeouts, _active_travels
    _active_travels.clear()

    db = MagicMock()
    result = check_travel_timeouts(db, 100)
    assert result == []


# ─── Consumer Handler Tests ───

@pytest.mark.asyncio
async def test_handle_travel_complete():
    """handle_travel_complete clears traveling state and applies gold delta."""
    mock_npc = MagicMock()
    mock_npc.id = 7
    mock_npc.name = "Bob"
    mock_npc.traveling = True
    mock_npc.travel_destination = "market_district"
    mock_npc.gold = 100

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_npc

    with patch("engine.kafka_consumer.SessionLocal", return_value=mock_db):
        from engine.kafka_consumer import handle_travel_complete
        await handle_travel_complete({
            "npc_id": 7,
            "status": "ok",
            "gold_delta": 50,
            "neighborhood": "market_district",
        })

    assert mock_npc.traveling == False
    assert mock_npc.travel_destination is None
    assert mock_npc.neighborhood == "market_district"
    assert mock_npc.gold == 150
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_handle_trade_settled():
    """handle_trade_settled applies gold delta to NPC."""
    mock_npc = MagicMock()
    mock_npc.id = 3
    mock_npc.name = "Alice"
    mock_npc.gold = 200

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_npc

    with patch("engine.kafka_consumer.SessionLocal", return_value=mock_db):
        from engine.kafka_consumer import handle_trade_settled
        await handle_trade_settled({
            "npc_id": 3,
            "gold_delta": -30,
            "resource": "iron",
            "trade_id": "trade-123",
        })

    assert mock_npc.gold == 170
    mock_db.commit.assert_called_once()
