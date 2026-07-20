# ADR 0002 — Academy: self-referential RAG, grounded answering, recall@k gate

- **Status:** Accepted (2026-07-16)
- **Area / service:** Academy → `services/academy` (Python)
- **Related:** FABLE-PLAN Wave 1B (W1-A0…A6); ADR-0001; `docs/v2-audit.md`

## Context

The Academy area is qtown v2's **retrieval-augmented-generation proof**. It needs
to demonstrate, for real: a document corpus embedded into a vector store, semantic
retrieval, and a model that answers **only** from what it retrieved and cites its
sources — end-to-end, with a retrieval-quality gate in CI, and without fabricating
data. The corpus is deliberately qtown's own documentation, so the town can answer
questions about itself and the answers can be checked against docs that live in the
same repo.

## Decision

1. **Self-referential docs corpus, heading-chunked.** The corpus is qtown's own
   markdown — `CLAUDE.md`, `AGENTS.md`, `docs/REQUIREMENTS.md`, the ADRs, the perf
   report, the area/fable plans, and each `services/*/README.md`
   (`corpus.py:CORPUS_GLOBS`). Files are split on h1/h2 boundaries into
   ≤1200-char chunks so a chunk is a coherent section, and each carries its source
   path + heading as metadata (used later for citations).

2. **`nomic-embed-text` (768-dim) into a pgvector table.** Chunks are embedded via
   Ollama and upserted into `academy.embeddings` (id, doc_type, doc_id UNIQUE,
   content, `embedding vector(768)`, metadata JSONB), created in
   `infra/init-db.sql`. Upsert is keyed on `doc_id`, so re-ingest is idempotent.

3. **Retrieve = cosine ANN, then rerank.** A question is embedded with the same
   model and matched by cosine similarity in pgvector; the hits are reranked
   (cross-encoder when the model is available, **BM25 fallback** otherwise) down to
   the top `k=5`. The fallback means retrieval degrades rather than hard-fails when
   an optional model isn't pulled.

4. **Grounded answering with structured output, or abstain.** The `k` passages are
   injected as *numbered* sources; the model is instructed to answer only from them
   and cite the numbers it used. The response is parsed as JSON and validated with
   Pydantic (one retry on invalid output). Citations are mapped back to real source
   ids — a citation can't point at a source that wasn't retrieved. If retrieval is
   empty, or the model returns nothing valid, the service returns an honest
   "I don't have that" with `grounded:false` — **it never invents a fact**
   (REQUIREMENTS §2 principle 1).

5. **A blocking recall@k gate + a local faithfulness report.** Retrieval quality is
   a deterministic **recall@k** over a *committed embedding fixture*
   (`evals/fixture.npz`, built locally with the embed model): pure-numpy cosine, no
   model or DB at run time, so it is reproducible in CI. The blocking `eval-academy`
   job fails the build if mean recall@5 drops below the threshold in
   `evals/golden.json` (0.75; currently 0.893). Generation *faithfulness* is a
   separate concern — LLM-judged over the same golden set, run locally and committed
   dated to `docs/evals/academy-rag-eval.md`, the same honesty pattern as the market
   perf report (measured, not gated).

## Consequences

- **Positive:** answers are grounded in real docs and cite them; the model abstains
  instead of guessing; retrieval quality is guarded by a fast, deterministic CI gate
  that needs no GPU; the proof panel shows a real answer or an honest dormant state;
  the corpus being the repo's own docs means the eval's ground truth is checkable.
- **Negative / deferred:**
  - **Table-embedded facts retrieve poorly.** The golden `validation-citadel`
    question (whose answer lives in a markdown *table* in `CLAUDE.md`) is a recall
    miss — a big table embeds as one lump and doesn't match a specific query. It is
    left *in* the golden set on purpose so the gate reports the weakness honestly
    rather than hiding it; table-aware chunking is a tracked follow-on.
  - **Cold-start latency.** The first generation after the model loads is ~45 s;
    warm answers are ~7–9 s. The dashboard BFF allows 60 s and shows a spinner. Not
    a throughput claim — no latency SLO is asserted.
  - **Single-model LLM judge.** Faithfulness uses one judge model (`qwen3.5:9b`); it
    is an LLM judgment, not ground truth, and is reported as a dated snapshot, never
    as a gate.
  - **Committed fixture can drift from the live corpus.** The recall gate tests the
    fixture, not the current docs; the fixture must be rebuilt
    (`evals/build_fixture.py`) when the corpus changes materially, or the gate
    guards a stale snapshot.

## Alternatives considered

- **Recall@k in CI against live Ollama/pgvector** — rejected: CI would need a GPU
  and a populated database, and embeddings could shift under it. Committing the
  fixture makes the gate deterministic and model-free; freshness is handled by
  rebuilding on corpus change.
- **Gate on generation faithfulness too** — rejected for now: it needs live models
  and is non-deterministic (temperature > 0), so it can't be a stable blocking
  check. It ships as a committed measurement instead, like the perf report.
- **Regex-scraped citations** — rejected: structured output + validation makes a
  citation a real, checked source id rather than a substring guess.
