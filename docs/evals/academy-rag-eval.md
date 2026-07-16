# Academy RAG — faithfulness eval

**Measured locally, not a CI gate.** The deterministic retrieval gate is
`evals/recall.py` (recall@k over a committed fixture, blocking in CI). This
report measures *generation* quality of the grounded answerer over the golden
set — it needs live Ollama + pgvector, so it is run by hand and committed dated,
the same honesty pattern as the M7 perf report. Generation runs at temperature
0.2, so this is a point-in-time snapshot, not a fixed number.

| | |
|---|---|
| Date | 2026-07-16 |
| Answer model | `qwen3.5:4b` |
| Judge model | `qwen3.5:9b` |
| Golden questions | 14 |
| Grounded (answer cited real retrieved sources) | 100% |
| Keyword correctness (conservative substring) | 79% |
| Judge faithfulness — mean score | 1.00 |
| Judge faithfulness — faithful rate | 100% |
| Mean answer latency | 2037 ms |

## What each metric means (and its limits)

- **Grounded** — the answerer emitted at least one citation to a real retrieved
  passage. An answer that can't be grounded is returned as an honest "I don't
  have that" (grounded=no), never a fabricated fact (principle #1).
- **Keyword correctness** — a *conservative* check: does the answer contain every
  expected substring? It under-counts, e.g. an answer that says "retrieval-
  augmented generation" fails the literal `RAG` check while still being correct.
- **Judge faithfulness** — an independent judge model scores whether every claim
  in the answer is supported by the passages the generator was shown (all k, full
  text — not the truncated UI snippet). It is an LLM judgment, not ground truth.

## Per-question

| Question | grounded | keywords | faithful | score | note |
|---|---|---|---|---|---|
| settlement-guarantee | yes | 1/2 | yes | 1.00 |  |
| settlement-key | yes | 2/2 | yes | 1.00 |  |
| single-sided | yes | 2/2 | yes | 1.00 |  |
| matching-engine | yes | 1/1 | yes | 1.00 |  |
| three-principles | yes | 2/2 | yes | 1.00 |  |
| dod-dimensions | yes | 2/2 | yes | 1.00 |  |
| placement-p99 | yes | 2/2 | yes | 1.00 |  |
| tail-cause | yes | 2/2 | yes | 1.00 |  |
| validation-citadel | yes | 1/1 | yes | 1.00 |  |
| v1-archived | yes | 1/1 | yes | 1.00 |  |
| cartographer-status | yes | 1/1 | yes | 1.00 |  |
| academy-teaches | yes | 0/1 | yes | 1.00 |  |
| market-grpc-surface | yes | 0/1 | yes | 1.00 |  |
| dormant-mode | yes | 1/1 | yes | 1.00 |  |

Reproduce: `cd services/academy && python -m evals.faithfulness` (regenerate the retrieval fixture first with `python -m evals.build_fixture`).
