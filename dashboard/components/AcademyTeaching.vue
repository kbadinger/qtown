<script setup lang="ts">
// Academy teaching layer (DoD "Explained"): how the RAG actually works, tied to
// the real code. Copy is accurate to the implementation — retrieve, ground, cite,
// abstain when unsupported — with no aspirational claims. Native <details> for
// accessible, JS-free disclosure.

interface Explainer {
  q: string
  body: string
  ref: string
}

const flow = [
  { label: 'question', sub: 'text' },
  { label: 'embed', sub: 'nomic 768d' },
  { label: 'pgvector', sub: 'cosine ANN' },
  { label: 'rerank', sub: 'top-k' },
  { label: 'ground + cite', sub: 'qwen3.5:4b' },
]

const explainers: Explainer[] = [
  {
    q: 'Corpus & chunking',
    body:
      'The corpus is qtown’s own docs — CLAUDE.md, REQUIREMENTS, the ADRs, the perf ' +
      'report, service READMEs. Each file is split on h1/h2 headings into ≤1200-char ' +
      'chunks, embedded with nomic-embed-text (768-dim), and stored in the ' +
      'academy.embeddings pgvector table. Self-referential RAG: the town answers ' +
      'questions about itself.',
    ref: 'services/academy/academy/rag/corpus.py · embeddings.py',
  },
  {
    q: 'Retrieval — cosine ANN, then rerank',
    body:
      'A question is embedded with the same model and matched against the corpus by ' +
      'cosine similarity in pgvector (CAST(:vec AS vector)). The top hits are reranked ' +
      'before the best k=5 go to the generator; when the cross-encoder model isn’t ' +
      'available it falls back to BM25 cleanly, so retrieval never hard-fails.',
    ref: 'services/academy/academy/rag/retriever.py',
  },
  {
    q: 'Grounded generation — cite or abstain',
    body:
      'The k passages are injected as numbered sources and the model is told to answer ' +
      'ONLY from them and cite what it used. Output is structured (Ollama format=json + ' +
      'Pydantic validation with one retry), so a citation is a real source id, not a ' +
      'guess. If the sources don’t contain the answer — or the model returns nothing ' +
      'valid — it says so (grounded=false); it never fabricates a fact (principle #1).',
    ref: 'services/academy/academy/rag/answer.py',
  },
  {
    q: 'How it’s proven — recall@k gate + faithfulness',
    body:
      'Retrieval quality is a deterministic recall@k over a committed embedding fixture ' +
      '(pure numpy, no model), asserted in CI by the blocking eval-academy job — it ' +
      'fails the build if mean recall@5 drops below 0.75 (currently 0.893). Generation ' +
      'faithfulness is LLM-judged locally over the golden set and committed dated, the ' +
      'same honesty pattern as the market perf report — measured, not a gate.',
    ref: 'services/academy/evals/recall.py · docs/evals/academy-rag-eval.md',
  },
]
</script>

<template>
  <div class="qtown-card">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-base font-bold text-qtown-text-primary">How this works</h2>
      <span class="section-title">Teaching</span>
    </div>

    <!-- Flow strip: the path a question actually takes -->
    <div class="flex items-stretch gap-1.5 overflow-x-auto pb-1 mb-5">
      <template v-for="(step, i) in flow" :key="step.label">
        <div class="flex-shrink-0 rounded border border-qtown-border bg-qtown-surface px-2.5 py-1.5 text-center min-w-[92px]">
          <div class="text-xs font-mono font-semibold text-qtown-text-primary">{{ step.label }}</div>
          <div class="text-[10px] text-qtown-text-dim uppercase tracking-wide mt-0.5">{{ step.sub }}</div>
        </div>
        <div v-if="i < flow.length - 1" class="flex items-center text-qtown-gold text-sm font-mono" aria-hidden="true">→</div>
      </template>
    </div>

    <!-- Explainers -->
    <div class="space-y-2">
      <details
        v-for="ex in explainers"
        :key="ex.q"
        class="group rounded border border-qtown-border bg-qtown-surface/40 open:bg-qtown-surface/70"
      >
        <summary
          class="flex items-center justify-between gap-2 cursor-pointer list-none px-3 py-2.5 text-sm font-medium text-qtown-text-primary hover:text-qtown-gold"
        >
          <span>{{ ex.q }}</span>
          <span class="text-qtown-text-dim text-xs transition-transform group-open:rotate-90" aria-hidden="true">▸</span>
        </summary>
        <div class="px-3 pb-3 -mt-0.5">
          <p class="text-sm text-qtown-text-secondary leading-relaxed">{{ ex.body }}</p>
          <p class="mt-2 text-xs font-mono text-qtown-text-dim">{{ ex.ref }}</p>
        </div>
      </details>
    </div>

    <p class="mt-4 text-xs text-qtown-text-dim">
      The retrieval claim is behind a green CI gate (<span class="font-mono">eval-academy</span>,
      <span class="font-mono">test-academy</span>); faithfulness is a committed dated measurement —
      see the service README and docs/evals/academy-rag-eval.md.
    </p>
  </div>
</template>
