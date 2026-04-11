<script setup lang="ts">
import type { WsMessage } from '~/composables/useWebSocket'
import { useWebSocket } from '~/composables/useWebSocket'
import { useTownState } from '~/composables/useTownState'
import type { TownEvent } from '~/composables/useTownState'

const props = withDefaults(
  defineProps<{
    channel?: string
    maxItems?: number
    autoScroll?: boolean
  }>(),
  {
    channel: 'events',
    maxItems: 100,
    autoScroll: true,
  }
)

const townStore = useTownState()
const feedEl = ref<HTMLDivElement | null>(null)

const localEvents = ref<TownEvent[]>([])
const isAtBottom = ref(true)

// Use WebSocket composable
const { status: wsStatus, subscribe, connect } = useWebSocket({
  autoConnect: false,
})

// Merge store events + local websocket events
const displayEvents = computed(() => {
  const combined = [
    ...localEvents.value,
    ...townStore.recentEvents.filter(
      (e) => !localEvents.value.some((le) => le.id === e.id)
    ),
  ]
  // Sort newest first, cap at maxItems
  return combined
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, props.maxItems)
})

const eventTypeConfig: Record<string, { color: string; bg: string }> = {
  'npc.moved': { color: 'text-blue-400', bg: 'bg-blue-400/10' },
  'npc.status_changed': { color: 'text-indigo-400', bg: 'bg-indigo-400/10' },
  'npc.trade': { color: 'text-qtown-gold', bg: 'bg-qtown-gold/10' },
  'npc.dialogue': { color: 'text-purple-400', bg: 'bg-purple-400/10' },
  'market.trade_executed': { color: 'text-green-400', bg: 'bg-green-400/10' },
  'market.order_placed': { color: 'text-teal-400', bg: 'bg-teal-400/10' },
  'market.order_cancelled': { color: 'text-red-400', bg: 'bg-red-400/10' },
  'world.tick': { color: 'text-qtown-text-dim', bg: 'bg-qtown-border/30' },
  'economy.tick': { color: 'text-yellow-400', bg: 'bg-yellow-400/10' },
  'validation.rejected': { color: 'text-qtown-accent', bg: 'bg-qtown-accent/10' },
  default: { color: 'text-qtown-text-secondary', bg: 'bg-qtown-border/20' },
}

function getEventStyle(type: string) {
  return eventTypeConfig[type] ?? eventTypeConfig['default']
}

function formatEventTime(timestamp: string): string {
  try {
    const d = new Date(timestamp)
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  } catch {
    return '--:--:--'
  }
}

function formatEventType(type: string): string {
  return type.replace(/\./g, ' › ')
}

function handleScroll() {
  if (!feedEl.value) return
  const { scrollTop, scrollHeight, clientHeight } = feedEl.value
  isAtBottom.value = scrollHeight - scrollTop - clientHeight < 40
}

function scrollToBottom() {
  if (feedEl.value) {
    feedEl.value.scrollTop = feedEl.value.scrollHeight
  }
}

// On mount, connect websocket and subscribe
onMounted(() => {
  if (import.meta.client) {
    connect()

    subscribe(props.channel, (message: WsMessage) => {
      const event = message.payload as TownEvent
      localEvents.value.unshift(event)
      if (localEvents.value.length > props.maxItems) {
        localEvents.value = localEvents.value.slice(0, props.maxItems)
      }
      townStore.updateFromEvent(event)

      // Auto-scroll if at bottom
      if (props.autoScroll && isAtBottom.value) {
        nextTick(scrollToBottom)
      }
    })
  }
})

// Watch events to auto-scroll
watch(displayEvents, () => {
  if (props.autoScroll && isAtBottom.value) {
    nextTick(scrollToBottom)
  }
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-qtown-border shrink-0">
      <div class="flex items-center gap-2">
        <span class="section-title">Live Events</span>
        <span
          :class="[
            'w-2 h-2 rounded-full',
            wsStatus === 'connected' ? 'bg-green-400 animate-pulse' : 'bg-gray-500'
          ]"
        />
      </div>
      <span class="text-qtown-text-dim text-xs font-mono">{{ displayEvents.length }}</span>
    </div>

    <!-- Feed -->
    <div
      ref="feedEl"
      class="flex-1 overflow-y-auto p-2 space-y-1"
      @scroll="handleScroll"
    >
      <div
        v-for="event in displayEvents"
        :key="event.id"
        class="flex items-start gap-2 px-2 py-1.5 rounded text-xs group hover:bg-qtown-border/30 transition-colors animate-fade-in"
      >
        <!-- Time -->
        <span class="font-mono text-qtown-text-dim shrink-0 tabular-nums pt-0.5">
          {{ formatEventTime(event.timestamp) }}
        </span>

        <!-- Type badge -->
        <span
          :class="['qtown-badge border border-transparent shrink-0', getEventStyle(event.type).bg, getEventStyle(event.type).color]"
          style="font-size: 10px; padding: 1px 5px"
        >
          {{ formatEventType(event.type) }}
        </span>

        <!-- Description -->
        <span class="text-qtown-text-secondary flex-1 leading-snug">{{ event.description }}</span>
      </div>

      <!-- Empty state -->
      <div
        v-if="displayEvents.length === 0"
        class="flex flex-col items-center justify-center py-12 text-qtown-text-dim"
      >
        <svg viewBox="0 0 24 24" class="w-8 h-8 mb-2 opacity-30" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 6v6l4 2" stroke-linecap="round" />
          <circle cx="12" cy="12" r="10" />
        </svg>
        <p class="text-sm">Waiting for events...</p>
      </div>
    </div>

    <!-- Scroll-to-bottom button -->
    <Transition name="fade">
      <button
        v-if="!isAtBottom && displayEvents.length > 0"
        class="absolute bottom-4 right-4 bg-qtown-accent text-white rounded-full p-2 shadow-lg hover:bg-qtown-crimson transition-colors"
        @click="scrollToBottom"
        aria-label="Scroll to latest events"
      >
        <svg viewBox="0 0 16 16" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 6l4 4 4-4" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    </Transition>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
