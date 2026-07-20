---
review_key: claude-qtown-20260711-fable-plan
review_status: Awaiting Review
created_by: claude
implements: docs/REQUIREMENTS.md
note: This is the HOW/WHEN. docs/REQUIREMENTS.md is the WHAT/bar. Phases = requirement waves; every story cites the requirement (§) it satisfies.
---

# Qtown v2 — The Fable Plan (execution)

> **Status:** Draft 2, 2026-07-11 — reconciled to `docs/REQUIREMENTS.md`.
> **Locked decisions:** full 15-area vision · AI-architect/AI-engineer primary · "now, but right."
> **Shape:** phases ARE the requirement waves (§8). Every story is gated by the three inviolable
> principles (REQUIREMENTS §2) and isn't "done" until its per-area DoD gate (§3.1) is green.
> **Executor:** Ralph codes / Kevin steers / Kevin voice-passes docs. Builds run on the toolchain
> box (Go/Rust/buf/Docker); the WSL box does TS/Python/docs. Agent-agnostic (Ralph or Claude Code).

## The spine (waves = gates)

```
WAVE 0  FLOOR & TRUTH       satisfy the 3 inviolable principles everywhere        [near-free; start here]
   GATE 0: fabricated proof gone · README honest · AI layer actually calls the model ·
           AGENTS.md/CLAUDE.md truthful for v2 · gitleaks clean + trivy/gitleaks CI gates.
WAVE 1  TWO FLAGSHIP AREAS  Market (systems) + Academy (AI) each GREEN per DoD §3.1  [the interim milestone]
   GATE 1: both areas wired+gated+proven(real data)+explained+documented+honest;
           proto codegen wired; measured p99 in README. → interview-ready milestone MET.
WAVE 2  THE CAPSTONE        agents act on real Salesforce/Odoo via MCP, safely       [the AI-architect headline]
   GATE 2: an agent creates a real SF/Odoo record ONLY via schema-validated + WASM-authorized +
           human-approved path; injection red-team test green in CI; one agent→validator→SaaS trace.
WAVE 3+ FAN OUT TO FULL     remaining 13 areas → green, area-by-area via the DoD unit  [the full vision]
   GATE 3: each area green per §3.1; STATE.md status board live + truthful; spine-hardened for cheap breadth.
CONTINUOUS  DOCS & DEPLOY   senior-signal docs (Kevin-voiced) + live deploy, threaded through every wave.
```

Rule: a wave doesn't open until the prior gate is green (Wave 0 excepted — it's unblocked now).

---

## WAVE 0 — Floor & truth  *(Ralph/Opus; ~1 week; agent-agnostic, most doable on the WSL box)*

| ID | Title | Req | Done-when |
|---|---|---|---|
| **W0-1** | Remove fabricated proof | §2.1 | `dashboard/server/api/**` render `—`/typed error on upstream failure; **zero `Math.random()`** in any proof/metric path (`sla/compliance.get.ts`, `visitor/*`). |
| **W0-2** | Fix AI-layer facade — restore `RouteResult` | §2.3, §4.1, §5 | **Corrected 2026-07-11:** the fix is the *opposite* of the first read. Three test files (`test_npc_agent/newspaper/quests`) import a `RouteResult` the code lost, and mock `route()` returning it with `.response/.model_used/.prompt_tokens/.completion_tokens`. Restore `RouteResult`; `route()` returns it via `generate_with_metadata` (this **also fixes the zero-token cost-tracking gap**); update the 6 string-callers to read `.response`. **Do on the toolchain box** (needs pytest + remote Ollama). The WSL first-attempt "callers→string" edits are the wrong direction — discard them. Done-when: `academy/tests` + `academy/academy/tests` green; a live `NPCDecide` yields non-fallback narration. |
| **W0-3** | Fix `run_npc_cycle` signature | §2.3 | `grpc_server.py:373` + `kafka_consumer.py:128` pass `npc_name`/`personality`; `NPCDecide` returns a model-derived decision in a test. |
| **W0-4** | Honest CI | §2.3 | CI runs both `academy/tests/` and `academy/academy/tests/`; remove `\|\| true` where tests exist; where none exist, emit a visible "no tests yet: <svc>". |
| **W0-5** | De-falsify README + landing (P6-025/026) | §2.2 | No unverified claim remains; perf/unsafe/Lighthouse reworded to audited truth; README links `docs/STATE.md`. |
| **W0-6** | Secret + supply-chain gates | §5-security | `gitleaks --log-opts=--all` clean; `gitleaks` + `trivy` are **blocking** CI jobs. |
| **W0-7** | Truthful agent orientation | §3.2.4 | Rewrite `AGENTS.md` for v2 (kill the v1-monolith description); add root `CLAUDE.md` "start here" with the area→service→code→docs map (v1 archived, v2 = `services/`). |

