"""Kafka consumer that indexes messages into Elasticsearch in real time.

Topics consumed
---------------
- ``events.broadcast``         → qtown-events
- ``ai.content.generated``     → qtown-newspapers  (content_type == "newspaper")
                               → qtown-dialogues   (content_type == "dialogue")
- ``economy.trade.settled``    → qtown-transactions

Batching strategy
-----------------
Documents are buffered up to MAX_BUFFER_SIZE (100) or FLUSH_INTERVAL_SECONDS (5).
Whichever limit is hit first triggers a bulk index call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from aiokafka import AIOKafkaConsumer

from library.elasticsearch_client import get_es_client

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CONSUMER_GROUP_ID = os.getenv("KAFKA_CONSUMER_GROUP", "library-indexer")

TOPICS = [
    "events.broadcast",
    "ai.content.generated",
    "economy.trade.settled",
]

MAX_BUFFER_SIZE = 100
FLUSH_INTERVAL_SECONDS = 5.0


class IndexBuffer:
    """Per-index document buffer with automatic flush on size or time thresholds."""

    def __init__(self, index: str) -> None:
        self.index = index
        self._docs: list[dict[str, Any]] = []
        self._last_flush = time.monotonic()

    def add(self, doc: dict[str, Any]) -> None:
        self._docs.append(doc)

    def should_flush(self) -> bool:
        if len(self._docs) >= MAX_BUFFER_SIZE:
            return True
        if self._docs and (time.monotonic() - self._last_flush) >= FLUSH_INTERVAL_SECONDS:
            return True
        return False

    def drain(self) -> list[dict[str, Any]]:
        docs = self._docs[:]
        self._docs.clear()
        self._last_flush = time.monotonic()
        return docs

    def is_empty(self) -> bool:
        return len(self._docs) == 0


class LibraryConsumer:
    """Kafka consumer that routes messages to the appropriate ES index."""

    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False
        self._buffers: dict[str, IndexBuffer] = {
            "qtown-events": IndexBuffer("qtown-events"),
            "qtown-newspapers": IndexBuffer("qtown-newspapers"),
            "qtown-dialogues": IndexBuffer("qtown-dialogues"),
            "qtown-transactions": IndexBuffer("qtown-transactions"),
        }
        self._flush_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *TOPICS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            max_poll_records=50,
            session_timeout_ms=30_000,
            heartbeat_interval_ms=10_000,
        )
        await self._consumer.start()
        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush(), name="library-flush")
        logger.info("LibraryConsumer started; subscribed to %s", TOPICS)

    async def stop(self) -> None:
        self._running = False
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Flush remaining buffered docs
        await self._flush_all()
        if self._consumer is not None:
            await self._consumer.stop()
        logger.info("LibraryConsumer stopped")

    # ------------------------------------------------------------------
    # Consume loop
    # ------------------------------------------------------------------

    async def consume(self) -> None:
        """Main consume loop — call this as an asyncio task."""
        if self._consumer is None:
            raise RuntimeError("Consumer not started — call start() first")

        async for msg in self._consumer:
            if not self._running:
                break
            try:
                await self._route(msg.topic, msg.value)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Error routing message from topic=%s: %s",
                    msg.topic,
                    exc,
                    exc_info=True,
                )

            # Check every message whether any buffer needs flushing
            for buf in self._buffers.values():
                if buf.should_flush():
                    await self._flush_buffer(buf)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def _route(self, topic: str, payload: dict[str, Any]) -> None:
        if topic == "events.broadcast":
            self._buffers["qtown-events"].add(payload)

        elif topic == "ai.content.generated":
            content_type = payload.get("content_type", "")
            if content_type == "newspaper":
                self._buffers["qtown-newspapers"].add(payload)
            elif content_type == "dialogue":
                self._buffers["qtown-dialogues"].add(payload)
            else:
                logger.debug("Unrecognised content_type %r — skipping", content_type)

        elif topic == "economy.trade.settled":
            self._buffers["qtown-transactions"].add(payload)

        else:
            logger.warning("Received message from unexpected topic: %s", topic)

    # ------------------------------------------------------------------
    # Flushing
    # ------------------------------------------------------------------

    async def _periodic_flush(self) -> None:
        """Background task: flush buffers every FLUSH_INTERVAL_SECONDS regardless of size."""
        while self._running:
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
            await self._flush_all()

    async def _flush_all(self) -> None:
        for buf in self._buffers.values():
            if not buf.is_empty():
                await self._flush_buffer(buf)

    async def _flush_buffer(self, buf: IndexBuffer) -> None:
        docs = buf.drain()
        if not docs:
            return
        es = get_es_client()
        try:
            result = await es.bulk_index(buf.index, docs)
            logger.info(
                "Bulk indexed %d docs → %s (errors=%s)",
                result["success"],
                buf.index,
                result["errors"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Bulk index failed for %s: %s", buf.index, exc, exc_info=True)
            # Put docs back so they are retried on the next flush cycle
            for doc in docs:
                buf.add(doc)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_consumer: LibraryConsumer | None = None


def get_consumer() -> LibraryConsumer:
    global _consumer
    if _consumer is None:
        _consumer = LibraryConsumer()
    return _consumer
