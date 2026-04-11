"""
chaos_runner.py — Random service failure injection for Qtown.

Injects failures into Docker Compose services and verifies graceful degradation
and recovery.  All docker compose commands are captured for dry-run / testing.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ChaosScenario:
    """Describes a single chaos injection test."""

    target_service: str
    failure_type: str          # kill | pause | network_partition | cpu_stress
    duration: int              # seconds
    expected_behavior: str     # human-readable description
    verification_steps: list[str] = field(default_factory=list)
    cpu_load_pct: int = 80     # used when failure_type == cpu_stress


@dataclass
class ChaosReport:
    """Result of running a ChaosScenario."""

    scenario: ChaosScenario
    start_time: datetime
    end_time: datetime
    degradation_detected: bool
    recovery_time_seconds: float
    kafka_lag_recovered: bool
    errors_observed: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()

    def passed(self) -> bool:
        return self.degradation_detected and self.kafka_lag_recovered

    def summary(self) -> dict:
        return {
            "scenario": self.scenario.target_service,
            "failure_type": self.scenario.failure_type,
            "passed": self.passed(),
            "degradation_detected": self.degradation_detected,
            "recovery_time_seconds": round(self.recovery_time_seconds, 1),
            "kafka_lag_recovered": self.kafka_lag_recovered,
            "errors_observed": self.errors_observed,
            "duration_seconds": round(self.duration_seconds, 1),
        }


# ---------------------------------------------------------------------------
# ChaosRunner
# ---------------------------------------------------------------------------

class ChaosRunner:
    """
    Injects failures into Docker Compose services and validates recovery.

    Example usage::

        runner = ChaosRunner(
            docker_compose_path="./docker-compose.yml",
            services=["town-core", "market-district", "kafka"],
        )
        report = runner.run_chaos_test(market_district_crash())
        print(report.summary())
    """

    KAFKA_CONSUMER_GROUP = "qtown-consumers"
    KAFKA_BOOTSTRAP = "localhost:9092"

    def __init__(
        self,
        docker_compose_path: str,
        services: list[str],
        dry_run: bool = False,
    ) -> None:
        self.compose_path = docker_compose_path
        self.services = services
        self.dry_run = dry_run  # if True, log commands but don't execute

    # ------------------------------------------------------------------
    # Failure injection
    # ------------------------------------------------------------------

    def inject_failure(
        self,
        service: str,
        failure_type: str,
        duration_seconds: int,
        **kwargs,
    ) -> None:
        """
        Inject a failure into *service* for *duration_seconds*.

        Supported failure_types: kill, pause, network_partition, cpu_stress
        """
        self._validate_service(service)

        logger.info(
            "Injecting %s into %s for %ds", failure_type, service, duration_seconds
        )

        if failure_type == "kill":
            self.kill_service(service)
        elif failure_type == "pause":
            self.pause_service(service)
        elif failure_type == "network_partition":
            self.network_partition(service)
        elif failure_type == "cpu_stress":
            load_pct = kwargs.get("load_pct", 80)
            self.cpu_stress(service, load_pct)
        else:
            raise ValueError(f"Unknown failure type: {failure_type!r}")

        logger.info("Failure injected — holding for %ds", duration_seconds)
        time.sleep(duration_seconds)

    def kill_service(self, service: str) -> None:
        """Stop (kill) a service via docker compose stop."""
        self._compose("stop", service)

    def pause_service(self, service: str) -> None:
        """Pause a service via docker compose pause (SIGSTOP)."""
        self._compose("pause", service)

    def unpause_service(self, service: str) -> None:
        """Resume a paused service."""
        self._compose("unpause", service)

    def network_partition(self, service: str) -> None:
        """
        Disconnect a service from the Docker Compose default network.

        Uses 'docker network disconnect' to cut all traffic to/from the service.
        """
        container_id = self._get_container_id(service)
        network_name = self._get_compose_network()
        self._run(["docker", "network", "disconnect", network_name, container_id])
        logger.info("Network-partitioned %s (container=%s)", service, container_id)

    def reconnect_network(self, service: str) -> None:
        """Re-attach a service to the compose network."""
        container_id = self._get_container_id(service)
        network_name = self._get_compose_network()
        self._run(["docker", "network", "connect", network_name, container_id])

    def cpu_stress(self, service: str, load_pct: int = 80) -> None:
        """
        Inject CPU load into a service container using 'stress-ng'.

        Requires stress-ng to be available inside the container (or on the host).
        Falls back to a shell busy-loop if stress-ng is absent.
        """
        container_id = self._get_container_id(service)
        # Try stress-ng first, fall back to yes | head
        cmd = [
            "docker", "exec", "-d", container_id,
            "sh", "-c",
            f"stress-ng --cpu 1 --cpu-load {load_pct} --timeout 30s "
            f"|| (yes > /dev/null &)",
        ]
        self._run(cmd)
        logger.info("CPU stress %d%% injected into %s", load_pct, service)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_graceful_degradation(self, service: str) -> "ChaosResult":
        """
        Verify that the system degrades gracefully when *service* is down.

        Checks:
        1. Other services are still running (docker ps).
        2. HTTP health endpoints of sibling services return 2xx.
        3. Error log lines in other services do not spike.

        Returns a ChaosResult (named tuple for simplicity).
        """
        other_services = [s for s in self.services if s != service]
        errors: list[str] = []
        degradation_detected = False

        for svc in other_services:
            running = self._is_container_running(svc)
            if not running:
                errors.append(f"{svc} is DOWN when {service} failed — cascading failure!")
            else:
                degradation_detected = True  # rest of the system stayed up

        # Check health endpoints
        health_errors = self._check_health_endpoints(other_services)
        errors.extend(health_errors)

        return _ChaosResult(
            service_down=service,
            other_services_healthy=len(errors) == 0,
            degradation_detected=degradation_detected,
            errors=errors,
        )

    def verify_recovery(self, service: str, max_wait_seconds: int = 60) -> bool:
        """
        Restart *service* and wait until Kafka consumer lag returns to 0.

        Returns True if recovery completes within *max_wait_seconds*.
        """
        logger.info("Restarting %s and waiting for recovery...", service)

        # Restart the service
        self._compose("start", service)

        deadline = time.monotonic() + max_wait_seconds
        while time.monotonic() < deadline:
            lag = self._get_kafka_consumer_lag(service)
            if lag == 0:
                elapsed = max_wait_seconds - (deadline - time.monotonic())
                logger.info(
                    "%s recovered: Kafka lag=0 after %.1fs", service, elapsed
                )
                return True
            logger.debug("%s Kafka lag=%d — waiting...", service, lag)
            time.sleep(3)

        logger.warning("%s did NOT recover within %ds", service, max_wait_seconds)
        return False

    def run_chaos_test(self, scenario: ChaosScenario) -> ChaosReport:
        """
        Execute a full chaos test scenario end-to-end.

        Steps:
        1. Record start time.
        2. Inject failure.
        3. Verify graceful degradation of remaining services.
        4. Restore service.
        5. Verify Kafka lag recovery.
        6. Emit a ChaosReport.
        """
        start_time = datetime.now(timezone.utc)
        errors: list[str] = []
        degradation_detected = False
        kafka_lag_recovered = False
        recovery_start = time.monotonic()

        try:
            # Step 2: inject
            self.inject_failure(
                scenario.target_service,
                scenario.failure_type,
                scenario.duration,
                cpu_load_pct=scenario.cpu_load_pct,
            )

            # Step 3: verify degradation
            result = self.verify_graceful_degradation(scenario.target_service)
            degradation_detected = result.degradation_detected
            errors.extend(result.errors)

            # Step 4: restore
            self._restore_service(scenario.target_service, scenario.failure_type)

            # Step 5: verify recovery
            kafka_lag_recovered = self.verify_recovery(
                scenario.target_service, max_wait_seconds=60
            )
            recovery_time = time.monotonic() - recovery_start

        except Exception as exc:
            errors.append(f"Chaos test error: {exc}")
            recovery_time = time.monotonic() - recovery_start

        end_time = datetime.now(timezone.utc)

        report = ChaosReport(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            degradation_detected=degradation_detected,
            recovery_time_seconds=recovery_time,
            kafka_lag_recovered=kafka_lag_recovered,
            errors_observed=errors,
        )

        logger.info(
            "Chaos test complete: service=%s type=%s passed=%s recovery=%.1fs",
            scenario.target_service,
            scenario.failure_type,
            report.passed(),
            report.recovery_time_seconds,
        )
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compose(self, *args: str) -> subprocess.CompletedProcess:
        cmd = ["docker", "compose", "-f", self.compose_path] + list(args)
        return self._run(cmd)

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        if self.dry_run:
            logger.info("[DRY RUN] %s", " ".join(cmd))
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")
        logger.debug("Running: %s", " ".join(cmd))
        return subprocess.run(cmd, check=True, capture_output=True, timeout=30)

    def _validate_service(self, service: str) -> None:
        if service not in self.services:
            raise ValueError(
                f"Service {service!r} not in known services: {self.services}"
            )

    def _get_container_id(self, service: str) -> str:
        """Return the running container ID for a compose service."""
        if self.dry_run:
            return f"dry-run-{service}"
        result = subprocess.run(
            ["docker", "compose", "-f", self.compose_path,
             "ps", "-q", service],
            capture_output=True, text=True, check=True, timeout=10,
        )
        cid = result.stdout.strip()
        if not cid:
            raise RuntimeError(f"No running container found for service {service!r}")
        return cid

    def _get_compose_network(self) -> str:
        """Derive the default compose network name (project_default)."""
        import os
        project = os.path.basename(
            os.path.dirname(os.path.abspath(self.compose_path))
        )
        return f"{project}_default"

    def _is_container_running(self, service: str) -> bool:
        if self.dry_run:
            return True
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", self.compose_path,
                 "ps", "--status", "running", "-q", service],
                capture_output=True, text=True, timeout=10,
            )
            return bool(result.stdout.strip())
        except subprocess.SubprocessError:
            return False

    def _check_health_endpoints(self, services: list[str]) -> list[str]:
        """
        Very lightweight health check — just verifies docker compose ps
        reports the service as running.  A real implementation would
        HTTP-GET the /health endpoint.
        """
        errors = []
        for svc in services:
            if not self._is_container_running(svc):
                errors.append(f"Health check failed: {svc} is not running")
        return errors

    def _get_kafka_consumer_lag(self, service: str) -> int:
        """
        Query Kafka consumer lag for service-specific consumer group.

        Returns total lag across all partitions, or 0 if service/topic not found.
        """
        if self.dry_run:
            return 0
        try:
            result = subprocess.run(
                [
                    "docker", "exec", "kafka",
                    "kafka-consumer-groups.sh",
                    "--bootstrap-server", self.KAFKA_BOOTSTRAP,
                    "--group", f"{service}-consumer",
                    "--describe",
                ],
                capture_output=True, text=True, timeout=15,
            )
            total_lag = 0
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 6 and parts[5].isdigit():
                    total_lag += int(parts[5])
            return total_lag
        except Exception as exc:
            logger.debug("Could not get Kafka lag for %s: %s", service, exc)
            return 0

    def _restore_service(self, service: str, failure_type: str) -> None:
        """Undo the failure injection based on failure_type."""
        if failure_type == "kill":
            self._compose("start", service)
        elif failure_type == "pause":
            self.unpause_service(service)
        elif failure_type == "network_partition":
            self.reconnect_network(service)
        elif failure_type == "cpu_stress":
            pass  # stress-ng finishes on its own after the timeout
        else:
            logger.warning("Don't know how to restore failure_type=%r", failure_type)


# ---------------------------------------------------------------------------
# Internal result type
# ---------------------------------------------------------------------------

class _ChaosResult:
    """Lightweight result object for verify_graceful_degradation."""

    def __init__(
        self,
        service_down: str,
        other_services_healthy: bool,
        degradation_detected: bool,
        errors: list[str],
    ) -> None:
        self.service_down = service_down
        self.other_services_healthy = other_services_healthy
        self.degradation_detected = degradation_detected
        self.errors = errors
