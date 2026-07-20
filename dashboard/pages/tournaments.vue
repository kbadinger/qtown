<script setup lang="ts">
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import type { ChartOptions } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

definePageMeta({ layout: 'default' })
useHead({ title: 'Tournaments — Qtown' })

// ─── Types ──────────────────────────────────────────────────────────────────────

interface TournamentStanding {
  rank: number
  npcId: string
  npcName: string
  gold: number
  inventoryValue: number
  totalValue: number
  tradesExecuted: number
  profitLoss: number
}

interface ActiveTournament {
  id: string
  name: string
  startTick: number
  endTick: number
  standings: TournamentStanding[]
  currentTick: number
}

interface HistoricalTournament {
  id: string
  name: string
  winnerName: string
  winnerProfit: number
  startTick: number
  endTick: number
  totalTrades: number
  participants: number
}

interface PortfolioPoint {
  tick: number
  value: number
}

// ─── State ──────────────────────────────────────────────────────────────────────

const activeTournament = ref<ActiveTournament | null>(null)
const history = ref<HistoricalTournament[]>([])
const selectedNpc = ref<string | null>(null)
const portfolioHistory = ref<Record<string, PortfolioPoint[]>>({})
const nextTournamentIn = ref<number | null>(null)
const isLoading = ref(true)
const sourceAvailable = ref(false)

// No fabricated values, ever (docs/REQUIREMENTS.md §2.1). This page renders only what
// the tournament source returns. Until market-district emits tournament.* events and a
// server route proxies them, every fetch below fails and the page stays dormant:
// metrics render `—`, tables render empty, nothing animates.

// ─── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(loadData)

async function loadData() {
  isLoading.value = true
  try {
    // The intended wiring seam: market-district tournament.* events → server proxy →
    // these endpoints. The routes don't exist yet, so both fetches reject and we render
    // the honest dormant state.
    const [active, hist] = await Promise.allSettled([
      $fetch<ActiveTournament & { nextTournamentIn?: number }>('/api/market/tournament/active'),
      $fetch<HistoricalTournament[]>('/api/market/tournament/history'),
    ])

    activeTournament.value = active.status === 'fulfilled' ? active.value : null
    history.value = hist.status === 'fulfilled' ? hist.value : []
    nextTournamentIn.value =
      active.status === 'fulfilled' ? active.value.nextTournamentIn ?? null : null
    sourceAvailable.value = active.status === 'fulfilled' || hist.status === 'fulfilled'
  } finally {
    isLoading.value = false
  }
}

async function selectNpc(npcId: string) {
  selectedNpc.value = npcId
  if (portfolioHistory.value[npcId]) return
  try {
    portfolioHistory.value[npcId] = await $fetch<PortfolioPoint[]>(
      `/api/market/tournament/portfolio/${encodeURIComponent(npcId)}`,
    )
  } catch {
    // No portfolio source yet — the chart panel renders its empty state.
    portfolioHistory.value[npcId] = []
  }
}

// ─── Computed / chart data ──────────────────────────────────────────────────────

const ticksRemaining = computed(() => {
  if (!activeTournament.value) return 0
  return Math.max(0, activeTournament.value.endTick - activeTournament.value.currentTick)
})

const progressPercent = computed(() => {
  if (!activeTournament.value) return 0
  const total = activeTournament.value.endTick - activeTournament.value.startTick
  const elapsed = activeTournament.value.currentTick - activeTournament.value.startTick
  return Math.min(100, Math.round((elapsed / total) * 100))
})

const chartData = computed(() => {
  const npc = selectedNpc.value
  if (!npc || !portfolioHistory.value[npc]?.length) return null
  const points = portfolioHistory.value[npc]
  return {
    labels: points.map(p => `T${p.tick}`),
    datasets: [
      {
        label: 'Portfolio Value',
        data: points.map(p => p.value),
        borderColor: '#f5a623',
        backgroundColor: 'rgba(245, 166, 35, 0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 2,
        pointHoverRadius: 5,
      },
    ],
  }
})

const chartOptions: ChartOptions<'line'> = {
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
        callback: (v: string | number) => `${Number(v).toLocaleString()}g`,
      },
    },
  },
}

function plClass(pl: number): string {
  if (pl > 50) return 'text-green-400'
  if (pl < -50) return 'text-red-400'
  return 'text-qtown-text-secondary'
}

