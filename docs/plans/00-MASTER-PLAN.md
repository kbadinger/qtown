---
review_key: claude-qtown-20260612-v2-build-plan-pack
notion_page_id: 37d7c992-27a0-812f-b326-e28d55a58387
notion_url: https://app.notion.com/p/37d7c99227a0812fb326e28d55a58387
review_status: Awaiting Review
created_by: claude
---

# Qtown v2 — Master Build Plan (Opus Handoff)

> **Status:** Plan pack v1, written 2026-06-12. Audience: a Claude Opus agent (or any
> capable coding agent) executing against this repo, plus Kevin reviewing.
> **Source inputs:** `docs/v2-audit.md` (honest gap report), `docs/v2-phase-7-rooms.md`
> (design seed), `asset-gen/style-spec.md` + `asset-gen/taxonomy.yaml` (locked art
> direction), `docs/2026-interview-gap-plan.md` (paper-signal priorities),
> `ralph/worklist.json` (220 stories: 194 complete, 26 P6 pending).

## The one-paragraph brief

Qtown v2 is a 9-service polyglot AI town simulation. v1 (live at v1.qtown.ai) proved an
autonomous agent could ship 550 stories; v2's job is to prove the *system* works — and to
make the AI visible. The product centerpiece is **drill-in interior rooms**: click a
building in the overhead town view and watch LLM-driven NPCs actually working inside it.
The engineering centerpiece is **proof**: every flow has an e2e test, every claim has a
measured number, every service shows it is alive.

## The unifying thesis: the town IS the architecture diagram

This is the idea that makes all five plan documents one product instead of five projects:

**Every building in Qtown maps to a real backing service or infrastructure component.
Every room renders real data from that component. Every room carries a "proof panel" —
an in-world holographic display showing live telemetry from the real system. The
documentation for each service is reachable from inside its room.**

A visitor who drills into the Market's trading floor sees NPCs haggling — driven by real
orders matched in the Go order book — and a holo-board showing live order-book depth and
the measured match latency. A visitor who climbs the Tower sees a real distributed trace
of one market trade fanning out across five services. The town stops being a skin over
the system and becomes the system's own living dashboard, demo, and documentation.

This thesis is what answers all three of Kevin's asks at once:
- **"Show they are working"** → rooms render real data + proof panels (Plan 03)
- **"Documentation to understand how they work"** → per-room docs + the docs pack (Plan 04)
- **"All the assets / the rooms"** → the manifest and room specs (Plans 01, 02)

## The plan pack

| Doc | Contents | Build phase |
|---|---|---|
| `00-MASTER-PLAN.md` | This file — thesis, sequencing, handoff format, gates | — |
| `01-ROOMS.md` | Building→service map, per-room spec (props, NPCs, data feeds, proof panel), sim-data model, drill-in UX, all 7 open design questions answered | Phase 7 |
| `02-ASSETS.md` | Complete asset manifest (counts, sizes, filenames), ComfyUI pipeline completion, QA bar | Phase 7-A (parallel) |
| `03-PROOF-OF-WORK.md` | E2E gates, load-test report, health model, proof panels, observability, the 5-minute demo script | Phase 6.5 + 7 |
| `04-DOCUMENTATION.md` | STATE.md, 10 ADRs, agent-ops.md, SECURITY.md, postmortem, per-service README template, in-app docs | Phase 6.5 + 7.5 |
| `05-2026-TECH-GAP-ANALYSIS.md` | 2026 tech coverage matrix, gaps → concrete stories → which room demonstrates each | Phase 8 |

## Build order (the gates matter more than the dates)

```
Phase 6   — WIRE IT          26 stories already in ralph/worklist.json (pending since May 5)
   GATE A: all 3 e2e flow tests green in CI (P6-022/023/024)
Phase 6.5 — PROVE IT         perf report, STATE.md, CI security gates, OTel spans  (Plan 03 + 04 Tier-0 items)
   GATE B: measured numbers in README; STATE.md truthful; gitleaks+trivy in CI
Phase 7-A — ASSETS           ComfyUI batch pre-gen on the 3090 box                  (Plan 02)
   GATE C: full library generated, QA'd, style-consistent       [parallel with 6/6.5 — different machine]
Phase 7-B — ROOMS            sim room model, interior renderer, drill-in UX,
                             proof panels, per-room data feeds                      (Plan 01 + 03)
   GATE D: 5 flagship rooms live with real data; demo script runs clean
Phase 7.5 — DOCUMENT IT      ADRs, agent-ops.md, SECURITY.md, postmortem, room docs (Plan 04)
Phase 8   — 2026 GAP CLOSE   MCP server, eval harness, structured outputs, etc.    (Plan 05)
```

