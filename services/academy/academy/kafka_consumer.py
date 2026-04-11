"""
Kafka consumer for the Academy service.

Subscribes to:
  ai.request            — inbound AI generation requests
  events.broadcast      — town-wide events (embedded into pgvector for RAG)
  npc.decision.request  — NPC agent decision requests from town-core

Uses aiokafka (consistent with town-core).

Run standalone::

    python -m academy.kafka_consumer
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
import uuid
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger("academy.kafka_consumer")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CONSUMER_GROUP = os.environ.get("KAFKA_CONSUMER_GROUP", "academy-service")

SUBSCRIBED_TOPICS = [
    "ai.request",
    "events.broadcast",
    "npc.decision.request",
]


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------


async def _handle_ai_request(payload: dict[str, Any]) -> None:
    """
    Handle an inbound AI generation request.

    Expected payload keys:
      request_id, task_type, prompt, system (optional), context (optional)

    Publishes the result to ai.response.
    """
    from academy.models.router import ModelRouter
    from academy.kafka_producer import get_producer
    from academy.cost_tracker import record_request

    request_id = payload.get("request_id", str(uuid.uuid4()))
    task_type = payload.get("task_type", "npc_chatter")
    prompt = payload.get("prompt", "")
    system = payload.get("system")

    if not prompt:
        logger.warning("ai.request missing prompt (request_id=%s)", request_id)
        return

    router = ModelRouter()
    cfg = router.ROUTES.get(task_type, router.ROUTES["npc_chatter"])

    t0 = time.monotonic()
    try:
        response = await router.route(task_type, prompt, system=system)
        latency_ms = (time.monotonic() - t0) * 1000.0
    except Exception as exc:
        logger.error("AI request %s failed: %s", request_id, exc)
        return

    stats = router.get_routing_stats()
    await record_request(
        task_type=task_type,
        model=cfg.model_id,
        tokens_in=0,
        tokens_out=0,
        latency_ms=latency_ms,
    )

    producer = await get_producer()
    await producer.emit_ai_response(
        request_id=request_id,
        task_type=task_type,
        content=response,
        model_used=cfg.model_id,
        latency_ms=latency_ms,
    )
    logger.info("Handled ai.request %s → %.0fms", request_id, latency_ms)


async def _handle_event_broadcast(payload: dict[str, Any]) -> None:
    """
    Embed and store a town-wide event in pgvector for RAG retrieval.
    """
    from academy.rag.embeddings import get_event_embedder

    embedder = get_event_embedder()
    doc_id = await embedder.process_event(payload)
    if doc_id:
        logger.debug("Embedded event → %s", doc_id)


async def _handle_npc_decision_request(payload: dict[str, Any]) -> None:
    """
    Run the LangGraph NPC decision agent and publish the result.
    """
    from academy.agents.npc import run_npc_cycle
    from academy.kafka_producer import get_producer

    npc_id = payload.get("npc_id", 0)
    event_data = payload.get("event", {})

    t0 = time.monotonic()
    try:
        result = await run_npc_cycle(str(npc_id), event_data)
        latency_ms = (time.monotonic() - t0) * 1000.0
    except Exception as exc:
        logger.error("NPC agent failed for npc_id=%s: %s", npc_id, exc)
        return

    producer = await get_producer()
    await producer.emit_npc_decision_result(
        npc_id=npc_id,
        decision=result.decision,
        narration=result.narration,
        model_used="langgraph",
        latency_ms=latency_ms,
    )
    logger.info("NPC %d decided: %s (%.0fms)", npc_id, result.decision, latency_ms)


_HANDLERS = {
    "ai.request": _handle_ai_request,
    "events.broadcast": _handle_event_broadcast,
    "npc.decision.request": _handle_npc_decision_request,
}


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------


async def consume(stop_event: asyncio.Event | None = None) -> None:
    """Continuously poll Kafka and dispatch messages to topic handlers."""
    consumer = AIOKafkaConsumer(
        *SUBSCRIBED_TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        max_poll_records=50,
    )

    await consumer.start()
    logger.info("Kafka consumer started — topics: %s", SUBSCRIBED_TOPICS)

    try:
        while not (stop_event and stop_event.is_set()):
            try:
                records = await asyncio.wait_for(
                    consumer.getmany(timeout_ms=1000, max_records=50),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                continue
            except KafkaError as exc:
                logger.error("Kafka error: %s", exc)
                await asyncio.sleep(1.0)
                continue

            for tp, messages in records.items():
                for msg in messages:
                    topic = msg.topic
                    payload = msg.value
                    if not isinstance(payload, dict):
                        logger.warning("Skipping non-dict payload on %s", topic)
                        continue

                    handler = _HANDLERS.get(topic)
                    if handler is None:
                        logger.debug("No handler for topic %s", topic)
                        continue

                    try:
                        await handler(payload)
                    except Exception as exc:
                        logger.error(
                            "Handler for %s raised: %s — skipping message", topic, exc
                        )
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped cleanly")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    loop = asyncio.new_event_loop()
    stop_event = asyncio.Event()

    def _handle_signal(*_: Any) -> None:
        logger.info("Shutdown signal received")
        loop.call_soon_threadsafe(stop_event.set)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    try:
        loop.run_until_complete(consume(stop_event))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
