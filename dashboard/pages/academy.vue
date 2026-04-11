<script setup lang="ts">
import type { ChartData, ChartOptions } from 'chart.js'
import { useApi } from '~/composables/useApi'
import type { AcademyStats, GenerationRecord } from '~/composables/useApi'

useHead({ title: 'Academy — Qtown' })

const api = useApi()
const stats = ref<AcademyStats | null>(null)

onMounted(async () => {
  stats.value = await api.fetchAcademyStats()
})

async function refresh() {
  stats.value = await api.fetchAcademyStats()
}

// ─── Charts ───────────────────────────────────────────────────────────────────

const modelPieData = computed<ChartData<'doughnut'>>(() => {
  const breakdown = stats.value?.modelBreakdown ?? []
  const colors = [
    'rgba(245, 166, 35, 0.85)',
    'rgba(233, 69, 96, 0.85)',
    'rgba(64, 145, 108, 0.85)',
    'rgba(100, 116, 139, 0.85)',
    'rgba(139, 92, 246, 0.85)',
    'rgba(59, 130, 246, 0.85)',
    'rgba(239, 68, 68, 0.85)',
  ]
  return {
    labels: breakdown.map((b) => b.model),
    datasets: [
      {
        data: breakdown.map((b) => b.count),
        backgroundColor: colors.slice(0, breakdown.length),
        borderColor: '#16213e',
        borderWidth: 2,
      },
    ],
  }
})

const costOverTimeData = computed<ChartData<'bar'>>(() => {
  const history = stats.value?.generationsOverTime ?? []
  return {
    labels: history.map((h) => h.hour),
    datasets: [
      {
        label: 'Cost (USD)',
        data: history.map((h) => h.costUsd),
        backgroundColor: 'rgba(245, 166, 35, 0.6)',
        borderColor: '#f5a623',
        borderWidth: 1,
        borderRadius: 3,
      },
      {
        label: 'Generations',
        data: history.map((h) => h.count),
        backgroundColor: 'rgba(64, 145, 108, 0.4)',
        borderColor: '#40916c',
        borderWidth: 1,
        borderRadius: 3,
        yAxisID: 'y2',
      },
    ],
  }
})

const costOverTimeOptions = computed<ChartOptions<'bar'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#94a3b8', font: { size: 11 }, padding: 12 },
    },
    tooltip: {
      backgroundColor: '#16213e',
      borderColor: '#2a2a4a',
      borderWidth: 1,
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
    },
  },
  scales: {
    x: {
      ticks: { color: '#475569', font: { size: 9 }, maxTicksLimit: 12 },
      grid: { color: '#1a1a2e' },
    },
    y: {
      type: 'linear' as const,
      position: 'left' as const,
      ticks: {
        color: '#f5a623',
        font: { size: 10 },
        callback: (val) => `$${Number(val).toFixed(4)}`,
      },
      grid: { color: '#2a2a4a' },
    },
    y2: {
      type: 'linear' as const,
      position: 'right' as const,
      ticks: {
        color: '#40916c',
        font: { size: 10 },
      },
      grid: { display: false },
    },
  },
}))

