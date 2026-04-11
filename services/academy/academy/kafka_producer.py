"""
Kafka producer for the Academy service.

Topics emitted:
  ai.response            — response to ai.request messages (request-reply)
  ai.content.generated   — generated content (dialogues, newspapers, quest text)
                           consumed by Tavern, Library, etc.
  npc.decision.result    — NPC agent decision results → town-core

Uses aiokafka (consistent with town-core).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger("academy.kafka_producer")

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Topic names
TOPIC_AI_RESPONSE = "ai.response"
TOPIC_CONTENT_GENERATED = "ai.content.generated"
TOPIC_NPC_DECISION_RESULT = "npc.decision.result"


# ---------------------------------------------------------------------------
# Producer wrapper
# ---------------------------------------------------------------------------


class AcademyProducer:
    """
    aiokafka producer with a simple typed interface for Academy messages.

    Must be started before use and stopped during shutdown::

        producer = AcademyProducer()
        await producer.start()
        ...
        await producer.stop()

    Or use as an async context manager::

        async with AcademyProducer() as producer:
            await producer.emit_ai_response(...)
    """

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        self._bootstrap = bootstrap_servers or KAFKA_BOOTSTRAP
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
            acks="all",
            enable_idempotence=True,
            compression_type="gzip",
        )
        await self._producer.start()
        logger.info("Kafka producer started (bootstrap=%s)", self._bootstrap)

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    async def __aenter__(self) -> "AcademyProducer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Emit helpers
    # ------------------------------------------------------------------

    async def _send(
        self, topic: str, value: dict[str, Any], key: str | None = None
    ) -> None:
        """Send a single message and wait for acknowledgement."""
        if not self._producer:
            raise RuntimeError("Producer not started; call await producer.start() first")
        try:
            await self._producer.send_and_wait(topic, value=value, key=key)
            logger.debug("Sent to %s key=%s", topic, key)
        except KafkaError as exc:
            logger.error("Failed to send to %s: %s", topic, exc)
            raise

    async def emit_ai_response(
        self,
        *,
        request_id: str,
        task_type: str,
        content: str,
        model_used: str,
        latency_ms: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """
        Publish a response to an ai.request on the ai.response topic.

        The ``request_id`` is used as the Kafka message key so consumers
        can correlate request and response.
        """
        payload: dict[str, Any] = {
            "request_id": request_id,
            "task_type": task_type,
            "content": content,
            "model_used": model_used,
            "latency_ms": latency_ms,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "timestamp": time.time(),
        }
        await self._send(TOPIC_AI_RESPONSE, payload, key=request_id)

    async def emit_content_generated(
        self,
        *,
        content_type: str,  # "dialogue" | "newspaper" | "quest"
        content_id: str,
        content: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Publish newly generated content to ai.content.generated.

        Downstream consumers (Tavern, Library) subscribe to this topic.
        ``content`` should be a JSON-serialisable object.
        """
        payload: dict[str, Any] = {
            "content_type": content_type,
            "content_id": content_id,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        await self._send(TOPIC_CONTENT_GENERATED, payload, key=f"{content_type}:{content_id}")

    async def emit_npc_decision_result(
        self,
        *,
        npc_id: int,
        decision: str,
        narration: str,
        model_used: str,
        latency_ms: float,
        trace: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Publish an NPC agent decision result to npc.decision.result.

        town-core subscribes to this topic to update NPC state.
        """
        payload: dict[str, Any] = {
            "npc_id": npc_id,
            "decision": decision,
            "narration": narration,
            "model_used": model_used,
            "latency_ms": latency_ms,
            "trace": trace or [],
            "timestamp": time.time(),
        }
        await self._send(TOPIC_NPC_DECISION_RESULT, payload, key=str(npc_id))


# ---------------------------------------------------------------------------
# Module-level singleton with lazy start
# ---------------------------------------------------------------------------

_producer: AcademyProducer | None = None
_start_lock = asyncio.Lock()


async def get_producer() -> AcademyProducer:
    """Return (and lazily start) the module-level producer singleton."""
    global _producer
    if _producer is not None:
        return _producer

    async with _start_lock:
        if _producer is None:
            _producer = AcademyProducer()
            try:
                await _producer.start()
            except Exception as exc:
                logger.warning("Kafka producer failed to start: %s — operating in degraded mode", exc)
                _producer = _NoopProducer()  # type: ignore[assignment]

    return _producer  # type: ignore[return-value]


class _NoopProducer(AcademyProducer):
    """Fallback when Kafka is unavailable — logs but does not raise."""

    async def _send(self, topic: str, value: dict[str, Any], key: str | None = None) -> None:
        logger.warning("Kafka unavailable; dropping message to %s key=%s", topic, key)
