<script setup lang="ts">
import { Line, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler)

definePageMeta({ layout: 'default' })
useHead({ title: 'SLA Dashboard — Qtown' })

import type { ComplianceReport, SLAViolation, MetricReport, ServiceMetrics } from '~/composables/useSLA'

const { fetchComplianceReport, fetchViolations, fetchServiceMetrics } = useSLA()

// ─── State ──────────────────────────────────────────────────────────────────────

const report = ref<ComplianceReport | null>(null)
const violations = ref<SLAViolation[]>([])
const selectedService = ref<string | null>(null)
const serviceMetrics = ref<ServiceMetrics | null>(null)
const isLoading = ref(true)
const isLoadingService = ref(false)

// ─── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadData()
  // Refresh every 30 seconds
  const interval = setInterval(loadData, 30_000)
  onUnmounted(() => clearInterval(interval))
})

async function loadData() {
  isLoading.value = true
  const [r, v] = await Promise.all([
    fetchComplianceReport(),
    fetchViolations(24),
  ])
  if (r) report.value = r
  violations.value = v
  isLoading.value = false
}

async function drillDown(service: string) {
  if (selectedService.value === service) {
    selectedService.value = null
    serviceMetrics.value = null
    return
  }
  selectedService.value = service
  isLoadingService.value = true
  serviceMetrics.value = await fetchServiceMetrics(service)
  isLoadingService.value = false
}

// ─── Computed ──────────────────────────────────────────────────────────────────

const serviceList = computed((): string[] => {
  if (!report.value) return []
  return Object.keys(report.value).sort()
})

function overallServiceCompliance(service: string): number {
  if (!report.value?.[service]) return 100
  const metrics = Object.values(report.value[service])
  if (metrics.length === 0) return 100
  return metrics.reduce((sum, m) => sum + m.compliance_pct, 0) / metrics.length
}

function complianceColor(pct: number): string {
  if (pct >= 99) return 'text-green-400'
  if (pct >= 95) return 'text-yellow-400'
  return 'text-red-400'
}

function complianceBg(pct: number): string {
  if (pct >= 99) return 'bg-green-500/10 border-green-500/20'
  if (pct >= 95) return 'bg-yellow-500/10 border-yellow-500/20'
  return 'bg-red-500/10 border-red-500/20'
}

function cellClass(metric: MetricReport): string {
  const pct = metric.compliance_pct
  if (pct >= 99) return 'bg-green-500/10 text-green-400'
  if (pct >= 95) return 'bg-yellow-500/10 text-yellow-400'
  return 'bg-red-500/10 text-red-400'
}

// Violation timeline chart
const violationChartData = computed(() => {
  if (violations.value.length === 0) return null

  // Bucket violations into 4-hour buckets over 24h
  const now = Date.now() / 1000
  const buckets = 6
  const bucketSize = (24 * 3600) / buckets
  const counts = new Array(buckets).fill(0)
  const labels = Array.from({ length: buckets }, (_, i) => {
    const hAgo = (buckets - i) * 4
    return `${hAgo}h ago`
  })

  for (const v of violations.value) {
    const age = now - v.timestamp
    if (age < 0 || age > 24 * 3600) continue
    const idx = Math.min(buckets - 1, Math.floor(age / bucketSize))
    // Invert: idx 0 is oldest, so reverse
    counts[buckets - 1 - idx]++
  }

  return {
    labels,
    datasets: [
      {
        label: 'Violations',
        data: counts,
        backgroundColor: 'rgba(233,69,96,0.3)',
        borderColor: '#e94560',
        borderWidth: 1,
      },
    ],
  }
})

const violationChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#16213e',
      borderColor: '#2a2a4a',
      borderWidth: 1,
      titleColor: '#94a3b8',
      bodyColor: '#e2e8f0',
    },
  },
  scales: {
    x: {
      grid: { color: '#2a2a4a' },
      ticks: { color: '#475569', font: { family: 'monospace', size: 10 } },
    },
    y: {
      grid: { color: '#2a2a4a' },
      ticks: {
        color: '#475569',
        font: { family: 'monospace', size: 10 },
        stepSize: 1,
      },
      beginAtZero: true,
    },
  },
}

// Service drill-down bar chart
const serviceChartData = computed(() => {
  if (!serviceMetrics.value) return null
  const entries = Object.entries(serviceMetrics.value.metrics)
  return {
    labels: entries.map(([k]) => k.replace('_ms', '').replace(/_/g, ' ')),
    datasets: [
      {
        label: 'p50',
        data: entries.map(([, v]) => v.p50_ms),
        backgroundColor: 'rgba(64,145,108,0.5)',
        borderColor: '#40916c',
        borderWidth: 1,
      },
      {
        label: 'p95',
        data: entries.map(([, v]) => v.p95_ms),
        backgroundColor: 'rgba(245,166,35,0.5)',
        borderColor: '#f5a623',
        borderWidth: 1,
      },
      {
        label: 'p99',
        data: entries.map(([, v]) => v.p99_ms),
        backgroundColor: 'rgba(233,69,96,0.4)',
        borderColor: '#e94560',
        borderWidth: 1,
      },
    ],
  }
})

const serviceChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#94a3b8', font: { family: 'monospace', size: 10 } },
    },
    tooltip: {
      backgroundColor: '#16213e',
      borderColor: '#2a2a4a',
      borderWidth: 1,
      titleColor: '#94a3b8',
      bodyColor: '#e2e8f0',
      callbacks: {
        label: (ctx: { dataset: { label: string }; raw: number }) => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)}ms`,
      },
    },
  },
  scales: {
    x: {
      grid: { color: '#2a2a4a' },
      ticks: { color: '#475569', font: { family: 'monospace', size: 9 } },
    },
    y: {
      grid: { color: '#2a2a4a' },
      ticks: {
        color: '#475569',
        font: { family: 'monospace', size: 10 },
        callback: (v: number) => `${v}ms`,
      },
      beginAtZero: true,
    },
  },
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="animate-fade-in space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">SLA Dashboard</h1>
        <p class="text-qtown-text-secondary text-sm mt-1">Performance budget compliance across all services</p>
      </div>
      <button
        class="text-xs text-qtown-text-dim hover:text-qtown-text-secondary border border-qtown-border rounded px-3 py-1.5 hover:bg-qtown-border transition-colors"
        :disabled="isLoading"
        @click="loadData"
      >
        <span v-if="isLoading">Refreshing...</span>
        <span v-else>↻ Refresh</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="isLoading && !report" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 border-2 border-qtown-accent border-t-transparent rounded-full animate-spin" />
    </div>

    <template v-else-if="report">
      <!-- Service status cards -->
      <div class="grid grid-cols-4 gap-3">
        <button
          v-for="svc in serviceList"
          :key="svc"
          class="rounded-xl border p-4 text-left transition-all duration-200 hover:scale-[1.01]"
          :class="[
            complianceBg(overallServiceCompliance(svc)),
            selectedService === svc ? 'ring-1 ring-qtown-accent/40' : '',
          ]"
          @click="drillDown(svc)"
        >
          <div class="text-xs font-mono text-qtown-text-dim mb-1">{{ svc }}</div>
          <div class="text-2xl font-bold font-mono" :class="complianceColor(overallServiceCompliance(svc))">
            {{ overallServiceCompliance(svc).toFixed(1) }}%
          </div>
          <div class="text-xs mt-1" :class="complianceColor(overallServiceCompliance(svc))">
            {{
              overallServiceCompliance(svc) >= 99 ? '● Healthy'
              : overallServiceCompliance(svc) >= 95 ? '● Warning'
              : '● Degraded'
            }}
          </div>
        </button>
      </div>

      <!-- Legend -->
      <div class="flex gap-4 text-xs text-qtown-text-dim">
        <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-green-500/30 border border-green-500/40" /> ≥99% compliant</span>
        <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-yellow-500/30 border border-yellow-500/40" /> 95–99% warning</span>
        <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm bg-red-500/30 border border-red-500/40" /> &lt;95% degraded</span>
      </div>

      <!-- Compliance matrix -->
      <div class="bg-qtown-card border border-qtown-border rounded-xl overflow-hidden">
        <div class="border-b border-qtown-border px-5 py-3">
          <h2 class="font-semibold text-qtown-text-primary text-sm">Compliance Matrix</h2>
          <p class="text-qtown-text-dim text-xs mt-0.5">Click a service row to drill down into percentile metrics</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="bg-qtown-surface border-b border-qtown-border">
                <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase tracking-wider sticky left-0 bg-qtown-surface">Service</th>
                <th
                  v-for="svc in serviceList"
                  :key="svc"
                  class="text-center px-3 py-3 text-qtown-text-dim font-mono uppercase tracking-wider"
                >
                  <button class="hover:text-qtown-text-secondary transition-colors" @click="drillDown(svc)">
                    {{ svc.replace('-', '‑') }}
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-for="svc in serviceList" :key="svc">
                <tr
                  v-for="(metricData, metricName) in report[svc]"
                  :key="`${svc}-${metricName}`"
                  class="border-b border-qtown-border last:border-b-0 hover:bg-qtown-border/20 transition-colors cursor-pointer"
                  @click="drillDown(svc)"
                >
                  <td class="px-4 py-2.5 font-mono sticky left-0 bg-qtown-card">
                    <span class="text-qtown-text-secondary">{{ svc }}</span>
                    <span class="text-qtown-text-dim mx-1">›</span>
                    <span class="text-qtown-text-dim">{{ metricName.replace(/_ms$/, '') }}</span>
                  </td>
                  <!-- Fill cells for the owning service, blank for others -->
                  <template v-for="colSvc in serviceList" :key="colSvc">
                    <td class="px-3 py-2.5 text-center">
                      <span
                        v-if="colSvc === svc"
                        class="inline-block px-2 py-0.5 rounded text-xs font-mono font-bold"
                        :class="cellClass(metricData)"
                      >{{ metricData.compliance_pct.toFixed(1) }}%</span>
                    </td>
                  </template>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Two-column: violation timeline + drill down -->
      <div class="grid grid-cols-2 gap-6">
        <!-- Violation timeline -->
        <div class="bg-qtown-card border border-qtown-border rounded-xl overflow-hidden">
          <div class="border-b border-qtown-border px-5 py-3">
            <h2 class="font-semibold text-qtown-text-primary text-sm">Violation Timeline (24h)</h2>
            <p class="text-xs text-qtown-text-dim mt-0.5">{{ violations.length }} total violations</p>
          </div>
          <div class="p-5">
            <div v-if="violationChartData" class="h-36">
              <Bar :data="violationChartData" :options="violationChartOptions" />
            </div>
            <div v-else class="h-36 flex items-center justify-center text-qtown-text-dim text-sm">
              No violations in the past 24 hours
            </div>

            <!-- Recent violation list -->
            <div class="mt-4 space-y-1.5 max-h-40 overflow-y-auto">
              <div
                v-for="v in violations.slice(0, 8)"
                :key="`${v.service}-${v.metric}-${v.timestamp}`"
                class="flex items-center justify-between text-xs bg-qtown-surface rounded px-3 py-1.5"
              >
                <div class="flex items-center gap-2">
                  <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                  <span class="font-mono text-qtown-text-secondary">{{ v.service }}</span>
                  <span class="text-qtown-text-dim">{{ v.metric.replace(/_ms$/, '') }}</span>
                </div>
                <div class="flex items-center gap-3 flex-shrink-0">
                  <span class="font-mono text-red-400">{{ v.value_ms.toFixed(1) }}ms</span>
                  <span class="text-qtown-text-dim">vs {{ v.threshold_ms }}ms</span>
                  <span class="text-qtown-text-dim">{{ formatTs(v.timestamp) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Service drill-down -->
        <div class="bg-qtown-card border border-qtown-border rounded-xl overflow-hidden">
          <div class="border-b border-qtown-border px-5 py-3 flex items-center justify-between">
            <div>
              <h2 class="font-semibold text-qtown-text-primary text-sm">
                {{ selectedService ? `${selectedService} — Latency Breakdown` : 'Service Drill-Down' }}
              </h2>
              <p class="text-xs text-qtown-text-dim mt-0.5">
                {{ selectedService ? 'p50 / p95 / p99 vs budget' : 'Click a service card above' }}
              </p>
            </div>
            <button
              v-if="selectedService"
              class="text-xs text-qtown-text-dim hover:text-qtown-text-secondary transition-colors"
              @click="selectedService = null; serviceMetrics = null"
            >
              ✕ Clear
            </button>
          </div>

          <div class="p-5">
            <div v-if="isLoadingService" class="h-56 flex items-center justify-center">
              <div class="w-6 h-6 border-2 border-qtown-accent border-t-transparent rounded-full animate-spin" />
            </div>

            <div v-else-if="serviceMetrics && serviceChartData" class="h-56">
              <Bar :data="serviceChartData" :options="serviceChartOptions" />
            </div>

            <div v-else-if="selectedService && serviceMetrics">
              <!-- Fallback table -->
              <div class="space-y-2">
                <div
                  v-for="(m, name) in serviceMetrics.metrics"
                  :key="String(name)"
                  class="bg-qtown-surface rounded p-3"
                >
                  <div class="flex items-center justify-between mb-2">
                    <span class="font-mono text-xs text-qtown-text-secondary">{{ String(name) }}</span>
                    <span class="text-xs font-mono" :class="m.compliance_pct >= 99 ? 'text-green-400' : m.compliance_pct >= 95 ? 'text-yellow-400' : 'text-red-400'">
                      {{ m.compliance_pct.toFixed(1) }}%
                    </span>
                  </div>
                  <div class="grid grid-cols-3 gap-2 text-xs">
                    <div><span class="text-qtown-text-dim">p50</span> <span class="font-mono text-qtown-text-secondary">{{ m.p50_ms.toFixed(1) }}ms</span></div>
                    <div><span class="text-qtown-text-dim">p95</span> <span class="font-mono text-qtown-text-secondary">{{ m.p95_ms.toFixed(1) }}ms</span></div>
                    <div><span class="text-qtown-text-dim">p99</span> <span class="font-mono text-qtown-text-secondary">{{ m.p99_ms.toFixed(1) }}ms</span></div>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="h-56 flex items-center justify-center border border-dashed border-qtown-border rounded-lg">
              <p class="text-qtown-text-dim text-sm">Select a service above to see latency breakdown</p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
