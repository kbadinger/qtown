# Qtown v2 — Honest Audit

**Date**: 2026-05-05
**Scope**: All 9 services + cross-service flows + v1-parity
**Conclusion**: v2 is *scaffolded*, not *delivered*. Ralph closed 194 stories; the per-service tests pass; the dashboard pages render. But none of the three flagship cross-service flows work end-to-end. The service-shaped bricks are there. The mortar isn't.

This document captures the gap and translates it into a Phase 6 backlog Ralph can execute.

---

## Executive summary

| Dimension | Verdict |
|---|---|
| Per-service implementations | 4/9 real, 4/9 shallow, 1/9 stub |
| End-to-end flows | 0/3 working (Market Trade, AI Dialogue, Validation) |
| v1 feature parity | ~96% on paper (routers ported), much lower in practice (no cross-service wiring) |
| Production deployment | Not started; no v2 service is hosted anywhere |
| Ralph claim ("194/194 complete") | True per-story; misleading at the system level |

The dashboard is the most honest part of v2: it correctly fans out to Cartographer, which correctly fans out to backing services. But several of those backing services either have ungenerated proto stubs (Fortress), unregistered gRPC servers (Market District), or one-sided Kafka topology (produced events nobody consumes; consumed events nobody produces).

---

## Service-by-service findings

### 1. town-core (Python · FastAPI · port 8000)
- **Real**: 30s tick loop wired (`services/town-core/engine/main.py:419` — `await asyncio.sleep(30)`); needs/goals/actions framework intact (`services/town-core/engine/simulation/`); Kafka producer wired (`services/town-core/engine/kafka_producer.py`).
- **Gap**: No gRPC server. Cartographer's gRPC client points at town-core but the service only exposes HTTP. Trade-event consumer exists but never fires because market-district doesn't produce.
- **Files to touch**: `services/town-core/engine/main.py` (add gRPC server start), new `services/town-core/engine/grpc_server.py`, `services/town-core/engine/kafka_consumer.py` (handler for `qtown.validation.result`).

### 2. market-district (Go · gRPC · port 50051)
- **Real**: Order book matching logic implemented (`services/market-district/internal/orderbook/orderbook.go:49-80`); benchmarks present (`internal/orderbook/orderbook_test.go:115-151`); gRPC handler defined (`internal/grpc/server.go:51-87`).
- **Gap**: gRPC server NOT registered in `cmd/server/main.go:34` — comment reads `// TODO: register gRPC service implementations here`. The server listens on :50051 but no handler is bound. **Net effect: every gRPC call to market-district fails.** Also: `internal/grpc/server.go:79` has `// TODO: emit economy.trade.settled to Kafka for each trade` — matches happen, nothing gets emitted.
- **Files to touch**: `services/market-district/cmd/server/main.go`, `services/market-district/internal/grpc/server.go`, new producer wiring under `internal/kafka/`.

### 3. fortress (Rust · gRPC + Kafka · ports 8080/50052)
- **Real**: Kafka consumer wired and works (`services/fortress/src/kafka_consumer.rs:40-100`); WASM sandbox module present (`src/wasm_sandbox.rs`); validation result producer works (`src/kafka_consumer.rs:81-93`).
- **Gap**: gRPC server is a marked placeholder — `src/main.rs:127` has `// proto codegen pending`. README claims zero `unsafe` in validation/rules; grep finds 27 `unsafe` blocks across `src/`. Either the WASM crate is bringing them in (acceptable, but should be confined to one module) or the claim was aspirational.
- **Files to touch**: `services/fortress/build.rs` (wire `tonic-build`), `services/fortress/src/main.rs` (mount Tonic router), `services/fortress/src/grpc_server.rs` (new), `src/wasm_sandbox.rs` (audit unsafe; confine to one wrapper module).

### 4. academy (Python · LangGraph + Ollama · port 8001)
- **Real**: Ollama client real and async (`services/academy/academy/ollama_client.py`); gRPC `GenerateDialogue` RPC fully implemented (`academy/grpc_server.py:90-100`); RAG dirs exist (`academy/rag/{retriever,reranker,__init__}`).
- **Gap**: LangGraph is in `pyproject.toml` deps but no `StatefulGraph` or compiled graph is found in code — only docstring references. Academy never emits to Kafka, so `qtown.ai.content.generated` (which Tavern consumes — `services/tavern/src/kafka-consumer.ts:220-224`) is never produced. No gRPC client to Library means RAG context isn't enriched. No upstream caller exists; nothing triggers `GenerateDialogue`.
- **Files to touch**: `services/academy/academy/agents/` (new — define the graph), `services/academy/academy/kafka_producer.py` (new), `services/academy/academy/library_client.py` (new gRPC client), `services/town-core/engine/routers/dialogues.py` or new caller.

