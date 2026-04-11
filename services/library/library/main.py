"""Qtown Library Service — FastAPI application (port 8004).

Endpoints
---------
GET /health
GET /search?q=...&types=...&limit=20&offset=0
GET /aggregations/events-per-day?days=30
GET /aggregations/resource-trends?resource=gold&days=30
GET /aggregations/economic-indicators
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from library.elasticsearch_client import get_es_client
from library.index_templates import INDEX_NAMES
from library.kafka_consumer import get_consumer

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
    es = get_es_client()
    await es.connect()

    consumer = get_consumer()
    await consumer.start()
    consume_task = asyncio.create_task(consumer.consume(), name="library-consumer")
    logger.info("Library service startup complete")

    yield

    # --- shutdown ---
    consume_task.cancel()
    try:
        await consume_task
    except asyncio.CancelledError:
        pass
    await consumer.stop()
    await es.close()
    logger.info("Library service shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Qtown Library",
    description="Full-text search and aggregation over Qtown history",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    es = get_es_client()
    try:
        info = await es.client.info()
        es_status = "ok"
        es_version = info["version"]["number"]
    except Exception as exc:  # noqa: BLE001
        es_status = f"error: {exc}"
        es_version = "unknown"
    return {
        "status": "ok",
        "elasticsearch": es_status,
        "elasticsearch_version": es_version,
    }


@app.get("/search", tags=["search"])
async def search(
    q: str = Query(..., min_length=1, description="Full-text search query"),
    types: str | None = Query(
        None,
        description="Comma-separated list of index types to search: events, newspapers, dialogues, transactions",
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict:
    """Full-text search across all Qtown indices (or a filtered subset)."""
    # Resolve requested indices
    type_map = {
        "events": "qtown-events",
        "newspapers": "qtown-newspapers",
        "dialogues": "qtown-dialogues",
        "transactions": "qtown-transactions",
    }

    if types:
        requested = [t.strip().lower() for t in types.split(",") if t.strip()]
        unknown = [r for r in requested if r not in type_map]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown type(s): {unknown}. Valid types: {list(type_map.keys())}",
            )
        indices = [type_map[r] for r in requested]
    else:
        indices = INDEX_NAMES

    es = get_es_client()
    try:
        result = await es.search(query=q, indices=indices, limit=limit, offset=offset)
    except Exception as exc:
        logger.error("Search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search error: {exc}") from exc

    return {
        "query": q,
        "indices": indices,
        "total": result["total"],
        "took_ms": result["took_ms"],
        "limit": limit,
        "offset": offset,
        "hits": result["hits"],
    }


@app.get("/aggregations/events-per-day", tags=["aggregations"])
async def events_per_day(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
) -> dict:
    """Return a daily histogram of events for the last *days* days."""
    es = get_es_client()
    try:
        buckets = await es.events_per_day(days=days)
    except Exception as exc:
        logger.error("events_per_day aggregation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Aggregation error: {exc}") from exc

    return {"days": days, "data": buckets}


@app.get("/aggregations/resource-trends", tags=["aggregations"])
async def resource_trends(
    resource: str = Query(..., description="Resource name, e.g. gold, wheat, iron"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
) -> dict:
    """Return price and volume trends for a given resource."""
    es = get_es_client()
    try:
        data = await es.resource_trends(resource=resource, days=days)
    except Exception as exc:
        logger.error("resource_trends aggregation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Aggregation error: {exc}") from exc

    return {"resource": resource, "days": days, "data": data}


@app.get("/aggregations/economic-indicators", tags=["aggregations"])
async def economic_indicators() -> dict:
    """Return current economic indicators: gold supply, trade volume, GDP proxy."""
    es = get_es_client()
    try:
        indicators = await es.economic_indicators()
    except Exception as exc:
        logger.error("economic_indicators aggregation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Aggregation error: {exc}") from exc

    return indicators


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "library.main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info",
    )
