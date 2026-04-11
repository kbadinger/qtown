<script setup lang="ts">
import type { ChartData, ChartOptions } from 'chart.js'
import { useGraphQL } from '~/composables/useGraphQL'
import type { OrderBook, Trade } from '~/composables/useGraphQL'
import { useWebSocket } from '~/composables/useWebSocket'
import type { WsMessage } from '~/composables/useWebSocket'

useHead({ title: 'Market — Qtown' })

const graphql = useGraphQL()
const { connect, subscribe } = useWebSocket({ autoConnect: false })

// ─── State ────────────────────────────────────────────────────────────────────

const resources = ['Wood', 'Stone', 'Grain', 'Iron', 'Gold', 'Fish', 'Leather', 'Coal', 'Herbs']
const selectedResource = ref('Wood')
const orderBook = ref<OrderBook | null>(null)
const recentTrades = ref<Trade[]>([])

// ─── Fetch ─────────────────────────────────────────────────────────────────────

async function loadOrderBook() {
  orderBook.value = await graphql.fetchOrderBook(selectedResource.value)
}

async function loadTrades() {
  recentTrades.value = await graphql.fetchRecentTrades(selectedResource.value, 50)
}

async function loadAll() {
  await Promise.all([loadOrderBook(), loadTrades()])
}

onMounted(async () => {
  await loadAll()

  connect()
  subscribe('market', (msg: WsMessage) => {
    // On trade execution, refresh
    if (msg.type === 'trade_executed' || msg.type === 'order_placed') {
      loadAll()
    }
  })
})

watch(selectedResource, () => {
  loadAll()
})

// ─── Price history chart ──────────────────────────────────────────────────────

const priceHistoryData = computed<ChartData<'line'>>(() => {
  const hist = orderBook.value?.priceHistory.slice(-80) ?? []
  return {
    labels: hist.map((h) => `T${h.tick}`),
    datasets: [
      {
        label: `${selectedResource.value} Price`,
        data: hist.map((h) => h.price),
        borderColor: '#f5a623',
        backgroundColor: 'rgba(245, 166, 35, 0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 1.5,
        pointHoverRadius: 4,
        borderWidth: 2,
      },
    ],
  }
})

const priceHistoryOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#16213e',
      borderColor: '#2a2a4a',
      borderWidth: 1,
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
      callbacks: {
        label: (ctx) => ` Price: ${Number(ctx.raw).toFixed(4)}`,
      },
    },
  },
  scales: {
    x: {
      ticks: { color: '#475569', font: { size: 9 }, maxTicksLimit: 10 },
      grid: { color: '#1a1a2e' },
    },
    y: {
      ticks: {
        color: '#475569',
        font: { size: 10 },
        callback: (val) => Number(val).toFixed(2),
      },
      grid: { color: '#2a2a4a' },
    },
  },
}))

// ─── Trade side color ─────────────────────────────────────────────────────────