### 5. tavern (TypeScript · WebSocket + Redis + Kafka · port 3001)
- **Real**: WebSocketManager attached to HTTP (`services/tavern/src/server.ts:52`); Kafka consumer (`server.ts:61-69`); Redis pub/sub (`server.ts:40-41`); broadcast helper (`server.ts:165`); leaderboard + presence tracker.
- **Gap**: Functional in isolation. Just consumes from upstream Kafka topics that are never produced. Not Tavern's bug.
- **Files to touch**: none required by Tavern itself; verify after upstream fixes that `economy.trade.settled` and `ai.content.generated` actually arrive.

### 6. library (Python · Elasticsearch · port 8003)
- **Real**: ES client connect (`services/library/library/main.py:43-44`); index templates defined (`library/index_templates.py`); Kafka consumer task started (`library/main.py:46-48`).
- **Gap**: Search endpoint and indexing pipeline implementations not verified — code beyond startup wasn't fully read in the audit. No gRPC server (Academy can't reach it for RAG).
- **Files to touch**: `services/library/library/search.py` (verify/implement), `services/library/library/indexer.py` (Kafka → ES write pipeline), new `services/library/library/grpc_server.py` for RAG queries.

### 7. cartographer (TypeScript · Apollo GraphQL · port 4000)
- **Real**: Apollo Server wired (`services/cartographer/src/server.ts:2-8`); gRPC clients instantiated (`server.ts:39-42`); resolvers call backing services (`src/resolvers.ts:54-61`, `:122`, `:187`); Redis cache layer; schema built via `makeExecutableSchema`.
- **Gap**: `src/grpc-clients.ts:24-35` uses `tryLoadPackage()` which silently fails on missing proto and returns `null`. That means downstream resolver calls hit `null` clients. The pattern is "fail soft" — for production this should be "fail loud + clear error".
- **Files to touch**: `services/cartographer/src/grpc-clients.ts` (replace soft-fail with strict load + diagnostic), regenerate proto into `src/__generated__/`.

### 8. asset-pipeline (Python · ComfyUI · Kafka)
- **Real**: ComfyUI HTTP client real (`services/asset-pipeline/asset_pipeline/comfyui_client.py:76-144`); Kafka producer/consumer wired (`asset_pipeline/main.py:42-48`).
- **Gap**: No CDN integration found. Generated sprites land in local storage; no path to S3/CloudFront/etc. No Kafka consumer connecting NPC creation → sprite generation.
- **Files to touch**: `services/asset-pipeline/asset_pipeline/storage.py` (new — S3/CDN upload), `services/asset-pipeline/asset_pipeline/main.py` (subscribe to NPC/building creation events).

### 9. dashboard (Nuxt 3 · port 3000)
- **Real**: All promised pages exist (`dashboard/pages/`); WebSocket composable (`useWebSocket()`); GraphQL composable (`useGraphQL()`); pages call `fetchOrderBook()`, `fetchRecentTrades()`, etc.
- **Gap**: Port 3000 collides with Kevin's reserved local-dev range (3000–3010 is for Guardian/etc.). For local dev, dashboard needs a different port. Also: dashboard correctness depends entirely on cartographer + backing services — when those fail soft, the dashboard renders stale/empty without telling the user.
- **Files to touch**: `dashboard/nuxt.config.ts` or `docker-compose.yml` env (override `PORT=3100`); `dashboard/composables/useGraphQL.ts` (surface server-side errors).

---

## Cross-service flow audit

### Flow 1 — Market Trade
NPC submits order → market matches → Kafka event → town-core wallet update → tavern broadcast → dashboard render.

