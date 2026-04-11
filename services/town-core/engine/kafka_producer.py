"""Async Kafka producer for Town Core event emission."""
import asyncio
import json
import logging
import os
from typing import Any

from aiokafka import AIOKafkaProducer

logger = logging.getLogger("town-core.kafka")

# Topic constants
TOPIC_EVENTS_BROADCAST = "qtown.events.broadcast"
TOPIC_ECONOMY_TRADE = "qtown.economy.trade"
TOPIC_NPC_TRAVEL = "qtown.npc.travel"
TOPIC_NPC_TRAVEL_COMPLETE = "qtown.npc.travel.complete"
TOPIC_ECONOMY_TRADE_SETTLED = "qtown.economy.trade.settled"
TOPIC_VALIDATION_REQUEST = "qtown.validation.request"
TOPIC_AI_REQUEST = "qtown.ai.request"

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    """Get or create the singleton Kafka producer."""
    global _producer
    if _producer is None:
        brokers = os.environ.get("KAFKA_BROKERS", "localhost:9092")
        _producer = AIOKafkaProducer(
            bootstrap_servers=brokers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retry_backoff_ms=500,
            request_timeout_ms=10000,
        )
        await _producer.start()
        logger.info("Kafka producer started (brokers=%s)", brokers)
    return _producer


async def close_producer():
    """Gracefully close the Kafka producer."""
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")


async def emit_event(topic: str, key: str, value: dict[str, Any]) -> None:
    """Send a message to a Kafka topic."""
    producer = await get_producer()
    try:
        await producer.send_and_wait(topic, key=key, value=value)
    except Exception:
        logger.exception("Failed to emit to %s key=%s", topic, key)
        raise


async def emit_event_broadcast(tick: int, event_type: str, description: str,
                                npc_id: int | None = None, severity: str = "info",
                                metadata: dict | None = None) -> None:
    """Emit an event to the broadcast topic."""
    await emit_event(
        TOPIC_EVENTS_BROADCAST,
        key=str(tick),
        value={
            "tick": tick,
            "event_type": event_type,
            "description": description,
            "npc_id": npc_id,
            "severity": severity,
            "metadata": metadata or {},
        },
    )


async def emit_economy_trade(tick: int, sender_id: int, receiver_id: int,
                              amount: int, resource: str = "gold",
                              reason: str = "") -> None:
    """Emit a trade event."""
    await emit_event(
        TOPIC_ECONOMY_TRADE,
        key=str(sender_id),
        value={
            "tick": tick,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "amount": amount,
            "resource": resource,
            "reason": reason,
        },
    )


async def emit_npc_travel(tick: int, npc_id: int, from_neighborhood: str,
                           to_neighborhood: str, npc_state: dict) -> None:
    """Emit NPC travel event — NPC is moving between neighborhoods."""
    await emit_event(
        TOPIC_NPC_TRAVEL,
        key=str(npc_id),  # partition by NPC ID for ordering
        value={
            "tick": tick,
            "npc_id": npc_id,
            "from": from_neighborhood,
            "to": to_neighborhood,
            "npc_state": npc_state,
        },
    )


async def emit_validation_request(tick: int, event_type: str, npc_id: int,
                                   amount: float = 0.0,
                                   metadata: dict | None = None) -> None:
    """Request validation from Fortress service."""
    await emit_event(
        TOPIC_VALIDATION_REQUEST,
        key=str(npc_id),
        value={
            "tick": tick,
            "event_type": event_type,
            "npc_id": npc_id,
            "amount": amount,
            "metadata": metadata or {},
        },
    )
