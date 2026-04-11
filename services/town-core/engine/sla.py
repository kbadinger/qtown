"""SLA monitoring for Qtown services.

Defines per-service SLA budgets and tracks compliance over a rolling window.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

logger = logging.getLogger(__name__)

# ─── SLA Definitions ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SLADefinition:
    """Immutable SLA budget for one metric on one service."""
    service: str
    metric: str
    threshold_ms: float
    percentile: str  # e.g. "p95", "p99"

    def __str__(self) -> str:
        return f"{self.service}.{self.metric} < {self.threshold_ms}ms @{self.percentile}"


# Master SLA table — edit here to adjust budgets.
SLA_DEFINITIONS: list[SLADefinition] = [
    # town-core
    SLADefinition("town-core", "tick_processing_ms",  500.0, "p95"),
    SLADefinition("town-core", "api_response_ms",     100.0, "p95"),
    # market-district
    SLADefinition("market-district", "order_matching_ms",  5.0, "p99"),
    SLADefinition("market-district", "grpc_response_ms",  50.0, "p95"),
    # fortress
    SLADefinition("fortress", "validation_ms",       2.0, "p99"),
    SLADefinition("fortress", "grpc_response_ms",   30.0, "p95"),
    # academy
    SLADefinition("academy", "inference_ms",       5000.0, "p95"),
    SLADefinition("academy", "grpc_response_ms",    200.0, "p95"),
    # tavern
    SLADefinition("tavern", "websocket_broadcast_ms", 50.0, "p95"),
    SLADefinition("tavern", "redis_ops_ms",            5.0, "p99"),
    # cartographer
    SLADefinition("cartographer", "graphql_response_ms", 200.0, "p95"),
    # library
    SLADefinition("library", "search_ms", 100.0, "p95"),
]

# Build a fast lookup: (service, metric) → SLADefinition
_SLA_LOOKUP: dict[tuple[str, str], SLADefinition] = {
    (d.service, d.metric): d for d in SLA_DEFINITIONS
}

# ─── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SLAViolation:
    """Records a single SLA breach."""
    service: str
    metric: str
    value_ms: float
    threshold_ms: float
    percentile: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "metric": self.metric,
            "value_ms": self.value_ms,
            "threshold_ms": self.threshold_ms,
            "percentile": self.percentile,
            "timestamp": self.timestamp,
        }


@dataclass
class SLAResult:
    """Result of a single compliance check."""
    compliant: bool
    service: str
    metric: str
    value_ms: float
    threshold_ms: float
    percentile: str

    def to_dict(self) -> dict:
        return {
            "compliant": self.compliant,
            "service": self.service,
            "metric": self.metric,
            "value_ms": self.value_ms,
            "threshold_ms": self.threshold_ms,
            "percentile": self.percentile,
        }


@dataclass
class ServiceMetrics:
    """Aggregated percentile metrics for a single service."""
    service: str
    metrics: dict[str, "MetricSummary"]

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
        }


@dataclass
class MetricSummary:
    """p50/p95/p99 summary for one metric."""
    metric: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    sample_count: int
    threshold_ms: float
    percentile_target: str
    compliance_pct: float  # 0–100

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "sample_count": self.sample_count,
            "threshold_ms": self.threshold_ms,
            "percentile_target": self.percentile_target,
            "compliance_pct": self.compliance_pct,
        }


# ─── SLAMonitor ───────────────────────────────────────────────────────────────

class SLAMonitor:
    """Tracks SLA compliance across all Qtown services.

    Usage::

        monitor = SLAMonitor(window_size=10_000)
        result = monitor.check_compliance("town-core", "tick_processing_ms", 423.7)
        report = monitor.get_compliance_report()
    """

    def __init__(self, window_size: int = 10_000) -> None:
        """
        Args:
            window_size: Maximum number of samples retained per (service, metric) pair.
        """
        self._window_size = window_size
        # Samples: (service, metric) → deque of float (latency values in ms)
        self._samples: dict[tuple[str, str], Deque[float]] = {}
        # Violations stored in insertion order.
        self._violations: Deque[SLAViolation] = deque(maxlen=100_000)

    # ─── Public API ────────────────────────────────────────────────────────────

    def check_compliance(self, service: str, metric: str, value_ms: float) -> SLAResult:
        """Record a single measurement and check it against the SLA.

        Records the measurement regardless of whether an SLA is defined (so
        metrics can be tracked without a formal SLA).  Returns an SLAResult
        indicating whether the value is within budget.
        """
        key = (service, metric)
        sla = _SLA_LOOKUP.get(key)

        # Store sample.
        if key not in self._samples:
            self._samples[key] = deque(maxlen=self._window_size)
        self._samples[key].append(value_ms)

        if sla is None:
            # No SLA defined — treat as compliant.
            return SLAResult(
                compliant=True,
                service=service,
                metric=metric,
                value_ms=value_ms,
                threshold_ms=float("inf"),
                percentile="none",
            )

        compliant = value_ms <= sla.threshold_ms

        if not compliant:
            violation = SLAViolation(
                service=service,
                metric=metric,
                value_ms=value_ms,
                threshold_ms=sla.threshold_ms,
                percentile=sla.percentile,
            )
            self._violations.append(violation)
            logger.warning(
                "[sla] VIOLATION service=%s metric=%s value=%.2fms threshold=%.2fms",
                service, metric, value_ms, sla.threshold_ms,
            )

        return SLAResult(
            compliant=compliant,
            service=service,
            metric=metric,
            value_ms=value_ms,
            threshold_ms=sla.threshold_ms,
            percentile=sla.percentile,
        )

    def get_compliance_report(self) -> dict:
        """Return per-service compliance percentages.

        For each (service, metric) pair that has a defined SLA, calculates
        what fraction of recorded samples are within the threshold.

        Returns::

            {
              "town-core": {
                "tick_processing_ms": {"compliance_pct": 98.7, "threshold_ms": 500.0, ...},
                ...
              },
              ...
            }
        """
        report: dict[str, dict[str, dict]] = {}

        for sla in SLA_DEFINITIONS:
            key = (sla.service, sla.metric)
            samples = list(self._samples.get(key, []))

            if not samples:
                pct = 100.0  # No data → assume compliant.
                p50 = p95 = p99 = 0.0
            else:
                p50 = self._percentile(samples, 50)
                p95 = self._percentile(samples, 95)
                p99 = self._percentile(samples, 99)
                within = sum(1 for v in samples if v <= sla.threshold_ms)
                pct = round(within / len(samples) * 100, 2)

            report.setdefault(sla.service, {})[sla.metric] = {
                "compliance_pct": pct,
                "threshold_ms": sla.threshold_ms,
                "percentile_target": sla.percentile,
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
                "sample_count": len(samples),
            }

        return report

    def get_violations(self, hours: int = 24) -> list[SLAViolation]:
        """Return violations from the past *hours* hours, newest first."""
        cutoff = time.time() - hours * 3600
        return [v for v in reversed(self._violations) if v.timestamp >= cutoff]

    def get_service_metrics(self, service: str) -> ServiceMetrics:
        """Return full p50/p95/p99 breakdown for a single service."""
        metrics: dict[str, MetricSummary] = {}

        for sla in SLA_DEFINITIONS:
            if sla.service != service:
                continue
            key = (service, sla.metric)
            samples = list(self._samples.get(key, []))

            if samples:
                p50 = self._percentile(samples, 50)
                p95 = self._percentile(samples, 95)
                p99 = self._percentile(samples, 99)
                within = sum(1 for v in samples if v <= sla.threshold_ms)
                pct = round(within / len(samples) * 100, 2)
            else:
                p50 = p95 = p99 = 0.0
                pct = 100.0

            metrics[sla.metric] = MetricSummary(
                metric=sla.metric,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                sample_count=len(samples),
                threshold_ms=sla.threshold_ms,
                percentile_target=sla.percentile,
                compliance_pct=pct,
            )

        return ServiceMetrics(service=service, metrics=metrics)

    def record_batch(self, service: str, metric: str, values_ms: list[float]) -> list[SLAResult]:
        """Convenience method: record multiple measurements at once."""
        return [self.check_compliance(service, metric, v) for v in values_ms]

    # ─── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _percentile(values: list[float], pct: int) -> float:
        """Return the *pct*-th percentile of *values* (nearest-rank method)."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, int(len(sorted_vals) * pct / 100) - 1)
        return round(sorted_vals[idx], 3)


# ─── Module-level singleton ────────────────────────────────────────────────────

_monitor: SLAMonitor | None = None


def get_monitor() -> SLAMonitor:
    """Return the module-level SLAMonitor singleton (creates it on first call)."""
    global _monitor
    if _monitor is None:
        _monitor = SLAMonitor()
    return _monitor