| Step | File | Status |
|---|---|---|
| 1. Origination | (none) | **MISSING** — no caller invokes `PlaceOrder` |
| 2. gRPC server reachable | `services/market-district/cmd/server/main.go:34` | **BROKEN** — handler not registered |
| 3. Order book match | `services/market-district/internal/grpc/server.go:76` | works |
| 4. Emit Kafka event | `services/market-district/internal/grpc/server.go:79` | **STUB** — TODO comment |
| 5. Town-core consumer | `services/town-core/engine/kafka_consumer.py:115-137` | works (but never receives anything) |
| 6. Tavern broadcast | `services/tavern/src/kafka-consumer.ts:195-212` | works (but never receives anything) |
| 7. Dashboard render | `dashboard/pages/market.vue:22-31` | works (renders empty data) |

**Verdict**: completely broken at steps 1, 2, and 4.

### Flow 2 — AI Dialogue
NPC interaction → academy generates → tavern broadcasts → dashboard renders.

| Step | File | Status |
|---|---|---|
| 1. Trigger | (none) | **MISSING** |
| 2. Academy `GenerateDialogue` | `services/academy/academy/grpc_server.py:90-100` | works in isolation |
| 3. Ollama call | `services/academy/academy/ollama_client.py` | works |
| 4. Library RAG | (no client) | **MISSING** — no gRPC client to Library |
| 5. Kafka emit | (none) | **MISSING** — no producer in academy |
| 6. Tavern broadcast | `services/tavern/src/kafka-consumer.ts:220-224` | works (but never receives anything) |
| 7. Dashboard render | `dashboard/pages/` | works (depends on Tavern data flow) |

**Verdict**: broken at 1, 4, 5.

### Flow 3 — Validation
State change → fortress consumes → WASM validates → emit result → downstream consumes.

| Step | File | Status |
|---|---|---|
| 1. Town-core emits request | `services/town-core/engine/kafka_producer.py:113-127` | works |
| 2. Fortress consumes | `services/fortress/src/kafka_consumer.rs:40-100` | works |
| 3. WASM sandbox validates | `services/fortress/src/wasm_sandbox.rs` | works |
| 4. Fortress emits result | `services/fortress/src/kafka_consumer.rs:81-93` | works |
| 5. Downstream consumes | (none) | **MISSING** — no service handles `qtown.validation.result` |

**Verdict**: 4/5 hops work; the loop never closes because no consumer acts on the validation outcome.

---

## v1 → v2 feature parity

The router-level port-over is broad:

| Concept | v1 | v2 | Status |
|---|---|---|---|
| Tick loop | `v1/engine/simulation/` | `services/town-core/engine/main.py:419` | exists |
| Needs/goals/actions | `v1/engine/simulation/` | `services/town-core/engine/simulation/npcs.py` | exists |
| Buildings | `v1/engine/routers/buildings.py` | `services/town-core/engine/routers/buildings.py` | exists |
| Wages | `v1/engine/routers/wages.py` | `services/town-core/engine/routers/wages.py` | exists |
| Elections | `v1/engine/routers/features.py` | `services/town-core/engine/routers/features.py` | exists |
| Factions | `v1/engine/simulation/events.py` | `services/town-core/engine/simulation/events.py` | exists |
| Crime | `v1/engine/simulation/buildings.py` | `services/town-core/engine/simulation/buildings.py` | exists |
| Gossip / rumor graph | `v1/engine/simulation/npcs.py` | `services/town-core/engine/simulation/npcs.py` | exists |
| Achievements | `v1/engine/routers/achievements.py` | `services/town-core/engine/routers/achievements.py` | exists |
| Newspaper | `v1/engine/routers/newspaper.py` | `services/town-core/engine/routers/newspaper.py` | exists |
| Visitor log | `v1/engine/routers/visitor_log.py` | `services/town-core/engine/routers/visitor_log.py` | exists |
| Snapshot system | `v1/snapshots/` (846 PNGs) + writer | (none) | **MISSING** |
| Sprite delivery | `v1/asset-gen/` + `assets/` | `services/asset-pipeline/` (no CDN) | partial |
| PixiJS isometric renderer | `v1/engine/static/js/town.js` | `dashboard/components/PixiRenderer.client.vue` | exists |

The router code was duplicated wholesale into `services/town-core/engine/`. The simulation logic lives there as Python objects, the same as v1. **What's different in v2 is that those routers are no longer the source of truth** — Cartographer + GraphQL is. And town-core's gRPC interface (which Cartographer expects) doesn't exist yet. So v2's town-core is a v1 monolith wearing a microservice nametag.

