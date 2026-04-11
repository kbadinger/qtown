"""
test_chaos.py — Tests for Qtown chaos engineering framework.

Covers:
- Scenario definitions have required fields.
- ChaosRunner issues the correct docker compose commands.
- Degradation detection logic.
- Recovery verification logic.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from infra.chaos.chaos_runner import ChaosRunner, ChaosScenario, ChaosReport
from infra.chaos.scenarios import (
    market_district_crash,
    academy_timeout,
    kafka_partition,
    postgres_slowdown,
    full_chaos_suite,
    ALL_SERVICES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> ChaosRunner:
    """ChaosRunner in dry-run mode — no real docker calls."""
    return ChaosRunner(
        docker_compose_path="./docker-compose.yml",
        services=ALL_SERVICES,
        dry_run=True,
    )


# ===========================================================================
# 1. Scenario definitions
# ===========================================================================

class TestScenarioDefinitions:

    REQUIRED_FIELDS = ["target_service", "failure_type", "duration",
                       "expected_behavior", "verification_steps"]

    def _check_scenario(self, scenario: ChaosScenario) -> None:
        for field in self.REQUIRED_FIELDS:
            value = getattr(scenario, field, None)
            assert value is not None and value != "" and value != [], (
                f"Scenario {scenario.target_service}: field {field!r} is empty"
            )

    def test_market_district_crash_fields(self):
        s = market_district_crash()
        self._check_scenario(s)
        assert s.target_service == "market-district"
        assert s.failure_type == "kill"
        assert s.duration > 0
        assert len(s.verification_steps) >= 2

    def test_academy_timeout_fields(self):
        s = academy_timeout()
        self._check_scenario(s)
        assert s.target_service == "academy"
        assert s.failure_type == "pause"
        assert s.duration > 0
        assert "rule" in s.expected_behavior.lower() or "fallback" in s.expected_behavior.lower()

    def test_kafka_partition_fields(self):
        s = kafka_partition()
        self._check_scenario(s)
        assert s.target_service == "kafka"
        assert s.failure_type == "network_partition"
        assert "replay" in s.expected_behavior.lower() or "buffer" in s.expected_behavior.lower()

    def test_postgres_slowdown_fields(self):
        s = postgres_slowdown()
        self._check_scenario(s)
        assert s.target_service == "postgres"
        assert s.failure_type == "cpu_stress"
        assert s.cpu_load_pct > 0
        assert "graceful" in s.expected_behavior.lower() or "cache" in s.expected_behavior.lower()

    def test_all_scenarios_have_unique_targets(self):
        scenarios = [market_district_crash(), academy_timeout(),
                     kafka_partition(), postgres_slowdown()]
        targets = [s.target_service for s in scenarios]
        assert len(targets) == len(set(targets)), "Duplicate target services found"

    def test_all_scenarios_known_failure_types(self):
        valid_types = {"kill", "pause", "network_partition", "cpu_stress"}
        scenarios = [market_district_crash(), academy_timeout(),
                     kafka_partition(), postgres_slowdown()]
        for s in scenarios:
            assert s.failure_type in valid_types, (
                f"Unknown failure type {s.failure_type!r} for {s.target_service}"
            )


# ===========================================================================
# 2. ChaosRunner — mocked docker calls
# ===========================================================================

class TestChaosRunnerMock:

    def test_kill_service_issues_compose_stop(self, runner):
        """kill_service must call 'docker compose stop <service>'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            runner.dry_run = False
            runner.kill_service("market-district")
            # Find the stop call
            stop_calls = [
                c for c in mock_run.call_args_list
                if "stop" in c.args[0] and "market-district" in c.args[0]
            ]
            assert len(stop_calls) == 1, "Expected exactly one 'docker compose stop' call"

    def test_pause_service_issues_compose_pause(self, runner):
        """pause_service must call 'docker compose pause <service>'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            runner.dry_run = False
            runner.pause_service("academy")
            pause_calls = [
                c for c in mock_run.call_args_list
                if "pause" in c.args[0] and "academy" in c.args[0]
            ]
            assert len(pause_calls) == 1

    def test_dry_run_does_not_call_subprocess(self):
        """In dry_run mode, no real subprocess calls should be made."""
        runner = ChaosRunner("./dc.yml", ALL_SERVICES, dry_run=True)
        with patch("subprocess.run") as mock_run:
            runner.kill_service("market-district")
            runner.pause_service("academy")
            mock_run.assert_not_called()

    def test_inject_failure_kill_calls_kill_service(self):
        """inject_failure('kill') must delegate to kill_service."""
        runner = ChaosRunner("./dc.yml", ALL_SERVICES, dry_run=True)
        runner.kill_service = MagicMock()
        import time
        with patch.object(time, "sleep"):  # skip real sleep
            runner.inject_failure("market-district", "kill", duration_seconds=1)
        runner.kill_service.assert_called_once_with("market-district")

    def test_inject_failure_pause_calls_pause_service(self):
        runner = ChaosRunner("./dc.yml", ALL_SERVICES, dry_run=True)
        runner.pause_service = MagicMock()
        import time
        with patch.object(time, "sleep"):
            runner.inject_failure("academy", "pause", duration_seconds=1)
        runner.pause_service.assert_called_once_with("academy")

    def test_inject_failure_unknown_type_raises(self, runner):
        """Unknown failure_type must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown failure type"):
            runner.inject_failure("town-core", "explode", duration_seconds=1)

    def test_inject_failure_unknown_service_raises(self):
        """Service not in services list must raise ValueError."""
        runner = ChaosRunner("./dc.yml", ["town-core"], dry_run=True)
        with pytest.raises(ValueError, match="not in known services"):
            runner.inject_failure("unknown-svc", "kill", duration_seconds=1)

    def test_verify_recovery_returns_true_in_dry_run(self, runner):
        """In dry_run mode, Kafka lag is 0 immediately so recovery is instant."""
        # dry_run mode _get_kafka_consumer_lag always returns 0
        result = runner.verify_recovery("market-district", max_wait_seconds=5)
        assert result is True

    def test_run_chaos_test_produces_report(self, runner):
        """Full chaos test run should produce a ChaosReport with correct fields."""
        import time
        with patch.object(time, "sleep"):  # skip sleeps
            report = runner.run_chaos_test(market_district_crash())

        assert isinstance(report, ChaosReport)
        assert report.scenario.target_service == "market-district"
        assert isinstance(report.start_time, datetime)
        assert isinstance(report.end_time, datetime)
        assert report.end_time >= report.start_time
        assert isinstance(report.degradation_detected, bool)
        assert isinstance(report.kafka_lag_recovered, bool)
        assert isinstance(report.errors_observed, list)


