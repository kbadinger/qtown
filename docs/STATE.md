---
review_key: claude-qtown-20260712-state
review_status: Awaiting Review
created_by: claude
authority: The living, honest status board. If a claim anywhere in the repo disagrees with STATE.md, STATE.md is what's true right now.
sources: docs/v2-audit.md (service/flow status), docs/REQUIREMENTS.md §3.1 (the DoD each area is measured against)
---

# Qtown v2 — STATE (the honest status board)

> **Status:** Draft 1, 2026-07-12.
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

**As of 2026-07-12, zero areas are green.** This is expected: Wave 0 (floor & truth) is landing;
Wave 1 (Market + Academy → green) has not started. The credibility of this project rests on this
table being *honest*, not on it being *all green*.

## Flagship end-to-end flows — 0 / 3 working

These are the cross-service flows the whole architecture exists to prove. None run end-to-end yet.

| Flow | Status | Reality (per `docs/v2-audit.md`) |
|---|---|---|
| **Market Trade** (town-core → market gRPC → Kafka → dashboard) | ⚫ | Go order-book matching is real, but the market gRPC handler isn't registered and town-core has no gRPC server to originate an order. Wave 1A. |
| **AI Dialogue** (town-core → academy → local model → response) | 🟡 | Ollama client is real, but code paths exist where the model is never actually called (the facade). LangGraph graph + Kafka producer not built. Facade fix + real RAG = Wave 0 W0-2 / Wave 1B. |
| **Validation** (event → fortress WASM → allow/reject → Kafka) | 🟡 | Rust/WASM sandbox + Kafka consumer are real, but gRPC codegen is pending and no upstream service calls it as an authorization gate yet. |

## Services — real vs scaffolded

| Service | Stack | Status | What's real / what's missing |
|---|---|---|---|
| **town-core** | Python · FastAPI | 🟡 | Tick loop (30s) + NPC/need model real. **No gRPC server**; originates no market order. |
| **market-district** | Go · gRPC | 🟡 | Order-book matching real. **gRPC handler not registered**; emits no trade event yet. |
| **fortress** | Rust · WASM + gRPC | 🟡 | WASM sandbox + Kafka consumer real. **gRPC codegen pending**; not wired as an authz gate. |
| **academy** | Python · LangGraph + Ollama | 🟡 | Ollama client real. **Facade paths never call the model**; LangGraph + Kafka producer not built. |
| **library** | Python · Elasticsearch | ⚫ | Search / index pipeline **unverified**. |
| **tavern** | TypeScript · WS + Redis | 🟡 | WebSocket broadcast layer real; depends on upstream events that don't flow yet. |
| **cartographer** | TypeScript · Apollo GraphQL | 🟡 | Resolvers exist; fan-out targets are mostly not wired. |
| **asset-pipeline** | Python · ComfyUI | 🟡 | Pipeline runs on the GPU box; 143 sprites still to generate. |
| **dashboard** | Nuxt 3 / Vue | 🟡 | UI exists; points at `localhost` defaults; proof panels render `—` without a backend. |

**Infra:** Kafka · Postgres · Redis · Elasticsearch — provisioned via `docker-compose.deps.yml`;
not deployed anywhere yet.

## Areas — the 15 proof-rooms + the meta-room

Areas are the *product* view (see `docs/plans/AREA-TECH-TEACHING-PLAN.md`); they don't map 1:1 to
services. Status is the honest per-area DoD roll-up.

| # | Area | Backing | Status |
|---|---|---|---|
| 1 | Town Square / Overhead Map | cartographer + dashboard | 🟡 |
| 2 | Tavern | tavern + academy | ⚫ |
| 3 | Market | market-district | 🟡 (Wave 1A target) |
| 4 | Academy | academy + library | 🟡 (Wave 1B target) |
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
| **qtown.ai** (apex) | Static landing page on **Vercel** ("v2 in development"). |
| **v1.qtown.ai** | The **v1** sim (FastAPI monolith) on **Railway** — live, but currently idle (Population 0 / Tick 0). |
| **v2 system** | **Not deployed.** Target: dashboard on Vercel + backend/Ollama on the 3090 box behind a tunnel; apex flips to v2 on Wave 1 green. See `docs/DEPLOY.md` (planned) and `v1/DEPLOY.md`. |

## Update discipline

This file is edited by hand whenever a status actually changes, and is the source the Planning
Office reads. Do not mark an area green here until its `REQUIREMENTS.md §3.1` gate is green in CI —
that is the whole point of the file.
