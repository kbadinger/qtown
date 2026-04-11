"""Qtown Asset Pipeline Service — FastAPI application (port 8005).

Handles image generation requests by consuming ``assets.generate`` Kafka
messages, submitting workflows to ComfyUI, uploading results to S3/R2, and
publishing ``assets.generated`` events.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from asset_pipeline.comfyui_client import get_comfyui_client
from asset_pipeline.kafka_consumer import get_consumer
from asset_pipeline.kafka_producer import get_producer

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- startup ---
    comfyui = get_comfyui_client()
    await comfyui.start()

    producer = get_producer()
    await producer.start()

    consumer = get_consumer()
    await consumer.start()
    consume_task = asyncio.create_task(consumer.consume(), name="asset-pipeline-consumer")

    logger.info("Asset pipeline service startup complete")
    yield

    # --- shutdown ---
    consume_task.cancel()
    try:
        await consume_task
    except asyncio.CancelledError:
        pass
    await consumer.stop()
    await producer.stop()
    await comfyui.close()
    logger.info("Asset pipeline service shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Qtown Asset Pipeline",
    description="AI image generation pipeline using ComfyUI + S3/R2",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    asset_type: str = Field(..., description="Category, e.g. npc-portrait, building")
    asset_id: str = Field(..., description="Subject identifier")
    prompt: str = Field(..., min_length=1, description="Positive text prompt")
    negative_prompt: str = Field(default="", description="Negative text prompt")
    width: int = Field(default=512, ge=64, le=2048)
    height: int = Field(default=512, ge=64, le=2048)
    metadata: dict = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    request_id: str
    cdn_url: str
    asset_type: str
    asset_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    comfyui_status = "unknown"
    try:
        comfyui = get_comfyui_client()
        resp = await comfyui.http.get("/system_stats", timeout=3.0)
        comfyui_status = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        comfyui_status = f"error: {exc}"

    return {"status": "ok", "comfyui": comfyui_status}


@app.post("/generate", response_model=GenerateResponse, tags=["generation"])
async def generate_asset(body: GenerateRequest) -> GenerateResponse:
    """Synchronously generate an asset via ComfyUI and upload to S3/R2.

    Returns the CDN URL of the generated image.
    This endpoint blocks until generation completes — use the Kafka consumer
    for fire-and-forget workflows.
    """
    import uuid as _uuid

    request_id = str(_uuid.uuid4())

    comfyui = get_comfyui_client()
    try:
        prompt_id = await comfyui.submit_workflow(
            prompt=body.prompt,
            negative_prompt=body.negative_prompt,
            width=body.width,
            height=body.height,
        )
        images = await comfyui.poll_for_result(prompt_id)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("ComfyUI generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    if not images:
        raise HTTPException(status_code=500, detail="No images returned by ComfyUI")

    first_image = images[0]
    image_bytes = await comfyui.download_image(
        filename=first_image["filename"],
        subfolder=first_image.get("subfolder", ""),
    )

    from datetime import datetime, timezone as _tz
    from asset_pipeline.s3_upload import build_asset_key, upload_image

    ts = datetime.now(tz=_tz.utc).strftime("%Y%m%d%H%M%S")
    key = build_asset_key(body.asset_type, body.asset_id, f"{ts}-{request_id}.png")

    try:
        cdn_url = await upload_image(image_bytes=image_bytes, key=key)
    except Exception as exc:
        logger.error("S3 upload failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    # Publish event (non-blocking — don't fail the request if this fails)
    try:
        producer = get_producer()
        await producer.publish_asset_generated(
            request_id=request_id,
            asset_type=body.asset_type,
            asset_id=body.asset_id,
            cdn_url=cdn_url,
            prompt=body.prompt,
            metadata=body.metadata,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to publish assets.generated event: %s", exc)

    return GenerateResponse(
        request_id=request_id,
        cdn_url=cdn_url,
        asset_type=body.asset_type,
        asset_id=body.asset_id,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "asset_pipeline.main:app",
        host="0.0.0.0",
        port=8005,
        reload=False,
        log_level="info",
    )
