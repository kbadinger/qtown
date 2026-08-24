---
review_key: claude-qtown-20260712-state
review_status: Awaiting Review
created_by: claude
authority: The living, honest status board. If a claim anywhere in the repo disagrees with STATE.md, STATE.md is what's true right now.
sources: docs/v2-audit.md (service/flow status), docs/REQUIREMENTS.md §3.1 (the DoD each area is measured against)
---

# Qtown v2 — STATE (the honest status board)

> **Status:** Draft 2, 2026-08-23.
> **What this is:** the single, truthful ledger of what actually works right now. It is the data
> source the **Planning Office** area renders in-app. Every status here is deliberately
> conservative — an area is only **green** when all six DoD points (`REQUIREMENTS.md §3.1`) hold,
> not when its unit tests pass.
> **How to read it:** this is a snapshot of reality, not a roadmap. The roadmap is
> `docs/plans/06-FABLE-PLAN.md`. Where they disagree, this file is the truth and the plan is the aim.

## Legend

| Mark | Status | Means |
|---|---|---|
| 🟢 | **green** | Wired end-to-end · e2e CI gate · real proof data · explained · documented · honest (all 6 of §3.1). |
| 🟡 | **partial** | Some real logic exists, but the flow is not wired end-to-end and/or has no gate. Ships **dormant** in-app. |
| ⚫ | **dormant** | Stub / scaffold / not started. Visibly labeled dormant in-app; never fakes activity. |