## WAVE 1 — Two flagship areas GREEN  *(the interim interview-ready milestone)*

Each area must hit all six of DoD §3.1 (wired · gated · proven · explained · documented · honest).

### 1A — Market (the distributed-systems proof)

| ID | Title | Req | Done-when |
|---|---|---|---|
| **W1-M0** | Wire proto codegen (prerequisite) | §5-extensibility | `buf` in toolchain; `fortress/build.rs` (tonic); drop `market-district/proto/placeholder.go` for `gen/`; CI checks regen matches. |
| **W1-M1** | Register market gRPC handler (P6-005) | §4.2 | `PlaceOrder` reachable on :50051; integration test places order → fill. |
| **W1-M2** | town-core originates order (P6-010) | §4.2 | A sim event calls `PlaceOrder`; test asserts the call. |
| **W1-M3** | Emit `economy.trade.settled` (P6-006) | §4.2 | On match, Kafka event produced; consumer test observes it. |
| **W1-M4** | Idempotent consumer + DLQ | §5-reliability | Keyed on `trade_id` (replay → gold unchanged); failures → DLQ with replay path. |
| **W1-M5** | Outbox (match↔emit atomicity) | §5-reliability | Kill-before-emit test recovers the event. → ADR. |
| **W1-M6** | Market-trade e2e CI gate (P6-022) | §3.1.2 | Compose-based e2e asserts the full path; **blocking** job. |
| **W1-M7** | Load test → `perf/REPORT.md` (P6.5-001/002) | §5-perf, §2.2 | `ghz` under compose; committed report; README quotes **measured** p99. |
| **W1-M8** | gRPC deadlines + breaker | §5-reliability | Slow/down market → typed error, not a hang; test covers timeout. |
| **W1-M9** | Market room: real data + proof panel | §3.1.3 | Renders live order book + measured latency; `—` when source down (no fake). |
| **W1-M10** | Market teaching layer | §3.1.4 | In-app/doc explainer: "how an order book matches trades." |
| **W1-M11** | Market README + ADR | §3.1.5 | Service README (what/why/run/contract/status) + ADR (Go order book). |

### 1B — Academy (the AI/RAG proof)

| ID | Title | Req | Done-when |
|---|---|---|---|
| **W1-A1** | Real RAG (retrieve→generate w/ citations) | §4.1 | Retrieved passages fed to the LLM; answer cites sources. Not retrieval-only; the "generation" span becomes real. |
| **W1-A2** | Structured outputs + schema validation | §4.1, §5 | Ollama `format=json` + Pydantic/instructor; validated with retry-on-invalid; regex-scrape gone from generation paths. |
| **W1-A3** | Eval harness in CI (P8-002) | §3.1.2, §4.1 | Golden dialogue/RAG set + rubric judge; **blocking** job; recall@k / faithfulness metric committed. |
| **W1-A4** | Academy proof panel: real retrieval + eval | §3.1.3 | Shows real retrieved chunks, citation links, eval score; `—` on source failure. |
| **W1-A5** | Academy teaching layer | §3.1.4 | Explainer: "what is an embedding / how RAG works." |
| **W1-A6** | Academy README + ADR | §3.1.5 | Service README + ADR (RAG design; local-model routing). |
| **W1-A7** | Route tool-use tasks to best-fit model | §4.1 | *Evidence-based, optional:* pick the model for structured/tool-use tasks by a measured score on the golden set (Hermes a candidate — see memory `hermes-agent-vs-ralph`). Only lands with a number behind it. |

## WAVE 2 — The capstone: agents act on real Salesforce/Odoo, safely  *(the AI-architect headline)*

