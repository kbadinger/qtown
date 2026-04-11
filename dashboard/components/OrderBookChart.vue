<script setup lang="ts">
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js'
import type { ChartData, ChartOptions } from 'chart.js'
import { Bar } from 'vue-chartjs'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

export interface OrderBookEntry {
  price: number
  quantity: number
  totalQuantity: number
}

const props = defineProps<{
  bids: OrderBookEntry[]
  asks: OrderBookEntry[]
  lastPrice?: number
  loading?: boolean
}>()

const chartData = computed<ChartData<'bar'>>(() => {
  // Sort: bids descending (highest first), asks ascending (lowest first)
  const sortedBids = [...props.bids].sort((a, b) => b.price - a.price).slice(0, 15)
  const sortedAsks = [...props.asks].sort((a, b) => a.price - b.price).slice(0, 15)

  // Build cumulative depth
  let cumBid = 0
  const bidDepth = sortedBids.map((b) => {
    cumBid += b.quantity
    return { price: b.price, cumQty: cumBid }
  })

  let cumAsk = 0
  const askDepth = sortedAsks.map((a) => {
    cumAsk += a.quantity
    return { price: a.price, cumQty: cumAsk }
  })

  const bidLabels = bidDepth.map((b) => b.price.toFixed(2))
  const askLabels = askDepth.map((a) => a.price.toFixed(2))
  const allLabels = [...bidLabels.reverse(), ...askLabels]

  return {
    labels: allLabels,
    datasets: [
      {
        label: 'Bids (cumulative)',
        data: [
          ...bidDepth.map((b) => b.cumQty).reverse(),
          ...new Array<null>(askDepth.length).fill(null),
        ],
        backgroundColor: 'rgba(64, 145, 108, 0.6)',
        borderColor: '#40916c',
        borderWidth: 1,
      },
      {
        label: 'Asks (cumulative)',
        data: [
          ...new Array<null>(bidDepth.length).fill(null),
          ...askDepth.map((a) => a.cumQty),
        ],
        backgroundColor: 'rgba(233, 69, 96, 0.6)',
        borderColor: '#e94560',
        borderWidth: 1,
      },
    ],
  }
})

const chartOptions = computed<ChartOptions<'bar'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: '#94a3b8',
        font: { size: 11, family: 'monospace' },
        padding: 12,
      },
    },
    tooltip: {
      backgroundColor: '#16213e',
      borderColor: '#2a2a4a',
      borderWidth: 1,
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
      callbacks: {
        title: (items) => `Price: ${items[0].label}`,
        label: (item) => `Cumulative Qty: ${Number(item.raw).toLocaleString()}`,
      },
    },
  },
  scales: {
    x: {
      stacked: false,
      ticks: {
        color: '#475569',
        font: { size: 9, family: 'monospace' },
        maxTicksLimit: 10,
      },
      grid: { color: '#1a1a2e' },
    },
    y: {
      ticks: {
        color: '#475569',
        font: { size: 10 },
        callback: (value) => Number(value).toLocaleString(),
      },
      grid: { color: '#2a2a4a' },
    },
  },
}))

const spread = computed(() => {
  if (!props.bids.length || !props.asks.length) return null
  const bestBid = Math.max(...props.bids.map((b) => b.price))
  const bestAsk = Math.min(...props.asks.map((a) => a.price))
  return {
    bestBid,
    bestAsk,
    spread: bestAsk - bestBid,
    spreadPct: ((bestAsk - bestBid) / bestBid) * 100,
  }
})
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- Spread info -->
    <div v-if="spread" class="flex items-center gap-4 text-xs font-mono">
      <div class="flex items-center gap-1.5">
        <span class="text-green-400 font-bold">BID {{ spread.bestBid.toFixed(4) }}</span>
      </div>
      <div class="flex items-center gap-1.5 text-qtown-text-dim">
        <span>SPREAD</span>
        <span class="text-qtown-gold">{{ spread.spread.toFixed(4) }}</span>
        <span class="text-qtown-text-dim">({{ spread.spreadPct.toFixed(2) }}%)</span>
      </div>
      <div class="flex items-center gap-1.5">
        <span class="text-red-400 font-bold">ASK {{ spread.bestAsk.toFixed(4) }}</span>
      </div>
      <div v-if="lastPrice" class="flex items-center gap-1.5 ml-auto">
        <span class="text-qtown-text-dim">LAST</span>
        <span class="text-qtown-text-primary font-bold">{{ lastPrice.toFixed(4) }}</span>
      </div>
    </div>

    <!-- Chart -->
    <div class="relative" style="height: 280px">
      <div
        v-if="loading"
        class="absolute inset-0 flex items-center justify-center bg-qtown-card/80 rounded z-10"
      >
        <div class="flex gap-1">
          <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 0ms" />
          <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 150ms" />
          <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 300ms" />
        </div>
      </div>

      <div
        v-if="!loading && (!bids.length && !asks.length)"
        class="absolute inset-0 flex items-center justify-center text-qtown-text-dim"
      >
        No order book data available
      </div>

      <Bar
        v-else-if="!loading"
        :data="chartData"
        :options="chartOptions"
      />
    </div>
  </div>
</template>
