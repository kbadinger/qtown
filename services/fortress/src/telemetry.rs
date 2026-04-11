//! OpenTelemetry + Prometheus instrumentation for the Fortress validation service.
//!
//! # Usage
//!
//! ```rust,no_run
//! use fortress::telemetry::{init_telemetry, trace_validation};
//!
//! #[tokio::main]
//! async fn main() {
//!     let _guard = init_telemetry("fortress").await.expect("telemetry init failed");
//!     // ...
//!     let _span = trace_validation("evt-001");
//! }
//! ```

use std::env;
use std::time::Instant;

use opentelemetry::global;
use opentelemetry::trace::{Span, SpanKind, Tracer, TracerProvider as _};
use opentelemetry::{KeyValue, StringValue};
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::propagation::TraceContextPropagator;
use opentelemetry_sdk::trace::{self as sdktrace, TracerProvider};
use opentelemetry_sdk::Resource;
use prometheus::{
    Counter, CounterVec, Histogram, HistogramOpts, HistogramVec, IntCounterVec, Opts, Registry,
};
use std::sync::OnceLock;

// ---------------------------------------------------------------------------
// Prometheus metrics
// ---------------------------------------------------------------------------

static REGISTRY: OnceLock<Registry> = OnceLock::new();

/// Duration (seconds) of each event validation operation.
static VALIDATION_DURATION: OnceLock<Histogram> = OnceLock::new();

/// Total validations processed (labelled by result: ok | rejected).
static VALIDATIONS_TOTAL: OnceLock<CounterVec> = OnceLock::new();

/// Total rejections.
static REJECTIONS_TOTAL: OnceLock<Counter> = OnceLock::new();

fn registry() -> &'static Registry {
    REGISTRY.get_or_init(|| {
        let reg = Registry::new();

        let duration = Histogram::with_opts(
            HistogramOpts::new(
                "validation_duration_seconds",
                "Duration of event validation operations",
            )
            .buckets(vec![0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1]),
        )
        .expect("failed to create validation_duration_seconds histogram");
        reg.register(Box::new(duration.clone()))
            .expect("failed to register validation_duration_seconds");
        VALIDATION_DURATION
            .set(duration)
            .expect("failed to set VALIDATION_DURATION");

        let validations = CounterVec::new(
            Opts::new("validations_total", "Total validations processed"),
            &["result"],
        )
        .expect("failed to create validations_total counter");
        reg.register(Box::new(validations.clone()))
            .expect("failed to register validations_total");
        VALIDATIONS_TOTAL
            .set(validations)
            .expect("failed to set VALIDATIONS_TOTAL");

        let rejections = Counter::new("rejections_total", "Total events rejected by fortress")
            .expect("failed to create rejections_total counter");
        reg.register(Box::new(rejections.clone()))
            .expect("failed to register rejections_total");
        REJECTIONS_TOTAL
            .set(rejections)
            .expect("failed to set REJECTIONS_TOTAL");

        reg
    })
}

// ---------------------------------------------------------------------------
// Guard type — shuts down the tracer provider on drop
// ---------------------------------------------------------------------------

/// Returned by [`init_telemetry`].  Keep alive for the duration of the process.
pub struct TelemetryGuard {
    provider: TracerProvider,
}

impl Drop for TelemetryGuard {
    fn drop(&mut self) {
        if let Err(e) = self.provider.shutdown() {
            eprintln!("[telemetry] Error shutting down tracer provider: {e}");
        }
    }
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

/// Initialise OpenTelemetry with an OTLP gRPC exporter and start Prometheus.
///
/// # Errors
///
/// Returns an error if the OTLP exporter cannot be created.
pub async fn init_telemetry(
    service_name: &str,
) -> Result<TelemetryGuard, Box<dyn std::error::Error + Send + Sync>> {
    let otlp_endpoint =
        env::var("OTLP_ENDPOINT").unwrap_or_else(|_| "http://localhost:4317".to_string());
    let prometheus_port: u16 = env::var("PROMETHEUS_PORT")
        .unwrap_or_else(|_| "9202".to_string())
        .parse()
        .unwrap_or(9202);

    // --- Propagator ---
    global::set_text_map_propagator(TraceContextPropagator::new());

    // --- OTLP exporter ---
    let exporter = opentelemetry_otlp::new_exporter()
        .tonic()
        .with_endpoint(&otlp_endpoint)
        .build_span_exporter()?;

    // --- Resource ---
    let resource = Resource::new(vec![
        KeyValue::new("service.name", service_name.to_string()),
        KeyValue::new(
            "service.version",
            env::var("SERVICE_VERSION").unwrap_or_else(|_| "0.1.0".to_string()),
        ),
        KeyValue::new(
            "deployment.environment",
            env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string()),
        ),
    ]);

