// useAcademyRag — reactive client for the Academy RAG proof panel.
//
// Polls /api/academy/rag-status for corpus size + availability, and runs grounded
// questions through /api/academy/ask. Every failure resolves to a dormant/empty
// shape — never a fabricated answer or count (REQUIREMENTS §2 principle 1).

export interface RagStatus {
  available: boolean
  chunks: number
  sources: number
}
export interface RagCitation {
  n: number
  source: string
  heading: string
  snippet: string
  score: number
}
export interface RagAnswer {
  question: string
  answer: string
  grounded: boolean
  model: string
  retrieved: number
  latencyMs: number
  citations: RagCitation[]
  unavailable: boolean
}

// Committed eval numbers. recall@k is CI-GATED (the blocking `eval-academy` job
// asserts it over a committed embedding fixture — deterministic, no model), so it
// is a proven figure. The faithfulness row is a dated LOCAL snapshot
// (docs/evals/academy-rag-eval.md), shown with provenance so it can't read as a
// gate or a fabricated live gauge.
export const ACADEMY_EVAL = {
  measuredOn: '2026-07-16',
  recallK: 5,
  recallAt5: 0.893,
  recallThreshold: 0.75,
  goldenQuestions: 14,
  groundedRate: 1.0,
  keywordCorrectness: 0.79,
  judgeFaithfulness: 1.0,
  embedModel: 'nomic-embed-text',
  answerModel: 'qwen3.5:4b',
  judgeModel: 'qwen3.5:9b',
  recallProvenance: 'CI-gated: eval-academy asserts recall@5 ≥ 0.75 over a committed fixture',
  faithProvenance: 'local snapshot — not a CI gate',
} as const

// Drawn from the golden eval set (services/academy/evals/golden.json) so the demo
// exercises questions the corpus can actually answer.
export const SAMPLE_QUESTIONS = [
  'What delivery guarantee does market trade settlement provide, and how are duplicate settlements handled?',
  'What are the three inviolable principles?',
  'How is the market order book matching implemented and what priority does it use?',
  'What is the current status of cartographer’s gRPC federation to backend services?',
  'Should new features be built in the v1 monolith?',
] as const

export function useAcademyRag() {
  const status = ref<RagStatus | null>(null)
  const statusPending = ref(true)
  const answer = ref<RagAnswer | null>(null)
  const asking = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null

  async function refreshStatus(): Promise<void> {
    try {
      status.value = await $fetch<RagStatus>('/api/academy/rag-status')
    } catch {
      status.value = { available: false, chunks: 0, sources: 0 }
    } finally {
      statusPending.value = false
    }
  }

  function startStatus(intervalMs = 8000): void {
    void refreshStatus()
    if (import.meta.client) {
      timer = setInterval(() => void refreshStatus(), intervalMs)
    }
  }

  function stopStatus(): void {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  async function ask(question: string): Promise<void> {
    const q = question.trim()
    if (!q || asking.value) return
    asking.value = true
    try {
      answer.value = await $fetch<RagAnswer>('/api/academy/ask', {
        method: 'POST',
        body: { question: q },
      })
    } catch {
      answer.value = {
        question: q,
        answer: '',
        grounded: false,
        model: '',
        retrieved: 0,
        latencyMs: 0,
        citations: [],
        unavailable: true,
      }
    } finally {
      asking.value = false
    }
  }

  const live = computed(() => status.value?.available ?? false)

  return { status, statusPending, answer, asking, live, startStatus, stopStatus, refreshStatus, ask }
}
