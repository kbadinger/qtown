# Fire-Off Runbook — Qtown v2

> The operational "go" doc. The plan pack (`00`–`05`) is the *what*; this is the *how
> and in what order*, wired to the materialized stories in `ralph/worklist.json`.
> Written 2026-06-12.

## Operating model (decided)

| Role | Who | Does |
|---|---|---|
| **Planner + janitor** | **Opus, in-session** | Authors well-structured stories (done — this pack), runs `grade:opus` stories directly, and runs periodic **cleanup passes**: stop Ralph, fix/restructure what it produced, resume. |
| **Bulk executor** | **Ralph** (local Ollama loop) | Churns `grade:ralph` stories autonomously between cleanup passes. |
| **GPU operator** | **Kevin** | Runs the asset batch on the 3090 box (`track:kevin-gpu`), QA-passes style. |

**No Opus path is added to the orchestrator.** Opus operates at the session level. Every
story carries a `grade:*` label so a cleanup pass knows what to scrutinize hard
(`grade:opus` = a local model probably got it subtly wrong).

### The cadence
```
Opus authors/grades stories ──► Ralph loop runs grade:ralph work ──► STOP
        ▲                                                              │
        └──────── Opus cleanup session: fix, restructure, ────────────┘
                  run grade:opus stories, re-grade, resume
```

## The backlog, materialized (113 pending stories)

| Phase | Stories | Opus / Ralph | Gate | Lane |
|---|---|---|---|---|
| **6 — WIRE IT** | 26 | 13 / 13 | **A** (3/3 e2e green) | critical path |
| **6.5 — PROVE IT** | 17 | 10 / 7 | **B** (measured numbers, CI gates) | after/with 6 |
| **7-A — ASSETS** | 6 | 4 / 2 | **C** (library QA'd) | **∥ now, 3090 box** |
| **7-B — ROOMS** | 31 | 10 / 21 | **D** (5 flagship rooms live) | after Gate A |
| **7.5 — DOCUMENT** | 23 | 16 / 7 | — | after the proofs land |
| **8 — 2026 GAP** | 10 | 8 / 2 | — | mostly independent |

Stories live in `ralph/worklist.json` with `description`, machine-checkable
`acceptance_criteria`, `deps`, and labels (`grade:*`, `gate:*`, `track:kevin-gpu`,
`voice-pass`, `proto`). Regenerate/re-grade idempotently via
`python3 ralph/build_v2_backlog.py`.

## Hard sequencing rules (from the audit + master plan)

1. **Phase 6 closes before Phase 7-B opens.** Rooms on broken plumbing = debugging two
   problems at once. (7-A assets are exempt — different machine, zero Phase-6 dependency.)
2. **No claim ships before its proof.** README/landing stay at the "in flight" wording
   (Plan 03 §8) until the gate that proves them is green.
3. **No room fakes its feed.** Unwired room ships in labeled *dormant* mode, never with
   fabricated activity (CLAUDE.md rule 10).

## What to fire off — in order

### Lane 1 — Assets (start TODAY, parallel, no blockers)
`track:kevin-gpu` work, gated by 3 Opus-authored pipeline stories:
1. **Opus:** `P7A-001` (ComfyUI workflow JSONs) → `P7A-002` (interior_cast + extras) →
   `P7A-003` (finish `run_batch.py`).
2. **Kevin (3090):** `run_batch.py --mode test --limit 10` → review contact sheet →
   tune → **flagship-first production (~70 assets)** → full batch.
3. **Ralph/Opus:** `P7A-004` post-process, `P7A-005` manifest emitter; `P7A-006` LoRA A/B.
   → **Gate C.** Full ledger in `ASSET-INVENTORY.md`.

### Lane 2 — Wire it (the critical path)
The 26 P6 stories have been pending since May 5. Decide the executor and **start the loop**:
1. **Ralph loop** runs the `grade:ralph` P6 stories (proto codegen, endpoint wiring, Kafka
   producers/consumers).
2. **Opus** runs the `grade:opus` P6 stories (gRPC server architecture P6-001/004,
   unsafe-confinement P6-003, the 3 e2e flow investigations P6-022/023/024).
3. Land **`P6.5-017`** (e2e as required CI gate) → **Gate A**. Until then the README
   architecture diagram stays marked live-vs-stubbed.

### Lane 3 — Prove it (with/after Lane 2)
Opus-heavy: `P6.5-001..004` perf report, `P6.5-008..010` OTel ×3, `P6.5-013..016` CI
supply-chain gates, `P6.5-005..007` health model. → **Gate B.**

### Lane 4 — Rooms (after Gate A; needs Lane 1 flagship assets)
`P7-001..017` (sim room model → gateway → dashboard primitives → flagship five → e2e),
then `P7-018..031` second ring. → **Gate D.**

### Lane 5 — Document (after the proofs exist) & Lane 6 — 2026 gap
`P7.5-*` (ADRs/agent-ops/SECURITY/postmortem are `voice-pass` — Opus drafts, Kevin edits).
`P8-001..004` Tier-1 (MCP, evals-in-CI, gateway hardening, structured outputs) are
interview-critical and mostly independent — start any time capacity exists.

## Definition of done for v2 (from the master plan)
Wired (3/3 e2e green in CI) · Proven (measured perf, truthful STATE.md) · Visible (≥5
flagship rooms live with real data + proof panels) · Documented (STATE.md, 10 ADRs,
agent-ops, SECURITY, postmortem, READMEs, room docs) · 2026-complete (MCP, evals,
structured outputs, guardrails, gateway hardening) · Deployed (min subset at qtown.ai).

## First three commands
```bash
# 1. See the whole backlog and what's ready to start right now
python3 -c "import sys;sys.path.insert(0,'ralph');from v2_worklist import Worklist as W; \
  w=W('ralph/worklist.json'); print(len(w.next_available(w.completed_ids())),'ready')"

# 2. Asset lane (Opus authors P7A-001..003, then on the 3090 box):
#    python3 asset-gen/run_batch.py --mode test --limit 10

# 3. Wire lane: start Ralph on grade:ralph P6 work, Opus takes grade:opus P6 stories.
```
