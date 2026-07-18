# academy

The **Academy** area's backing service — a Python (FastAPI + gRPC) service that
does model routing/analytics for the town **and** hosts qtown v2's **RAG proof**:
grounded, cited question-answering over the project's own documentation, with a
retrieval-quality gate in CI.

## What it does

- **Ingests** qtown's docs corpus — `CLAUDE.md`, `AGENTS.md`, the requirements,
  the ADRs, the perf report, the area/fable plans, and each service README — by
  splitting them on h1/h2 headings into ≤1200-char chunks, embedding each with
  `nomic-embed-text` (768-dim), and upserting into the `academy.embeddings`
  pgvector table (`academy/rag/corpus.py`, `embeddings.py`).
- **Retrieves** by embedding the question and taking the cosine-nearest chunks in
  pgvector, then reranking (cross-encoder when available, clean BM25 fallback)
  down to the top `k` (`academy/rag/retriever.py`).
- **Answers, grounded** — injects the `k` passages as numbered sources and has the
  model answer **only** from them, citing what it used. Output is structured
  (Ollama `format=json` + Pydantic validation, one retry). If the sources don't
  support an answer, it says so — it never fabricates (`academy/rag/answer.py`).
- Also serves the existing model-routing metrics + generation endpoints used by
  the rest of the town (dialogue, newspaper).

## Contract

- **HTTP (:8001)**
  - `POST /rag/ask` — `{ "question": str, "k"?: int }` → grounded answer:
    `{ question, answer, grounded, model, retrieved, latency_ms, citations[] }`,
    each citation `{ n, doc_id, source, heading, snippet, score }`. Empty
    question → `400`; backend failure → `503` (never a fabricated answer).
  - `GET /rag/status` → `{ available, chunks, sources }` (dormant-safe: returns
    `available:false` if the vector store is unreachable, never an error).
  - `GET /metrics/models`, `POST /generate/dialogue`, `POST /generate/newspaper`, …
- **gRPC (:50053)** — dialogue generation (`academy/grpc_server.py`).
- **Kafka** — consumer for town events (`academy/kafka_consumer.py`).
- **Store** — `academy.embeddings` (pgvector, 768-dim), created in
  `infra/init-db.sql`.

## Run

```bash
cd services/academy
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"

# 1. ingest the docs corpus into pgvector (needs Ollama + Postgres/pgvector)
DATABASE_URL=postgresql+asyncpg://qtown:qtown_dev@localhost:5432/qtown \
  .venv/Scripts/python -m academy.rag.corpus

# 2. run the HTTP API (KAFKA_ENABLED=false to skip the consumer)
KAFKA_ENABLED=false HTTP_PORT=8001 \
  DATABASE_URL=postgresql+asyncpg://qtown:qtown_dev@localhost:5432/qtown \
  .venv/Scripts/python -m academy.main

# 3. evals
.venv/Scripts/python -m evals.build_fixture   # rebuild committed fixture (needs Ollama)
.venv/Scripts/python -m evals.recall --assert  # recall@k gate (deterministic, no model)
.venv/Scripts/python -m evals.faithfulness     # local faithfulness report (needs Ollama + pg)
```

## Status (honest)

| Capability | State |
|---|---|
| Docs corpus → chunk → embed → pgvector | ✅ real — 11 docs chunked + embedded (`academy/rag/corpus.py`); live count via `/rag/status` |
| Vector retrieval (cosine ANN + rerank/BM25 fallback) | ✅ real (`academy/rag/retriever.py`) |
| Grounded, cited answering (structured output, abstains) | ✅ real (`academy/rag/answer.py`); `POST /rag/ask` verified live |
| Recall@k retrieval gate | ✅ **blocking CI job** `eval-academy` — recall@5 **0.893** ≥ 0.75 over a committed fixture, pure numpy, no model (`evals/recall.py`) |
| Dialogue grounding (NPCs reference real town events) | ✅ real — `GenerateDialogue` retrieves `doc_type='event'` rows (town-core emits them via `qtown.events.broadcast`) and injects them; `grounded_events` attribution rides the content event. Gated by a **separate** town-event recall@k (`eval-academy`, `evals/events_recall.py`); local demo in [`docs/evals/dialogue-grounding-demo.md`](../../docs/evals/dialogue-grounding-demo.md) |
| Unit tests (RAG answer mapping / abstain paths) | ✅ real, mocked (`tests/test_rag_answer.py`) in `test-academy` |
| Generation faithfulness | ✅ measured locally (LLM-judged, 100% grounded / judge 1.00 / 79% keyword) — a committed dated snapshot, **not** a gate ([`docs/evals/academy-rag-eval.md`](../../docs/evals/academy-rag-eval.md)) |
| Dashboard proof panel (ask + citations, dormant-safe) | ✅ real (W1-A4) — `AcademyProofPanel.vue` renders a live grounded answer or an honest dormant `—` |
| In-app teaching layer ("how RAG works") | ✅ real (W1-A5) — `AcademyTeaching.vue`, each step tied to the real module |
| Reranker cross-encoder model | ⏳ optional — falls back to BM25 cleanly when the model isn't pulled |
| Table-embedded facts (e.g. the area→service map) | ⚠️ known weak spot — surfaced honestly by the eval (`validation-citadel` recall miss) |

See `docs/adr/0002-academy-rag.md` for the design rationale, and
`docs/v2-audit.md` for the cross-service flow status.
