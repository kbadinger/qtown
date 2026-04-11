"""OpenTelemetry instrumentation for the town-core service.

Initialise once at startup::

    from engine.telemetry import init_telemetry
    init_telemetry()

Then use the span helpers anywhere in the codebase::

    from engine.telemetry import trace_tick
    with trace_tick(tick_number=42):
        ...
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Generator
from typing import Any

# --- OpenTelemetry --------------------------------------------------------
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# --- Prometheus client -----------------------------------------------------
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9100"))
SERVICE_NAME_DEFAULT = "town-core"

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

tick_duration_seconds = Histogram(
    "tick_duration_seconds",
    "Duration of a single game-tick processing cycle",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

active_npcs = Gauge(
    "active_npcs",
    "Number of NPCs currently active in the simulation",
)

kafka_produce_total = Counter(
    "kafka_produce_total",
    "Total number of messages produced to Kafka",
    labelnames=["topic"],
)

error_total = Counter(
    "error_total",
    "Total number of errors encountered",
    labelnames=["component"],
)

# ---------------------------------------------------------------------------
# Global tracer (populated by init_telemetry)
# ---------------------------------------------------------------------------

_tracer: trace.Tracer | None = None


def init_telemetry(service_name: str = SERVICE_NAME_DEFAULT) -> None:
    """Configure OTLP trace exporter and start the Prometheus metrics HTTP server.

    Must be called once at application startup before using any span helpers.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _tracer
    if _tracer is not None:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("SERVICE_VERSION", "0.1.0"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    exporter = OTLPSpanExporter(
        endpoint=OTLP_ENDPOINT,
        insecure=True,
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _tracer = trace.get_tracer(service_name)

    # Start Prometheus metrics server on a dedicated port
    start_http_server(PROMETHEUS_PORT)


def _get_tracer() -> trace.Tracer:
    if _tracer is None:
        raise RuntimeError("Telemetry not initialised — call init_telemetry() first")
    return _tracer


# ---------------------------------------------------------------------------
# Span helpers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def trace_tick(tick_number: int) -> Generator[trace.Span, None, None]:
    """Context manager that wraps the processing of a single game tick.

    Records tick duration to the Prometheus histogram and creates an OTLP span.
    """
    tracer = _get_tracer()
    start = time.perf_counter()
    with tracer.start_as_current_span(
        "town_core.tick",
        attributes={"tick.number": tick_number},
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            error_total.labels(component="tick").inc()
            raise
        finally:
            elapsed = time.perf_counter() - start
            tick_duration_seconds.observe(elapsed)


@contextlib.contextmanager
def trace_kafka_produce(topic: str, key: str | None = None) -> Generator[trace.Span, None, None]:
    """Context manager that wraps a Kafka produce call.

    Increments the kafka_produce_total counter for the given topic.
    """
    tracer = _get_tracer()
    attrs: dict[str, Any] = {"messaging.destination": topic}
    if key is not None:
        attrs["messaging.kafka.message_key"] = key

    with tracer.start_as_current_span("kafka.produce", attributes=attrs) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            error_total.labels(component="kafka_producer").inc()
            raise
        finally:
            kafka_produce_total.labels(topic=topic).inc()


@contextlib.contextmanager
def trace_travel(npc_id: str, destination: str) -> Generator[trace.Span, None, None]:
    """Context manager that wraps an NPC travel operation."""
    tracer = _get_tracer()
    with tracer.start_as_current_span(
        "npc.travel",
        attributes={"npc.id": npc_id, "npc.destination": destination},
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            error_total.labels(component="npc_travel").inc()
            raise
