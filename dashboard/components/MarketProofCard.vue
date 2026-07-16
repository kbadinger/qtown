<script setup lang="ts">
// Compact Market proof summary for the landing grid: live status + mid/spread
// (real, or —) and the measured placement p99 (committed). Links to the full
// proof panel on /market.
import { MARKET_PERF, useMarketProof } from '~/composables/useMarketProof'

const { data, pending, start, stop } = useMarketProof('gold')

onMounted(() => start(5000))
onUnmounted(() => stop())

const live = computed(() => data.value?.live ?? false)
const mid = computed(() => data.value?.book.mid ?? null)
const spread = computed(() => data.value?.book.spread ?? null)

const placementP99 = `${MARKET_PERF.placementP99Ms} ms`
</script>

<template>
  <NuxtLink to="/market" class="qtown-card block hover:border-qtown-gold/40 transition-colors">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <span class="text-sm font-bold text-qtown-text-primary">Market</span>
        <ProofBadge :live="live" />
      </div>
      <span class="text-xs text-qtown-text-dim">gold →</span>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div>
        <div class="stat-number text-xl">
          {{ mid !== null ? mid.toFixed(2) : (pending ? '·' : '—') }}
        </div>
        <div class="section-title mt-0.5">mid price</div>
      </div>
      <div>
        <div class="stat-number text-xl text-qtown-text-primary">{{ placementP99 }}</div>
        <div class="section-title mt-0.5">placement p99</div>
      </div>
    </div>

    <div class="mt-3 pt-2 border-t border-qtown-border text-xs text-qtown-text-dim">
      spread <span class="text-qtown-text-secondary font-mono">{{ spread !== null ? spread.toFixed(2) : '—' }}</span>
      <span class="mx-1">·</span> measured {{ MARKET_PERF.measuredOn }}
    </div>
  </NuxtLink>
</template>
