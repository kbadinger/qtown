"""
Academy service entry point.

Starts:
  - FastAPI application (HTTP on port 8001, served via uvicorn)
  - gRPC server on port 50053 (background thread)
  - Kafka consumer (background asyncio task)
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger("academy")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)


# ---------------------------------------------------------------------------
# gRPC server
# ---------------------------------------------------------------------------


def _start_grpc_server(port: int = 50053) -> None:
    """Start the gRPC server in its own thread (blocking call)."""
    from academy.grpc_server import serve

    logger.info("Starting gRPC server on port %d", port)
    try:
        serve(port)
    except Exception as exc:
        logger.error("gRPC server crashed: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------


_kafka_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _kafka_task
    logger.info("academy service starting up")

    # ---- Cost tracker DB init (best-effort) ----
    try:
        from academy.cost_tracker import ensure_table
        await ensure_table()
    except Exception as exc:
        logger.warning("Cost tracker DB init failed (non-fatal): %s", exc)

    # ---- gRPC server in a daemon thread ----
    grpc_port = int(os.environ.get("GRPC_PORT", "50053"))
    grpc_thread = threading.Thread(
        target=_start_grpc_server,
        args=(grpc_port,),
        daemon=True,
        name="grpc-server",
    )
    grpc_thread.start()

    # ---- Kafka consumer as background asyncio task ----
    kafka_enabled = os.environ.get("KAFKA_ENABLED", "true").lower() not in ("0", "false", "no")
    if kafka_enabled:
        try:
            from academy.kafka_consumer import consume

            stop_event = asyncio.Event()
            _kafka_task = asyncio.create_task(consume(stop_event))
            app.state.kafka_stop = stop_event
        except Exception as exc:
            logger.warning("Kafka consumer failed to start (non-fatal): %s", exc)

    yield

    # ---- Shutdown ----
    logger.info("academy service shutting down")

    if _kafka_task is not None:
        try:
            app.state.kafka_stop.set()
            await asyncio.wait_for(_kafka_task, timeout=5.0)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("Kafka consumer shutdown: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Qtown Academy",
    version="2.0.0",
    description="NPC intelligence, model routing, and RAG for Qtown v2",
    lifespan=lifespan,
)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    from academy.ollama_client import get_client

    client = get_client()
    ollama_ok = await client.is_available()

    return JSONResponse({
        "status": "ok",
        "service": "academy",
        "version": "2.0.0",
        "dependencies": {
            "ollama": "ok" if ollama_ok else "unavailable",
        },
    })


@app.get("/metrics/model-routing", tags=["metrics"])
async def model_routing_metrics() -> JSONResponse:
    """
    Aggregate routing and cost statistics.

    Shape::

        {
            "total_requests": int,
            "local_pct": float,
            "cloud_pct": float,
            "avg_latency_ms": float,
            "cost_today_usd": float,
            "by_model": [...]
        }
    """
    from academy.cost_tracker import get_metrics, get_db_metrics_today
    from academy.models.router import ModelRouter

    # In-memory fast path
    router = ModelRouter()
    router_stats = router.get_routing_stats()

    # DB ground truth for today (may fail gracefully)
    try:
        db_stats = await get_db_metrics_today()
    except Exception:
        db_stats = {}

    return JSONResponse({
        **router_stats,
        "db_today": db_stats,
    })


@app.get("/metrics/models", tags=["metrics"])
async def available_models() -> JSONResponse:
    """List models currently available in Ollama."""
    from academy.ollama_client import get_client

    client = get_client()
    try:
        models = await client.list_models()
        return JSONResponse({"models": models, "count": len(models)})
    except Exception as exc:
        return JSONResponse({"error": str(exc), "models": []}, status_code=503)


@app.post("/generate/dialogue", tags=["generation"])
async def generate_dialogue(body: dict[str, Any]) -> JSONResponse:
    """
    HTTP convenience wrapper around the GenerateDialogue gRPC RPC.

    Body: { npc_id_a, npc_id_b, context, tone }
    """
    from academy.models.router import ModelRouter

    npc_a = body.get("npc_id_a", 1)
    npc_b = body.get("npc_id_b", 2)
    tone = body.get("tone", "friendly")
    ctx = body.get("context", "They meet in the town square.")

    router = ModelRouter()
    prompt = (
        f"Write a {tone} conversation between NPC #{npc_a} and NPC #{npc_b}. "
        f"Context: {ctx}"
    )
    system = (
        "You are a dialogue writer for a medieval fantasy simulation. "
        "Write engaging, character-appropriate dialogue."
    )
    response = await router.route("npc_dialogue", prompt, system=system)
    cfg = router.ROUTES["npc_dialogue"]
    return JSONResponse({"dialogue": response, "model_used": cfg.model_id})


@app.post("/generate/newspaper", tags=["generation"])
async def generate_newspaper(body: dict[str, Any]) -> JSONResponse:
    """HTTP wrapper for newspaper generation."""
    from academy.models.router import ModelRouter

    tick = body.get("tick", 0)
    max_articles = body.get("max_articles", 3)

    router = ModelRouter()
    system = (
        "You are the editor of The Qtown Gazette. "
        "Write concise news articles about events in a medieval fantasy town."
    )
    prompt = (
        f"Generate {max_articles} articles for Tick {tick}. "
        "Include: HEADLINE:, CATEGORY:, BODY: for each. Separate with ---"
    )
    response = await router.route("newspaper", prompt, system=system)
    cfg = router.ROUTES["newspaper"]
    return JSONResponse({"raw": response, "tick": tick, "model_used": cfg.model_id})


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    http_port = int(os.environ.get("HTTP_PORT", "8001"))
    uvicorn.run(
        "academy.main:app",
        host="0.0.0.0",
        port=http_port,
        reload=False,
        log_level="info",
    )