**As of 2026-08-23, 3 of 16 areas are green** — Market, Academy, Tavern — each behind a blocking
CI gate (`e2e-market`, `eval-academy`, `e2e-tavern`). Wave 1 merged to `main` 2026-07-20 (PR #1).
The credibility of this project rests on this table being *honest*, not on it being *all green*.

## Flagship end-to-end flows — 2 / 3 working

These are the cross-service flows the whole architecture exists to prove. Flows 1 and 2 run
end-to-end behind blocking CI; flow 3 still doesn't close its loop.

| Flow | Status | Reality (per `docs/v2-audit.md`) |
|---|---|---|
| **Market Trade** (town-core → market gRPC → Kafka → dashboard) | 🟢 | Runs e2e behind the blocking `e2e-market` gate: town-core originates orders → registered `PlaceOrder` gRPC → match → single-sided `trade.settled` on real Kafka → read-model proof panel. Measured p99 committed (`docs/perf/market-loadtest.md`). |
| **AI Dialogue** (town-core → academy → local model → response) | 🟢 | Runs e2e: town-core's tick triggers `GenerateDialogue` for co-located NPCs; dialogue is RAG-grounded on real town events (pgvector); emitted on `qtown.ai.content.generated` and consumed by tavern. Blocking `eval-academy` recall gates (docs + events). |
| **Validation** (event → fortress WASM → allow/reject → Kafka) | 🟡 | 4/5 hops work (emit → fortress consume → WASM validate → result emit), but **nothing consumes `qtown.validation.result`** — the loop never closes. Fortress gRPC codegen still pending; not an authz gate yet. |

## Services — real vs scaffolded

| Service | Stack | Status | What's real / what's missing |
|---|---|---|---|
| **town-core** | Python · FastAPI | 🟡 | Tick loop (30s) + NPC/need model real; **originates market orders and dialogue calls** (gRPC clients with deadlines + breaker, Wave 1). Still **no gRPC server** of its own — cartographer can't fan out to it. |
| **market-district** | Go · gRPC | 🟢 | Order book + `PlaceOrder` gRPC + single-sided `trade.settled` all real; `e2e-market` gate green; measured p99 + proof panel (W1-M*). |
| **fortress** | Rust · WASM + gRPC | 🟡 | WASM sandbox + Kafka consumer real. **gRPC codegen pending**; not wired as an authz gate. |
| **academy** | Python · LangGraph + Ollama | 🟢 | Grounded RAG over the qtown-docs corpus; `recall@k` gate (`eval-academy`) + faithfulness report + proof panel; dialogue `GenerateDialogue` wired to town-core (W1-A*). LangGraph decision graph still deferred. |
| **library** | Python · Elasticsearch | ⚫ | Search / index pipeline **unverified**. |
| **tavern** | TypeScript · WS + Redis | 🟢 | Real-time gateway: Kafka → Redis pub/sub (single fan-out path) → WebSocket channels; `test-tavern` + live `e2e-tavern` gates; read-model proof panel (W1-T). Grounding cross-linked to Academy, not re-implemented. |
| **cartographer** | TypeScript · Apollo GraphQL | 🟡 | Resolvers exist; fan-out targets are mostly not wired. |
| **asset-pipeline** | Python · ComfyUI | 🟡 | Pipeline runs on the GPU box; 143 sprites still to generate. |
| **dashboard** | Nuxt 3 / Vue | 🟡 | UI exists; proof panels are dormant-safe (`—` without a backend, never fabricated). Vercel build validated via the deploy kit (`deploy/dashboard/`) — **not deployed yet**. |

**Infra:** Kafka · Postgres · Redis · Elasticsearch — provisioned via `docker-compose.deps.yml`;
not deployed anywhere yet.

## Areas — the 15 proof-rooms + the meta-room

Areas are the *product* view (see `docs/plans/AREA-TECH-TEACHING-PLAN.md`); they don't map 1:1 to
services. Status is the honest per-area DoD roll-up.

| # | Area | Backing | Status |
|---|---|---|---|
| 1 | Town Square / Overhead Map | cartographer + dashboard | 🟡 |
| 2 | Tavern | tavern + academy | 🟢 (gateway: e2e-tavern) |
| 3 | Market | market-district | 🟢 (Wave 1A) |
| 4 | Academy | academy + library | 🟢 (Wave 1B) |
| 5 | Clinic | (ML — not started) | ⚫ |
| 6 | Workshop / Maker Space | Ralph loop | ⚫ |
| 7 | Warehouse | (Kafka topology) | ⚫ |
| 8 | Bank | (ledger) | ⚫ |
| 9 | Validation Citadel | fortress | 🟡 |
| 10 | Courthouse | (policy) | ⚫ |
| 11 | Town Hall | town-core | ⚫ |
| 12 | Restoration Center | (behavior) | ⚫ |
| 13 | Tower / Observatory | all + infra (OTel) | ⚫ |
| 14 | Farm / Bakery / Blacksmith | town-core | ⚫ |
| 15 | Temple / Park / Theater | town-core | ⚫ |
| 16 | **Planning Office** (meta) | cartographer + this file | ⚫ (being built; dormant content lands first) |
| — | Embassy / Capstone (agentic MCP) | academy + fortress + MCP | ⚫ (Wave 2) |

## Deployment

| Property | Reality |
|---|---|
| **qtown.ai** (apex) | Static landing page on **Vercel** — updated 2026-07-20 to the honest v2 status (3 areas "Proven · 6/6", rest "In flight"). |
| **v1.qtown.ai** | The **v1** sim (FastAPI monolith) on **Railway** — live, but currently idle (Population 0 / Tick 0). |
| **v2 system** | **Nothing hosted yet.** A deploy kit is merged (PR #4, 2026-07-22) but every public-facing step (box, tunnel, Vercel project, DNS) is still pending manual go-live. Target model: the **market exhibit** — market-district on a free/cheap box (Oracle Always Free first, Hetzner CX22 fallback) behind a **Cloudflare Tunnel** at `market.qtown.ai`, plus the dashboard on **Vercel** at `dashboard.qtown.ai` pointed at it via `MARKET_HTTP_URL`; ~$0–4/mo, with wake/sleep scripts so **asleep is honest, not broken** (panels render `—`/dormant, never fake). Runbooks: `deploy/market-exhibit/README.md` and `deploy/dashboard/README.md`. |

## Update discipline

This file is edited by hand whenever a status actually changes, and is the source the Planning
Office reads. Do not mark an area green here until its `REQUIREMENTS.md §3.1` gate is green in CI —
that is the whole point of the file.