    // --- TracerProvider ---
    let provider = sdktrace::TracerProvider::builder()
        .with_batch_exporter(exporter, opentelemetry_sdk::runtime::Tokio)
        .with_resource(resource)
        .build();

    global::set_tracer_provider(provider.clone());

    // Ensure metrics registry is initialised
    let _ = registry();

    // --- Prometheus HTTP server ---
    let addr = format!("0.0.0.0:{prometheus_port}");
    let reg_clone = registry().clone();
    tokio::spawn(async move {
        serve_metrics(addr, reg_clone).await;
    });

    tracing::info!(
        service = service_name,
        otlp_endpoint = %otlp_endpoint,
        prometheus_port = prometheus_port,
        "Telemetry initialised"
    );

    Ok(TelemetryGuard { provider })
}

// ---------------------------------------------------------------------------
// Prometheus HTTP server (minimal hyper/axum-free implementation)
// ---------------------------------------------------------------------------

async fn serve_metrics(addr: String, registry: Registry) {
    use prometheus::Encoder;
    use std::convert::Infallible;
    use std::net::SocketAddr;

    let addr: SocketAddr = addr.parse().expect("invalid prometheus bind address");
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("failed to bind prometheus listener");

    tracing::info!("Prometheus metrics listening on {addr}");

    loop {
        let Ok((stream, _)) = listener.accept().await else {
            continue;
        };
        let reg = registry.clone();
        tokio::spawn(async move {
            let mut buf = [0u8; 512];
            let _ = stream.peek(&mut buf).await;

            let mut body = Vec::new();
            let encoder = prometheus::TextEncoder::new();
            let metric_families = reg.gather();
            encoder
                .encode(&metric_families, &mut body)
                .expect("failed to encode metrics");

            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: text/plain; version=0.0.4\r\nContent-Length: {}\r\n\r\n",
                body.len()
            );

            use tokio::io::AsyncWriteExt;
            let mut stream = stream;
            let _ = stream.write_all(response.as_bytes()).await;
            let _ = stream.write_all(&body).await;
        });
    }
}

// ---------------------------------------------------------------------------
// Span helpers
// ---------------------------------------------------------------------------

/// Create a span for validating a single event.
///
/// Call `.end()` on the returned span (or drop it) when validation completes.
/// The function also records duration to `validation_duration_seconds` and
/// increments `validations_total`.
pub fn trace_validation(event_id: &str) -> ValidationSpan {
    let tracer = global::tracer("fortress");
    let span = tracer
        .span_builder("fortress.validate_event")
        .with_kind(SpanKind::Internal)
        .with_attributes(vec![KeyValue::new("event.id", event_id.to_string())])
        .start(&tracer);

    ValidationSpan {
        inner: span,
        start: Instant::now(),
    }
}

/// RAII guard for a validation span.  Ends the span and records metrics on drop.
pub struct ValidationSpan {
    inner: sdktrace::Span,
    start: Instant,
}

impl ValidationSpan {
    /// Mark the validation as rejected and end the span.
    pub fn reject(mut self, reason: &str) {
        self.inner.set_attribute(KeyValue::new(
            "validation.result",
            StringValue::from("rejected"),
        ));
        self.inner
            .set_attribute(KeyValue::new("validation.rejection_reason", reason.to_string()));
        if let Some(c) = REJECTIONS_TOTAL.get() {
            c.inc();
        }
        if let Some(c) = VALIDATIONS_TOTAL.get() {
            c.with_label_values(&["rejected"]).inc();
        }
        self.record_duration();
        self.inner.end();
        std::mem::forget(self); // Prevent double-end in Drop
    }

    fn record_duration(&self) {
        let elapsed = self.start.elapsed().as_secs_f64();
        if let Some(h) = VALIDATION_DURATION.get() {
            h.observe(elapsed);
        }
    }
}

impl Drop for ValidationSpan {
    fn drop(&mut self) {
        // Normal (accepted) path
        self.inner.set_attribute(KeyValue::new(
            "validation.result",
            StringValue::from("ok"),
        ));
        if let Some(c) = VALIDATIONS_TOTAL.get() {
            c.with_label_values(&["ok"]).inc();
        }
        self.record_duration();
        self.inner.end();
    }
}
