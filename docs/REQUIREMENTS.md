---
review_key: claude-qtown-20260711-requirements
review_status: Awaiting Review
created_by: claude
authority: AUTHORITATIVE — this is the single source of truth for what "qtown v2 done" means.
indexes_and_supersedes:
  - docs/v2-spec.md (subordinate reference; where it conflicts, this wins)
  - docs/2026-interview-gap-plan.md (priorities feed this)
  - docs/plans/00-MASTER-PLAN.md (thesis feeds this)
  - docs/plans/AREA-TECH-TEACHING-PLAN.md (the 15-area definitions)
  - docs/plans/06-FABLE-PLAN.md (the HOW; this is the WHAT)
---

# Qtown v2 — Requirements

> **Status:** Draft 1, 2026-07-11. The WHAT and the bar for "done." The HOW/WHEN lives in
> `docs/plans/06-FABLE-PLAN.md`, which must trace back to these requirements.
> **Decisions locked with Kevin (2026-07-11):** full 15-area vision · AI-architect/AI-engineer
> primary audience · "now, but it has to be right to serve its purpose."

## 1. North Star

Qtown v2 is a **full, 15-area, AI-architect-grade living system disguised as a town** — a
portfolio-grade AI systems lab where every area demonstrates a real capability, renders real
data, proves itself with live telemetry, and explains how it works. The purpose is **interview
conversion for AI-architect / AI-engineer roles** (senior/staff backend is the secondary
audience). Kevin can point at any area and say: *"I built that kind of AI system — here's the
code, the proof, and the teaching view."*

## 2. The three inviolable principles (the "right" bar)

These gate every increment. Violating any one means the increment is not done, regardless of
how finished it looks. The audit found all three currently violated somewhere.

1. **No fabricated data, ever.** A metric whose source errors renders as `—`, never as a
   plausible number. (Currently violated: `dashboard/server/api/sla/compliance.get.ts` invents
   SLA figures with `Math.random()`. Must be removed before anything else ships.)
2. **No claim before its gate.** README/landing/proof-panel claims stay at "in flight" wording
   until the gate that measures them is green. (Currently violated: perf, unsafe, Lighthouse.)
3. **Real, not scaffolded.** An area is not "done" until its flow works end-to-end with a
   green CI gate. "Passes its own unit tests" is not done. (Currently violated: the Academy AI
   layer passes units but never calls the model.)

## 3. Definition of done

### 3.1 Per-area DoD (the repeatable unit of delivery)

An area is **green** only when ALL six hold — this is the contract for every one of the 15:

1. **Wired** — its backing flow runs end-to-end (not stubbed, not TODO).
2. **Gated** — an e2e test for that flow is a blocking CI job.
3. **Proven** — a proof panel renders *real* live telemetry from the backing system (or `—`).
4. **Explained** — a teaching layer answers "how does this concept work" in-app or in docs.
5. **Documented** — a service README + an ADR for any non-obvious decision.
6. **Honest** — its status (real / partial / dormant) is truthfully labeled everywhere.

Until an area is green, it ships in **dormant** mode: visibly labeled, NPCs idle, proof panel
says "awaiting wiring" — never faking activity.

### 3.2 System-level DoD (the full vision — the North Star realized)

1. **All 15 areas green** per §3.1.
2. **AI-architect capstone live** — LLM agents take real, schema-validated, WASM-authorized,
   human-approved actions on Salesforce and Odoo via MCP, with an injection red-team test green
   in CI (see §4.1).
3. **Measured, not claimed** — every performance number in the repo is from a committed load
   test; `docs/STATE.md` is truthful.
4. **Self-documenting** — `AGENTS.md`/`CLAUDE.md` orient a new agent to v2; 10 ADRs;
   `agent-ops.md`; `SECURITY.md` + threat model; per-service READMEs; the teaching layer.
5. **Deployed** — the live system is reachable at qtown.ai; v1 stays archived at v1.qtown.ai.
6. **Extensible** — proto codegen actually wired; one enforced source of truth for areas;
   a service scaffold so area N+1 is cheap.

### 3.3 Interim "interview-ready" milestone (satisfies "now")

A credible thing to show *while* the full vision continues — this is the near-term target:

- The **credibility floor** (§2 all satisfied: fabricated proof gone, claims honest, AI layer
  actually invokes the model).
- **Two flagship areas green**: **Market** (the distributed-systems proof) and **Academy**
  (the real RAG+evals AI proof) — because the AI-architect story needs a real *agentic/LLM*
  area AND a real *systems* area under it.
- The **capstone as a vertical slice** (one agent, one real SF/Odoo action, safely gated).
- **Deployed + a 90-second demo + honest STATE.md.**

Hitting this milestone = interview-credible today; the remaining 13 areas continue as waves.

## 4. Functional requirements

Weighted AI-architect-first. Every area must satisfy §3.1; below is what each must *demonstrate*.

### 4.1 AI / agentic core (first-class — the headline)
- **Academy** — real RAG: chunk → embed → retrieve → **generate with citations** → eval
  (golden set + rubric, in CI). Not retrieval-only; not regex-scraped output.
- **Tavern** — grounded multi-agent dialogue with memory + a social graph; "why this NPC said
  this" is inspectable.
- **Workshop** — the agentic dev loop (Ralph) made legible: task → routing → diff → tests →
  human review, shown as real state.
