<script setup lang="ts">
import { useTownState } from '~/composables/useTownState'
import { useWebSocket } from '~/composables/useWebSocket'
import type { TownEvent } from '~/composables/useTownState'
import type { WsMessage } from '~/composables/useWebSocket'

useHead({ title: 'Town View — Qtown' })

const townStore = useTownState()
const { subscribe, connect, status: wsStatus } = useWebSocket({ autoConnect: false })

// Fetch initial state
onMounted(async () => {
  await townStore.fetchState()

  // Connect and subscribe to world events
  connect()
  subscribe('world', (msg: WsMessage) => {
    const event = msg.payload as TownEvent
    townStore.updateFromEvent(event)
  })
})

const weatherIcons: Record<string, string> = {
  clear: '☀️',
  cloudy: '☁️',
  rain: '🌧',
  storm: '⛈',
  snow: '❄️',
  fog: '🌫',
}

const weatherIcon = computed(
  () => weatherIcons[townStore.worldState.weather.condition] ?? '🌤'
)

const timeOfDayPct = computed(() => Math.round(townStore.worldState.timeOfDay * 100))

const dayNightBg = computed(() =>
  townStore.worldState.isNight
    ? 'from-qtown-bg to-[#0a0a1a]'
    : 'from-[#0d1a0d] to-qtown-surface'
)

const stats = computed(() => [
  {
    label: 'Population',
    value: townStore.worldState.population.toLocaleString(),
    color: 'text-green-400',
  },
  {
    label: 'Total Gold',
    value: `${townStore.worldState.totalGold.toLocaleString()} g`,
    color: 'text-qtown-gold',
  },
  {
    label: 'Avg Happiness',
    value: `${townStore.worldState.averageHappiness}%`,
    color: 'text-purple-400',
  },
  {
    label: 'Active NPCs',
    value: townStore.worldState.activeNpcs.toLocaleString(),
    color: 'text-blue-400',
  },
])
</script>

<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">
          Town View
        </h1>
        <p class="text-qtown-text-secondary text-sm mt-0.5">
          Isometric world · Day {{ townStore.worldState.dayNumber }} ·
          {{ townStore.dayNightLabel }}
        </p>
      </div>

      <!-- Day/Night + Weather -->
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2 text-sm">
          <span class="text-qtown-text-dim">Weather</span>
          <span class="text-lg">{{ weatherIcon }}</span>
          <span class="text-qtown-text-secondary capitalize">
            {{ townStore.worldState.weather.condition }}
          </span>
          <span class="text-qtown-text-dim font-mono">
            {{ townStore.worldState.weather.temperature }}°C
          </span>
        </div>

        <!-- Connection status -->
        <div class="flex items-center gap-1.5 text-xs">
          <span
            :class="[
              'w-2 h-2 rounded-full',
              wsStatus === 'connected' ? 'bg-green-400 animate-pulse' : 'bg-gray-500',
            ]"
          />
          <span class="text-qtown-text-dim">
            {{ wsStatus === 'connected' ? 'Live' : 'Offline' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Day/Night cycle bar -->
    <div class="qtown-card p-3">
      <div class="flex items-center gap-3">
        <span class="text-xs text-qtown-text-dim font-mono">DAWN</span>
        <div class="flex-1 h-2 bg-qtown-border rounded-full overflow-hidden relative">
          <!-- Day gradient -->
          <div class="absolute inset-0 bg-gradient-to-r from-[#1a0a00] via-[#f5a623] to-[#1a0a00] opacity-30 rounded-full" />
          <!-- Position indicator -->
          <div
            class="absolute top-0 bottom-0 w-3 -ml-1.5 rounded-full bg-qtown-gold shadow-glow-gold transition-all duration-1000"
            :style="{ left: `${timeOfDayPct}%` }"
          />
        </div>
        <span class="text-xs text-qtown-text-dim font-mono">DUSK</span>
        <span class="text-xs font-mono text-qtown-text-secondary w-8 text-right">
          {{ timeOfDayPct }}%
        </span>
      </div>
    </div>

    <!-- Stats row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="qtown-card text-center"
      >
        <div :class="['stat-number', stat.color]">{{ stat.value }}</div>
        <div class="section-title mt-1">{{ stat.label }}</div>
      </div>
    </div>

    <!-- Main layout: renderer + event feed -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <!-- PixiJS renderer -->
      <div class="xl:col-span-2 qtown-card p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-qtown-border flex items-center justify-between">
          <span class="section-title">Isometric World Renderer</span>
          <span class="text-xs font-mono text-qtown-text-dim">
            {{ townStore.worldState.buildings.length }} buildings ·
            {{ townStore.worldState.npcs.length }} npcs
          </span>
        </div>

        <ClientOnly>
          <PixiRenderer
            :world-state="townStore.worldState"
            :width="900"
            :height="520"
          />
          <template #fallback>
            <div
              class="flex items-center justify-center bg-qtown-bg"
              style="height: 520px"
            >
              <div class="text-center text-qtown-text-dim">
                <div class="text-3xl mb-2">🏰</div>
                <div class="text-sm">Loading world renderer...</div>
              </div>
            </div>
          </template>
        </ClientOnly>
      </div>

      <!-- Event feed -->
      <div class="qtown-card p-0 overflow-hidden relative" style="height: 600px">
        <EventFeed channel="world" :max-items="150" :auto-scroll="true" />
      </div>
    </div>

    <!-- Tick info footer -->
    <div class="flex items-center gap-4 text-xs text-qtown-text-dim font-mono">
      <span>TICK <span class="text-qtown-gold">{{ townStore.worldState.tick.toLocaleString() }}</span></span>
      <span>·</span>
      <span>
        LAST UPDATED
        <span class="text-qtown-text-secondary">
          {{ townStore.lastUpdated ? townStore.lastUpdated.toLocaleTimeString() : 'Never' }}
        </span>
      </span>
      <div v-if="townStore.isLoading" class="flex items-center gap-1">
        <div class="w-1.5 h-1.5 rounded-full bg-qtown-gold animate-bounce" />
        <span class="text-qtown-text-dim">Fetching...</span>
      </div>
    </div>
  </div>
</template>