function plSign(pl: number): string {
  return pl >= 0 ? '+' : ''
}
</script>

<template>
  <div class="animate-fade-in space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">NPC Trading Tournaments</h1>
        <p class="text-qtown-text-secondary text-sm mt-1">Market competitions among NPC traders</p>
      </div>
      <div class="flex items-center gap-3">
        <div class="bg-qtown-card border border-qtown-border rounded-lg px-4 py-2 text-sm">
          <span class="text-qtown-text-dim">Next tournament: </span>
          <span class="font-mono text-qtown-gold">{{ nextTournamentIn ?? '—' }} ticks</span>
        </div>
      </div>
    </div>

    <!-- Honesty banner — shown while no tournament source is wired (docs/STATE.md) -->
    <div
      v-if="!isLoading && !sourceAvailable"
      class="rounded-lg border border-qtown-gold/40 bg-qtown-gold/5 p-4 text-sm text-qtown-text-secondary"
    >
      <strong class="text-qtown-gold">Status: dormant.</strong>
      No tournament service is wired yet &mdash; market-district emits no
      <code class="text-qtown-gold">tournament.*</code> events, so there is no data source behind
      this page. Nothing here is simulated: metrics render <span class="font-mono">—</span> and
      tables stay empty until real events flow. Live status board:
      <code class="text-qtown-gold">docs/STATE.md</code>.
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-qtown-accent border-t-transparent rounded-full animate-spin" />
    </div>

    <template v-else>
      <!-- Active tournament -->
      <div v-if="activeTournament" class="bg-qtown-card border border-qtown-gold/20 rounded-xl overflow-hidden">
        <!-- Header -->
        <div class="bg-gradient-to-r from-qtown-gold/10 to-transparent border-b border-qtown-border px-6 py-4 flex items-center justify-between">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span class="text-xs font-mono text-green-400 uppercase tracking-wider">Live</span>
            </div>
            <h2 class="font-bold text-qtown-text-primary text-lg">{{ activeTournament.name }}</h2>
          </div>
          <div class="text-right">
            <div class="text-xs text-qtown-text-dim font-mono mb-1">Tick {{ activeTournament.currentTick.toLocaleString() }}</div>
            <div class="text-xs text-qtown-text-dim">{{ ticksRemaining }} ticks remaining</div>
          </div>
        </div>

        <!-- Progress bar -->
        <div class="h-1 bg-qtown-surface">
          <div
            class="h-full bg-gradient-to-r from-qtown-gold to-qtown-gold/60 transition-all duration-500"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>

        <div class="p-6 grid grid-cols-3 gap-6">
          <!-- Standings table (2/3) -->
          <div class="col-span-2">
            <h3 class="text-sm font-semibold text-qtown-text-secondary mb-3 flex items-center gap-2">
              Live Standings
              <span class="text-xs font-mono text-qtown-text-dim">(portfolio value = gold + inventory)</span>
            </h3>
            <div class="overflow-x-auto rounded border border-qtown-border">
              <table class="w-full text-sm">
                <thead>
                  <tr class="bg-qtown-surface border-b border-qtown-border">
                    <th class="text-left px-3 py-2.5 text-qtown-text-dim font-mono text-xs uppercase w-10">Rank</th>
                    <th class="text-left px-3 py-2.5 text-qtown-text-dim font-mono text-xs uppercase">NPC</th>
                    <th class="text-right px-3 py-2.5 text-qtown-text-dim font-mono text-xs uppercase">Gold</th>
                    <th class="text-right px-3 py-2.5 text-qtown-text-dim font-mono text-xs uppercase">Inventory</th>
                    <th class="text-right px-3 py-2.5 text-qtown-text-dim font-mono text-xs uppercase">Total</th>
                    <th class="text-right px-3 py-2.5 text-qtown-text-dim font-mono text-xs uppercase">P&L</th>
                    <th class="text-right px-3 py-2.5 text-qtown-text-dim font-mono text-xs uppercase">Trades</th>
                    <th class="w-10 px-3 py-2.5" />
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="s in activeTournament.standings"
                    :key="s.npcId"
                    class="border-b border-qtown-border last:border-b-0 hover:bg-qtown-border/30 transition-colors cursor-pointer"
                    :class="selectedNpc === s.npcId ? 'bg-qtown-gold/5' : ''"
                    @click="selectNpc(s.npcId)"
                  >
                    <td class="px-3 py-2.5">
                      <span
                        class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold font-mono"
                        :class="s.rank === 1 ? 'bg-yellow-500/20 text-yellow-400' : s.rank === 2 ? 'bg-qtown-stone-light/20 text-qtown-stone-light' : s.rank === 3 ? 'bg-yellow-700/20 text-yellow-700' : 'text-qtown-text-dim'"
                      >{{ s.rank }}</span>
                    </td>
                    <td class="px-3 py-2.5 font-medium text-qtown-text-primary">{{ s.npcName }}</td>
                    <td class="px-3 py-2.5 text-right font-mono text-qtown-gold text-xs">{{ Math.round(s.gold).toLocaleString() }}g</td>
                    <td class="px-3 py-2.5 text-right font-mono text-qtown-text-secondary text-xs">{{ Math.round(s.inventoryValue).toLocaleString() }}g</td>
                    <td class="px-3 py-2.5 text-right font-mono font-semibold text-qtown-text-primary text-xs">{{ Math.round(s.totalValue).toLocaleString() }}g</td>
                    <td class="px-3 py-2.5 text-right font-mono text-xs" :class="plClass(s.profitLoss)">
                      {{ plSign(s.profitLoss) }}{{ Math.round(s.profitLoss).toLocaleString() }}g
                    </td>
                    <td class="px-3 py-2.5 text-right font-mono text-qtown-text-dim text-xs">{{ s.tradesExecuted }}</td>
                    <td class="px-3 py-2.5 text-center">
                      <svg v-if="selectedNpc === s.npcId" viewBox="0 0 16 16" fill="currentColor" class="w-3 h-3 text-qtown-gold mx-auto">
                        <circle cx="8" cy="8" r="4" />
                      </svg>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Portfolio chart (1/3) -->
          <div>
            <h3 class="text-sm font-semibold text-qtown-text-secondary mb-3">
              {{ selectedNpc ? activeTournament.standings.find(s => s.npcId === selectedNpc)?.npcName : 'Select an NPC' }}
              <span v-if="selectedNpc" class="text-qtown-text-dim font-normal"> — portfolio</span>
            </h3>
            <div v-if="selectedNpc && chartData" class="h-48">
              <Line :data="chartData" :options="chartOptions" />
            </div>
            <div
              v-else
              class="h-48 rounded border border-qtown-border border-dashed flex items-center justify-center text-qtown-text-dim text-sm px-4 text-center"
            >
              {{ selectedNpc ? 'No portfolio data — source not wired yet' : 'Click a row to view chart' }}
            </div>
          </div>
        </div>
      </div>

      <div v-else class="bg-qtown-card border border-qtown-border rounded-xl p-10 text-center">
        <p class="text-qtown-text-dim">No active tournament.</p>
      </div>

      <!-- Tournament history -->
      <div>
        <h2 class="text-lg font-semibold text-qtown-text-primary mb-4">Tournament History</h2>
        <div class="overflow-x-auto rounded-lg border border-qtown-border">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-qtown-surface border-b border-qtown-border">
                <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Tournament</th>
                <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Winner</th>
                <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Winner Profit</th>
                <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Ticks</th>
                <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Total Trades</th>
                <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Participants</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="h in history"
                :key="h.id"
                class="border-b border-qtown-border last:border-b-0 bg-qtown-card hover:bg-qtown-border/30 transition-colors"
              >
                <td class="px-4 py-3 font-medium text-qtown-text-primary">{{ h.name }}</td>
                <td class="px-4 py-3">
                  <span class="text-qtown-gold font-medium">🏆 {{ h.winnerName }}</span>
                </td>
                <td class="px-4 py-3 text-right font-mono text-green-400">+{{ Math.round(h.winnerProfit).toLocaleString() }}g</td>
                <td class="px-4 py-3 text-right font-mono text-qtown-text-dim">{{ h.endTick - h.startTick }}</td>
                <td class="px-4 py-3 text-right font-mono text-qtown-text-secondary">{{ h.totalTrades.toLocaleString() }}</td>
                <td class="px-4 py-3 text-right font-mono text-qtown-text-dim">{{ h.participants }}</td>
              </tr>
              <tr v-if="history.length === 0">
                <td colspan="6" class="px-4 py-8 text-center text-qtown-text-dim bg-qtown-card">
                  No tournaments recorded — no data source wired yet.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
