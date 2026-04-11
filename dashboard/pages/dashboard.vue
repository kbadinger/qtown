<script setup lang="ts">
import type { ChartData } from 'chart.js'
import { useTownState } from '~/composables/useTownState'
import type { TownEvent } from '~/composables/useTownState'
import { useWebSocket } from '~/composables/useWebSocket'
import type { WsMessage } from '~/composables/useWebSocket'

useHead({ title: 'Dashboard — Qtown' })

const townStore = useTownState()
const { connect, subscribe } = useWebSocket({ autoConnect: false })

onMounted(async () => {
  await townStore.fetchState()
  connect()
  subscribe('metrics', (msg: WsMessage) => {
    const event = msg.payload as TownEvent
    townStore.updateFromEvent(event)
  })
})

// ─── Metric cards ─────────────────────────────────────────────────────────────

const metricCards = computed(() => [
  {
    label: 'Population',
    value: townStore.worldState.population.toLocaleString(),
    subtext: `${townStore.worldState.activeNpcs} active`,
    icon: '👥',
    color: 'border-green-500/30 text-green-400',
    bg: 'bg-green-400/5',
  },
  {
    label: 'Total Gold',
    value: townStore.worldState.totalGold.toLocaleString(),
    subtext: 'in circulation',
    icon: '💰',
    color: 'border-qtown-gold/30 text-qtown-gold',
    bg: 'bg-qtown-gold/5',
  },
  {
    label: 'Avg Happiness',
    value: `${townStore.worldState.averageHappiness}%`,
    subtext: townStore.worldState.averageHappiness >= 60 ? 'Thriving' : townStore.worldState.averageHappiness >= 40 ? 'Stable' : 'Struggling',
    icon: '😊',
    color: 'border-purple-400/30 text-purple-400',
    bg: 'bg-purple-400/5',
  },
  {
    label: 'Active NPCs',
    value: townStore.worldState.activeNpcs.toLocaleString(),
    subtext: `of ${townStore.worldState.population} total`,
    icon: '🧑‍🤝‍🧑',
    color: 'border-blue-400/30 text-blue-400',
    bg: 'bg-blue-400/5',
  },
  {
    label: 'Current Tick',
    value: townStore.worldState.tick.toLocaleString(),
    subtext: `Day ${townStore.worldState.dayNumber}`,
    icon: '⏱',
    color: 'border-teal-400/30 text-teal-400',
    bg: 'bg-teal-400/5',
  },
  {
    label: 'Weather',
    value: townStore.worldState.weather.condition.charAt(0).toUpperCase() + townStore.worldState.weather.condition.slice(1),
    subtext: `${townStore.worldState.weather.temperature}°C · ${townStore.worldState.weather.windSpeed} km/h`,
    icon: '🌤',
    color: 'border-sky-400/30 text-sky-400',
    bg: 'bg-sky-400/5',
  },
])

// ─── Economy chart ─────────────────────────────────────────────────────────────

const economyChartData = computed<ChartData<'line'>>(() => {
  const hist = townStore.worldState.economyHistory.slice(-50)
  return {
    labels: hist.map((h) => `T${h.tick}`),
    datasets: [
      {
        label: 'Gold Supply',
        data: hist.map((h) => h.goldSupply),
        borderColor: '#f5a623',
        backgroundColor: 'rgba(245, 166, 35, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 5,
      },
    ],
  }
})

// ─── Population chart ──────────────────────────────────────────────────────────

const populationChartData = computed<ChartData<'line'>>(() => {
  const hist = townStore.worldState.populationHistory.slice(-50)
  return {
    labels: hist.map((h) => `T${h.tick}`),
    datasets: [
      {
        label: 'Population',
        data: hist.map((h) => h.count),
        borderColor: '#40916c',
        backgroundColor: 'rgba(64, 145, 108, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 5,
      },
    ],
  }
})

// ─── Happiness distribution chart ────────────────────────────────────────────

const happinessDistChartData = computed<ChartData<'doughnut'>>(() => {
  const npcs = townStore.worldState.npcs
  const veryHappy = npcs.filter((n) => n.happiness >= 80).length
  const happy = npcs.filter((n) => n.happiness >= 60 && n.happiness < 80).length
  const neutral = npcs.filter((n) => n.happiness >= 40 && n.happiness < 60).length
  const sad = npcs.filter((n) => n.happiness >= 20 && n.happiness < 40).length
  const miserable = npcs.filter((n) => n.happiness < 20).length

  return {
    labels: ['Very Happy (80+)', 'Happy (60-80)', 'Neutral (40-60)', 'Sad (20-40)', 'Miserable (<20)'],
    datasets: [
      {
        data: [veryHappy, happy, neutral, sad, miserable],
        backgroundColor: [
          'rgba(74, 222, 128, 0.8)',
          'rgba(34, 197, 94, 0.8)',
          'rgba(251, 191, 36, 0.8)',
          'rgba(249, 115, 22, 0.8)',
          'rgba(239, 68, 68, 0.8)',
        ],
        borderColor: ['#16213e'],
        borderWidth: 2,
      },
    ],
  }
})

