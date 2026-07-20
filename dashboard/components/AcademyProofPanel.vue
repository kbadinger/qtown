<script setup lang="ts">
// Academy RAG proof panel — the "grounded generation proof" made visible.
//
// Ask a question → academy retrieves top-k passages from the qtown-docs corpus,
// answers ONLY from them, and cites each source (via the /api/academy/ask BFF).
// The eval tiles show committed numbers: recall@k is CI-gated (eval-academy);
// faithfulness is a dated local snapshot. If academy is unreachable the panel is
// honestly dormant — no fabricated answer, no fabricated count.
import { ACADEMY_EVAL, SAMPLE_QUESTIONS, useAcademyRag } from '~/composables/useAcademyRag'

const { status, statusPending, answer, asking, live, startStatus, stopStatus, ask } = useAcademyRag()

const question = ref<string>(SAMPLE_QUESTIONS[0])

onMounted(() => startStatus(8000))
onUnmounted(() => stop())

function stop(): void {
  stopStatus()
}

function submit(): void {
  void ask(question.value)
}
function pick(q: string): void {
  question.value = q
  void ask(q)
}

const chunks = computed(() => status.value?.chunks ?? 0)
const sources = computed(() => status.value?.sources ?? 0)

const recallPct = `${Math.round(ACADEMY_EVAL.recallAt5 * 100)}%`
const thresholdPct = `${Math.round(ACADEMY_EVAL.recallThreshold * 100)}%`
const groundedPct = `${Math.round(ACADEMY_EVAL.groundedRate * 100)}%`
const keywordPct = `${Math.round(ACADEMY_EVAL.keywordCorrectness * 100)}%`
const judge = ACADEMY_EVAL.judgeFaithfulness.toFixed(2)

function fmtScore(n: number): string {
  return n.toFixed(2)
}
</script>

