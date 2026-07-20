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

// When town-core cannot be reached we return an honest "no data" state — an empty
// report / empty violations, with a `sourceAvailable: false` flag on the violations and
// per-service shapes. No metrics are ever fabricated: emptiness renders as a dormant /
// `—` panel (docs/plans/03-PROOF-OF-WORK.md §4 rule 1: "No fabricated values, ever").

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
    // Upstream unavailable — return an honest "no data" shape, never fabricated
    // metrics (docs/plans/03-PROOF-OF-WORK.md §4 rule 1: "No fabricated values, ever").
    console.warn('[sla/compliance] upstream unavailable, returning unavailable state (no data)')

    if (wantsViolations) {
      return { violations: [] as SLAViolation[], sourceAvailable: false }
    }

    if (serviceFilter) {
      return {
        service: serviceFilter,
        metrics: {},
        sourceAvailable: false,
      } as ServiceMetrics & { sourceAvailable: false }
    }

    // Empty report → the UI renders an empty/dormant compliance matrix (no fabricated
    // rows). The report shape is a bare `Record<service, …>`, so the flag cannot live at
    // the top level without masquerading as a service; emptiness is the honest signal here.
    return {} as ComplianceReport
  }
})
