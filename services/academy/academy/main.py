"""
Academy service entry point.

Starts:
  - FastAPI application (HTTP on port 8001, served via uvicorn)
  - gRPC server on port 50053 (placeholder, spun up in a background thread)
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger("academy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


# ---------------------------------------------------------------------------
# gRPC server placeholder
# ---------------------------------------------------------------------------

def _start_grpc_server(port: int = 50053) -> None:
    """
    Placeholder for the gRPC server.

    Replace the body of this function with real tonic / grpcio setup once
    the .proto files are compiled.
    """
    logger.info("gRPC server placeholder listening on port %d (not yet implemented)", port)
    # Example once proto stubs are generated:
    #
    # from concurrent import futures
    # import grpc
    # from academy_pb2_grpc import add_AcademyServicer_to_server, AcademyServicer
    #
    # server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # add_AcademyServicer_to_server(AcademyServicer(), server)
    # server.add_insecure_port(f"[::]:{port}")
    # server.start()
    # server.wait_for_termination()


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("academy service starting up")

    grpc_port = int(os.environ.get("GRPC_PORT", "50053"))
    grpc_thread = threading.Thread(
        target=_start_grpc_server,
        args=(grpc_port,),
        daemon=True,
        name="grpc-server",
    )
    grpc_thread.start()

    yield

    logger.info("academy service shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Qtown Academy",
    version="0.1.0",
    description="NPC intelligence, model routing, and RAG for Qtown v2",
    lifespan=lifespan,
)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "academy"})


@app.get("/metrics/model-routing", tags=["metrics"])
async def model_routing_metrics() -> JSONResponse:
    """
    Returns aggregate cost and routing statistics for the ModelRouter.
    The real implementation will query the ModelRouter's in-memory cost tracker.
    """
    from academy.models.router import ModelRouter  # imported lazily to avoid circular issues

    router = ModelRouter()
    return JSONResponse(
        {
            "total_requests": router.total_requests,
            "total_cost_tokens": router.total_cost_tokens,
            "routes": router.ROUTES,
        }
    )


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
