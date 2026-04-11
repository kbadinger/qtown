// SLA monitoring composable

export interface MetricReport {
  compliance_pct: number
  threshold_ms: number
  percentile_target: string
  p50_ms: number
  p95_ms: number
  p99_ms: number
  sample_count: number
}

export interface ComplianceReport {
  [service: string]: {
    [metric: string]: MetricReport
  }
}

export interface SLAViolation {
  service: string
  metric: string
  value_ms: number
  threshold_ms: number
  percentile: string
  timestamp: number
}

export interface MetricSummary {
  metric: string
  p50_ms: number
  p95_ms: number
  p99_ms: number
  sample_count: number
  threshold_ms: number
  percentile_target: string
  compliance_pct: number
}

export interface ServiceMetrics {
  service: string
  metrics: Record<string, MetricSummary>
}

export function useSLA() {
  const isLoading = ref(false)
  const lastError = ref<string | null>(null)

  async function fetchComplianceReport(): Promise<ComplianceReport | null> {
    isLoading.value = true
    lastError.value = null
    try {
      const data = await $fetch<ComplianceReport>('/api/sla/compliance')
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch SLA compliance report'
      lastError.value = message
      console.error('[useSLA] fetchComplianceReport error:', message)
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function fetchViolations(hours = 24): Promise<SLAViolation[]> {
    try {
      const data = await $fetch<{ violations: SLAViolation[] }>(`/api/sla/compliance?violations=true&hours=${hours}`)
      return data.violations ?? []
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch SLA violations'
      lastError.value = message
      console.error('[useSLA] fetchViolations error:', message)
      return []
    }
  }

  async function fetchServiceMetrics(service: string): Promise<ServiceMetrics | null> {
    try {
      const data = await $fetch<ServiceMetrics>(`/api/sla/compliance?service=${encodeURIComponent(service)}`)
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : `Failed to fetch metrics for ${service}`
      lastError.value = message
      console.error('[useSLA] fetchServiceMetrics error:', message)
      return null
    }
  }

  return {
    isLoading: readonly(isLoading),
    lastError: readonly(lastError),
    fetchComplianceReport,
    fetchViolations,
    fetchServiceMetrics,
  }
}
