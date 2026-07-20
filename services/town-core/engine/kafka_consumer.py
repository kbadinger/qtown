"""Async Kafka consumers for Town Core — processes events from other services."""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Callable, Awaitable

from aiokafka import AIOKafkaConsumer
from sqlalchemy.exc import IntegrityError

# Imported at module level so the async handlers — and their tests' patches —
# can reach them as engine.kafka_consumer.SessionLocal / .NPC.
from engine.db import SessionLocal
from engine.models import NPC, ProcessedTrade
from engine.kafka_producer import emit_event

logger = logging.getLogger("town-core.kafka.consumer")

# Failed messages are routed to "<topic>.dlq" for inspection + replay.
DLQ_SUFFIX = ".dlq"


class TownCoreConsumer:
    """Consumes Kafka messages relevant to Town Core and dispatches to handlers."""

    def __init__(self):
        brokers = os.environ.get("KAFKA_BROKERS", "localhost:9092")
        self.brokers = brokers
        self.consumer: AIOKafkaConsumer | None = None
        self._handlers: dict[str, Callable] = {}
        self._running = False

    def register_handler(self, topic: str, handler: Callable[[dict], Awaitable[None]]):
        """Register an async handler for a topic."""
        self._handlers[topic] = handler

    async def start(self):
        """Start consuming from all registered topics."""
        if not self._handlers:
            logger.warning("No handlers registered, skipping consumer start")
            return

        topics = list(self._handlers.keys())
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.brokers,
            group_id="town-core",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        self._running = True
        logger.info("Town Core consumer started — topics: %s", topics)

        asyncio.create_task(self._consume_loop())

    async def _consume_loop(self):
        """Main consumer loop — dispatches messages to registered handlers."""
        try:
            async for msg in self.consumer:
                handler = self._handlers.get(msg.topic)
                if handler:
                    try:
                        await handler(msg.value)
                    except Exception as exc:
                        logger.exception(
                            "Handler error for topic=%s offset=%d",
                            msg.topic, msg.offset,
                        )
                        await self._send_to_dlq(msg, exc)
        except Exception:
            if self._running:
                logger.exception("Consumer loop crashed")

    async def _send_to_dlq(self, msg, exc: Exception) -> None:
        """Route a message whose handler raised to a dead-letter topic.

        The DLQ record preserves the original topic + payload so it can be
        replayed later (see ``replay_dlq_record``). A DLQ produce failure is
        logged but never re-raised — it must not crash the consume loop.
        """
        dlq_topic = f"{msg.topic}{DLQ_SUFFIX}"
        key = msg.key.decode("utf-8") if getattr(msg, "key", None) else ""
        record = {
            "original_topic": msg.topic,
            "key": key or None,
            "value": msg.value,
            "error": repr(exc),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await emit_event(dlq_topic, key=key, value=record)
            logger.info("routed failed message to DLQ %s", dlq_topic)
        except Exception:
            logger.exception("failed to route message to DLQ %s", dlq_topic)

    async def stop(self):
        """Stop the consumer."""
        self._running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Town Core consumer stopped")


async def handle_travel_complete(data: dict) -> None:
    """Handle npc.travel.complete — NPC has arrived or returned from another neighborhood."""
    npc_id = data["npc_id"]
    status = data.get("status", "ok")
    gold_delta = data.get("gold_delta", 0)
    new_neighborhood = data.get("neighborhood", "town_core")

    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if npc is None:
            logger.warning("travel_complete for unknown NPC %d", npc_id)
            return

        # Clear traveling state
        npc.traveling = False
        npc.travel_destination = None

        if status == "ok":
            npc.neighborhood = new_neighborhood
            npc.gold += gold_delta
            logger.info("NPC %d (%s) arrived at %s, gold_delta=%d",
                        npc_id, npc.name, new_neighborhood, gold_delta)
        else:
            # Travel failed — NPC stays where they were
            logger.info("NPC %d (%s) travel failed: %s",
                        npc_id, npc.name, data.get("reason", "unknown"))

        db.commit()
    finally:
        db.close()


async def handle_trade_settled(data: dict) -> None:
    """Handle economy.trade.settled — apply gold changes from Market District trades.

    Idempotent: keyed on (trade_id, npc_id) via ProcessedTrade, so a redelivered
    or replayed message never double-credits gold (buyer and seller messages share
    a trade_id, hence the compound key). The gold update and the idempotency record
    commit atomically — a replay after a crash either applied both or neither.
    """
    npc_id = data["npc_id"]
    gold_delta = data["gold_delta"]
    resource = data.get("resource", "unknown")
    trade_id = data.get("trade_id", "")

    db = SessionLocal()
    try:
        if trade_id:
            already = db.query(ProcessedTrade).filter(
                ProcessedTrade.trade_id == trade_id,
                ProcessedTrade.npc_id == npc_id,
            ).first()
            if already is not None:
                logger.info("trade_settled replay ignored: trade=%s npc=%s",
                            trade_id, npc_id)
                return

        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if npc is None:
            logger.warning("trade_settled for unknown NPC %s", npc_id)
            return

        npc.gold += gold_delta
        if trade_id:
            db.add(ProcessedTrade(trade_id=trade_id, npc_id=npc_id, gold_delta=gold_delta))
        logger.info("NPC %s (%s) trade settled: gold_delta=%d resource=%s trade=%s",
                    npc_id, npc.name, gold_delta, resource, trade_id)
        try:
            db.commit()
        except IntegrityError:
            # A concurrent/duplicate delivery already recorded this (trade_id,
            # npc_id); rollback undoes our gold delta too, keeping it applied once.
            db.rollback()
            logger.info("trade_settled duplicate on commit: trade=%s npc=%s",
                        trade_id, npc_id)
    finally:
        db.close()


async def replay_dlq_record(record: dict, handler: Callable[[dict], Awaitable[None]]) -> None:
    """Re-dispatch a DLQ record's original payload through its handler.

    The replay path for the dead-letter queue: because the trade handler is
    idempotent, replaying a recovered message is safe (no double-credit).
    """
    await handler(record["value"])
