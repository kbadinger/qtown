<script setup lang="ts">
// Compact Academy proof summary for the landing grid: live status + corpus size
// (real, or —) and the CI-gated recall@5. Links to the full RAG proof panel on
// /academy.
import { ACADEMY_EVAL, useAcademyRag } from '~/composables/useAcademyRag'

const { status, statusPending, live, startStatus, stopStatus } = useAcademyRag()

onMounted(() => startStatus(8000))
onUnmounted(() => stopStatus())

const chunks = computed(() => status.value?.chunks ?? 0)
const recallPct = `${Math.round(ACADEMY_EVAL.recallAt5 * 100)}%`
</script>

<template>
  <NuxtLink to="/academy" class="qtown-card block hover:border-qtown-gold/40 transition-colors">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <span class="text-sm font-bold text-qtown-text-primary">Academy</span>
        <ProofBadge :live="live" />
      </div>
      <span class="text-xs text-qtown-text-dim">RAG →</span>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div>
        <div class="stat-number text-xl">
          {{ chunks > 0 ? chunks.toLocaleString() : (statusPending ? '·' : '—') }}
        </div>
        <div class="section-title mt-0.5">corpus chunks</div>
      </div>
      <div>
        <div class="stat-number text-xl text-qtown-text-primary">{{ recallPct }}</div>
        <div class="section-title mt-0.5">recall@{{ ACADEMY_EVAL.recallK }}</div>
      </div>
    </div>

    <div class="mt-3 pt-2 border-t border-qtown-border text-xs text-qtown-text-dim">
      grounded + cited <span class="mx-1">·</span> gate ≥ {{ Math.round(ACADEMY_EVAL.recallThreshold * 100) }}%
    </div>
  </NuxtLink>
</template>