const hasEconomyHistory = computed(() => townStore.worldState.economyHistory.length > 0)
const hasPopHistory = computed(() => townStore.worldState.populationHistory.length > 0)
const hasNpcs = computed(() => townStore.worldState.npcs.length > 0)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-qtown-text-primary">Dashboard</h1>
      <p class="text-qtown-text-secondary text-sm mt-0.5">
        Real-time metrics · Tick {{ townStore.worldState.tick.toLocaleString() }}
      </p>
    </div>

    <!-- Metric cards -->
    <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
      <div
        v-for="card in metricCards"
        :key="card.label"
        :class="['qtown-card border', card.color, card.bg, 'transition-all duration-300']"
      >
        <div class="flex items-start justify-between">
          <div>
            <div class="section-title text-qtown-text-dim">{{ card.label }}</div>
            <div :class="['font-mono font-bold text-xl mt-1', card.color.split(' ')[1]]">
              {{ card.value }}
            </div>
            <div class="text-qtown-text-dim text-xs mt-0.5">{{ card.subtext }}</div>
          </div>
          <span class="text-2xl" aria-hidden="true">{{ card.icon }}</span>
        </div>
      </div>
    </div>

    <!-- Charts row -->
    <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
      <!-- Economy chart -->
      <div class="qtown-card lg:col-span-1">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-qtown-text-primary">Gold Supply Over Time</h2>
          <span class="text-qtown-text-dim text-xs">last 50 ticks</span>
        </div>
        <ClientOnly>
          <div v-if="hasEconomyHistory">
            <MetricsChart
              type="line"
              :data="economyChartData"
              :height="240"
            />
          </div>
          <div
            v-else
            class="flex items-center justify-center text-qtown-text-dim"
            style="height: 240px"
          >
            <div class="text-center">
              <div class="text-2xl mb-2">📊</div>
              <div class="text-xs">No economy history yet</div>
            </div>
          </div>
        </ClientOnly>
      </div>

      <!-- Population chart -->
      <div class="qtown-card lg:col-span-1">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-qtown-text-primary">Population Over Time</h2>
          <span class="text-qtown-text-dim text-xs">last 50 ticks</span>
        </div>
        <ClientOnly>
          <div v-if="hasPopHistory">
            <MetricsChart
              type="line"
              :data="populationChartData"
              :height="240"
            />
          </div>
          <div
            v-else
            class="flex items-center justify-center text-qtown-text-dim"
            style="height: 240px"
          >
            <div class="text-center">
              <div class="text-2xl mb-2">👥</div>
              <div class="text-xs">No population history yet</div>
            </div>
          </div>
        </ClientOnly>
      </div>

      <!-- Happiness distribution -->
      <div class="qtown-card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-qtown-text-primary">Happiness Distribution</h2>
          <span class="text-qtown-text-dim text-xs">{{ townStore.worldState.npcs.length }} NPCs</span>
        </div>
        <ClientOnly>
          <div v-if="hasNpcs">
            <MetricsChart
              type="doughnut"
              :data="happinessDistChartData"
              :height="240"
              :options="{
                plugins: {
                  legend: { position: 'bottom', labels: { font: { size: 10 } } }
                }
              }"
            />
          </div>
          <div
            v-else
            class="flex items-center justify-center text-qtown-text-dim"
            style="height: 240px"
          >
            <div class="text-center">
              <div class="text-2xl mb-2">😊</div>
              <div class="text-xs">No NPC data yet</div>
            </div>
          </div>
        </ClientOnly>
      </div>
    </div>

    <!-- Event feed -->
    <div class="qtown-card p-0 overflow-hidden" style="height: 320px">
      <EventFeed channel="metrics" :max-items="100" />
    </div>

    <!-- Error state -->
    <div
      v-if="townStore.lastFetchError"
      class="qtown-card border border-qtown-accent/30 bg-qtown-accent/5 flex items-center gap-3"
    >
      <svg viewBox="0 0 20 20" class="w-5 h-5 text-qtown-accent shrink-0" fill="currentColor">
        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
      </svg>
      <div>
        <p class="text-qtown-accent text-sm font-medium">Error fetching data</p>
        <p class="text-qtown-text-dim text-xs">{{ townStore.lastFetchError }}</p>
      </div>
      <button
        class="ml-auto qtown-btn-ghost text-sm"
        @click="townStore.fetchState()"
      >
        Retry
      </button>
    </div>
  </div>
</template>
