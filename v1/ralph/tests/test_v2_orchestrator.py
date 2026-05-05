"""
test_v2_orchestrator.py — Tests for Ralph v2 multi-agent orchestrator.

Covers:
- Story conflict detection (same service, shared proto dep, explicit dep chain)
- No-conflict detection (different services with no shared deps)
- Cross-service story detection (proto keyword triggers affected services)
- Model routing (language and keyword → correct Ollama model)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import the modules under test (relative imports work when run via pytest
# from the qtown root with `python -m pytest ralph/tests/`)
# ---------------------------------------------------------------------------
import sys
import os

# Allow running standalone from the ralph/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ralph.v2_worklist import Story, Worklist
from ralph.v2_orchestrator import RalphV2Orchestrator, WorkerResult
from ralph.v2_model_router import (
    ModelRouter,
    TIER_1_CODE,
    TIER_2_ARCHITECTURE,
    TIER_3_DEBUG,
)
from ralph.v2_cross_service import detect_cross_service, plan_cross_service, requires_proto_changes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_story(
    id: str = "P5-001",
    title: str = "Add endpoint",
    service: str = "town-core",
    language: str = "python",
    deps: list[str] | None = None,
    labels: list[str] | None = None,
    status: str = "pending",
) -> Story:
    return Story(
        id=id,
        title=title,
        service=service,
        language=language,
        deps=deps or [],
        labels=labels or [],
        status=status,
    )


@pytest.fixture
def tmp_worklist(tmp_path):
    """Write a minimal worklist.json and return its path."""
    stories = [
        {
            "id": "P5-001",
            "title": "Add health endpoint",
            "service": "town-core",
            "language": "python",
            "deps": [],
            "status": "pending",
        },
        {
            "id": "P5-002",
            "title": "Market price feed",
            "service": "market-district",
            "language": "python",
            "deps": [],
            "status": "pending",
        },
        {
            "id": "P5-003",
            "title": "Fortress guard patrol",
            "service": "fortress",
            "language": "go",
            "deps": ["P5-001"],
            "status": "pending",
        },
    ]
    path = tmp_path / "worklist.json"
    path.write_text(json.dumps({"stories": stories}), encoding="utf-8")
    return str(path)


# ===========================================================================
# 1. Story conflict detection — same service
# ===========================================================================

class TestStoryConflictDetection:

    def _make_orchestrator(self, tmp_path: Path) -> RalphV2Orchestrator:
        """Create a lightweight orchestrator backed by a minimal worklist."""
        stories = [
            {"id": "S1", "title": "Story 1", "service": "town-core",
             "language": "python", "deps": [], "status": "pending"},
            {"id": "S2", "title": "Story 2", "service": "town-core",
             "language": "python", "deps": [], "status": "pending"},
            {"id": "S3", "title": "Story 3", "service": "market-district",
             "language": "python", "deps": [], "status": "pending"},
        ]
        wl_path = tmp_path / "wl.json"
        wl_path.write_text(json.dumps({"stories": stories}))
        return RalphV2Orchestrator(
            worklist_path=str(wl_path),
            max_parallel=3,
            repo_root=str(tmp_path),
        )

    def test_story_conflict_detection(self, tmp_path):
        """Two stories on the same service must conflict."""
        orch = self._make_orchestrator(tmp_path)
        s1 = make_story("S1", service="town-core")
        s2 = make_story("S2", service="town-core")

        # Simulate S1 already active
        orch._active_files["town-core"] = "S1"
        # Patch worklist to return s1 for get_story
        orch.worklist._stories = {"S1": s1, "S2": s2}

        assert orch._conflicts_with_active(s2) is True, (
            "Two stories on 'town-core' should conflict"
        )

    def test_no_conflict_different_services(self, tmp_path):
        """Stories on different services without shared deps must NOT conflict."""
        orch = self._make_orchestrator(tmp_path)
        s1 = make_story("S1", service="town-core")
        s3 = make_story("S3", service="market-district")

        orch._active_files["town-core"] = "S1"
        orch.worklist._stories = {"S1": s1, "S3": s3}

        assert orch._conflicts_with_active(s3) is False, (
            "Stories on different services should not conflict"
        )

    def test_conflict_via_explicit_dep_chain(self, tmp_path):
        """A story that depends on an active story must conflict."""
        orch = self._make_orchestrator(tmp_path)
        s1 = make_story("S1", service="town-core")
        # S4 depends on S1 but lives on a different service
        s4 = make_story("S4", service="fortress", deps=["S1"])

        orch._active_files["town-core"] = "S1"
        orch.worklist._stories = {"S1": s1, "S4": s4}

        assert orch._conflicts_with_active(s4) is True, (
            "S4 depends on active S1 — should conflict"
        )

    def test_conflict_via_proto_label(self, tmp_path):
        """Two stories with 'proto' label must conflict even on different services."""
        orch = self._make_orchestrator(tmp_path)
        s1 = make_story("S1", service="town-core", labels=["proto"])
        s5 = make_story("S5", service="academy", labels=["proto"])

        orch._active_files["town-core"] = "S1"
        orch.worklist._stories = {"S1": s1, "S5": s5}

        assert orch._conflicts_with_active(s5) is True, (
            "Two proto-labelled stories should conflict"
        )


# ===========================================================================
# 2. Cross-service story detection
# ===========================================================================

class TestCrossServiceDetection:

    def test_single_service_story(self):
        """A story with no cross-service signals returns just its own service."""
        story = make_story("X1", title="Add rate limiter", service="tavern")
        affected = detect_cross_service(story, [story])
        assert "tavern" in affected
        assert len(affected) == 1

    def test_cross_service_detection_title(self):
        """Story title mentioning another service triggers detection."""
        story = make_story(
            "X2",
            title="Sync market-district prices with town-core ledger",
            service="market-district",
        )
        affected = detect_cross_service(story, [story])
        assert "market-district" in affected
        assert "town-core" in affected

    def test_cross_service_detection_proto(self):
        """Proto keyword in title expands to all proto-owning services."""
        story = make_story(
            "X3",
            title="Update gRPC proto for NPC movement API",
            service="town-core",
        )
        affected = detect_cross_service(story, [story])
        # Should include at least the proto-owning services
        assert "town-core" in affected
        assert "academy" in affected or "fortress" in affected or "market-district" in affected

    def test_requires_proto_changes_positive(self):
        """Story with 'proto' in title returns True."""
        story = make_story("X4", title="Add proto message for inventory")
        assert requires_proto_changes(story) is True

    def test_requires_proto_changes_negative(self):
        """Story without proto keywords returns False."""
        story = make_story("X5", title="Optimise SQL query for tavern orders")
        assert requires_proto_changes(story) is False

    def test_plan_cross_service_proto_first(self):
        """Plan for a proto story sets proto_changes_first = True."""
        story = make_story(
            "X6",
            title="Extend gRPC proto for combat service",
            service="fortress",
        )
        affected = ["fortress", "town-core", "academy"]
        plan = plan_cross_service(story, affected)
        assert plan.proto_changes_first is True
        assert plan.integration_test_required is True
        assert plan.service_order[0] in {"fortress", "town-core", "academy"}

    def test_plan_cross_service_no_proto(self):
        """Plan for a non-proto multi-service story does NOT set proto_first."""
        story = make_story(
            "X7",
            title="Share Redis session cache between tavern and academy",
            service="tavern",
        )
        affected = ["tavern", "academy"]
        plan = plan_cross_service(story, affected)
        assert plan.proto_changes_first is False
        assert plan.integration_test_required is True


# ===========================================================================
# 3. Model routing
# ===========================================================================

class TestModelRouting:

    @pytest.fixture
    def router(self) -> ModelRouter:
        return ModelRouter()

    def test_python_routes_to_code_model(self, router):
        story = make_story(title="Add unit tests", language="python")
        assert router.route(story) == TIER_1_CODE

    def test_go_routes_to_code_model(self, router):
        story = make_story(title="Implement gRPC handler", language="go")
        assert router.route(story) == TIER_1_CODE

    def test_rust_routes_to_code_model(self, router):
        story = make_story(title="Port hot path to Rust", language="rust")
        assert router.route(story) == TIER_1_CODE

    def test_typescript_routes_to_code_model(self, router):
        story = make_story(title="Add React component", language="typescript")
        assert router.route(story) == TIER_1_CODE

    def test_architecture_keyword_routes_to_arch_model(self, router):
        story = make_story(
            title="Refactor service mesh architecture for multi-region",
            language="yaml",
        )
        assert router.route(story) == TIER_2_ARCHITECTURE

    def test_debug_keyword_routes_to_debug_model(self, router):
        story = make_story(
            title="Fix race condition in Kafka consumer",
            language="python",
        )
        assert router.route(story) == TIER_3_DEBUG

    def test_investigate_routes_to_debug_model(self, router):
        story = make_story(
            title="Investigate memory leak in town-core worker",
            language="python",
        )
        assert router.route(story) == TIER_3_DEBUG

    def test_fallback_chain_not_empty(self, router):
        """Primary model must have at least one fallback."""
        next_model = router.next_fallback(TIER_1_CODE)
        assert next_model is not None

    def test_success_rate_tracking(self, router):
        story = make_story(language="python")
        model = router.route(story)
        router.record_result(model, "python", success=True, duration_seconds=10.0)
        router.record_result(model, "python", success=False)
        stats = router.get_stats()
        assert len(stats) == 1
        assert stats[0].successes == 1
        assert stats[0].failures == 1
        assert abs(stats[0].success_rate - 0.5) < 0.001

    def test_proactive_reroute_on_low_success_rate(self, router):
        """If primary model has < 50% success rate, router prefers fallback."""
        story = make_story(title="Generate config", language="python")
        # Record many failures for the primary model
        for _ in range(5):
            router.record_result(TIER_1_CODE, "python", success=False)
        # Record successes for the architecture model
        for _ in range(5):
            router.record_result(TIER_2_ARCHITECTURE, "python", success=True, duration_seconds=1.0)

        routed = router.route(story)
        # Should have switched away from the failing primary
        assert routed != TIER_1_CODE


# ===========================================================================
# 4. Worklist functionality
# ===========================================================================

class TestWorklist:

    def test_load_and_progress(self, tmp_worklist):
        wl = Worklist(tmp_worklist)
        progress = wl.get_progress()
        assert progress["total"] == 3
        assert progress["pending"] == 3

    def test_next_available_no_deps(self, tmp_worklist):
        wl = Worklist(tmp_worklist)
        available = wl.next_available(completed=set())
        ids = [s.id for s in available]
        # P5-001 and P5-002 have no deps; P5-003 depends on P5-001
        assert "P5-001" in ids
        assert "P5-002" in ids
        assert "P5-003" not in ids

    def test_next_available_with_completed(self, tmp_worklist):
        wl = Worklist(tmp_worklist)
        available = wl.next_available(completed={"P5-001"})
        ids = [s.id for s in available]
        assert "P5-003" in ids   # P5-001 dep now satisfied

    def test_mark_complete_updates_progress(self, tmp_worklist):
        wl = Worklist(tmp_worklist)
        wl.mark_complete("P5-001")
        progress = wl.get_progress()
        assert "P5-001" in progress["by_status"]["complete"]
        assert progress["complete"] == 1

    def test_mark_failed_records_error(self, tmp_worklist):
        wl = Worklist(tmp_worklist)
        wl.mark_failed("P5-002", "Ollama timeout")
        story = wl.get_story("P5-002")
        assert story.status == "failed"
        assert story.last_error == "Ollama timeout"