Two rules carried over from the audit and the interview gap plan:

1. **Phase 6 closes before Phase 7-B opens.** Rooms on broken plumbing means debugging
   two problems at once. Phase 7-A (assets) is exempt — it runs on the 3090 box and has
   zero dependency on service wiring.
2. **No claim ships before its proof.** README/landing copy stays at "in flight" wording
   (see Plan 03 §Claim hygiene) until the gate that proves it is green.

## Who executes what

| Track | Executor | Why |
|---|---|---|
| Phase 6 wiring (P6-001..026) | Ralph (local Ollama) **or** Opus | Stories already written to Ralph's routing convention; Opus can run them directly if Ralph isn't activated. Either way, Kevin reviews diffs, not writes code. |
| Phase 6.5 proof + CI gates | Opus | Cross-cutting, judgment-heavy (perf methodology, CI design). |
| Phase 7-A asset batch | Opus authors `workflows/*.json` + finishes `run_batch.py`; **Kevin runs the batch** on the 3090 box (ComfyUI is local hardware) | Code is agent work; GPU execution is physical. |
| Phase 7-B rooms | Opus (new stories P7-001+, appended to worklist or run directly) | New product surface, needs the specs in Plan 01. |
| Phase 7.5 docs | Opus drafts, **Kevin voice-passes** ADRs/agent-ops/postmortem | These are interview artifacts in Kevin's voice. |
| Phase 8 gap items | Opus, cherry-picked by priority tier in Plan 05 | Each is independent. |

## Handoff format — how to prompt Opus with this pack

Each plan doc contains story tables with stable IDs (`P6.5-xxx`, `P7-xxx`, `P8-xxx`).
A story is handed to Opus as:

```
You are building Qtown v2. Read these files before writing any code:
  docs/plans/00-MASTER-PLAN.md        (thesis + gates)
  docs/plans/<the plan doc owning this story>
  docs/v2-audit.md                    (current ground truth per service)
  <files listed in the story's "touches" column>

Execute story <ID>: <title>.
Definition of done: <the story's acceptance criteria, verbatim from the plan doc>.
Constraints: smallest possible diff; no new claims in README/landing without a green
gate; follow the existing service's language idioms; update docs/STATE.md if the
story changes what runs.
```

Stories within one group are ordered; groups marked ∥ are safe to parallelize across
worktrees. Every story's acceptance criteria are written to be machine-checkable
(a test goes green, a file exists, an endpoint returns X) — "looks done" is not done.

## Definition of done for v2 overall

1. **Wired:** 3/3 cross-service flows pass e2e tests in CI on every PR.
2. **Proven:** README performance numbers are measured (perf/REPORT.md), the unsafe
   claim is reworded to the audited truth, `docs/STATE.md` says exactly what runs.
3. **Visible:** overhead town in the locked solarpunk style; ≥5 flagship rooms
   (Tavern bar, Market floor, Academy classroom, Validation Citadel chamber, Tower
   observation deck) drill in and render live data with proof panels.
4. **Documented:** STATE.md, 10 ADRs, agent-ops.md, SECURITY.md + threat model,
   secrets postmortem, per-service READMEs against the template, room info panels.
5. **2026-complete:** every Tier-1 row of the gap matrix (Plan 05) is Covered —
   MCP server, LLM eval harness in CI, OTel traces, structured outputs, CI supply-chain
   gates.
6. **Deployed:** the minimum demonstrable subset is live at qtown.ai (P6-019 decides
   host); v1 stays archived at v1.qtown.ai.

## What is explicitly out of scope for this pack

- Multi-region deploy, CDN optimization beyond "assets are publicly fetchable",
  animals/stable, docks, voice/TTS for NPCs (parked as Phase 8+ options in Plan 05).
- Re-litigating locked decisions: solarpunk + tech accents style (Guardian `2f7c20c8`),
  full-reboot Option B, taxonomy building/room/NPC set (`asset-gen/taxonomy.yaml`,
  `locked: true`). Changes to those require a new locked version, not drift.
