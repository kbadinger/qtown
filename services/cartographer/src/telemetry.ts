/**
 * OpenTelemetry + Prometheus instrumentation for the Cartographer GraphQL service.
 *
 * @example
 * ```ts
 * import { initTelemetry, traceGraphQLResolve, traceDataLoaderBatch } from './telemetry';
 *
 * await initTelemetry('cartographer');
 * ```
 */

import {
  context,
  diag,
  DiagConsoleLogger,
  DiagLogLevel,
  SpanStatusCode,
  trace,
} from '@opentelemetry/api';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { Counter, Histogram, Registry, collectDefaultMetrics } from 'prom-client';
import * as http from 'http';

// ---------------------------------------------------------------------------
// Prometheus metrics
// ---------------------------------------------------------------------------

const metricsRegistry = new Registry();
collectDefaultMetrics({ register: metricsRegistry });

export const graphqlResolveDurationSeconds = new Histogram({
  name: 'graphql_resolve_duration_seconds',
  help: 'Duration of GraphQL field resolver executions',
  labelNames: ['field_name', 'parent_type'] as const,
  buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
  registers: [metricsRegistry],
});

export const dataloaderBatchSize = new Histogram({
  name: 'dataloader_batch_size',
  help: 'Size of DataLoader batch requests',
  labelNames: ['loader_name'] as const,
  buckets: [1, 2, 5, 10, 25, 50, 100, 250, 500],
  registers: [metricsRegistry],
});

export const graphqlRequestsTotal = new Counter({
  name: 'graphql_requests_total',
  help: 'Total GraphQL requests processed',
  labelNames: ['operation_type', 'status'] as const,
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
 */
export async function initTelemetry(serviceName: string): Promise<void> {
  if (sdk !== null) return;

  const otlpEndpoint = process.env.OTLP_ENDPOINT ?? 'http://localhost:4317';
  const prometheusPort = parseInt(process.env.PROMETHEUS_PORT ?? '9105', 10);

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

  console.log(
    `[telemetry] ${serviceName} telemetry initialised (OTLP → ${otlpEndpoint})`,
  );
}

// ---------------------------------------------------------------------------
// Span helpers
// ---------------------------------------------------------------------------

/**
 * Wrap a GraphQL field resolver in a trace span.
 * Records resolve duration to the `graphql_resolve_duration_seconds` histogram.
 */
export async function traceGraphQLResolve<T>(
  fieldName: string,
  parentType: string,
  fn: () => Promise<T>,
): Promise<T> {
  const tracer = trace.getTracer('cartographer');
  const span = tracer.startSpan('graphql.resolve', {
    attributes: {
      'graphql.field': fieldName,
      'graphql.parent_type': parentType,
    },
  });

  const startTime = process.hrtime.bigint();

  return context.with(trace.setSpan(context.active(), span), async () => {
    try {
      const result = await fn();
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
      errorTotal.labels({ component: 'graphql_resolve' }).inc();
      throw err;
    } finally {
      const endTime = process.hrtime.bigint();
      const durationSeconds = Number(endTime - startTime) / 1e9;
      graphqlResolveDurationSeconds
        .labels({ field_name: fieldName, parent_type: parentType })
        .observe(durationSeconds);
      span.end();
    }
  });
}

/**
 * Wrap a DataLoader batch load in a trace span.
 * Records the batch size to `dataloader_batch_size`.
 */
export async function traceDataLoaderBatch<T>(
  loaderName: string,
  batchSize: number,
  fn: () => Promise<T>,
): Promise<T> {
  const tracer = trace.getTracer('cartographer');
  const span = tracer.startSpan('dataloader.batch', {
    attributes: {
      'dataloader.name': loaderName,
      'dataloader.batch_size': batchSize,
    },
  });

  return context.with(trace.setSpan(context.active(), span), async () => {
    try {
      const result = await fn();
      dataloaderBatchSize.labels({ loader_name: loaderName }).observe(batchSize);
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
      errorTotal.labels({ component: `dataloader_${loaderName}` }).inc();
      throw err;
    } finally {
      span.end();
    }
  });
}
