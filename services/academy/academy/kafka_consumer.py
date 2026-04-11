from __future__ import annotations

"""Kafka consumer for the Academy service.

Subscribes to:
  - qtown.events.*   — town-wide events; embedded and stored in pgvector for RAG
  - qtown.npc.*      — NPC-specific messages; decision requests trigger the LangGraph agent

Run standalone:
    python -m academy.kafka_consumer
"""

import asyncio
import json
import logging
import os
import signal

from confluent_kafka import Consumer, KafkaError, KafkaException

from academy.agents.npc import NPCState, npc_agent
from academy.rag import RAGStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "academy-service")
TOPIC_PATTERNS = ["qtown.events", "qtown.npc"]

_KAFKA_CONFIG: dict[str, str] = {
    "bootstrap.servers": KAFKA_BOOTSTRAP,
    "group.id": CONSUMER_GROUP,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": "true",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_consumer() -> Consumer:
    return Consumer(_KAFKA_CONFIG)


async def _handle_event(rag: RAGStore, topic: str, payload: dict) -> None:
    """Embed and store a town event in pgvector for RAG retrieval."""
    event_id: int = payload.get("event_id", 0)
    text: str = payload.get("text", json.dumps(payload))
    logger.info("Ingesting event %d from topic '%s' into RAG store", event_id, topic)
    try:
        embedding = await rag.embed_event(text)
        await rag.store_event(event_id, text, embedding)
    except Exception as exc:
        logger.error("Failed to store event %d: %s", event_id, exc)


async def _handle_npc_message(topic: str, payload: dict) -> None:
    """Process an NPC-related Kafka message.

    If the payload contains a ``type == "decision_request"`` field, the
    LangGraph NPC agent is invoked and the result is logged (in a real system
    it would be published back to a response topic).
    """
    msg_type: str = payload.get("type", "")
    if msg_type != "decision_request":
        logger.debug("Ignoring NPC message of type '%s'", msg_type)
        return

    initial_state: NPCState = {
        "npc_id": payload.get("npc_id", 0),
        "name": payload.get("name", "Unknown"),
        "gold": float(payload.get("gold", 50.0)),
        "happiness": float(payload.get("happiness", 75.0)),
        "needs": [],
        "memories": [],
        "options": [],
        "decision": None,
        "narration": None,
    }
    logger.info("Running NPC agent for NPC %d (%s)", initial_state["npc_id"], initial_state["name"])
    try:
        result = await npc_agent.ainvoke(initial_state)
        logger.info(
            "NPC %d decision: %s — %s",
            initial_state["npc_id"],
            result.get("decision"),
            result.get("narration"),
        )
        # TODO: publish result to qtown.npc.decisions topic
    except Exception as exc:
        logger.error("NPC agent failed for NPC %d: %s", initial_state["npc_id"], exc)


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------


async def consume(stop_event: asyncio.Event | None = None) -> None:
    """Continuously poll Kafka and dispatch messages to handlers."""
    rag = RAGStore()

    consumer = _build_consumer()
    # Subscribe with a regex that matches all configured topic prefixes.
    # confluent-kafka supports regex subscriptions when the pattern starts with '^'.
    regex_pattern = "^(" + "|".join(rf"{t}\..+" for t in TOPIC_PATTERNS) + ")"
    consumer.subscribe([regex_pattern])
    logger.info("Kafka consumer subscribed to pattern: %s", regex_pattern)

    try:
        while not (stop_event and stop_event.is_set()):
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            topic: str = msg.topic()
            try:
                payload: dict = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("Skipping malformed message on '%s': %s", topic, exc)
                continue

            if topic.startswith("qtown.events"):
                await _handle_event(rag, topic, payload)
            elif topic.startswith("qtown.npc"):
                await _handle_npc_message(topic, payload)
            else:
                logger.debug("No handler for topic '%s'", topic)

    finally:
        consumer.close()
        await rag.close()
        logger.info("Kafka consumer shut down cleanly")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    stop_event = asyncio.Event()

    loop = asyncio.new_event_loop()

    def _handle_signal(*_):
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    try:
        loop.run_until_complete(consume(stop_event))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
