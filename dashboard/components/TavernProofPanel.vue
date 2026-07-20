<script setup lang="ts">
// Tavern proof panel — the "real-time gateway" made visible.
//
// Tavern consumes town events off Kafka, fans them out over Redis pub/sub, and
// broadcasts them to WebSocket channels. This panel proves that path through
// tavern's HTTP read-model (recent content that passed through + live gateway
// metrics) via the dormant-safe /api/tavern/content BFF — real data or an honest
// — , never fabricated.
interface ContentEntry {
  id: string
  contentType: string
  text: string
  receivedAt: string
  participants: string | null
  tone: string | null
  model: string | null
}
interface TavernProof {
  live: boolean
  connections: number | null
  messagesPerSecond: number | null
  activeChannels: string[]
  items: ContentEntry[]
}

const data = ref<TavernProof | null>(null)
const pending = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

async function refresh(): Promise<void> {
  try {
    data.value = await $fetch<TavernProof>('/api/tavern/content', { query: { limit: 12 } })
  } catch {
    data.value = { live: false, connections: null, messagesPerSecond: null, activeChannels: [], items: [] }
  } finally {
    pending.value = false
  }
}

onMounted(() => {
  void refresh()
  if (import.meta.client) timer = setInterval(() => void refresh(), 5000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const live = computed(() => data.value?.live ?? false)
const items = computed(() => data.value?.items ?? [])
const connections = computed(() => data.value?.connections ?? null)
const mps = computed(() => data.value?.messagesPerSecond ?? null)
const channels = computed(() => data.value?.activeChannels ?? [])

function fmt(n: number | null): string {
  return n === null ? '—' : String(n)
}
function fmtTime(iso: string): string {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? '—' : new Date(t).toLocaleTimeString()
}
</script>

<template>
  <div class="qtown-card">
    <!-- Header -->
    <div class="flex items-start justify-between flex-wrap gap-3 mb-4">
      <div>
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-bold text-qtown-text-primary">Tavern</h2>
          <ProofBadge :live="live" />
        </div>
        <p class="section-title mt-1">Real-time gateway proof</p>
      </div>
    </div>

    <!-- Gateway metrics -->
    <div class="grid grid-cols-3 gap-3 text-center mb-4">
      <div>
        <div class="stat-number text-xl">{{ fmt(connections) }}</div>
        <div class="section-title mt-0.5">WS clients</div>
      </div>
      <div>
        <div class="stat-number text-xl">{{ fmt(mps) }}</div>
        <div class="section-title mt-0.5">msg / sec</div>
      </div>
      <div>
        <div class="stat-number text-xl">{{ live ? channels.length : '—' }}</div>
        <div class="section-title mt-0.5">active channels</div>
      </div>
    </div>

    <!-- Recent content through the gateway -->
    <div class="section-title mb-2">Recent content</div>
    <div v-if="!live && !pending" class="py-8 text-center text-qtown-text-dim text-sm">
      Tavern unavailable — <span class="font-mono">—</span>
    </div>
    <div v-else-if="items.length === 0" class="py-8 text-center text-qtown-text-dim text-sm">
      No content through the gateway yet
    </div>
    <div v-else class="space-y-2 max-h-[360px] overflow-y-auto pr-1">
      <div
        v-for="it in items"
        :key="it.id"
        class="rounded border border-qtown-border bg-qtown-surface/40 px-3 py-2"
      >
        <div class="flex items-center justify-between text-xs mb-1">
          <span class="font-semibold text-qtown-gold">
            {{ it.participants ?? it.contentType }}
          </span>
          <span class="text-qtown-text-dim font-mono">{{ fmtTime(it.receivedAt) }}</span>
        </div>
        <p class="text-sm text-qtown-text-secondary leading-snug whitespace-pre-line">{{ it.text }}</p>
        <div v-if="it.tone || it.model" class="mt-1 text-[11px] text-qtown-text-dim font-mono">
          <span v-if="it.tone">{{ it.tone }}</span>
          <span v-if="it.tone && it.model"> · </span>
          <span v-if="it.model">{{ it.model }}</span>
        </div>
      </div>
    </div>

    <!-- What it proves -->
    <div class="mt-4 pt-3 border-t border-qtown-border text-xs text-qtown-text-secondary">
      <span class="section-title">Proves</span>
      <span class="ml-2">Kafka consume · Redis pub/sub fan-out · channel-scoped WebSocket delivery</span>
    </div>
  </div>
</template>
