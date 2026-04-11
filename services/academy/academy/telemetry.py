"""OpenTelemetry instrumentation for the Academy (AI inference) service.

Initialise once at startup::

    from academy.telemetry import init_telemetry
    init_telemetry()

Span helpers::

    from academy.telemetry import trace_inference, trace_rag_query
    with trace_inference(model="llama3", task_type="dialogue"):
        ...
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Generator
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram, start_http_server

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9103"))
SERVICE_NAME_DEFAULT = "academy"

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

inference_duration_seconds = Histogram(
    "inference_duration_seconds",
    "Duration of model inference calls",
    labelnames=["model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

rag_query_duration_seconds = Histogram(
    "rag_query_duration_seconds",
    "Duration of RAG retrieval + generation queries",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

tokens_total = Counter(
    "tokens_total",
    "Total tokens consumed by model inference",
    labelnames=["model", "direction"],  # direction: prompt | completion
)

error_total = Counter(
    "error_total",
    "Total errors by component",
    labelnames=["component"],
)

# ---------------------------------------------------------------------------
# Global tracer
# ---------------------------------------------------------------------------

_tracer: trace.Tracer | None = None


def init_telemetry(service_name: str = SERVICE_NAME_DEFAULT) -> None:
    """Configure OTLP exporter and start Prometheus HTTP server.

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

    exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _tracer = trace.get_tracer(service_name)

    start_http_server(PROMETHEUS_PORT)


def _get_tracer() -> trace.Tracer:
    if _tracer is None:
        raise RuntimeError("Telemetry not initialised — call init_telemetry() first")
    return _tracer


# ---------------------------------------------------------------------------
# Span helpers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def trace_inference(
    model: str,
    task_type: str,
    prompt_tokens: int = 0,
) -> Generator[trace.Span, None, None]:
    """Context manager for a model inference call.

    Records wall-clock duration per model and increments prompt token counter.
    Completion tokens can be added inside the ``with`` block via
    ``tokens_total.labels(model=model, direction='completion').inc(n)``.
    """
    tracer = _get_tracer()
    start = time.perf_counter()
    attrs: dict[str, Any] = {
        "ai.model": model,
        "ai.task_type": task_type,
        "ai.prompt_tokens": prompt_tokens,
    }
    with tracer.start_as_current_span("academy.inference", attributes=attrs) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            error_total.labels(component="inference").inc()
            raise
        finally:
            elapsed = time.perf_counter() - start
            inference_duration_seconds.labels(model=model).observe(elapsed)
            if prompt_tokens:
                tokens_total.labels(model=model, direction="prompt").inc(prompt_tokens)


@contextlib.contextmanager
def trace_rag_query(query: str) -> Generator[trace.Span, None, None]:
    """Context manager for a Retrieval-Augmented Generation query."""
    tracer = _get_tracer()
    start = time.perf_counter()
    # Truncate long queries for the span name
    short_query = query[:100] + ("…" if len(query) > 100 else "")
    with tracer.start_as_current_span(
        "academy.rag_query",
        attributes={"rag.query": short_query},
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            error_total.labels(component="rag").inc()
            raise
        finally:
            elapsed = time.perf_counter() - start
            rag_query_duration_seconds.observe(elapsed)
