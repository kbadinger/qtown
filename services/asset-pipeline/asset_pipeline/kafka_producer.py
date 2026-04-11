"""Kafka producer for the Asset Pipeline service.

Produces ``assets.generated`` events once a CDN URL is ready.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ASSETS_GENERATED_TOPIC = "assets.generated"


class AssetProducer:
    """Thin async wrapper around AIOKafkaProducer."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            compression_type="gzip",
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()
        logger.info("AssetProducer started")

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            logger.info("AssetProducer stopped")

    @property
    def producer(self) -> AIOKafkaProducer:
        if self._producer is None:
            raise RuntimeError("AssetProducer not started — call start() first")
        return self._producer

    async def publish_asset_generated(
        self,
        request_id: str,
        asset_type: str,
        asset_id: str,
        cdn_url: str,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Publish an ``assets.generated`` event.

        Parameters
        ----------
        request_id:
            Correlation ID from the original ``assets.generate`` request.
        asset_type:
            Category, e.g. ``npc-portrait``, ``building``, ``newspaper-illustration``.
        asset_id:
            Identifier of the subject (NPC id, building id, etc.).
        cdn_url:
            Public CDN URL of the generated image.
        prompt:
            The text prompt used for generation.
        metadata:
            Optional free-form metadata.
        """
        payload: dict[str, Any] = {
            "request_id": request_id,
            "asset_type": asset_type,
            "asset_id": asset_id,
            "cdn_url": cdn_url,
            "prompt": prompt,
            "metadata": metadata or {},
        }
        await self.producer.send_and_wait(
            ASSETS_GENERATED_TOPIC,
            key=request_id,
            value=payload,
        )
        logger.info(
            "Published assets.generated: request_id=%s asset_type=%s cdn_url=%s",
            request_id,
            asset_type,
            cdn_url,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_producer: AssetProducer | None = None


def get_producer() -> AssetProducer:
    global _producer
    if _producer is None:
        _producer = AssetProducer()
    return _producer
