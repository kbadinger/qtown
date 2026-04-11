"""Async Kafka consumers for Town Core — processes events from other services."""
import asyncio
import json
import logging
import os
from typing import Callable, Awaitable

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger("town-core.kafka.consumer")

# Import these at module level so handlers can use them
from engine.kafka_producer import (
    TOPIC_NPC_TRAVEL_COMPLETE,
    TOPIC_ECONOMY_TRADE_SETTLED,
)


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
                    except Exception:
                        logger.exception(
                            "Handler error for topic=%s offset=%d",
                            msg.topic, msg.offset,
                        )
        except Exception:
            if self._running:
                logger.exception("Consumer loop crashed")

    async def stop(self):
        """Stop the consumer."""
        self._running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Town Core consumer stopped")


async def handle_travel_complete(data: dict) -> None:
    """Handle npc.travel.complete — NPC has arrived or returned from another neighborhood."""
    from engine.db import SessionLocal
    from engine.models import NPC

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
    """Handle economy.trade.settled — apply gold changes from Market District trades."""
    from engine.db import SessionLocal
    from engine.models import NPC

    npc_id = data["npc_id"]
    gold_delta = data["gold_delta"]
    resource = data.get("resource", "unknown")
    trade_id = data.get("trade_id", "")

    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if npc is None:
            logger.warning("trade_settled for unknown NPC %d", npc_id)
            return

        npc.gold += gold_delta
        logger.info("NPC %d (%s) trade settled: gold_delta=%d resource=%s trade=%s",
                    npc_id, npc.name, gold_delta, resource, trade_id)
        db.commit()
    finally:
        db.close()