The two hard misses are:
- **Snapshots**: Ralph never wrote a v2 equivalent. v1 snapshotted state to PNG every N ticks for debugging/portfolio purposes.
- **Asset pipeline → CDN**: ComfyUI generates sprites; nothing puts them where the dashboard can fetch them.

---

## Phase 6 backlog (P6-001 onward)

These stories are appended to `ralph/worklist.json` with `status: pending`. Story IDs and story titles use Ralph v2's keyword routing convention (`architect|design|refactor|schema` → 27b; `debug|fix|race condition|investigate|root cause` → r1:14b; default → qwen3-coder-next).

The backlog is grouped by theme:

**Group 6.1 — Wire missing gRPC servers (architect-grade)**
- P6-001: Architect & wire town-core gRPC server with proto contracts
- P6-002: Architect Fortress proto codegen via build.rs and Tonic router
- P6-003: Refactor Fortress unsafe blocks to confine to a single wasm wrapper module
- P6-004: Architect Library gRPC server for RAG queries from Academy
- P6-005: Register market-district gRPC service in cmd/server/main.go

**Group 6.2 — Close Kafka topology (default coder)**
- P6-006: Emit qtown.economy.trade.settled from market-district after each match
- P6-007: Add Kafka producer in academy emitting qtown.ai.content.generated
- P6-008: Add town-core consumer handler for qtown.validation.result
- P6-009: Subscribe asset-pipeline to NPC creation events to trigger sprite generation

**Group 6.3 — Close cross-service entrypoints (default coder)**
- P6-010: Add NPC order origination in town-core (calls market-district PlaceOrder via gRPC)
- P6-011: Add NPC dialogue trigger endpoint in town-core that calls academy GenerateDialogue
- P6-012: Add gRPC client in academy to query Library for RAG context

**Group 6.4 — Real implementations behind shallow stubs (default coder)**
- P6-013: Define and compile academy LangGraph workflow for NPC decision agents
- P6-014: Implement library indexing pipeline: Kafka consumer writes events into ES per template
- P6-015: Implement library search and aggregation query endpoints
- P6-016: Wire asset-pipeline output to S3/CDN delivery with public URLs

**Group 6.5 — Production hardening (debug + design)**
- P6-017: Investigate cartographer grpc-clients.ts: replace tryLoadPackage soft-fail with strict load + diagnostic
- P6-018: Override dashboard port from 3000 to 3100 in docker-compose to avoid Kevin's reserved range
- P6-019: Design v2 production deployment: pick host (Railway / Fly / k8s via existing Helm), publish minimum subset to qtown.ai

**Group 6.6 — v1 parity gaps (architect)**
- P6-020: Architect world snapshot system in town-core — periodic state export for replay/QA
- P6-021: Migrate v1 sprite assets into asset-pipeline storage so dashboard can render them

**Group 6.7 — End-to-end verification (debug)**
- P6-022: Investigate market-trade flow end-to-end: write integration test covering 7 hops
- P6-023: Investigate AI-dialogue flow end-to-end: write integration test covering academy → tavern → dashboard
- P6-024: Investigate validation flow end-to-end: confirm fortress accept/reject is acted on by town-core

**Group 6.8 — Documentation truthing (default coder)**
- P6-025: Update README v2 architecture diagram to mark which gRPC contracts are live vs stubbed
- P6-026: Update landing page stats to reflect Phase-6 truth (replace "194 stories complete" with "Phase 6 in progress")

That's 26 stories. Once Ralph closes them, run all three e2e flow tests; if all pass, qtown v2 has earned the README it claims.

---

## What this audit does NOT cover

- **Performance**: The README claims "<5ms p99 at 10K orders/sec" for market-district. The benchmark file exists, but no one has actually run it under load. Treat the number as marketing until a benchmark commit lands.
- **Security**: No threat model, no auth on internal RPCs, no rate limiting on Cartographer. Out of scope for Phase 6 — file as Phase 7.
- **Observability**: Jaeger + Prometheus + Loki are configured in `infra/`, but no service emits OpenTelemetry spans yet. Phase 7.
- **Cost**: No production deploy means no cost. Once qtown.ai actually serves v2, infra cost becomes a constraint.
