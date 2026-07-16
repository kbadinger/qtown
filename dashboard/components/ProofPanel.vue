<script setup lang="ts">
// Market proof panel — the "distributed-systems proof" made visible.
//
// Live order book + recent trades come from market-district's read-model via the
// /api/market/proof BFF (real data, or an honest dormant state — never fabricated).
// The performance tile shows the committed, dated measurements from W1-M7. The
// "proves" line lists only claims already behind green CI gates.
import { MARKET_PERF, useMarketProof } from '~/composables/useMarketProof'

const props = withDefaults(defineProps<{ resource?: string }>(), { resource: 'gold' })

const resources = ['gold', 'wood', 'stone', 'iron', 'grain', 'fish']

const { resource, data, pending, start, stop } = useMarketProof(props.resource)

onMounted(() => start(4000))
onUnmounted(() => stop())

const live = computed(() => data.value?.live ?? false)
const book = computed(() => data.value?.book ?? { bids: [], asks: [], mid: null, spread: null })
const trades = computed(() => data.value?.trades ?? [])
const hasBook = computed(() => book.value.bids.length > 0 || book.value.asks.length > 0)

// Ladder display: asks descending (best/lowest ask sits just above the spread).
const asksDesc = computed(() => [...book.value.asks].sort((a, b) => b.price - a.price))
const maxQty = computed(() => {
  const qtys = [...book.value.bids, ...book.value.asks].map((l) => l.quantity)
  return qtys.length > 0 ? Math.max(...qtys) : 1
})

function barPct(qty: number): number {
  return Math.min(100, (qty / maxQty.value) * 100)
}
function fmtPrice(n: number): string {
  return n.toFixed(2)
}
function fmtTime(ts: number): string {
  return ts > 0 ? new Date(ts * 1000).toLocaleTimeString() : '—'
}

const placementP99 = `${MARKET_PERF.placementP99Ms} ms`
const placementRps = `~${Math.round(MARKET_PERF.placementRps / 1000)}k rps`
const fullSpineP99 = `${MARKET_PERF.fullSpineP99Ms} ms`
const enginePerOp = `${(MARKET_PERF.engineNsPerOp / 1000).toFixed(1)} µs/op`
</script>

<template>
  <div class="qtown-card">
    <!-- Header -->
    <div class="flex items-start justify-between flex-wrap gap-3 mb-4">
      <div>
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-bold text-qtown-text-primary">Market</h2>
          <ProofBadge :live="live" />
        </div>
        <p class="section-title mt-1">Distributed-systems proof</p>
      </div>
      <div class="flex items-center gap-2">
        <span class="section-title">Resource</span>
        <select v-model="resource" class="qtown-input text-sm font-medium">
          <option v-for="r in resources" :key="r" :value="r">{{ r }}</option>
        </select>
      </div>
    </div>

    <!-- Body: order book + recent trades -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <!-- Order book ladder -->
      <div>
        <div class="section-title mb-2">Order Book</div>

        <div v-if="!live && !pending" class="py-8 text-center text-qtown-text-dim text-sm">
          Source unavailable — <span class="font-mono">—</span>
        </div>
        <div v-else-if="!hasBook" class="py-8 text-center text-qtown-text-dim text-sm">
          No resting orders
        </div>
        <div v-else class="space-y-0.5 font-mono text-xs">
          <!-- Asks (red), highest price on top -->
          <div
            v-for="(ask, i) in asksDesc"
            :key="`a-${i}`"
            class="relative flex items-center justify-between px-2 py-1 rounded"
          >
            <div class="absolute right-0 top-0 bottom-0 bg-red-500/10 rounded" :style="{ width: `${barPct(ask.quantity)}%` }" />
            <span class="relative text-red-400 font-semibold">{{ fmtPrice(ask.price) }}</span>
            <span class="relative text-qtown-text-secondary">{{ ask.quantity }}</span>
          </div>

          <!-- Spread / mid -->
          <div class="flex items-center justify-between px-2 py-1.5 my-1 border-y border-qtown-border text-qtown-text-dim">
            <span>spread <span class="text-qtown-text-secondary">{{ book.spread !== null ? fmtPrice(book.spread) : '—' }}</span></span>
            <span>mid <span class="text-qtown-gold">{{ book.mid !== null ? fmtPrice(book.mid) : '—' }}</span></span>
          </div>

          <!-- Bids (green), highest price on top -->
          <div
            v-for="(bid, i) in book.bids"
            :key="`b-${i}`"
            class="relative flex items-center justify-between px-2 py-1 rounded"
          >
            <div class="absolute right-0 top-0 bottom-0 bg-green-500/10 rounded" :style="{ width: `${barPct(bid.quantity)}%` }" />
            <span class="relative text-green-400 font-semibold">{{ fmtPrice(bid.price) }}</span>
            <span class="relative text-qtown-text-secondary">{{ bid.quantity }}</span>
          </div>
        </div>
      </div>

      <!-- Recent trades -->
      <div>
        <div class="section-title mb-2">Recent Trades</div>

        <div v-if="!live && !pending" class="py-8 text-center text-qtown-text-dim text-sm">
          Source unavailable — <span class="font-mono">—</span>
        </div>
        <div v-else-if="trades.length === 0" class="py-8 text-center text-qtown-text-dim text-sm">
          No trades yet
        </div>
        <div v-else class="space-y-0.5 font-mono text-xs">
          <div
            v-for="trade in trades"
            :key="trade.id"
            class="flex items-center justify-between px-2 py-1 rounded hover:bg-qtown-border/20"
          >
            <span class="text-qtown-text-dim">{{ fmtTime(trade.ts) }}</span>
            <span class="text-qtown-gold font-semibold">{{ fmtPrice(trade.price) }}</span>
            <span class="text-qtown-text-secondary">×{{ trade.quantity }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Measured performance (committed, dated) -->
    <div class="mt-5 pt-4 border-t border-qtown-border">
      <div class="flex items-center justify-between mb-2">
        <span class="section-title">Measured</span>
        <span class="text-xs text-qtown-text-dim">{{ MARKET_PERF.measuredOn }} · {{ MARKET_PERF.hardware }}</span>
      </div>
      <div class="grid grid-cols-3 gap-3 text-center">
        <div>
          <div class="stat-number text-xl">{{ placementP99 }}</div>
          <div class="section-title mt-0.5">placement p99</div>
          <div class="text-xs text-qtown-text-dim mt-0.5">{{ placementRps }}</div>
        </div>
        <div>
          <div class="stat-number text-xl">{{ fullSpineP99 }}</div>
          <div class="section-title mt-0.5">full-spine p99</div>
          <div class="text-xs text-qtown-text-dim mt-0.5">match → 2× settle</div>
        </div>
        <div>
          <div class="stat-number text-xl">{{ enginePerOp }}</div>
          <div class="section-title mt-0.5">engine</div>
          <div class="text-xs text-qtown-text-dim mt-0.5">CI bench</div>
        </div>
      </div>
      <p class="text-xs text-qtown-text-dim mt-2 italic">{{ MARKET_PERF.provenance }}</p>
    </div>

    <!-- What it proves (each claim already behind a green CI gate) -->
    <div class="mt-4 pt-3 border-t border-qtown-border text-xs text-qtown-text-secondary">
      <span class="section-title">Proves</span>
      <span class="ml-2">concurrent matching · typed gRPC contract · at-least-once + idempotent settlement</span>
    </div>
  </div>
</template>
