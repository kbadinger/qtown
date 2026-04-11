"""Kafka consumer for the Asset Pipeline.

Listens on ``assets.generate``, triggers a ComfyUI workflow, uploads the
result to S3/R2, and publishes ``assets.generated``.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer

from asset_pipeline.comfyui_client import get_comfyui_client
from asset_pipeline.kafka_producer import get_producer
from asset_pipeline.s3_upload import build_asset_key, upload_image

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CONSUMER_GROUP_ID = os.getenv("KAFKA_CONSUMER_GROUP", "asset-pipeline-worker")
ASSETS_GENERATE_TOPIC = "assets.generate"


class AssetPipelineConsumer:
    """Consumer that processes asset generation requests end-to-end."""

    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            ASSETS_GENERATE_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # Manual commit after successful processing
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            max_poll_records=5,  # Process a few at a time — each job is slow
            session_timeout_ms=60_000,
            heartbeat_interval_ms=20_000,
        )
        await self._consumer.start()
        self._running = True
        logger.info("AssetPipelineConsumer started; listening on %s", ASSETS_GENERATE_TOPIC)

    async def stop(self) -> None:
        self._running = False
        if self._consumer is not None:
            await self._consumer.stop()
        logger.info("AssetPipelineConsumer stopped")

    async def consume(self) -> None:
        """Main processing loop."""
        if self._consumer is None:
            raise RuntimeError("Consumer not started — call start() first")

        async for msg in self._consumer:
            if not self._running:
                break
            try:
                await self._process(msg.value)
                await self._consumer.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to process asset generation request: %s",
                    exc,
                    exc_info=True,
                )
                # Do NOT commit — message will be retried

    async def _process(self, payload: dict[str, Any]) -> None:
        """Process a single asset generation request.

        Expected payload fields
        -----------------------
        request_id: str       — Correlation ID
        asset_type: str       — e.g. "npc-portrait", "building", "newspaper-illustration"
        asset_id: str         — Subject identifier
        prompt: str           — Positive text prompt
        negative_prompt: str  — (optional) Negative text prompt
        width: int            — (optional) Image width, default 512
        height: int           — (optional) Image height, default 512
        workflow: dict        — (optional) Full ComfyUI workflow override
        metadata: dict        — (optional) Arbitrary metadata
        """
        request_id: str = payload.get("request_id") or str(uuid.uuid4())
        asset_type: str = payload.get("asset_type", "generic")
        asset_id: str = payload.get("asset_id", "unknown")
        prompt: str = payload["prompt"]
        negative_prompt: str = payload.get("negative_prompt", "")
        width: int = int(payload.get("width", 512))
        height: int = int(payload.get("height", 512))
        workflow_override: dict[str, Any] | None = payload.get("workflow")
        metadata: dict[str, Any] = payload.get("metadata", {})

        logger.info(
            "Processing request_id=%s asset_type=%s asset_id=%s",
            request_id,
            asset_type,
            asset_id,
        )

        # 1. Submit to ComfyUI
        comfyui = get_comfyui_client()
        prompt_id = await comfyui.submit_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            workflow_override=workflow_override,
        )

        # 2. Poll until done
        images = await comfyui.poll_for_result(prompt_id)

        if not images:
            raise RuntimeError(f"No images returned for request_id={request_id}")

        # 3. Download the first image
        first_image = images[0]
        image_bytes = await comfyui.download_image(
            filename=first_image["filename"],
            subfolder=first_image.get("subfolder", ""),
            image_type=first_image.get("type", "output"),
        )

        # 4. Build S3 key and upload
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
        filename = f"{ts}-{request_id}.png"
        key = build_asset_key(asset_type, asset_id, filename)

        s3_metadata = {
            "request_id": request_id,
            "asset_type": asset_type,
            "asset_id": asset_id,
            "comfyui_prompt_id": prompt_id,
        }
        cdn_url = await upload_image(
            image_bytes=image_bytes,
            key=key,
            content_type="image/png",
            extra_metadata=s3_metadata,
        )

        # 5. Publish assets.generated
        producer = get_producer()
        await producer.publish_asset_generated(
            request_id=request_id,
            asset_type=asset_type,
            asset_id=asset_id,
            cdn_url=cdn_url,
            prompt=prompt,
            metadata=metadata,
        )

        logger.info(
            "Completed request_id=%s  cdn_url=%s",
            request_id,
            cdn_url,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_consumer: AssetPipelineConsumer | None = None


def get_consumer() -> AssetPipelineConsumer:
    global _consumer
    if _consumer is None:
        _consumer = AssetPipelineConsumer()
    return _consumer
