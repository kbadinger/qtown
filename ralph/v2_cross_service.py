"""
v2_cross_service.py — Cross-service story detection and execution planning.

Determines when a story touches multiple services and builds an ExecutionPlan
that sequences work correctly (proto changes always first).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known services and their proto dependencies
# ---------------------------------------------------------------------------

ALL_SERVICES = [
    "town-core",
    "market-district",
    "fortress",
    "academy",
    "tavern",
    "cartographer",
    "library",
    "asset-pipeline",
]

# Canonical service name aliases (handles hyphen/underscore/camel variants)
SERVICE_ALIASES: dict[str, str] = {
    "town_core": "town-core",
    "towncore": "town-core",
    "market_district": "market-district",
    "marketdistrict": "market-district",
    "asset_pipeline": "asset-pipeline",
    "assetpipeline": "asset-pipeline",
}

# Services that own proto definitions
PROTO_OWNING_SERVICES = {"town-core", "market-district", "fortress", "academy"}

# Keywords in story titles that imply proto changes
PROTO_KEYWORDS = {
    "proto", "protobuf", "grpc", "buf generate", "buf lint",
    "rpc", "message type", "service definition", "api contract",
}

# Keywords that mention a service by name (normalised to canonical)
_SERVICE_NAME_TOKENS: dict[str, str] = {
    "town-core": "town-core",
    "town core": "town-core",
    "market-district": "market-district",
    "market district": "market-district",
    "fortress": "fortress",
    "academy": "academy",
    "tavern": "tavern",
    "cartographer": "cartographer",
    "library": "library",
    "asset-pipeline": "asset-pipeline",
    "asset pipeline": "asset-pipeline",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExecutionPlan:
    """Describes how to execute a cross-service story."""

    story_id: str
    affected_services: list[str]

    # Proto workflow flags
    proto_changes_first: bool = False
    proto_owner: Optional[str] = None       # which service owns the changed proto

    # Ordered list of services to implement (after proto, if needed)
    service_order: list[str] = field(default_factory=list)

    # Whether an integration test pass is required after all services done
    integration_test_required: bool = False

    # Human-readable rationale
    rationale: str = ""

    def is_multi_service(self) -> bool:
        return len(self.affected_services) > 1

    def summary(self) -> dict:
        return {
            "story_id": self.story_id,
            "affected_services": self.affected_services,
            "proto_changes_first": self.proto_changes_first,
            "service_order": self.service_order,
            "integration_test_required": self.integration_test_required,
        }


# ---------------------------------------------------------------------------
# Detection functions
# ---------------------------------------------------------------------------

def detect_cross_service(story, worklist: list) -> list[str]:
    """
    Return the list of services affected by *story*.

    Detection heuristics (in priority order):
    1. story.service is always included
    2. Story title mentions another service name
    3. Story deps include stories on different services
    4. Story requires proto changes → all proto-owning services may be affected
    """
    affected: set[str] = set()

    # 1. Own service
    own = _canonical(story.service)
    if own:
        affected.add(own)

    # 2. Title mentions
    title_lower = story.title.lower()
    for token, canonical in _SERVICE_NAME_TOKENS.items():
        if token in title_lower:
            affected.add(canonical)

    # 3. Dep chain spans services
    story_map = {s.id: s for s in worklist}
    for dep_id in story.deps:
        dep = story_map.get(dep_id)
        if dep:
            dep_svc = _canonical(dep.service)
            if dep_svc:
                affected.add(dep_svc)

    # 4. Proto keywords imply cross-service impact
    if _has_proto_keywords(title_lower):
        affected.update(PROTO_OWNING_SERVICES)

    return sorted(affected)


def plan_cross_service(story, affected_services: list[str]) -> ExecutionPlan:
    """
    Build an ExecutionPlan for a story that touches multiple services.

    Rules:
    - If proto changes needed, put proto-owning services first and set
      proto_changes_first = True.
    - Services with no proto dependency can be implemented in parallel
      (represented as a flat list here; the orchestrator decides parallelism).
    - Integration test required whenever more than one service is involved.
    """
    title_lower = story.title.lower()
    needs_proto = _has_proto_keywords(title_lower) or len(
        [s for s in affected_services if s in PROTO_OWNING_SERVICES]
    ) > 1

    proto_first = needs_proto and bool(
        set(affected_services) & PROTO_OWNING_SERVICES
    )

    # Determine proto owner (prefer story's own service if it owns proto)
    own = _canonical(story.service)
    if proto_first:
        if own in PROTO_OWNING_SERVICES:
            proto_owner: Optional[str] = own
        else:
            # Pick the first proto-owning service that's affected
            proto_owner = next(
                (s for s in affected_services if s in PROTO_OWNING_SERVICES),
                None,
            )
    else:
        proto_owner = None

    # Build service_order: proto owners first, then the rest
    if proto_first and proto_owner:
        proto_first_list = [proto_owner] + [
            s for s in affected_services
            if s in PROTO_OWNING_SERVICES and s != proto_owner
        ]
        remainder = [s for s in affected_services if s not in set(proto_first_list)]
        service_order = proto_first_list + remainder
    else:
        # Own service first, then the rest alphabetically
        service_order = [own] + sorted(
            [s for s in affected_services if s != own]
        ) if own else sorted(affected_services)

    rationale_parts = []
    if proto_first:
        rationale_parts.append(
            f"Proto changes detected — {proto_owner} generates stubs first"
        )
    if len(affected_services) > 1:
        rationale_parts.append(
            f"Integration test required across {len(affected_services)} services"
        )

    return ExecutionPlan(
        story_id=story.id,
        affected_services=affected_services,
        proto_changes_first=proto_first,
        proto_owner=proto_owner,
        service_order=service_order,
        integration_test_required=len(affected_services) > 1,
        rationale="; ".join(rationale_parts) or "Single-service story",
    )


def requires_proto_changes(story) -> bool:
    """Quick check — does this story need proto regeneration?"""
    return _has_proto_keywords(story.title.lower())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical(service: str) -> Optional[str]:
    """Normalise a service name to its canonical hyphenated form."""
    s = service.strip().lower()
    if s in ALL_SERVICES:
        return s
    # Try alias map
    normalised = s.replace(" ", "_").replace("-", "_")
    return SERVICE_ALIASES.get(normalised) or SERVICE_ALIASES.get(s)


def _has_proto_keywords(text: str) -> bool:
    return any(kw in text for kw in PROTO_KEYWORDS)
