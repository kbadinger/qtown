<script setup lang="ts">
import type { ChartData } from 'chart.js'
import { useApi } from '~/composables/useApi'
import type { FortressStats, ValidationEntry } from '~/composables/useApi'

useHead({ title: 'Fortress — Qtown' })

const api = useApi()
const stats = ref<FortressStats | null>(null)
const searchRejection = ref('')

onMounted(async () => {
  stats.value = await api.fetchFortressStats()
})

async function refresh() {
  stats.value = await api.fetchFortressStats()
}

// ─── Charts ───────────────────────────────────────────────────────────────────

const rejectionReasonData = computed<ChartData<'bar'>>(() => {
  const reasons = stats.value?.topRejectionReasons ?? []
  return {
    labels: reasons.map((r) => truncate(r.reason, 30)),
    datasets: [
      {
        label: 'Rejections',
        data: reasons.map((r) => r.count),
        backgroundColor: 'rgba(233, 69, 96, 0.7)',
        borderColor: '#e94560',
        borderWidth: 1,
        borderRadius: 3,
      },
    ],
  }
})

const rejectionRateGaugeData = computed<ChartData<'doughnut'>>(() => {
  const rate = stats.value?.rejectionRate ?? 0
  return {
    labels: ['Rejected', 'Passed'],
    datasets: [
      {
        data: [rate, 100 - rate],
        backgroundColor: [
          'rgba(233, 69, 96, 0.8)',
          'rgba(64, 145, 108, 0.3)',
        ],
        borderColor: ['#e94560', '#2a2a4a'],
        borderWidth: 2,
        circumference: 270,
        rotation: -135,
      },
    ],
  }
})

// ─── Audit log filtering ──────────────────────────────────────────────────────

const filteredAuditLog = computed<ValidationEntry[]>(() => {
  const log = stats.value?.recentAuditLog ?? []
  if (!searchRejection.value) return log
  const q = searchRejection.value.toLowerCase()
  return log.filter(
    (e) =>
      e.eventType.toLowerCase().includes(q) ||
      e.entityId.toLowerCase().includes(q) ||
      (e.rejectionReason?.toLowerCase().includes(q) ?? false)
  )
})

// ─── Helpers ──────────────────────────────────────────────────────────────────

function truncate(str: string, max: number): string {
  return str.length > max ? `${str.slice(0, max)}…` : str
}

function formatValidationMs(ms: number): string {
  return ms < 1 ? `<1ms` : `${Math.round(ms)}ms`
}

