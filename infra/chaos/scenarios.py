"""
scenarios.py — Pre-built chaos scenarios for Qtown.

Each function returns a ChaosScenario (or runs it directly against a ChaosRunner).
`full_chaos_suite()` runs all scenarios sequentially and generates a combined report.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .chaos_runner import ChaosRunner, ChaosReport, ChaosScenario

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default compose file (override via full_chaos_suite(compose_path=...))
# ---------------------------------------------------------------------------

DEFAULT_COMPOSE = "./docker-compose.yml"

ALL_SERVICES = [
    "town-core",
    "market-district",
    "fortress",
    "academy",
    "tavern",
    "cartographer",
    "library",
    "asset-pipeline",
    "kafka",
    "postgres",
]


# ---------------------------------------------------------------------------
# Individual scenario builders
# ---------------------------------------------------------------------------

def market_district_crash() -> ChaosScenario:
    """
    Kill Market District and verify NPCs return to Town Core within 60s.

    Expected behavior: NPCs that were in Market District fall back to Town
    Core's default decision engine within 60 seconds of Market District going
    down.
    """
    return ChaosScenario(
        target_service="market-district",
        failure_type="kill",
        duration=30,
        expected_behavior=(
            "NPCs currently in Market District should migrate back to Town Core "
            "within 60 seconds. No panic or crash in town-core logs expected."
        ),
        verification_steps=[
            "Check town-core /health returns 200",
            "Verify NPC location table shows 0 NPCs in market-district zone",
            "Check town-core logs for 'fallback activated' message",
            "Verify Kafka consumer lag for market-district-consumer returns to 0",
        ],
    )


def academy_timeout() -> ChaosScenario:
    """
    Pause Academy and verify NPC decisions fall back to rule-based logic.

    Expected behavior: when Academy is paused (SIGSTOP), NPC AI calls time
    out after 5 seconds and fall back to a deterministic rule-based engine.
    Decision latency spikes but no errors propagate to players.
    """
    return ChaosScenario(
        target_service="academy",
        failure_type="pause",
        duration=45,
        expected_behavior=(
            "NPC decision calls to Academy should time out gracefully after 5s "
            "and fall back to rule-based decisions. No 5xx errors on player-facing "
            "endpoints. Academy resumes normally after SIGCONT."
        ),
        verification_steps=[
            "Check academy /health returns 503 (paused = not responding)",
            "Verify town-core logs show 'academy_timeout, using rule_engine'",
            "Confirm player-facing /api/npc/decision still returns 200",
            "After unpause: verify academy resumes and Kafka lag → 0",
        ],
    )


def kafka_partition() -> ChaosScenario:
    """
    Network-partition Kafka and verify services queue locally and replay.

    Expected behavior: services lose connectivity to Kafka but continue
    operating by buffering events locally.  On reconnect, buffered events
    replay in order and Kafka consumer lag returns to 0 within 60s.
    """
    return ChaosScenario(
        target_service="kafka",
        failure_type="network_partition",
        duration=20,
        expected_behavior=(
            "Services should detect Kafka unreachability and switch to local "
            "event buffering. On reconnect, buffered events replay in order and "
            "Kafka consumer lag returns to 0 within 60 seconds."
        ),
        verification_steps=[
            "Check individual service /health — should return 200 (degraded mode)",
            "Confirm event replay order via audit log after reconnection",
            "Verify Kafka consumer lag returns to 0 within 60s post-reconnect",
            "No duplicate events delivered (idempotency check)",
        ],
    )


def postgres_slowdown() -> ChaosScenario:
    """
    Add latency to Postgres and verify services degrade gracefully (no crash).

    Uses cpu_stress on the postgres container to simulate I/O slowdown.
    Expected behavior: query latency rises but services remain available,
    returning cached results or 503 with Retry-After instead of 500.
    """
    return ChaosScenario(
        target_service="postgres",
        failure_type="cpu_stress",
        duration=30,
        cpu_load_pct=95,
        expected_behavior=(
            "Postgres queries slow down under CPU saturation. Services should "
            "detect elevated latency, serve stale cache where possible, and "
            "return 503 Retry-After for uncached queries instead of 500 errors."
        ),
        verification_steps=[
            "Measure p99 query latency — expect > 200ms but < 5s",
            "Verify town-core returns 503 (not 500) for uncached reads",
            "Check Redis hit rate increases during degradation",
            "After stress removed: query latency returns to baseline within 30s",
        ],
    )


# ---------------------------------------------------------------------------
# Full suite runner
# ---------------------------------------------------------------------------

@dataclass
class SuiteReport:
    """Combined report for all chaos scenarios."""
    reports: list[ChaosReport] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def passed_count(self) -> int:
        return sum(1 for r in self.reports if r.passed())

    def failed_count(self) -> int:
        return sum(1 for r in self.reports if not r.passed())

    def total_count(self) -> int:
        return len(self.reports)

    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total": self.total_count(),
            "passed": self.passed_count(),
            "failed": self.failed_count(),
            "scenarios": [r.summary() for r in self.reports],
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        logger.info("Suite report saved to %s", path)

    def print_summary(self) -> None:
        print("\n=== Chaos Suite Report ===")
        print(f"  Start:  {self.start_time}")
        print(f"  End:    {self.end_time}")
        print(f"  Passed: {self.passed_count()}/{self.total_count()}")
        for r in self.reports:
            status = "PASS" if r.passed() else "FAIL"
            print(
                f"  [{status}] {r.scenario.target_service} "
                f"({r.scenario.failure_type}) "
                f"recovery={r.recovery_time_seconds:.1f}s"
            )
        print("==========================\n")


def full_chaos_suite(
    compose_path: str = DEFAULT_COMPOSE,
    services: Optional[list[str]] = None,
    dry_run: bool = False,
    report_path: str = "/tmp/qtown_chaos_report.json",
) -> SuiteReport:
    """
    Run all chaos scenarios sequentially and generate a combined SuiteReport.

    Args:
        compose_path: path to docker-compose.yml
        services: override default service list
        dry_run: if True, log commands but don't execute them
        report_path: where to write the JSON report
    """
    runner = ChaosRunner(
        docker_compose_path=compose_path,
        services=services or ALL_SERVICES,
        dry_run=dry_run,
    )

    scenarios = [
        market_district_crash(),
        academy_timeout(),
        kafka_partition(),
        postgres_slowdown(),
    ]

    suite = SuiteReport(start_time=datetime.now(timezone.utc))

    for scenario in scenarios:
        logger.info(
            "Running scenario: %s / %s",
            scenario.target_service,
            scenario.failure_type,
        )
        try:
            report = runner.run_chaos_test(scenario)
            suite.reports.append(report)
        except Exception as exc:
            logger.error(
                "Scenario %s/%s crashed: %s",
                scenario.target_service, scenario.failure_type, exc,
            )

    suite.end_time = datetime.now(timezone.utc)
    suite.print_summary()
    suite.save(report_path)
    return suite


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Qtown chaos test suite")
    parser.add_argument("--compose", default=DEFAULT_COMPOSE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default="/tmp/qtown_chaos_report.json")
    parser.add_argument(
        "--scenario",
        choices=["market_district_crash", "academy_timeout",
                 "kafka_partition", "postgres_slowdown", "all"],
        default="all",
    )
    args = parser.parse_args()

    if args.scenario == "all":
        full_chaos_suite(
            compose_path=args.compose,
            dry_run=args.dry_run,
            report_path=args.report,
        )
    else:
        scenario_map = {
            "market_district_crash": market_district_crash,
            "academy_timeout": academy_timeout,
            "kafka_partition": kafka_partition,
            "postgres_slowdown": postgres_slowdown,
        }
        runner = ChaosRunner(
            docker_compose_path=args.compose,
            services=ALL_SERVICES,
            dry_run=args.dry_run,
        )
        scenario = scenario_map[args.scenario]()
        report = runner.run_chaos_test(scenario)
        print(json.dumps(report.summary(), indent=2))
