// Package telemetry provides OpenTelemetry tracing and Prometheus metrics
// for the market-district service.
package telemetry

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// ---------------------------------------------------------------------------
// Prometheus metrics
// ---------------------------------------------------------------------------

var (
	// OrderMatchDuration tracks how long it takes to match an order.
	OrderMatchDuration = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "order_match_duration_seconds",
		Help:    "Duration of order matching operations",
		Buckets: prometheus.DefBuckets,
	})

	// OrderBookDepth is the current depth of the order book.
	OrderBookDepth = promauto.NewGaugeVec(prometheus.GaugeOpts{
		Name: "order_book_depth",
		Help: "Current number of open orders per side and resource",
	}, []string{"side", "resource"})

	// GRPCRequestTotal counts total gRPC requests.
	GRPCRequestTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "grpc_request_total",
		Help: "Total number of gRPC requests handled",
	}, []string{"method", "status"})

	// ErrorTotal counts total errors by component.
	ErrorTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "error_total",
		Help: "Total errors by component",
	}, []string{"component"})
)

// ---------------------------------------------------------------------------
// Tracer
// ---------------------------------------------------------------------------

var globalTracer trace.Tracer

// InitTelemetry configures an OTLP gRPC trace exporter pointing at Jaeger
// and starts a Prometheus /metrics HTTP endpoint.
//
// It must be called once at application startup. The returned shutdown function
// should be deferred to flush any pending spans.
func InitTelemetry(serviceName string) (shutdown func(context.Context) error, err error) {
	otlpEndpoint := getEnv("OTLP_ENDPOINT", "localhost:4317")
	prometheusPort := getEnv("PROMETHEUS_PORT", "9201")

	// --- OTLP exporter ---
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(
		ctx,
		otlpEndpoint,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to dial OTLP endpoint %s: %w", otlpEndpoint, err)
	}

	exporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
	if err != nil {
		return nil, fmt.Errorf("failed to create OTLP trace exporter: %w", err)
	}

	// --- TracerProvider ---
	res, err := resource.Merge(
		resource.Default(),
		resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName(serviceName),
			semconv.ServiceVersion(getEnv("SERVICE_VERSION", "0.1.0")),
			attribute.String("deployment.environment", getEnv("ENVIRONMENT", "development")),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create OTel resource: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(
		propagation.NewCompositeTextMapPropagator(
			propagation.TraceContext{},
			propagation.Baggage{},
		),
	)

	globalTracer = otel.Tracer(serviceName)

	// --- Prometheus metrics HTTP server ---
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	go func() {
		addr := ":" + prometheusPort
		log.Printf("[telemetry] Prometheus metrics listening on %s", addr)
		if serveErr := http.ListenAndServe(addr, mux); serveErr != nil {
			log.Printf("[telemetry] Prometheus server error: %v", serveErr)
		}
	}()

	shutdownFn := func(shutdownCtx context.Context) error {
		return tp.Shutdown(shutdownCtx)
	}
	return shutdownFn, nil
}

// ---------------------------------------------------------------------------
// Span helpers
// ---------------------------------------------------------------------------

// TraceOrderMatch creates a span for an order match operation.
// It also records the duration to the OrderMatchDuration histogram.
func TraceOrderMatch(ctx context.Context, orderID string) (context.Context, trace.Span) {
	if globalTracer == nil {
		return ctx, noopSpan(ctx)
	}
	ctx, span := globalTracer.Start(
		ctx,
		"market.order_match",
		trace.WithAttributes(attribute.String("order.id", orderID)),
	)
	return ctx, &timedSpan{Span: span, histogram: OrderMatchDuration}
}

// TraceGRPC creates a span for an inbound gRPC call and increments the request counter.
func TraceGRPC(ctx context.Context, method string) (context.Context, trace.Span) {
	if globalTracer == nil {
		return ctx, noopSpan(ctx)
	}
	ctx, span := globalTracer.Start(
		ctx,
		"grpc.server.call",
		trace.WithAttributes(attribute.String("rpc.method", method)),
	)
	return ctx, &grpcSpan{Span: span, method: method}
}

// ---------------------------------------------------------------------------
// timedSpan — wraps a span and records elapsed time to a histogram on End()
// ---------------------------------------------------------------------------

type timedSpan struct {
	trace.Span
	histogram prometheus.Observer
	start     time.Time
}

func (s *timedSpan) End(options ...trace.SpanEndOption) {
	elapsed := time.Since(s.start).Seconds()
	s.histogram.Observe(elapsed)
	s.Span.End(options...)
}

// grpcSpan — wraps a span and records the gRPC counter on End()
type grpcSpan struct {
	trace.Span
	method string
}

func (s *grpcSpan) End(options ...trace.SpanEndOption) {
	status := "ok"
	if !s.Span.IsRecording() {
		status = "error"
	}
	GRPCRequestTotal.WithLabelValues(s.method, status).Inc()
	s.Span.End(options...)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func noopSpan(ctx context.Context) trace.Span {
	_, span := otel.Tracer("noop").Start(ctx, "noop")
	return span
}