const latencyBarData = computed<ChartData<'bar'>>(() => {
  const breakdown = stats.value?.modelBreakdown ?? []
  return {
    labels: breakdown.map((b) => b.model),
    datasets: [
      {
        label: 'Avg Latency (ms)',
        data: breakdown.map((b) => b.avgLatencyMs),
        backgroundColor: breakdown.map((_, i) =>
          i % 2 === 0 ? 'rgba(233, 69, 96, 0.7)' : 'rgba(139, 92, 246, 0.7)'
        ),
        borderColor: breakdown.map((_, i) =>
          i % 2 === 0 ? '#e94560' : '#8b5cf6'
        ),
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  }
})

// ─── Quality score color ──────────────────────────────────────────────────────

function qualityColor(score: number | null): string {
  if (score === null) return 'text-qtown-text-dim'
  if (score >= 4) return 'text-green-400'
  if (score >= 3) return 'text-yellow-400'
  return 'text-red-400'
}

function formatCost(usd: number): string {
  if (usd < 0.001) return `$${(usd * 1000).toFixed(3)}m`
  return `$${usd.toFixed(4)}`
}

function formatLatency(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
  return `${Math.round(ms)}ms`
}

const recentGens = computed<GenerationRecord[]>(() =>
  stats.value?.recentGenerations.slice(0, 50) ?? []
)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">Academy</h1>
        <p class="text-qtown-text-secondary text-sm mt-0.5">
          AI model analytics · generation costs · quality metrics
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
      <div class="qtown-card">
        <div class="section-title">Total Generations</div>
        <div class="stat-number mt-1">{{ stats?.totalGenerations.toLocaleString() ?? '—' }}</div>
      </div>
      <div class="qtown-card">
        <div class="section-title">Total Cost</div>
        <div class="stat-number mt-1 text-qtown-accent">{{ stats ? formatCost(stats.totalCostUsd) : '—' }}</div>
      </div>
      <div class="qtown-card">
        <div class="section-title">Avg Latency</div>
        <div class="stat-number mt-1 text-blue-400">{{ stats ? formatLatency(stats.avgLatencyMs) : '—' }}</div>
      </div>
      <div class="qtown-card">
        <div class="section-title">Models Used</div>
        <div class="stat-number mt-1 text-purple-400">{{ stats?.modelBreakdown.length ?? '—' }}</div>
      </div>
    </div>

    <!-- Charts row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Model routing pie -->
      <div class="qtown-card">
        <h2 class="text-sm font-semibold text-qtown-text-primary mb-4">Model Routing Breakdown</h2>
        <ClientOnly>
          <MetricsChart
            v-if="(stats?.modelBreakdown.length ?? 0) > 0"
            type="doughnut"
            :data="modelPieData"
            :height="260"
            :options="{
              plugins: {
                legend: { position: 'bottom', labels: { font: { size: 10 } } }
              }
            }"
          />
          <div
            v-else
            class="flex items-center justify-center text-qtown-text-dim"
            style="height: 260px"
          >
            <div class="text-center">
              <div class="text-2xl mb-2">🤖</div>
              <div class="text-xs">No model data yet</div>
            </div>
          </div>
        </ClientOnly>
      </div>

      <!-- Cost over time -->
      <div class="qtown-card lg:col-span-2">
        <h2 class="text-sm font-semibold text-qtown-text-primary mb-4">Generation Cost &amp; Volume Over Time</h2>
        <ClientOnly>
          <MetricsChart
            v-if="(stats?.generationsOverTime.length ?? 0) > 0"
            type="bar"
            :data="costOverTimeData"
            :options="costOverTimeOptions"
            :height="260"
          />
          <div
            v-else
            class="flex items-center justify-center text-qtown-text-dim"
            style="height: 260px"
          >
            <div class="text-center">
              <div class="text-2xl mb-2">📊</div>
              <div class="text-xs">No time-series data yet</div>
            </div>
          </div>
        </ClientOnly>
      </div>
    </div>

    <!-- Latency by model -->
    <div class="qtown-card">
      <h2 class="text-sm font-semibold text-qtown-text-primary mb-4">Average Latency by Model</h2>
      <ClientOnly>
        <MetricsChart
          v-if="(stats?.modelBreakdown.length ?? 0) > 0"
          type="bar"
          :data="latencyBarData"
          :height="200"
          :options="{
            plugins: { legend: { display: false } },
            scales: {
              y: { ticks: { callback: (v) => `${v}ms` } }
            }
          }"
        />
        <div
          v-else
          class="flex items-center justify-center text-qtown-text-dim"
          style="height: 200px"
        >No latency data</div>
      </ClientOnly>
    </div>

    <!-- Model breakdown table -->
    <div class="qtown-card p-0 overflow-hidden">
      <div class="px-4 py-3 border-b border-qtown-border">
        <h2 class="text-sm font-semibold text-qtown-text-primary">Model Statistics</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-qtown-border">
              <th class="px-4 py-3 text-left section-title">Model</th>
              <th class="px-4 py-3 text-right section-title">Generations</th>
              <th class="px-4 py-3 text-right section-title">Total Tokens</th>
              <th class="px-4 py-3 text-right section-title">Total Cost</th>
              <th class="px-4 py-3 text-right section-title">Avg Latency</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="model in (stats?.modelBreakdown ?? [])"
              :key="model.model"
              class="border-b border-qtown-border/50 hover:bg-qtown-border/20 transition-colors"
            >
              <td class="px-4 py-3 font-mono text-qtown-text-primary">{{ model.model }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-text-secondary">{{ model.count.toLocaleString() }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-text-secondary">{{ model.totalTokens.toLocaleString() }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-accent">{{ formatCost(model.totalCostUsd) }}</td>
              <td class="px-4 py-3 text-right font-mono text-blue-400">{{ formatLatency(model.avgLatencyMs) }}</td>
            </tr>
            <tr v-if="!stats?.modelBreakdown.length">
              <td colspan="5" class="px-4 py-10 text-center text-qtown-text-dim">No model data</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Recent generations -->
    <div class="qtown-card p-0 overflow-hidden">
      <div class="px-4 py-3 border-b border-qtown-border flex items-center justify-between">
        <h2 class="text-sm font-semibold text-qtown-text-primary">Recent Generations</h2>
        <span class="text-xs text-qtown-text-dim">{{ recentGens.length }} records</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-qtown-border">
              <th class="px-3 py-2.5 text-left section-title">Time</th>
              <th class="px-3 py-2.5 text-left section-title">Model</th>
              <th class="px-3 py-2.5 text-left section-title">Purpose</th>
              <th class="px-3 py-2.5 text-right section-title">Tokens</th>
              <th class="px-3 py-2.5 text-right section-title">Cost</th>
              <th class="px-3 py-2.5 text-right section-title">Latency</th>
              <th class="px-3 py-2.5 text-right section-title">Quality</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="gen in recentGens"
              :key="gen.id"
              class="border-b border-qtown-border/30 hover:bg-qtown-border/20 transition-colors"
            >
              <td class="px-3 py-2 text-qtown-text-dim font-mono">
                {{ new Date(gen.createdAt).toLocaleTimeString() }}
              </td>
              <td class="px-3 py-2 font-mono text-purple-400">{{ gen.model }}</td>
              <td class="px-3 py-2 text-qtown-text-secondary">{{ gen.purpose }}</td>
              <td class="px-3 py-2 text-right font-mono text-qtown-text-secondary">{{ gen.totalTokens.toLocaleString() }}</td>
              <td class="px-3 py-2 text-right font-mono text-qtown-accent">{{ formatCost(gen.costUsd) }}</td>
              <td class="px-3 py-2 text-right font-mono text-blue-400">{{ formatLatency(gen.latencyMs) }}</td>
              <td :class="['px-3 py-2 text-right font-mono font-bold', qualityColor(gen.qualityScore)]">
                {{ gen.qualityScore !== null ? gen.qualityScore.toFixed(1) : '—' }}
              </td>
            </tr>
            <tr v-if="recentGens.length === 0">
              <td colspan="7" class="px-4 py-10 text-center text-qtown-text-dim">No generations yet</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