# ===========================================================================
# 3. Graceful degradation detection
# ===========================================================================

class TestGracefulDegradation:

    def test_other_services_running_means_degradation_detected(self, runner):
        """If other services are up while target is down, degradation is detected."""
        # dry_run: _is_container_running always returns True
        result = runner.verify_graceful_degradation("market-district")
        assert result.degradation_detected is True
        assert result.other_services_healthy is True

    def test_degradation_result_has_required_attrs(self, runner):
        result = runner.verify_graceful_degradation("academy")
        assert hasattr(result, "degradation_detected")
        assert hasattr(result, "other_services_healthy")
        assert hasattr(result, "errors")


# ===========================================================================
# 4. ChaosReport helpers
# ===========================================================================

class TestChaosReport:

    def _make_report(self, degradation: bool = True, kafka: bool = True) -> ChaosReport:
        return ChaosReport(
            scenario=market_district_crash(),
            start_time=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 1, 12, 1, tzinfo=timezone.utc),
            degradation_detected=degradation,
            recovery_time_seconds=15.0,
            kafka_lag_recovered=kafka,
        )

    def test_passed_when_both_true(self):
        assert self._make_report(True, True).passed() is True

    def test_failed_when_degradation_false(self):
        assert self._make_report(False, True).passed() is False

    def test_failed_when_kafka_not_recovered(self):
        assert self._make_report(True, False).passed() is False

    def test_duration_seconds(self):
        report = self._make_report()
        assert abs(report.duration_seconds - 60.0) < 1.0

    def test_summary_dict_structure(self):
        report = self._make_report()
        summary = report.summary()
        assert "scenario" in summary
        assert "failure_type" in summary
        assert "passed" in summary
        assert "recovery_time_seconds" in summary
        assert "kafka_lag_recovered" in summary
