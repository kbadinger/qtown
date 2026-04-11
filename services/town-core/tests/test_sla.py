"""Tests for engine/sla.py — SLA monitoring and compliance tracking."""
import time
from engine.sla import SLAMonitor, SLA_DEFINITIONS, SLAViolation


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_monitor() -> SLAMonitor:
    return SLAMonitor(window_size=1000)


# ─── test_compliance_pass ─────────────────────────────────────────────────────

def test_compliance_pass_tick_processing():
    """Value well within the town-core tick_processing_ms SLA (500ms p95)."""
    monitor = make_monitor()
    result = monitor.check_compliance("town-core", "tick_processing_ms", 350.0)
    assert result.compliant is True
    assert result.service == "town-core"
    assert result.metric == "tick_processing_ms"
    assert result.value_ms == 350.0
    assert result.threshold_ms == 500.0


def test_compliance_pass_exact_threshold():
    """Value exactly at the threshold is compliant (≤ threshold)."""
    monitor = make_monitor()
    result = monitor.check_compliance("market-district", "order_matching_ms", 5.0)
    assert result.compliant is True


def test_compliance_pass_fortress_validation():
    """Fortress validation SLA: 2ms p99."""
    monitor = make_monitor()
    result = monitor.check_compliance("fortress", "validation_ms", 1.8)
    assert result.compliant is True
    assert result.threshold_ms == 2.0


def test_compliance_pass_academy_inference():
    """Academy inference has a generous 5000ms p95 SLA."""
    monitor = make_monitor()
    result = monitor.check_compliance("academy", "inference_ms", 3200.0)
    assert result.compliant is True


def test_compliance_pass_no_sla_defined():
    """Metrics without a defined SLA should always be reported as compliant."""
    monitor = make_monitor()
    result = monitor.check_compliance("unknown-service", "some_metric", 99999.0)
    assert result.compliant is True
    assert result.threshold_ms == float("inf")


# ─── test_compliance_violation ────────────────────────────────────────────────

def test_compliance_violation_tick_processing():
    """Value exceeding the SLA threshold → violation logged."""
    monitor = make_monitor()
    result = monitor.check_compliance("town-core", "tick_processing_ms", 650.0)
    assert result.compliant is False

    violations = monitor.get_violations(hours=1)
    assert len(violations) == 1
    v = violations[0]
    assert v.service == "town-core"
    assert v.metric == "tick_processing_ms"
    assert v.value_ms == 650.0
    assert v.threshold_ms == 500.0


def test_compliance_violation_order_matching():
    """Market order matching SLA: 5ms p99."""
    monitor = make_monitor()
    result = monitor.check_compliance("market-district", "order_matching_ms", 8.3)
    assert result.compliant is False
    violations = monitor.get_violations()
    assert any(
        v.service == "market-district" and v.metric == "order_matching_ms"
        for v in violations
    )


def test_compliance_multiple_violations():
    """Multiple violations are all recorded and retrievable."""
    monitor = make_monitor()

    offenders = [
        ("town-core", "tick_processing_ms", 600.0),
        ("fortress", "validation_ms", 10.0),
        ("tavern", "websocket_broadcast_ms", 200.0),
    ]

    for service, metric, value in offenders:
        result = monitor.check_compliance(service, metric, value)
        assert result.compliant is False

    violations = monitor.get_violations(hours=1)
    assert len(violations) == len(offenders)


def test_compliance_violation_not_returned_outside_window():
    """Violations older than the requested hours window are excluded."""
    monitor = make_monitor()

    # Inject a violation with a timestamp in the past.
    old_violation = SLAViolation(
        service="town-core",
        metric="tick_processing_ms",
        value_ms=999.0,
        threshold_ms=500.0,
        percentile="p95",
        timestamp=time.time() - 48 * 3600,  # 48 hours ago
    )
    monitor._violations.append(old_violation)

    # A fresh violation.
    monitor.check_compliance("town-core", "tick_processing_ms", 700.0)

    # Only the recent one should be returned with hours=24.
    violations = monitor.get_violations(hours=24)
    assert len(violations) == 1
    assert violations[0].value_ms == 700.0


# ─── test_compliance_report ───────────────────────────────────────────────────

