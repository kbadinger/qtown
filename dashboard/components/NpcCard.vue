<script setup lang="ts">
import type { NpcSummary } from '~/composables/useTownState'

const props = defineProps<{
  npc: NpcSummary
  clickable?: boolean
}>()

const statusConfig: Record<NpcSummary['status'], { label: string; color: string; dot: string }> = {
  active: { label: 'Active', color: 'text-green-400 bg-green-400/10 border-green-400/30', dot: 'bg-green-400' },
  traveling: { label: 'Traveling', color: 'text-blue-400 bg-blue-400/10 border-blue-400/30', dot: 'bg-blue-400 animate-pulse' },
  sleeping: { label: 'Sleeping', color: 'text-indigo-400 bg-indigo-400/10 border-indigo-400/30', dot: 'bg-indigo-400' },
  idle: { label: 'Idle', color: 'text-qtown-text-dim bg-qtown-border/50 border-qtown-border', dot: 'bg-qtown-text-dim' },
}

const status = computed(() => statusConfig[props.npc.status] ?? statusConfig.idle)

const happinessColor = computed(() => {
  const h = props.npc.happiness
  if (h >= 70) return 'bg-green-500'
  if (h >= 40) return 'bg-yellow-500'
  return 'bg-red-500'
})

// Generate a pseudo-consistent color from npc id
const portraitColor = computed(() => {
  let hash = 0
  for (const char of props.npc.id) {
    hash = (hash << 5) - hash + char.charCodeAt(0)
    hash |= 0
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 60%, 35%)`
})

const initials = computed(() => {
  const parts = props.npc.name.split(' ')
  return parts.length >= 2
    ? `${parts[0][0]}${parts[1][0]}`
    : props.npc.name.slice(0, 2)
})
</script>

<template>
  <div
    class="qtown-card flex items-center gap-3 transition-all duration-200"
    :class="clickable ? 'cursor-pointer hover:border-qtown-accent/50 hover:shadow-card-hover hover:-translate-y-0.5' : ''"
  >
    <!-- Portrait -->
    <div
      class="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold font-mono text-white shrink-0"
      :style="{ backgroundColor: portraitColor }"
      aria-hidden="true"
    >
      {{ initials.toUpperCase() }}
    </div>

    <!-- Info -->
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="text-qtown-text-primary font-medium text-sm truncate">{{ npc.name }}</span>
        <span
          :class="['qtown-badge border', status.color]"
          style="font-size: 10px"
        >
          <span :class="['w-1.5 h-1.5 rounded-full mr-1', status.dot]" />
          {{ status.label }}
        </span>
      </div>

      <div class="flex items-center gap-3 mt-0.5">
        <span class="text-qtown-text-dim text-xs">{{ npc.role }}</span>
        <span class="text-qtown-text-dim text-xs">{{ npc.neighborhood }}</span>
      </div>

      <!-- Happiness bar -->
      <div class="mt-1.5 flex items-center gap-2">
        <div class="flex-1 h-1 bg-qtown-border rounded-full overflow-hidden">
          <div
            :class="['h-full rounded-full transition-all duration-500', happinessColor]"
            :style="{ width: `${Math.max(0, Math.min(100, npc.happiness))}%` }"
          />
        </div>
        <span class="text-qtown-text-dim text-xs font-mono w-8 text-right">{{ npc.happiness }}%</span>
      </div>
    </div>

    <!-- Gold -->
    <div class="text-right shrink-0">
      <div class="text-qtown-gold font-mono font-bold text-sm">{{ npc.gold.toLocaleString() }}</div>
      <div class="text-qtown-text-dim text-xs">gold</div>
    </div>
  </div>
</template>