- **Capstone (Embassy / external-agent interface)** — LLM agents act on **real Salesforce +
  Odoo** via MCP, with: schema-validated tool-call args; every action routed through the
  Rust/WASM validator as an **authorization** boundary; human-in-the-loop for writes; RAG/CRM
  text treated as untrusted; an **injection red-team test** in CI. This is the core
  AI-architect requirement, not a stretch.

### 4.2 Distributed-systems spine
- **Market** — Go order book over gRPC, Kafka trade events, idempotent consumers, DLQ, outbox;
  measured p50/p99 from a committed load test.
- **Tower / Observatory** — OTel traces across ≥3 languages into Jaeger; a real cross-service
  trace of one trade; health model.
- **Warehouse** — the Kafka event backbone made visible: topics, lag, throughput.
- **Town Square / Overhead Map + Cartographer** — real-time state aggregation, GraphQL fan-out,
  live rendering with source/staleness badges.

### 4.3 Safety / governance
- **Validation Citadel** — WASM validation, policy-as-code, audit log; the capstone's authz gate.
- **Town Hall / Courthouse / Restoration Center** — the tick loop, policy, and justice loop as
  real sim state.

### 4.4 ML & the remaining areas
- **Clinic** — real classical ML (features → train → metrics → predict → drift), not LLM.
- **Bank** (economy/settlements), **Farm/Bakery/Blacksmith** (production chains), **Temple/
  Park/Theater** (culture/gossip loop) — each real sim state, proof + teaching per §3.1.

## 5. Non-functional requirements

- **Performance** — measured SLOs for the systems areas (Market, gateway); methodology +
  hardware committed in `perf/REPORT.md`.
- **Security** — secret scanning (gitleaks) + image/dependency scanning (trivy) as CI gates;
  gateway authn + rate limiting; service-to-service authz (Linkerd); a threat model; and —
  because agents take real actions — **prompt-injection and tool-call abuse defense** as a
  named requirement, not an afterthought.
- **Observability** — OTel spans in ≥3 languages; structured logs with correlation IDs;
  dependency-aware health/readiness (not HTTP-200-always).
- **Reliability** — idempotent Kafka consumers, DLQs, outbox for DB+Kafka atomicity, gRPC
  timeouts + graceful degradation, graceful shutdown.
- **Self-documentation** — see §3.2.4; a new human *or agent* can understand any area in
  <10 min from `CLAUDE.md` → area map → service README → proof/teaching.
- **Extensibility** — proto is the enforced single source of truth (codegen wired for all 4
  languages); one area-list (not three unsynced copies); a per-language service scaffold.
- **Honesty of the record** — README carries zero falsifiable claims; STATE.md is the truth.

## 6. Constraints

- **Budget:** ≤2 evenings/week + occasional weekend chunks, always after the job-search work.
  This is interview-conversion, not the mission; the mission is the pipeline.
- **Local-first:** built on Kevin's own hardware; ≥90% local-model routing; the "cost-per-story
  on my own box" story is preserved. (Hosted-agent products like Hermes are tools to evaluate
  later, not the dev-loop replacement — see memory `hermes-agent-vs-ralph`.)
- **Execution:** Ralph codes / Kevin steers / Kevin voice-passes the interview-facing docs.
  Builds run on the toolchain box (Go/Rust/buf/Docker), not the WSL box `hazardandmoonie`.
- **Locked decisions (not re-litigated):** solarpunk + tech-accent style, the `taxonomy.yaml`
  building/room/NPC set, full-reboot Option B.

## 7. Scope

- **In (the full vision):** all 15 areas green + the agentic capstone. This is the requirement.
- **Parked (do only when growing breadth):** the service scaffold/generator, data-driven
  CI/compose lists, Kafka topic registry — valuable but only pay off across many areas.
- **Out:** voice/TTS for NPCs, animals/stable, docks, multi-region deploy (stays code + ADR),
  landing redesign beyond the honest narrative.

## 8. Delivery sequence (requirements → waves)

The full vision, delivered in correctness-gated waves, AI-architect-first. Each wave is gated
by §2. This is the requirements view; `06-FABLE-PLAN.md` holds the story-level detail.

- **Wave 0 — Floor & truth:** satisfy §2 everywhere (kill fabricated proof, honest README,
  fix the AI-layer facade, fix AGENTS.md/CLAUDE.md, secret scan). *→ interim milestone begins.*
- **Wave 1 — Two flagship areas real:** Market (systems) + Academy (AI), each green per §3.1;
  wire proto codegen as the prerequisite. *→ interim interview-ready milestone met.*
- **Wave 2 — The capstone:** MCP + Salesforce/Odoo + the WASM authorization boundary + evals +
  injection red-team.
- **Wave 3+ — Fan out to full vision:** the remaining 13 areas to green, area-by-area via the
  §3.1 unit, plus the §7-parked spine-hardening that makes each new area cheap.

## 9. Traceability

Every requirement maps to an area/service and a wave; every area carries a live status
(dormant/partial/green) surfaced in `docs/STATE.md` and in-app. No requirement is "met" without
its §3.1 gate green. `06-FABLE-PLAN.md` must be reconciled so each story cites the requirement
it satisfies.

## 10. Open items to confirm

- Capstone: Salesforce-first (brand) then Odoo (portability) — confirm.
- Deploy host for the live full system (Railway vs fly.io vs the local box exposed).
- Which areas beyond Market/Academy are the next wave-3 priorities (interviewer-weighted).
