# Plan 04 — Documentation: Understanding How It Works

> Part of the v2 plan pack (`00-MASTER-PLAN.md`). Owns Phase 6.5 doc items + Phase 7.5.
> Source: `docs/2026-interview-gap-plan.md` Tier 1 (the highest paper-ROI-per-hour work
> in the whole program). Principle: **docs are written for a reader who clicks** — every
> claim links to the file, test, or report that proves it (Plan 03 provides the proofs).

Two audiences, two surfaces:
- **Repo readers** (interviewers, recruiters, engineers): `docs/` + per-service READMEs.
- **Town visitors** (anyone at qtown.ai): the in-room docs drawer (§6) — the same
  knowledge, narrative-wrapped, reachable from inside each room.

One source of truth feeds both: room-doc content is generated from the repo docs, never
written twice.

## 1. `docs/STATE.md` — the landing page for humans who click

The single page that says what runs today, what doesn't, and the numbers. Sections:
**What works now** (the green e2e flows, live rooms) · **What's in flight** (current
phase + gate) · **The numbers** (only measured ones, linked to `perf/REPORT.md`) ·
**5-minute quickstart** (`make deps && make build && make run && open …` — CI runs the
quickstart in a smoke job so it can never rot) · **Honest gaps** (the audit summary,
updated per phase).

Done when: a stranger reproduces the quickstart from a fresh clone, and every number on
the page has a link to its proof. Updated as a required part of any story that changes
what runs (the master plan's handoff prompt enforces this).

## 2. ADR pack — `docs/adr/` (10 × ~half page)

Template: Context → Decision → Consequences → Receipts (links to code/tests/reports).
The ten, from the interview gap plan:

| # | Decision | The receipt that makes it credible |
|---|---|---|
| 01 | Go for the order book | `perf/REPORT.md` numbers; orderbook.go |
| 02 | Rust + WASM for untrusted validation | the confined-unsafe module (P6-003); sandbox tests |
| 03 | Kafka, at-least-once + idempotent consumers (vs the exactly-once myth) | consumer idempotency tests; topic catalog §5 |
| 04 | GraphQL gateway as sole public entry | cartographer authz + rate limit (Plan 05 G-07) |
| 05 | Polyglot-by-domain vs resume-driven engineering | the building→service map (Plan 01 §1) — each language earns its building |
| 06 | v1 deliberate monolith → v2 decomposition triggers | v1 closeout post; audit parity table |
| 07 | Local-model routing by task type | `ralph/v2_model_router.py` — it's literally in production |
| 08 | Fail-loud over fail-soft | the cartographer `tryLoadPackage` lesson (audit §7, P6-017) |
| 09 | Linkerd mTLS + service authz | `infra/linkerd/` policies |
| 10 | Agent-written code: CI as the trust boundary | the e2e gates (Plan 03 §1); the audit itself |

Opus drafts all ten from the receipts; **Kevin voice-passes** (these are interview
artifacts in his voice). Done when: each ADR ≤ 1 page, every Consequences claim links
to a receipt, zero aspirational statements.

## 3. `docs/agent-ops.md` — the differentiator document

Nobody else interviews with this doc. Contents: Ralph architecture (orchestrator,
worklist, conflict detection) · the model-routing policy as production config (27b for
architect-keyword stories, r1:14b for debug, qwen3-coder-next default, auto-fallback
<50% success) · the HUMAN.md steering protocol + intervention log · cost-per-story
methodology (`COST_METHODOLOGY.md`, BigQuery commit-stream analytics) · **the audit
story**: 194/194 "complete" while 0/3 flows worked — what "true per-story, misleading at
the system level" means, and the structural fix (e2e gates, Plan 03 §1) · how Opus +
Ralph divide work in this very plan pack (master plan §Who executes what — the doc
should describe the process that produced it).

## 4. `SECURITY.md` + threat model + postmortem

- **`SECURITY.md`:** trust-boundary diagram (public → cartographer → mesh; Kafka as
  internal bus; Ollama/ComfyUI as local-only planes), what's enforced today (Linkerd
  mTLS/authz), **what's honestly not done** (no auth on internal RPCs, no gateway rate
  limit — with the Plan 05 G-07 plan attached). Honest partial > silent absence.
- **Threat model (1 page, STRIDE-lite):** assets = world state, wallet integrity,
  generated-content integrity; actors = drive-by web, malicious GraphQL, poisoned RAG
  content, compromised dependency; mitigations mapped to the CI gates (Plan 03 §6) and
  OWASP-LLM items (Plan 05 G-05/G-06).
- **`docs/postmortems/2026-05-30-committed-secrets.md`:** what leaked (commit `280d792`
  context), blast radius, rotation timeline, and the guards now in CI (gitleaks, trivy,
  dependency audit). Converts a visible negative in git history into operational signal.
  Opus drafts from git history; Kevin confirms the rotation facts.

## 5. Per-service READMEs — one template, nine services

Template (`docs/templates/service-readme.md`): What this is (2 sentences + its building
in the town) · Interface (gRPC/HTTP/Kafka in+out, linked to proto + topic catalog) ·
Run/test locally · How it proves itself (health endpoint, its e2e flow, its room's proof
panel) · Design notes (link to owning ADRs) · Honest status (live/dormant per feature).

Plus the **Kafka topic catalog** (`docs/kafka-topics.md`): all 27 topics — producer,
consumers, schema, and the e2e test that exercises it. This is also the Warehouse room's
docs hook. Generated from a checked-in YAML so the catalog, kafka-init.sh, and the
Warehouse feed can't drift apart.

## 6. In-room docs — `RoomDocs.vue` content (the town teaches itself)

Each room's ⓘ drawer (P7-011) renders a content file `docs/rooms/<building>.<room>.md`
with frontmatter:

```yaml
---
building: market          # which room this teaches
service: market-district  # backing system
sources:                  # repo docs this was distilled from — CI checks links resolve
  - docs/adr/01-go-orderbook.md
  - services/market-district/README.md
---
```

Body structure (~200 words max — a drawer, not a wiki): **What you're watching** (the
real system behind the animation) · **How it flows** (the 3–5 hop path, each hop naming
its real file) · **Why it's built this way** (one paragraph distilled from the owning
ADR) · **Go deeper** (links: ops page, ADR, service README, the e2e test).

Done when: all rooms with live feeds have a doc; CI link-check passes; a non-engineer
can read one and correctly explain what the room demonstrates (Kevin's read test).

## 7. Story list — Phase 7.5 (`P7.5-0xx`)

| ID | Story | Depends on |
|---|---|---|
| P7.5-001 | STATE.md + CI quickstart smoke job | Gate A |
| P7.5-002..011 | ADR-01..10 (one story each, ∥) | receipts per §2 table |
| P7.5-012 | agent-ops.md | none |
| P7.5-013 | SECURITY.md + threat model | Plan 03 §6 gates landed |
| P7.5-014 | Secrets postmortem | Kevin's rotation facts |
| P7.5-015 | Service README template + 9 service READMEs (∥) | none |
| P7.5-016 | Kafka topic catalog (YAML + generated md) | Gate A |
| P7.5-017..021 | Room docs for flagship five (∥) | P7-012..016 |
| P7.5-022 | Room docs for second ring (batch) | P7-018+ |
| P7.5-023 | `docs/index.json` + docs IA refresh; README links the pack | all above |

Voice-pass rule: P7.5-002..014 ship as PRs Kevin edits before merge; the rest are
mergeable on review.
