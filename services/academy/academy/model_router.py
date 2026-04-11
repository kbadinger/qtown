"""
academy.model_router — public re-export shim.

Tests import from ``academy.model_router`` directly, so this module
re-exports the canonical implementations from ``academy.models.router``.
"""

from __future__ import annotations

from academy.models.router import (
    ROUTE_TABLE,
    ModelTier,
    RouteConfig,
    RoutingStats,
    ModelRouter,
)

__all__ = [
    "ROUTE_TABLE",
    "ModelTier",
    "RouteConfig",
    "RoutingStats",
    "ModelRouter",
]