def test_compliance_report_all_pass():
    """When all values are within SLA, every service shows 100% compliance."""
    monitor = make_monitor()

    # Record passing values for every defined SLA.
    for sla_def in SLA_DEFINITIONS:
        monitor.check_compliance(sla_def.service, sla_def.metric, sla_def.threshold_ms * 0.5)

    report = monitor.get_compliance_report()

    for sla_def in SLA_DEFINITIONS:
        assert sla_def.service in report, f"Service {sla_def.service!r} missing from report"
        svc_report = report[sla_def.service]
        assert sla_def.metric in svc_report, f"Metric {sla_def.metric!r} missing from {sla_def.service}"
        assert svc_report[sla_def.metric]["compliance_pct"] == 100.0


def test_compliance_report_partial_violations():
    """When some values breach the SLA, compliance_pct is proportional."""
    monitor = make_monitor()

    # Send 8 passing and 2 failing values for town-core tick_processing_ms.
    for _ in range(8):
        monitor.check_compliance("town-core", "tick_processing_ms", 200.0)  # pass
    for _ in range(2):
        monitor.check_compliance("town-core", "tick_processing_ms", 600.0)  # fail

    report = monitor.get_compliance_report()
    pct = report["town-core"]["tick_processing_ms"]["compliance_pct"]
    assert pct == 80.0


def test_compliance_report_no_data_is_100():
    """Services with no recorded samples should show 100% compliance."""
    monitor = make_monitor()
    report = monitor.get_compliance_report()

    for sla_def in SLA_DEFINITIONS:
        pct = report[sla_def.service][sla_def.metric]["compliance_pct"]
        assert pct == 100.0, (
            f"Expected 100% for {sla_def.service}.{sla_def.metric} with no data, got {pct}"
        )


def test_compliance_report_contains_all_services():
    """The report covers all 7 services defined in SLA_DEFINITIONS."""
    monitor = make_monitor()
    report = monitor.get_compliance_report()

    expected_services = {d.service for d in SLA_DEFINITIONS}
    assert set(report.keys()) == expected_services


def test_compliance_report_percentile_values():
    """Compliance report includes p50/p95/p99 percentile values."""
    monitor = make_monitor()

    values = [10.0, 20.0, 50.0, 80.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0]
    for v in values:
        monitor.check_compliance("library", "search_ms", v)

    report = monitor.get_compliance_report()
    metric_report = report["library"]["search_ms"]

    assert "p50_ms" in metric_report
    assert "p95_ms" in metric_report
    assert "p99_ms" in metric_report
    assert metric_report["p50_ms"] <= metric_report["p95_ms"] <= metric_report["p99_ms"]
    assert metric_report["sample_count"] == len(values)


# ─── test_service_metrics ──────────────────────────────────────────────────────

def test_get_service_metrics():
    """get_service_metrics returns MetricSummary objects for the requested service."""
    monitor = make_monitor()

    for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
        monitor.check_compliance("cartographer", "graphql_response_ms", v)

    svc_metrics = monitor.get_service_metrics("cartographer")
    assert svc_metrics.service == "cartographer"
    assert "graphql_response_ms" in svc_metrics.metrics

    summary = svc_metrics.metrics["graphql_response_ms"]
    assert summary.p50_ms > 0
    assert summary.sample_count == 5
    assert summary.threshold_ms == 200.0


# ─── test_record_batch ────────────────────────────────────────────────────────

def test_record_batch():
    """record_batch processes multiple measurements and returns one SLAResult per value."""
    monitor = make_monitor()
    values = [10.0, 20.0, 500.0, 600.0, 50.0]
    results = monitor.record_batch("tavern", "websocket_broadcast_ms", values)

    assert len(results) == len(values)
    # Values > 50ms (the SLA threshold) should be violations.
    compliance = [r.compliant for r in results]
    assert compliance == [True, True, False, False, True]


# ─── test_get_violations_order ────────────────────────────────────────────────

def test_get_violations_newest_first():
    """get_violations returns violations in reverse chronological order."""
    monitor = make_monitor()

    monitor.check_compliance("town-core", "tick_processing_ms", 600.0)
    time.sleep(0.01)
    monitor.check_compliance("fortress", "validation_ms", 5.0)

    violations = monitor.get_violations(hours=1)
    assert len(violations) == 2
    # Newest first.
    assert violations[0].service == "fortress"
    assert violations[1].service == "town-core"