| ID | Title | Req | Done-when |
|---|---|---|---|
| **W2-1** | Tool-call outputs hardened | §4.1 | Tool-call args schema-validated before dispatch; no free-text parse on any action path. (Builds on W1-A2.) |
| **W2-2** | qtown MCP server (P8-001) | §4.1 | Town state exposed via MCP; a client reads it. |
| **W2-3** | Salesforce MCP adapter (#1, brand) | §4.1 | Thin MCP server; agent reads + writes one object (e.g. Opportunity) on a free Dev org. |
| **W2-4** | `EnterpriseConnector` + Odoo (#2) | §4.1 | Same interface; self-hosted Odoo as always-on demo box. Built after #1 works. |
| **W2-5** | WASM authorization boundary + HITL | §4.1, §4.3, §5-security | Every proposed action routes through the Rust/WASM validator (allowlist + schema + policy); human confirmation for writes; RAG/CRM text treated as untrusted. |
| **W2-6** | Injection red-team test | §5-security | A poisoned town/CRM record must NOT trigger an unauthorized tool call; test green in CI. |
| **W2-7** | Capstone ADR + Embassy area | §3.1, §4.1 | ADR "letting LLM agents act on production SaaS: the trust boundary"; the Embassy area ships green per §3.1. |

## WAVE 3+ — Fan out to the full vision  *(the remaining 13 areas → green)*

Each area taken to green via the DoD §3.1 unit. **Order (interviewer-weighted, AI/systems first — confirm):**
1. **Tavern**, **Workshop**, **Tower/Observatory** (AI + observability signal)
2. **Warehouse**, **Town Square**, **Validation Citadel** (systems + safety, some already advanced by Wave 1/2)
3. **Clinic** (real ML), **Town Hall**, **Courthouse**, **Restoration Center**, **Bank**, **Farm/Bakery/Blacksmith**, **Temple/Park/Theater**

**Spine-hardening (unpark as breadth grows — REQUIREMENTS §7):**
- `taxonomy.yaml → rooms.yaml` sync + `Neighborhood` enum derived from it + CI drift gate (collapse 3 area-lists → 1).
- Per-language service scaffold + minimal shared runtime lib (config/logging/health/shutdown/Kafka).
- Central Kafka topic registry (generated) + payload schema versioning.
- Data-drive Makefile/CI/compose service lists (follow the Helm pattern).

**Status board:** `docs/STATE.md` renders each area's live status (dormant/partial/green) — the self-documenting truth table (REQUIREMENTS §9).

## CONTINUOUS — Docs & deploy  *(Opus drafts, Kevin voice-passes; threaded through all waves)*

| ID | Title | Req |
|---|---|---|
| **DOC-1** | `docs/STATE.md` (honest, living) — **drafted 2026-07-12** | §3.2.3, §9 |
| **DOC-2** | 10 ADRs (incl. idempotency+DLQ, outbox, "CI as trust boundary for agent code", capstone) | §3.2.4 |
| **DOC-3** | `agent-ops.md` — centered on the facade-catch story | §3.2.4 |
| **DOC-4** | postmortem + `SECURITY.md` + threat model (incl. prompt-injection) | §3.2.4, §5 |
| **DOC-5** | `docs/DEMO.md` + 90s GIF + 60s recruiter narrative | §3.3 |
| **DOC-6** | Architecture-of-record (`docs/architecture.md`, honest Mermaid) + **Planning Office** meta-area (AREA plan §16); de-falsify in-app `architecture.vue` — **drafted 2026-07-12; goes green when it renders live STATE.md status + a real trace + a drift gate** | §3.2.4, §2 |
| **DEP-1** | Deploy the live subset (Wave 1 first, grows per wave) — host TBD (§10) | §3.2.5 |

## Traceability & gates

Every story cites its requirement §; no story is "done" until its DoD §3.1 gate is green; no
claim ships before its gate (§2.2); no proof panel shows a number it didn't measure (§2.1).
`docs/STATE.md` is the running ledger of which requirements are met.

## Open items (defaulted; confirm — REQUIREMENTS §10)

- Capstone: **Salesforce-first** (brand) then Odoo (portability) — assumed; confirm.
- Deploy host: **TBD** (Railway / fly.io / local box exposed) — decide at DEP-1.
- Wave-3 order: **AI/systems areas first** (Tavern/Workshop/Tower) — assumed; confirm interviewer weighting.