<template>
  <div class="qtown-card">
    <!-- Header -->
    <div class="flex items-start justify-between flex-wrap gap-3 mb-4">
      <div>
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-bold text-qtown-text-primary">Academy</h2>
          <ProofBadge :live="live" />
        </div>
        <p class="section-title mt-1">Grounded RAG proof</p>
      </div>
      <div class="text-right text-xs text-qtown-text-dim">
        <div>
          corpus
          <span class="font-mono text-qtown-text-secondary">
            {{ chunks > 0 ? `${chunks} chunks` : (statusPending ? '·' : '—') }}
          </span>
        </div>
        <div v-if="sources > 0" class="font-mono">{{ sources }} docs · {{ ACADEMY_EVAL.embedModel }}</div>
      </div>
    </div>

    <!-- Ask box -->
    <div class="flex items-stretch gap-2">
      <input
        v-model="question"
        type="text"
        class="qtown-input flex-1 text-sm"
        placeholder="Ask about qtown's architecture…"
        :disabled="asking"
        @keydown.enter="submit"
      >
      <button
        class="qtown-btn-primary text-sm px-4 whitespace-nowrap disabled:opacity-50"
        :disabled="asking || !question.trim()"
        @click="submit"
      >
        {{ asking ? 'Asking…' : 'Ask' }}
      </button>
    </div>

    <!-- Sample questions -->
    <div class="flex flex-wrap gap-1.5 mt-2">
      <button
        v-for="q in SAMPLE_QUESTIONS"
        :key="q"
        class="text-[11px] px-2 py-1 rounded border border-qtown-border text-qtown-text-dim hover:text-qtown-gold hover:border-qtown-gold/40 transition-colors truncate max-w-[220px]"
        :disabled="asking"
        :title="q"
        @click="pick(q)"
      >
        {{ q }}
      </button>
    </div>

    <!-- Answer -->
    <div class="mt-4 min-h-[96px]">
      <!-- Asking -->
      <div v-if="asking" class="py-8 text-center text-qtown-text-dim text-sm">
        <div class="inline-flex items-center gap-2">
          <span class="w-1.5 h-1.5 rounded-full bg-qtown-gold animate-bounce" />
          retrieving + generating…
        </div>
      </div>

      <!-- Backend unavailable — honest dormant, no fabricated answer -->
      <div
        v-else-if="answer?.unavailable"
        class="py-8 text-center text-qtown-text-dim text-sm"
      >
        RAG backend unavailable — <span class="font-mono">—</span>
      </div>

      <!-- Grounded answer -->
      <div v-else-if="answer && answer.grounded">
        <p class="text-sm text-qtown-text-primary leading-relaxed whitespace-pre-line">{{ answer.answer }}</p>

        <div class="mt-3 space-y-1.5">
          <div class="section-title">Citations</div>
          <div
            v-for="c in answer.citations"
            :key="c.n"
            class="flex items-start gap-2 text-xs"
          >
            <span class="mt-0.5 flex-shrink-0 w-5 h-5 rounded bg-qtown-gold/10 text-qtown-gold font-mono font-semibold flex items-center justify-center">
              {{ c.n }}
            </span>
            <div class="min-w-0">
              <div class="font-mono text-qtown-text-secondary truncate">
                {{ c.source }}<span v-if="c.heading" class="text-qtown-text-dim"> · {{ c.heading }}</span>
                <span class="text-qtown-text-dim"> · {{ fmtScore(c.score) }}</span>
              </div>
              <div class="text-qtown-text-dim truncate">{{ c.snippet }}</div>
            </div>
          </div>
        </div>

        <div class="mt-3 text-[11px] text-qtown-text-dim font-mono">
          {{ answer.model }} · {{ answer.retrieved }} retrieved · {{ Math.round(answer.latencyMs) }} ms
        </div>
      </div>

      <!-- Answered but not grounded — the answerer's honest "I don't have that" -->
      <div v-else-if="answer" class="py-6 text-center text-qtown-text-secondary text-sm">
        {{ answer.answer || 'No grounded answer from the retrieved sources.' }}
      </div>

      <!-- Idle -->
      <div v-else class="py-8 text-center text-qtown-text-dim text-sm">
        Ask a question to see a grounded, cited answer.
      </div>
    </div>

    <!-- Eval tiles (committed) -->
    <div class="mt-4 pt-4 border-t border-qtown-border">
      <div class="flex items-center justify-between mb-2">
        <span class="section-title">Evaluated</span>
        <span class="text-xs text-qtown-text-dim">{{ ACADEMY_EVAL.goldenQuestions }}-question golden set · {{ ACADEMY_EVAL.measuredOn }}</span>
      </div>
      <div class="grid grid-cols-3 gap-3 text-center">
        <div>
          <div class="stat-number text-xl">{{ recallPct }}</div>
          <div class="section-title mt-0.5">recall@{{ ACADEMY_EVAL.recallK }}</div>
          <div class="text-xs text-green-400 mt-0.5">gate ≥ {{ thresholdPct }}</div>
        </div>
        <div>
          <div class="stat-number text-xl">{{ judge }}</div>
          <div class="section-title mt-0.5">faithfulness</div>
          <div class="text-xs text-qtown-text-dim mt-0.5">grounded {{ groundedPct }}</div>
        </div>
        <div>
          <div class="stat-number text-xl">{{ keywordPct }}</div>
          <div class="section-title mt-0.5">keyword</div>
          <div class="text-xs text-qtown-text-dim mt-0.5">conservative</div>
        </div>
      </div>
      <p class="text-xs text-qtown-text-dim mt-2 italic">
        recall@k — {{ ACADEMY_EVAL.recallProvenance }}. faithfulness — {{ ACADEMY_EVAL.faithProvenance }}.
      </p>
    </div>

    <!-- What it proves -->
    <div class="mt-3 pt-3 border-t border-qtown-border text-xs text-qtown-text-secondary">
      <span class="section-title">Proves</span>
      <span class="ml-2">vector retrieval over real docs · answers only from cited sources · no-fabrication on empty retrieval</span>
    </div>
  </div>
</template>
