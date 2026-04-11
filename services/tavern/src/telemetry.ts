/**
 * OpenTelemetry + Prometheus instrumentation for the Tavern WebSocket gateway.
 *
 * @example
 * ```ts
 * import { initTelemetry, traceWebSocketBroadcast, traceRedisOp } from './telemetry';
 *
 * await initTelemetry('tavern');
 * ```
 */

import { diag, DiagConsoleLogger, DiagLogLevel, context, trace, SpanStatusCode } from '@opentelemetry/api';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { Counter, Gauge, Registry, collectDefaultMetrics } from 'prom-client';
import * as http from 'http';

// ---------------------------------------------------------------------------
// Prometheus metrics
// ---------------------------------------------------------------------------

const metricsRegistry = new Registry();
collectDefaultMetrics({ register: metricsRegistry });

export const wsConnectionsTotal = new Gauge({
  name: 'ws_connections_total',
  help: 'Current number of active WebSocket connections',
  registers: [metricsRegistry],
});

export const wsMessagesTotal = new Counter({
  name: 'ws_messages_total',
  help: 'Total WebSocket messages sent',
  labelNames: ['channel', 'direction'] as const,
  registers: [metricsRegistry],
});

export const redisOpsTotal = new Counter({
  name: 'redis_ops_total',
  help: 'Total Redis operations performed',
  labelNames: ['operation', 'status'] as const,
  registers: [metricsRegistry],
});

export const errorTotal = new Counter({
  name: 'error_total',
  help: 'Total errors by component',
  labelNames: ['component'] as const,
  registers: [metricsRegistry],
});

// ---------------------------------------------------------------------------
// SDK singleton
// ---------------------------------------------------------------------------

let sdk: NodeSDK | null = null;

/**
 * Initialise the OpenTelemetry Node SDK with an OTLP gRPC exporter and
 * start a Prometheus /metrics HTTP server.
 *
 * Safe to call once at startup.
 */
export async function initTelemetry(serviceName: string): Promise<void> {
  if (sdk !== null) return;

  const otlpEndpoint = process.env.OTLP_ENDPOINT ?? 'http://localhost:4317';
  const prometheusPort = parseInt(process.env.PROMETHEUS_PORT ?? '9104', 10);

  diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.WARN);

  const exporter = new OTLPTraceExporter({
    url: otlpEndpoint,
  });

  sdk = new NodeSDK({
    resource: new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: serviceName,
      [SemanticResourceAttributes.SERVICE_VERSION]: process.env.SERVICE_VERSION ?? '0.1.0',
      'deployment.environment': process.env.NODE_ENV ?? 'development',
    }),
    spanProcessor: new BatchSpanProcessor(exporter),
  });

  await sdk.start();

  // Prometheus HTTP server
  const server = http.createServer(async (req, res) => {
    if (req.url === '/metrics') {
      try {
        const metrics = await metricsRegistry.metrics();
        res.writeHead(200, { 'Content-Type': metricsRegistry.contentType });
        res.end(metrics);
      } catch (err) {
        res.writeHead(500);
        res.end(String(err));
      }
    } else {
      res.writeHead(404);
      res.end('Not found');
    }
  });

  server.listen(prometheusPort, () => {
    console.log(`[telemetry] Prometheus metrics listening on :${prometheusPort}`);
  });

  process.on('SIGTERM', async () => {
    await sdk?.shutdown();
    server.close();
  });

  console.log(`[telemetry] ${serviceName} telemetry initialised (OTLP → ${otlpEndpoint})`);
}

// ---------------------------------------------------------------------------
// Span helpers
// ---------------------------------------------------------------------------

/**
 * Wrap a WebSocket broadcast operation in a trace span.
 * Increments ws_messages_total for the given channel.
 */
export async function traceWebSocketBroadcast<T>(
  channel: string,
  messageCount: number,
  fn: () => Promise<T>,
): Promise<T> {
  const tracer = trace.getTracer('tavern');
  const span = tracer.startSpan('ws.broadcast', {
    attributes: {
      'ws.channel': channel,
      'ws.message_count': messageCount,
    },
  });

  return context.with(trace.setSpan(context.active(), span), async () => {
    try {
      const result = await fn();
      wsMessagesTotal.labels({ channel, direction: 'outbound' }).inc(messageCount);
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
      errorTotal.labels({ component: 'ws_broadcast' }).inc();
      throw err;
    } finally {
      span.end();
    }
  });
}

/**
 * Wrap a Redis operation in a trace span.
 * Increments redis_ops_total with the given operation name.
 */
export async function traceRedisOp<T>(
  operation: string,
  fn: () => Promise<T>,
): Promise<T> {
  const tracer = trace.getTracer('tavern');
  const span = tracer.startSpan('redis.op', {
    attributes: { 'db.operation': operation, 'db.system': 'redis' },
  });

  return context.with(trace.setSpan(context.active(), span), async () => {
    try {
      const result = await fn();
      redisOpsTotal.labels({ operation, status: 'ok' }).inc();
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
      redisOpsTotal.labels({ operation, status: 'error' }).inc();
      errorTotal.labels({ component: 'redis' }).inc();
      throw err;
    } finally {
      span.end();
    }
  });
}