const passRate = computed(() => {
  if (!stats.value) return null
  return (100 - stats.value.rejectionRate).toFixed(1)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">Fortress</h1>
        <p class="text-qtown-text-secondary text-sm mt-0.5">
          Event validation · audit log · rejection analysis
        </p>
      </div>
      <button class="qtown-btn-ghost text-sm flex items-center gap-2" @click="refresh">
        <svg viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 8A6 6 0 102 8" stroke-linecap="round" />
          <path d="M14 5v3h-3" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        Refresh
      </button>
    </div>

    <!-- Summary stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="qtown-card border border-green-500/20 bg-green-500/5">
        <div class="section-title text-green-400/70">Total Validated</div>
        <div class="stat-number mt-1 text-green-400">{{ stats?.totalValidated.toLocaleString() ?? '—' }}</div>
      </div>
      <div class="qtown-card border border-qtown-accent/20 bg-qtown-accent/5">
        <div class="section-title text-qtown-accent/70">Total Rejected</div>
        <div class="stat-number mt-1 text-qtown-accent">{{ stats?.totalRejected.toLocaleString() ?? '—' }}</div>
      </div>
      <div class="qtown-card">
        <div class="section-title">Rejection Rate</div>
        <div
          :class="[
            'stat-number mt-1',
            (stats?.rejectionRate ?? 0) > 20 ? 'text-qtown-accent' :
            (stats?.rejectionRate ?? 0) > 10 ? 'text-yellow-400' : 'text-green-400'
          ]"
        >
          {{ stats ? `${stats.rejectionRate.toFixed(1)}%` : '—' }}
        </div>
      </div>
      <div class="qtown-card">
        <div class="section-title">Pass Rate</div>
        <div class="stat-number mt-1 text-green-400">{{ passRate ? `${passRate}%` : '—' }}</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Rejection rate gauge -->
      <div class="qtown-card flex flex-col items-center justify-center">
        <h2 class="section-title mb-4 self-start">Rejection Rate Gauge</h2>
        <ClientOnly>
          <div class="relative w-48">
            <MetricsChart
              type="doughnut"
              :data="rejectionRateGaugeData"
              :height="180"
              :options="{
                plugins: {
                  legend: { display: false },
                  tooltip: { enabled: false }
                }
              }"
            />
            <div class="absolute inset-0 flex items-center justify-center pb-4">
              <div class="text-center">
                <div
                  :class="[
                    'text-2xl font-bold font-mono',
                    (stats?.rejectionRate ?? 0) > 20 ? 'text-qtown-accent' :
                    (stats?.rejectionRate ?? 0) > 10 ? 'text-yellow-400' : 'text-green-400'
                  ]"
                >
                  {{ stats ? `${stats.rejectionRate.toFixed(1)}%` : '?' }}
                </div>
                <div class="text-xs text-qtown-text-dim">rejected</div>
              </div>
            </div>
          </div>
        </ClientOnly>
        <div class="mt-4 text-center">
          <p class="text-xs text-qtown-text-dim">
            {{ stats?.totalRejected.toLocaleString() ?? '0' }} of
            {{ stats?.totalValidated.toLocaleString() ?? '0' }} events rejected
          </p>
        </div>
      </div>

      <!-- Top rejection reasons chart -->
      <div class="qtown-card lg:col-span-2">
        <h2 class="text-sm font-semibold text-qtown-text-primary mb-4">Top Rejection Reasons</h2>
        <ClientOnly>
          <MetricsChart
            v-if="(stats?.topRejectionReasons.length ?? 0) > 0"
            type="bar"
            :data="rejectionReasonData"
            :height="200"
            :options="{
              indexAxis: 'y',
              plugins: { legend: { display: false } },
              scales: {
                x: { ticks: { color: '#475569' }, grid: { color: '#2a2a4a' } },
                y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } }
              }
            }"
          />
          <div
            v-else
            class="flex items-center justify-center text-qtown-text-dim"
            style="height: 200px"
          >
            <div class="text-center">
              <div class="text-2xl mb-2">✅</div>
              <div class="text-xs">No rejections recorded</div>
            </div>
          </div>
        </ClientOnly>
      </div>
    </div>

    <!-- Rejection reasons table -->
    <div class="qtown-card p-0 overflow-hidden">
      <div class="px-4 py-3 border-b border-qtown-border">
        <h2 class="text-sm font-semibold text-qtown-text-primary">Rejection Reason Breakdown</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-qtown-border">
              <th class="px-4 py-3 text-left section-title">Reason</th>
              <th class="px-4 py-3 text-right section-title">Count</th>
              <th class="px-4 py-3 text-right section-title">Percentage</th>
              <th class="px-4 py-3 text-left section-title">Distribution</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="reason in (stats?.topRejectionReasons ?? [])"
              :key="reason.reason"
              class="border-b border-qtown-border/50 hover:bg-qtown-border/20"
            >
              <td class="px-4 py-3 text-qtown-text-primary">{{ reason.reason }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-accent">{{ reason.count.toLocaleString() }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-text-secondary">{{ reason.percentage.toFixed(1) }}%</td>
              <td class="px-4 py-3">
                <div class="w-32 h-1.5 bg-qtown-border rounded-full overflow-hidden">
                  <div
                    class="h-full bg-qtown-accent rounded-full"
                    :style="{ width: `${Math.min(100, reason.percentage)}%` }"
                  />
                </div>
              </td>
            </tr>
            <tr v-if="!stats?.topRejectionReasons.length">
              <td colspan="4" class="px-4 py-8 text-center text-qtown-text-dim">No rejections</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Audit log -->
    <div class="qtown-card p-0 overflow-hidden">
      <div class="px-4 py-3 border-b border-qtown-border flex items-center justify-between gap-3 flex-wrap">
        <h2 class="text-sm font-semibold text-qtown-text-primary">Audit Log</h2>
        <div class="flex items-center gap-2">
          <span class="text-xs text-qtown-text-dim">{{ filteredAuditLog.length }} entries</span>
          <input
            v-model="searchRejection"
            type="text"
            placeholder="Filter..."
            class="qtown-input text-xs py-1 px-2 w-40"
          />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-qtown-border">
              <th class="px-3 py-2.5 text-left section-title">Time</th>
              <th class="px-3 py-2.5 text-left section-title">Tick</th>
              <th class="px-3 py-2.5 text-left section-title">Event Type</th>
              <th class="px-3 py-2.5 text-left section-title">Entity</th>
              <th class="px-3 py-2.5 text-left section-title">Result</th>
              <th class="px-3 py-2.5 text-left section-title">Reason</th>
              <th class="px-3 py-2.5 text-right section-title">Latency</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in filteredAuditLog"
              :key="entry.id"
              class="border-b border-qtown-border/30 hover:bg-qtown-border/20 transition-colors"
            >
              <td class="px-3 py-2 text-qtown-text-dim font-mono">
                {{ new Date(entry.timestamp).toLocaleTimeString() }}
              </td>
              <td class="px-3 py-2 font-mono text-qtown-text-secondary">{{ entry.tick }}</td>
              <td class="px-3 py-2">
                <span class="qtown-badge bg-qtown-border text-qtown-text-secondary">
                  {{ entry.eventType }}
                </span>
              </td>
              <td class="px-3 py-2">
                <div class="text-qtown-text-primary">{{ entry.entityId }}</div>
                <div class="text-qtown-text-dim" style="font-size: 10px">{{ entry.entityType }}</div>
              </td>
              <td class="px-3 py-2">
                <span
                  :class="[
                    'qtown-badge font-semibold',
                    entry.passed
                      ? 'bg-green-400/10 text-green-400'
                      : 'bg-qtown-accent/10 text-qtown-accent'
                  ]"
                >
                  {{ entry.passed ? 'PASS' : 'REJECT' }}
                </span>
              </td>
              <td class="px-3 py-2 text-qtown-text-secondary max-w-xs truncate">
                {{ entry.rejectionReason ?? '—' }}
              </td>
              <td class="px-3 py-2 text-right font-mono text-qtown-text-dim">
                {{ formatValidationMs(entry.validationMs) }}
              </td>
            </tr>
            <tr v-if="filteredAuditLog.length === 0">
              <td colspan="7" class="px-4 py-10 text-center text-qtown-text-dim">
                {{ searchRejection ? 'No matching entries' : 'No audit entries yet' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