const tradeItems = computed(() =>
  recentTrades.value.slice(0, 30)
)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">Market</h1>
        <p class="text-qtown-text-secondary text-sm mt-0.5">
          Live order book · bid/ask depth · trade history
        </p>
      </div>

      <!-- Resource selector -->
      <div class="flex items-center gap-2">
        <span class="section-title">Resource</span>
        <select
          v-model="selectedResource"
          class="qtown-input text-sm font-medium min-w-36"
        >
          <option v-for="r in resources" :key="r" :value="r">{{ r }}</option>
        </select>

        <button
          class="qtown-btn-ghost text-sm flex items-center gap-1.5"
          @click="loadAll"
        >
          <svg viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 8A6 6 0 102 8" stroke-linecap="round" />
            <path d="M14 5v3h-3" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- Stats row -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="qtown-card">
        <div class="section-title">Last Price</div>
        <div class="stat-number mt-1">{{ orderBook?.lastPrice.toFixed(4) ?? '—' }}</div>
      </div>
      <div class="qtown-card">
        <div class="section-title">24h Volume</div>
        <div class="stat-number mt-1 text-green-400">{{ orderBook?.volume24h.toLocaleString() ?? '—' }}</div>
      </div>
      <div class="qtown-card">
        <div class="section-title">Open Bids</div>
        <div class="stat-number mt-1 text-green-400">{{ orderBook?.bids.length ?? '—' }}</div>
      </div>
      <div class="qtown-card">
        <div class="section-title">Open Asks</div>
        <div class="stat-number mt-1 text-red-400">{{ orderBook?.asks.length ?? '—' }}</div>
      </div>
    </div>

    <!-- Main layout -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <!-- Order book depth chart -->
      <div class="qtown-card">
        <h2 class="text-sm font-semibold text-qtown-text-primary mb-4">
          Order Book Depth — {{ selectedResource }}
        </h2>
        <ClientOnly>
          <OrderBookChart
            :bids="orderBook?.bids ?? []"
            :asks="orderBook?.asks ?? []"
            :last-price="orderBook?.lastPrice"
            :loading="graphql.isLoading.value"
          />
        </ClientOnly>
      </div>

      <!-- Price history chart -->
      <div class="qtown-card">
        <h2 class="text-sm font-semibold text-qtown-text-primary mb-4">
          Price History — {{ selectedResource }}
        </h2>
        <ClientOnly>
          <div style="height: 280px">
            <MetricsChart
              v-if="(orderBook?.priceHistory.length ?? 0) > 0"
              type="line"
              :data="priceHistoryData"
              :options="priceHistoryOptions"
              :height="280"
            />
            <div
              v-else
              class="flex items-center justify-center h-full text-qtown-text-dim"
            >
              <div class="text-center">
                <div class="text-2xl mb-2">📈</div>
                <div class="text-xs">No price history available</div>
              </div>
            </div>
          </div>
        </ClientOnly>
      </div>
    </div>

    <!-- Level 2 order book -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Bids -->
      <div class="qtown-card p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-qtown-border flex items-center justify-between">
          <h2 class="text-sm font-semibold text-green-400">Bids</h2>
          <span class="text-xs text-qtown-text-dim">{{ orderBook?.bids.length ?? 0 }} orders</span>
        </div>
        <div class="overflow-y-auto" style="max-height: 280px">
          <table class="w-full text-xs">
            <thead class="sticky top-0 bg-qtown-card">
              <tr class="border-b border-qtown-border">
                <th class="px-4 py-2 text-left text-qtown-text-dim section-title">Price</th>
                <th class="px-4 py-2 text-right text-qtown-text-dim section-title">Quantity</th>
                <th class="px-4 py-2 text-right text-qtown-text-dim section-title">Cumulative</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(bid, idx) in [...(orderBook?.bids ?? [])].sort((a, b) => b.price - a.price).slice(0, 20)"
                :key="idx"
                class="border-b border-qtown-border/30 hover:bg-green-400/5 relative"
              >
                <!-- Depth bar -->
                <td colspan="3" class="absolute inset-0 pointer-events-none">
                  <div
                    class="absolute right-0 top-0 bottom-0 bg-green-500/10"
                    :style="{ width: `${Math.min(100, (bid.totalQuantity / (orderBook?.bids[0]?.totalQuantity ?? 1)) * 100)}%` }"
                  />
                </td>
                <td class="px-4 py-1.5 text-green-400 font-mono font-semibold relative">
                  {{ bid.price.toFixed(4) }}
                </td>
                <td class="px-4 py-1.5 text-right font-mono text-qtown-text-secondary relative">
                  {{ bid.quantity.toLocaleString() }}
                </td>
                <td class="px-4 py-1.5 text-right font-mono text-qtown-text-dim relative">
                  {{ bid.totalQuantity.toLocaleString() }}
                </td>
              </tr>
              <tr v-if="!orderBook?.bids.length">
                <td colspan="3" class="px-4 py-6 text-center text-qtown-text-dim">No bids</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Asks -->
      <div class="qtown-card p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-qtown-border flex items-center justify-between">
          <h2 class="text-sm font-semibold text-red-400">Asks</h2>
          <span class="text-xs text-qtown-text-dim">{{ orderBook?.asks.length ?? 0 }} orders</span>
        </div>
        <div class="overflow-y-auto" style="max-height: 280px">
          <table class="w-full text-xs">
            <thead class="sticky top-0 bg-qtown-card">
              <tr class="border-b border-qtown-border">
                <th class="px-4 py-2 text-left text-qtown-text-dim section-title">Price</th>
                <th class="px-4 py-2 text-right text-qtown-text-dim section-title">Quantity</th>
                <th class="px-4 py-2 text-right text-qtown-text-dim section-title">Cumulative</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(ask, idx) in [...(orderBook?.asks ?? [])].sort((a, b) => a.price - b.price).slice(0, 20)"
                :key="idx"
                class="border-b border-qtown-border/30 hover:bg-red-400/5 relative"
              >
                <td colspan="3" class="absolute inset-0 pointer-events-none">
                  <div
                    class="absolute left-0 top-0 bottom-0 bg-red-500/10"
                    :style="{ width: `${Math.min(100, (ask.totalQuantity / (orderBook?.asks[0]?.totalQuantity ?? 1)) * 100)}%` }"
                  />
                </td>
                <td class="px-4 py-1.5 text-red-400 font-mono font-semibold relative">
                  {{ ask.price.toFixed(4) }}
                </td>
                <td class="px-4 py-1.5 text-right font-mono text-qtown-text-secondary relative">
                  {{ ask.quantity.toLocaleString() }}
                </td>
                <td class="px-4 py-1.5 text-right font-mono text-qtown-text-dim relative">
                  {{ ask.totalQuantity.toLocaleString() }}
                </td>
              </tr>
              <tr v-if="!orderBook?.asks.length">
                <td colspan="3" class="px-4 py-6 text-center text-qtown-text-dim">No asks</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Recent trades -->
    <div class="qtown-card p-0 overflow-hidden">
      <div class="px-4 py-3 border-b border-qtown-border flex items-center justify-between">
        <h2 class="text-sm font-semibold text-qtown-text-primary">Recent Trades</h2>
        <span class="text-xs text-qtown-text-dim">{{ tradeItems.length }} trades</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-qtown-border">
              <th class="px-4 py-3 text-left section-title">Time</th>
              <th class="px-4 py-3 text-left section-title">Resource</th>
              <th class="px-4 py-3 text-right section-title">Price</th>
              <th class="px-4 py-3 text-right section-title">Qty</th>
              <th class="px-4 py-3 text-left section-title">Buyer</th>
              <th class="px-4 py-3 text-left section-title">Seller</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="trade in tradeItems"
              :key="trade.id"
              class="border-b border-qtown-border/50 hover:bg-qtown-border/20 transition-colors"
            >
              <td class="px-4 py-2.5 text-xs text-qtown-text-dim font-mono">
                {{ new Date(trade.executedAt).toLocaleTimeString() }}
              </td>
              <td class="px-4 py-2.5 text-qtown-text-primary">{{ trade.resourceType }}</td>
              <td class="px-4 py-2.5 text-right font-mono text-qtown-gold">{{ trade.price.toFixed(4) }}</td>
              <td class="px-4 py-2.5 text-right font-mono text-qtown-text-secondary">{{ trade.quantity }}</td>
              <td class="px-4 py-2.5 text-green-400 text-xs">{{ trade.buyerName }}</td>
              <td class="px-4 py-2.5 text-red-400 text-xs">{{ trade.sellerName }}</td>
            </tr>
            <tr v-if="tradeItems.length === 0">
              <td colspan="6" class="px-4 py-10 text-center text-qtown-text-dim">
                No trades yet for {{ selectedResource }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
