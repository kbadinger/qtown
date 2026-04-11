// GET /api/sla/compliance
// Proxies to town-core SLA monitor.
// Query params:
//   violations=true      → return violations list (with hours param)
//   service=<name>       → return per-service metrics
//   hours=N              → window for violations (default 24)

interface MetricReport {
  compliance_pct: number
  threshold_ms: number
  percentile_target: string
  p50_ms: number
  p95_ms: number
  p99_ms: number
  sample_count: number
}

type ComplianceReport = Record<string, Record<string, MetricReport>>

interface SLAViolation {
  service: string
  metric: string
  value_ms: number
  threshold_ms: number
  percentile: string
  timestamp: number
}

interface ServiceMetrics {
  service: string
  metrics: Record<string, MetricReport>
}

// Stub data for when town-core is unavailable in development.
function stubComplianceReport(): ComplianceReport {
  const services: Record<string, Array<{ metric: string; threshold: number; p: string }>> = {
    'town-core': [
      { metric: 'tick_processing_ms', threshold: 500, p: 'p95' },
      { metric: 'api_response_ms', threshold: 100, p: 'p95' },
    ],
    'market-district': [
      { metric: 'order_matching_ms', threshold: 5, p: 'p99' },
      { metric: 'grpc_response_ms', threshold: 50, p: 'p95' },
    ],
    'fortress': [
      { metric: 'validation_ms', threshold: 2, p: 'p99' },
      { metric: 'grpc_response_ms', threshold: 30, p: 'p95' },
    ],
    'academy': [
      { metric: 'inference_ms', threshold: 5000, p: 'p95' },
      { metric: 'grpc_response_ms', threshold: 200, p: 'p95' },
    ],
    'tavern': [
      { metric: 'websocket_broadcast_ms', threshold: 50, p: 'p95' },
      { metric: 'redis_ops_ms', threshold: 5, p: 'p99' },
    ],
    'cartographer': [
      { metric: 'graphql_response_ms', threshold: 200, p: 'p95' },
    ],
    'library': [
      { metric: 'search_ms', threshold: 100, p: 'p95' },
    ],
  }

  const report: ComplianceReport = {}
  for (const [svc, metrics] of Object.entries(services)) {
    report[svc] = {}
    for (const m of metrics) {
      const pct = 94 + Math.random() * 6  // 94–100%
      const p50 = m.threshold * 0.3
      const p95 = m.threshold * (0.7 + Math.random() * 0.4)
      const p99 = p95 * (1.1 + Math.random() * 0.3)
      report[svc][m.metric] = {
        compliance_pct: Math.round(pct * 10) / 10,
        threshold_ms: m.threshold,
        percentile_target: m.p,
        p50_ms: Math.round(p50 * 100) / 100,
        p95_ms: Math.round(p95 * 100) / 100,
        p99_ms: Math.round(p99 * 100) / 100,
        sample_count: 500 + Math.floor(Math.random() * 3000),
      }
    }
  }
  return report
}

function stubViolations(hours: number): SLAViolation[] {
  const violations: SLAViolation[] = []
  const services = ['town-core', 'market-district', 'fortress', 'academy']
  const metrics: Record<string, string> = {
    'town-core': 'tick_processing_ms',
    'market-district': 'order_matching_ms',
    'fortress': 'validation_ms',
    'academy': 'inference_ms',
  }
  const thresholds: Record<string, number> = {
    'tick_processing_ms': 500,
    'order_matching_ms': 5,
    'validation_ms': 2,
    'inference_ms': 5000,
  }

  const count = 15 + Math.floor(Math.random() * 10)
  const now = Date.now() / 1000
  for (let i = 0; i < count; i++) {
    const svc = services[Math.floor(Math.random() * services.length)]
    const metric = metrics[svc]
    const threshold = thresholds[metric]
    violations.push({
      service: svc,
      metric,
      value_ms: threshold * (1.1 + Math.random() * 0.8),
      threshold_ms: threshold,
      percentile: 'p95',
      timestamp: now - Math.random() * hours * 3600,
    })
  }
  return violations.sort((a, b) => b.timestamp - a.timestamp)
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const townCoreUrl = config.townCoreUrl as string

  const query = getQuery(event)
  const wantsViolations = String(query.violations) === 'true'
  const serviceFilter = query.service ? String(query.service) : null
  const hours = Number(query.hours ?? 24)

  try {
    if (wantsViolations) {
      const data = await $fetch<{ violations: SLAViolation[] }>(
        `${townCoreUrl}/api/sla/violations?hours=${hours}`,
        { headers: { 'Content-Type': 'application/json' } }
      )
      return data
    }

    if (serviceFilter) {
      const data = await $fetch<ServiceMetrics>(
        `${townCoreUrl}/api/sla/service/${encodeURIComponent(serviceFilter)}`,
        { headers: { 'Content-Type': 'application/json' } }
      )
      return data
    }

    const data = await $fetch<ComplianceReport>(
      `${townCoreUrl}/api/sla/compliance`,
      { headers: { 'Content-Type': 'application/json' } }
    )
    return data
  } catch {
    // Upstream unavailable — return stub data for development.
    console.warn('[sla/compliance] upstream unavailable, returning stub data')

    if (wantsViolations) {
      return { violations: stubViolations(hours) }
    }

    if (serviceFilter) {
      const full = stubComplianceReport()
      const svcData = full[serviceFilter]
      if (!svcData) {
        throw createError({ statusCode: 404, statusMessage: `Service '${serviceFilter}' not found` })
      }
      return {
        service: serviceFilter,
        metrics: Object.fromEntries(
          Object.entries(svcData).map(([metric, data]) => [
            metric,
            { metric, ...data },
          ])
        ),
      } as ServiceMetrics
    }

    return stubComplianceReport()
  }
})
