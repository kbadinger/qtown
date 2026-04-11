"""
Cost tracking for Academy generation requests.

Persists every inference call to the academy.generation_costs Postgres table
and exposes an aggregate metrics endpoint consumed by FastAPI.

Table schema (created by init-db.sql or the ensure_table() call below)::

    CREATE TABLE academy.generation_costs (
        id          BIGSERIAL PRIMARY KEY,
        task_type   TEXT NOT NULL,
        model       TEXT NOT NULL,
        tokens_in   INT  NOT NULL DEFAULT 0,
        tokens_out  INT  NOT NULL DEFAULT 0,
        latency_ms  FLOAT NOT NULL,
        cost_usd    FLOAT NOT NULL DEFAULT 0.0,
        created_at  TIMESTAMPTZ DEFAULT now()
    );
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("academy.cost_tracker")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://qtown:qtown@localhost:5432/qtown"
)

# ---------------------------------------------------------------------------
# In-memory aggregates (fast path; DB is ground truth)
# ---------------------------------------------------------------------------


@dataclass
class InMemoryCostStore:
    total_requests: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    latencies: list[float] = field(default_factory=list)
    cost_by_model: dict[str, float] = field(default_factory=dict)
    requests_by_model: dict[str, int] = field(default_factory=dict)
    latency_by_model: dict[str, list[float]] = field(default_factory=dict)

    def record(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        cost_usd: float,
    ) -> None:
        self.total_requests += 1
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        self.total_cost_usd += cost_usd
        self.latencies.append(latency_ms)

        self.cost_by_model[model] = self.cost_by_model.get(model, 0.0) + cost_usd
        self.requests_by_model[model] = self.requests_by_model.get(model, 0) + 1
        self.latency_by_model.setdefault(model, []).append(latency_ms)


_store = InMemoryCostStore()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

_engine: Any = None


async def _get_engine() -> Any:
    global _engine
    if _engine is not None:
        return _engine

    from sqlalchemy.ext.asyncio import create_async_engine

    _engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    return _engine


async def ensure_table() -> None:
    """Create academy.generation_costs if it doesn't exist."""
    from sqlalchemy import text as sa_text

    ddl = """
        CREATE SCHEMA IF NOT EXISTS academy;

        CREATE TABLE IF NOT EXISTS academy.generation_costs (
            id          BIGSERIAL PRIMARY KEY,
            task_type   TEXT NOT NULL,
            model       TEXT NOT NULL,
            tokens_in   INT  NOT NULL DEFAULT 0,
            tokens_out  INT  NOT NULL DEFAULT 0,
            latency_ms  FLOAT NOT NULL,
            cost_usd    FLOAT NOT NULL DEFAULT 0.0,
            created_at  TIMESTAMPTZ DEFAULT now()
        );
    """
    engine = await _get_engine()
    async with engine.begin() as conn:
        await conn.execute(sa_text(ddl))
    logger.info("academy.generation_costs table ready")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def record_request(
    *,
    task_type: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    cost_usd: float = 0.0,
) -> None:
    """
    Persist one generation request to DB and update in-memory counters.

    This is fire-and-forget from the caller's perspective; errors are logged
    but not re-raised so they never interrupt the generation path.
    """
    # In-memory update is synchronous and always succeeds
    _store.record(model, tokens_in, tokens_out, latency_ms, cost_usd)

    # Async DB write
    try:
        from sqlalchemy import text as sa_text

        sql = """
            INSERT INTO academy.generation_costs
                (task_type, model, tokens_in, tokens_out, latency_ms, cost_usd)
            VALUES (:task_type, :model, :tokens_in, :tokens_out, :latency_ms, :cost_usd)
        """
        engine = await _get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                sa_text(sql),
                {
                    "task_type": task_type,
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": latency_ms,
                    "cost_usd": cost_usd,
                },
            )
    except Exception as exc:
        logger.error("Failed to persist cost record: %s", exc)


def get_metrics() -> dict[str, Any]:
    """
    Return aggregate routing/cost metrics suitable for the FastAPI endpoint.

    Shape::

        {
            "total_requests": int,
            "local_pct": float,      # always 0 here; router provides this
            "avg_latency_ms": float,
            "cost_today_usd": float,
            "cost_by_model": { model: float, ... },
        }
    """
    s = _store
    avg_lat = sum(s.latencies) / max(len(s.latencies), 1)

    by_model = [
        {
            "model": model,
            "requests": s.requests_by_model.get(model, 0),
            "avg_latency_ms": round(
                sum(s.latency_by_model.get(model, [0])) /
                max(len(s.latency_by_model.get(model, [1])), 1),
                2,
            ),
            "cost_usd": round(s.cost_by_model.get(model, 0.0), 6),
        }
        for model in s.requests_by_model
    ]

    return {
        "total_requests": s.total_requests,
        "avg_latency_ms": round(avg_lat, 2),
        "cost_today_usd": round(s.total_cost_usd, 6),
        "cost_by_model": by_model,
    }


async def get_db_metrics_today() -> dict[str, Any]:
    """
    Query Postgres for today's aggregate metrics (authoritative ground truth).
    """
    from sqlalchemy import text as sa_text

    sql = """
        SELECT
            model,
            COUNT(*)            AS request_count,
            AVG(latency_ms)     AS avg_latency_ms,
            SUM(cost_usd)       AS total_cost_usd
        FROM academy.generation_costs
        WHERE created_at >= CURRENT_DATE
        GROUP BY model
        ORDER BY request_count DESC
    """
    try:
        engine = await _get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(sa_text(sql))
            rows = result.fetchall()

        total_req = sum(row.request_count for row in rows)
        total_cost = sum(row.total_cost_usd for row in rows)

        by_model = [
            {
                "model": row.model,
                "requests": row.request_count,
                "avg_latency_ms": round(float(row.avg_latency_ms or 0), 2),
                "cost_usd": round(float(row.total_cost_usd or 0), 6),
            }
            for row in rows
        ]

        return {
            "total_requests": total_req,
            "cost_today_usd": round(total_cost, 6),
            "by_model": by_model,
        }
    except Exception as exc:
        logger.warning("DB metrics query failed: %s", exc)
        return get_metrics()  # fall back to in-memory
