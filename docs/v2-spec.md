# Qtown v2 — Master Spec

**Status:** Draft 1 · 2026-05-06
**Companions:** [`visual-style-guide.md`](./visual-style-guide.md) · [`v2-pipeline.md`](./v2-pipeline.md) · [`v2-map.md`](./v2-map.md) · [`v2-audit.md`](./v2-audit.md)

This is the source of truth for what "v2 done" means. Everything else — the sprite manifest, the world layout, the Ralph worklist, the Railway deploy — derives from here.

---

## 1 · Overview

v1 shipped at 550 stories as a Python monolith on Railway, archived under `/v1/` and live at `v1.qtown.ai`. v2 is a polyglot microservices rewrite: 9 services across Python · Go · Rust · TypeScript, communicating via Protobuf-defined gRPC and 12 Kafka topics, fronted by an Apollo GraphQL gateway.

The framework code exists but per `docs/v2-audit.md`:
- 0 of 3 flagship cross-service flows work end-to-end
- gRPC servers are unregistered for town-core, market-district, and fortress (only academy is wired)
- 7 of 12 Kafka topics are unwired (orphans or TODO-only producers)
- 4 of 9 CI jobs are non-blocking (`|| true`)
- The dashboard renders procedural shapes; zero sprites
- No deployment plan

**v2 done** means parity + working + proven:
- All 9 services have registered gRPC servers and consume/produce the right Kafka topics
- All 3 flagship cross-service flows pass end-to-end tests
- Every README proof claim verified by `make proof-*` against a live deployment
- Visual identity complete (~200-250 fresh sprites, 9 distinct neighborhoods)
- qtown.ai serves a live demo where the polyglot architecture is *legible* — visitors can see each tech doing its thing

---

## 2 · Framing doctrine — the town IS the architecture

v1 was a town simulation that happened to be implemented in Python. v2 is a town **whose layout is the system architecture**. Each service is a neighborhood with:

- **Distinct architectural style** — visitors can tell which neighborhood they're in by sight alone
- **Ambient activity** — NPCs and props characteristic of the service's role
- **Tech-signature animation** — a continuously running visual that shows what the underlying tech does (Go's concurrency, Rust's safety, GraphQL's fan-out, etc.)

Walking through the town is walking through the system. A visitor with no README context should grok the architecture in 30 seconds.

**The three headline visual hooks** (the things that make a casual visitor go "wait, what's that doing?"):
1. **Cartographer fan-out** — external GraphQL queries enter as visitors who travel to multiple neighborhoods then return with the answer
2. **Market concurrency lines** — multiple trade lines firing in parallel between stalls (Go's signature)
3. **Fortress gate** — accept/reject made physical, with the WASM sandbox visible inside

---

## 3 · Per-neighborhood specification

### 3.1 Town Hall (town-core · Python + FastAPI · port 8000)
- **Architectural style:** Civic-Roman, marble columns, central plaza with a great clock
- **Ambient activity:** Citizens of all roles flowing through; tax collectors; town crier
- **Tech-signature animation:** Plaza clock shows the 30s simulation tick advancing; day/night cycle radiates outward from the plaza across the entire map
- **Building manifest:** great clock (1), town hall main (1), tax office (1), records hall (1), citizens' homes (mixed 5-8), notice boards (2)
- **NPC roles:** mayor, tax collector, town crier, scribe, citizen (generic, multiple variants)
- **Tech-signature props:** plaza clock face, day/night sky overlay
- **Connected roads (terminating Kafka topics):** all of them — Town Hall is the central nexus
- **`/metrics` exports:** `tick_count`, `tick_duration_ms`, `npcs_alive`, `gold_total`, `simulation_uptime_s`

### 3.2 Market District (market-district · Go + gRPC · port 50051/6060)
- **Architectural style:** Open-air bazaar, copper-trimmed awnings, pneumatic-tube messaging system between stalls
- **Ambient activity:** Traders shouting bids, runners delivering goods, the order-book ledger board updating
- **Tech-signature animation:** **Order-book ledger board** in the central plaza shows live bids/asks updating; **trade lines fly between stalls in parallel** (multiple lines simultaneously visible) — Go's concurrency made literal
- **Building manifest:** order-book plaza (1), trade stalls (8-10), warehouse (1), pneumatic-tube hub (1), customs house (1)
- **NPC roles:** trader, broker, runner, customs officer, warehouse hand
- **Tech-signature props:** order-book ledger board, pneumatic tubes, trade-route flags
- **Connected roads:** `qtown.economy.trade` (incoming from Town Hall), `qtown.economy.trade.settled` (outgoing to Town Hall), `qtown.economy.price.update` (broadcast outgoing)
- **`/metrics` exports:** `trades_per_second`, `concurrent_trades_active`, `match_latency_ms_p99`, `orderbook_depth_bids`, `orderbook_depth_asks`

### 3.3 The Fortress (fortress · Rust + WASM · port 50052/8080)
- **Architectural style:** Stone keep, brass-bound gates, parapets, walls
- **Ambient activity:** Guards on patrol, validators at the gate, occasional inspectors entering the WASM chamber
- **Tech-signature animation:** **Validation gate** at the entrance — events arrive as glowing orbs, gate flashes green (accept) or red (reject); the **WASM sandbox is a contained brass chamber** visible through fortress windows where untrusted policies execute; clean stone surfaces (no "rust") = no `unsafe`
- **Building manifest:** main gate with validation arch (1), keep (1), brass WASM chamber (1), guard towers (4), policy library (1)
- **NPC roles:** guard, validator, sandbox-keeper, inspector
- **Tech-signature props:** glowing validation orbs, brass WASM chamber doors, "0 unsafe" engraved plaque
- **Connected roads:** `qtown.validation.request` (incoming from Town Hall), `qtown.validation.result` (outgoing to Town Hall)
- **`/metrics` exports:** `validations_per_second`, `unsafe_block_count` (must stay 0 in `src/rules/` + `src/validation/`), `policies_active`, `wasm_sandbox_executions`, `validation_latency_ms_p99`

### 3.4 The Academy (academy · Python + Ollama + LangGraph · port 8001)
- **Architectural style:** University library + glowing tomes + Tesla-coil thinking devices on rooftops
- **Ambient activity:** Scholar NPCs reading, walking between Library and Academy, in animated discussion
- **Tech-signature animation:** Scholar NPCs near the Academy show **live AI dialogue thought-bubbles** generated by Ollama; the **model-router is a literal switching board** on a wall in the lecture hall (lit lamp = which model handled the last query, with running ≥85% local indicator); **RAG queries visualized as scrolls** retrieved from the Library next door
- **Building manifest:** lecture hall with switching board (1), scholar dormitories (2), thinking-device tower (1), open quad (1), bookbinder's shop (1)
- **NPC roles:** scholar, lecturer, sandbox-debugger, model-router-attendant, RAG-archivist
- **Tech-signature props:** glowing tomes, Tesla-coil thinking devices, model-router switching board, scroll bundles
- **Connected roads:** `qtown.ai.request` (incoming from Town Hall), `qtown.ai.response` (outgoing to Town Hall), `qtown.ai.content.generated` (outgoing to Tavern)
- **`/metrics` exports:** `local_routing_pct` (must be ≥85), `dialogues_in_flight`, `dialogue_latency_ms_p99`, `model_calls_per_second`, `rag_queries_per_second`

### 3.5 The Tavern (tavern · TypeScript + Redis + WebSocket · port 3001)
- **Architectural style:** Inn with hearth, gossip board outside, leaderboard plaque on the wall
- **Ambient activity:** Patrons drinking, gossip exchanges, lottery draws on the leaderboard
- **Tech-signature animation:** Every new event creates a **visible pulse radiating outward** from the Tavern across the entire map — the WebSocket broadcast made literal; **leaderboard plaque** updates with live ranks; gossip board scrolls recent events
- **Building manifest:** main inn (1), hearth room (1), gossip board (1), leaderboard plaque (1), beer garden (1)
- **NPC roles:** innkeeper, patron, gossip, scribe (gossip-board), leaderboard-herald
- **Tech-signature props:** broadcast pulse rings, leaderboard plaque, gossip scrolls
- **Connected roads:** consumes from many topics (`events.broadcast`, `economy.trade.settled`, `economy.price.update`, `ai.content.generated`, `npc.travel.*`); produces no Kafka but emits WebSocket pulses across the map
- **`/metrics` exports:** `connected_clients`, `events_broadcast_per_second`, `redis_pubsub_lag_ms`, `leaderboard_updates`

### 3.6 The Library (library · Python + Elasticsearch · port 8003)
- **Architectural style:** Archive vault, reading desks, towering shelves, brass index cards
- **Ambient activity:** Archivists pulling scrolls, scholars searching, indexers cataloguing
- **Tech-signature animation:** Archivists physically **pull scrolls per query**; recent searches scroll across an awning banner over the front entrance (ES index throughput); when Academy needs RAG context, scrolls travel from Library to Academy on the road between them
- **Building manifest:** archive vault main (1), reading hall (1), index card room (1), search desk (1), conservation lab (1)
- **NPC roles:** archivist, indexer, conservator, search-clerk, scholar (visiting from Academy)
- **Tech-signature props:** scrolls (mid-flight versions), search-result banner, index card stacks
- **Connected roads:** consumes events from `events.broadcast` for indexing; emits via gRPC to Academy on RAG queries (no Kafka outgoing)
- **`/metrics` exports:** `search_latency_ms_p99`, `documents_indexed`, `searches_per_second`, `index_size_bytes`

### 3.7 Cartographer's Guild (cartographer · TypeScript + Apollo GraphQL · port 4000)
- **Architectural style:** Mapmaker's office; centerpiece is a **giant cartograph table** that updates in real time with the visitors fanning out and returning
- **Ambient activity:** Cartographers drafting; visitors arriving from the gate, dispatched to neighborhoods, returning with answers
- **Tech-signature animation:** **External queries enter as visitors at the front gate** — each visitor is colored by query type — **dispatched to multiple neighborhoods** along the relevant roads, **return to the Cartographer's Guild with their findings**, and the cartograph table updates. **You literally watch GraphQL fan-out execute across the map.** Headline visualization.
- **Building manifest:** mapmaker's office with giant cartograph table (1), drafting rooms (2), reception/visitor gate (1), pigeon coop (1)
- **NPC roles:** cartographer, draftsman, dispatcher, visitor (transient — colored per query, lifecycle = single GraphQL query)
- **Tech-signature props:** giant cartograph table, query-visitor sprites (multiple color variants), dispatch flags
- **Connected roads:** none direct (Cartographer talks gRPC to backing services, not Kafka). Visualized as visitors traveling on the existing topic-roads
- **`/metrics` exports:** `active_queries`, `query_latency_ms_p50`, `query_latency_ms_p99`, `services_touched_per_query_avg`, `query_cache_hit_rate`

### 3.8 Artisan's Workshop (asset-pipeline · Python + ComfyUI)
- **Architectural style:** Crafts hall with kilns, work benches, in-progress sprites mounted on display
- **Ambient activity:** Artisans working at benches; new buildings/NPCs unveiled in a public display when complete; runners shipping finished sprites along the roads
- **Tech-signature animation:** **New buildings and NPCs unveil here first** when asset-pipeline generates them — a "tarp dropped" moment with a small fanfare sprite — then they "ship" along the roads to their destination; **visible queue of in-progress sprites** on the workbenches
- **Building manifest:** main workshop (1), kiln (1), display plaza (1), shipping yard (1), workbench (4-6)
- **NPC roles:** artisan, kiln-keeper, shipper, displayer
- **Tech-signature props:** in-progress sprite easels, ribbon-cutting tarp, shipping crates
- **Connected roads:** consumes `assets.generate` (currently orphan — to be wired); produces `assets.generated`
- **`/metrics` exports:** `sprites_generated_total`, `generation_queue_depth`, `generation_latency_s_p99`, `comfyui_status`

### 3.9 Roads + countryside (the Kafka topology)
The 12 Kafka topics map to 12 named, signed roads on the map:

| Topic | Road | From → To | Visual |
|---|---|---|---|
| `qtown.events.broadcast` | Broadcast Way | Town Hall → all | Trunk roads radiating from plaza |
| `qtown.npc.travel` | Wanderers' Path | varies | Origin → destination per NPC |
| `qtown.npc.travel.complete` | Returners' Path | varies | Reverse direction |
| `qtown.npc.travel.failed` | Lost Lane | side path | Visible only on failure |
| `qtown.economy.trade` | Trader's Road | Town Hall → Market | Bidirectional, traffic = order flow |
| `qtown.economy.trade.settled` | Settler's Way | Market → Town Hall | Settled trades return |
| `qtown.economy.price.update` | Crier's Way | Market → all | Periodic broadcast |
| `qtown.validation.request` | Sentinel's Approach | Town Hall → Fortress | Validation requests |
| `qtown.validation.result` | Verdict's Return | Fortress → Town Hall | Accept/reject results |
| `qtown.ai.request` | Scholar's Path | Town Hall → Academy | AI generation requests |
| `qtown.ai.response` | Wisdom's Return | Academy → Town Hall | Generated content responses |
| `qtown.ai.content.generated` | Gossip Pipeline | Academy → Tavern | Content for broadcast |

**Tech-signature animation for roads:** **Messengers run on the roads** — sprite frequency proportional to topic throughput; idle topic = empty road. Hover any road for `topic_name · X msg/s · Y partitions`.

---

## 4 · Map specification

- **Grid:** 100×100 isometric tiles (10,000 tiles). Tile dimensions inherited from v1 (`TILE_W=64, TILE_H=32`).
- **Layout:** Town Hall central; 8 other neighborhoods arranged radially around it with road-distance correlated to topic frequency (high-traffic neighborhoods closer to Town Hall).
- **Per-neighborhood footprint:** ~25×25 tiles average. Each neighborhood has clear edges (decorative walls/hedges/shoreline) so visitors know they've crossed a boundary.
- **Per-neighborhood ground tinting:** subtle terrain palette shift inside each zone (Market = warm clay, Fortress = grey stone, Academy = cobble, Tavern = grass, Library = flagstone, Cartographer = polished marble, Artisan's = sand, Town Hall = central marble).
- **Camera:** drag-to-pan (continuation of v1), scroll-to-zoom (range 0.2–3.0×), **number keys 1–9 jump to the corresponding neighborhood with smooth pan**.
- **Mini-map:** corner overlay showing the 9 zones, current camera position, and live activity dots per neighborhood.

Detailed coordinates + road geometry → `docs/v2-map.md` + `world-layout.json` (Phase 3 deliverables).

---

## 5 · Per-service definition of done

Every service must satisfy:

| Criterion | Required |
|---|---|
| **gRPC server** | Every proto-defined RPC has a registered handler; `make proof-grpc` confirms each server reachable on its port |
| **Kafka topics** | All topics listed in section 3 produced/consumed; no orphans; no TODOs in producer paths |
| **`/metrics` endpoint** | Exports the metrics listed in section 3 over Prometheus-compatible HTTP, on a documented port |
| **`make test-<service>`** | Strict (no `\|\| true`) and green in CI |
| **`make proof-<service>`** | Exists and `PROOF PASS`es. New proof targets required for: town-core, tavern, cartographer, library |
| **Health check** | `/health` returns 200 when the service is healthy and dependencies (DB, Kafka, etc.) are reachable |
| **Dockerfile** | Builds clean; Railway-deployable as a single container |
| **`README.md` per service** | One page summarizing tech stack, ports, env vars, dependencies, how to run locally |

### Service-specific gates beyond the universal criteria

| Service | Extra gate |
|---|---|
| town-core | All 8 RPCs registered; tick loop's metrics endpoint validated |
| market-district | All 7 RPCs registered; `BenchmarkOrderBook` passes <5ms p99 at 10K orders/sec; emits `economy.trade.settled` after match |
| fortress | All 13 RPCs registered (proto codegen via `build.rs` with `tonic-build`); `unsafe_block_count == 0` in `src/rules/` and `src/validation/`; WASM sandbox executes a test policy |
| academy | LangGraph workflow compiled and used by `GenerateDialogue`; gRPC client to Library for RAG context; Kafka producer for `ai.content.generated` |
| tavern | Real test suite (currently `\|\| true`); WebSocket broadcast verified end-to-end |
| library | gRPC server for RAG queries from Academy; indexing pipeline writes events into ES; search endpoint returns p99 <100ms |
| cartographer | `tryLoadPackage` soft-fail replaced with strict load + diagnostic; all backing-service clients connect; resolver fan-out works |
| asset-pipeline | Subscribes to NPC/building creation events; uploads sprites to a CDN-accessible location; emits `assets.generated` |
| dashboard | All overlay components functional; sprite layer renders; flow-trace mode toggles cleanly; runs on Nuxt port 3100 (not 3000 — reserved range) |

---

## 6 · Per-flow definition of done

### 6.1 Market Trade flow
NPC submits an order → market matches → trade event fires → wallet updates → tavern broadcasts → dashboard ticker updates.

| Hop | Source → Sink | File:func | Acceptance |
|---|---|---|---|
| 1 | NPC tick → town-core PlaceOrder caller | `services/town-core/engine/simulation/economy.py` | Periodic NPCs place orders during tick |
| 2 | town-core → market-district `PlaceOrder` (gRPC) | `services/town-core/engine/grpc_clients/market.py` (new) | Round-trip succeeds |
| 3 | market-district matches | `services/market-district/internal/orderbook/orderbook.go` | Match returns trade |
| 4 | market-district → Kafka `economy.trade.settled` | `services/market-district/internal/kafka/producer.go` (new) | Trade emitted per match |
| 5 | town-core consumes `economy.trade.settled` → wallet update | `services/town-core/engine/kafka_consumer.py:115-137` | NPC wallet updated |
| 6 | tavern consumes `economy.trade.settled` → WS broadcast | `services/tavern/src/kafka-consumer.ts:195-212` | WS frame fired to all clients |
| 7 | dashboard renders trade ticker | `dashboard/pages/market.vue` + `MarketConcurrencyLines.vue` | Trade line visible on map |

**E2E test:** `tests/e2e/test_market_trade.py` exercises hops 1-7, asserts dashboard receives trade event within 2s of submission. Demonstration layer: flow-trace mode "Trace: Market Trade" highlights the path.

### 6.2 AI Dialogue flow
NPC interaction triggers dialogue → academy generates → tavern broadcasts → dashboard speech bubble.

| Hop | Source → Sink | File:func | Acceptance |
|---|---|---|---|
| 1 | NPC interaction in tick → town-core dialogue trigger | `services/town-core/engine/routers/dialogues.py` (new or extend) | Trigger fires on NPC interaction |
| 2 | town-core → academy `GenerateDialogue` (gRPC) | new client | Round-trip succeeds |
| 3 | academy queries Library for RAG context (gRPC) | `services/academy/academy/library_client.py` (new) | Context retrieved |
| 4 | academy calls Ollama via `ollama_client.py` | existing | Dialogue generated |
| 5 | academy → Kafka `ai.content.generated` | `services/academy/academy/kafka_producer.py` | Dialogue emitted |
| 6 | tavern consumes `ai.content.generated` → WS broadcast | `services/tavern/src/kafka-consumer.ts:220-224` | WS frame fired |
| 7 | dashboard renders speech bubble | `AcademyThoughtBubble.vue` | Bubble visible above NPC |

**E2E test:** `tests/e2e/test_ai_dialogue.py` exercises hops 1-7, asserts speech bubble within 3s of trigger.

### 6.3 Validation flow
State change → fortress validates → result acted on by town-core.

| Hop | Source → Sink | File:func | Acceptance |
|---|---|---|---|
| 1 | town-core emits `validation.request` | `services/town-core/engine/kafka_producer.py:113-127` | Existing — works |
| 2 | fortress consumes | `services/fortress/src/kafka_consumer.rs:40-100` | Existing — works |
| 3 | WASM sandbox validates | `services/fortress/src/wasm_sandbox.rs` | Existing — works |
| 4 | fortress emits `validation.result` | `services/fortress/src/kafka_consumer.rs:81-93` | Existing — works |
| 5 | town-core consumes `validation.result` → state apply | new handler in `services/town-core/engine/kafka_consumer.py` | State change reflected |

**E2E test:** `tests/e2e/test_validation.py` exercises hops 1-5, asserts state change within 1s of validation.

---

## 7 · Visual definition of done

- **Sprite count:** ~200-250 fresh sprites delivered to `dashboard/public/sprites/<neighborhood>/{buildings,npcs,props}/`. Per-neighborhood inventory enumerated in `visual-style-guide.md` § sprite manifest.
- **Renderer:**
  - `PixiRenderer.client.vue` loads sprites via `useSpriteTextures` composable with retry-on-failure pattern (logic ported from `v1/engine/static/js/town.js`)
  - Buildings rendered with anchor `(0.5, 1.0)`, scale `TILE_W * 2.0`, position `toScreen(b.x+1, b.y+1)` with `y + TILE_H/2`
  - NPCs rendered with anchor `(0.5, 1.0)`, scale `TILE_W * 0.6`, position `y + TILE_H * 0.25`
  - Procedural fallback for any sprite that fails to load (v1's pattern preserved)
- **Tooltips:** hover any building or NPC for an overlay tooltip showing name + role + stats (NPC: happiness, energy, hunger, gold, age, workplace; Building: type, level, output)
- **Camera:** drag-to-pan, scroll-to-zoom, **1-9 number keys jump to neighborhoods**, mini-map corner overlay
- **HUD parity with v1:** weather indicator, time-of-day cycle bar, activity feed (15 max items, color-coded by severity), tick/day/population/gold counters
- **Asset versioning:** `ASSET_VERSION=v22` constant + `?v=N` on script tag (v1 was on v21)

---

## 8 · Demonstration definition of done — the 4 layers

### Layer 1 — Tech-signature animations
All 9 neighborhoods have their tech-signature animation continuously running (per § 3). No interaction required. Failure modes: animation falls back gracefully if data isn't flowing (e.g., empty roads when Kafka is down).

### Layer 2 — Live numbers overlay
- `LiveNumbersHUD.vue` — discreet panels per neighborhood showing real `/metrics` values
- Numbers update every 2s
- Hover any number for one-line explanation (e.g., "p99 latency = 99% of validations completed in this time or faster")
- Sources: per-service `/metrics` endpoints (Prometheus format), aggregated by Cartographer behind a `/api/v2/metrics` GraphQL field

### Layer 3 — Flow trace mode
- `FlowTraceMode.vue` — toggle in HUD with three options: "Trace: Market Trade" / "Trace: AI Dialogue" / "Trace: Validation"
- When active:
  - Selected flow path highlights orange across the map
  - Side panel shows hop-by-hop latency breakdown
  - A periodic event fires the flow visibly so the visitor watches it traverse in real time
- Trace data sourced from Jaeger spans via Cartographer's `/api/v2/trace/{flow}` endpoint

### Layer 4 — Proof sidebar
- `ProofSidebar.vue` — collapsible right-side panel
- Shows last `make proof-*` results per service: timestamp + PROOF PASS/FAIL + headline number
- "Re-run proof" button per service (rate-limited to 1/min per visitor IP)
- Proof outputs sourced from a `/api/v2/proofs` endpoint that re-runs the targets against the live deploy

**Acceptance:** A first-time visitor lands on qtown.ai. Within 30 seconds they see ambient activity in all 9 neighborhoods including the headline animations (Cartographer fan-out, Market concurrency lines, Fortress gate). Within 60 seconds they see all 3 flagship flows produce visible activity. They can toggle flow-trace mode and watch a Market Trade traverse all 7 hops with per-hop latency. The proof sidebar shows PROOF PASS for every service that has a proof target. They never had to read a README.

---

## 9 · Deployment definition of done

- **Hosting target:** Railway hybrid demo-tier, no HA, total monthly cost <$60
- **Service plan (Railway):**
  - All 9 application services as separate Railway services
  - Postgres: managed plugin
  - Redis: managed plugin
  - Kafka: Docker service, single broker, KRaft mode, persistent volume
  - Elasticsearch: Docker service, 512MB JVM heap, persistent volume
  - Optionally (Phase 8 extension): Jaeger + Prometheus + Grafana + Loki as Railway Docker services
- **Networking:** Private networking via `{service-name}.railway.internal`; only the dashboard exposed publicly
- **Secrets:** env vars per service via Railway env, no `.env` in repo
- **Domains:**
  - `qtown.ai` → dashboard
  - `v1.qtown.ai` → existing v1 service (unchanged)
- **Monitoring:** simple cost alert at >$60/mo via Railway billing webhook → Telegram
- **Rollback plan:** if v2 deploy goes sideways, DNS flip back to landing page is one Railway dashboard click; v1.qtown.ai is independent and unaffected

**Acceptance for the live qtown.ai:**
- `curl https://qtown.ai` returns dashboard HTML within 2s
- All 9 neighborhood animations visible within 30s of page load
- All 3 flagship flows produce activity within 60s
- Flow-trace mode works on live data
- `/proofs` panel renders with non-stale results
- `curl https://v1.qtown.ai` continues to return v1 dashboard
- Railway monthly bill at next month's billing date is <$60

---

## 10 · Out of scope (Phase 7+ candidates)

These are **explicitly NOT** part of v2 done — they're future work:
- High availability (multi-broker Kafka, ES cluster, multi-region)
- Authentication / authorization on internal RPCs
- Rate limiting on Cartographer beyond the proof re-run gate
- Threat modeling / security review
- OpenTelemetry span emission from services (Jaeger configured but unused at v2 done)
- Performance under sustained load beyond the proof targets
- Cost optimization beyond the demo-tier baseline
- Mobile-responsive dashboard (desktop only at v2 done)
- Internationalization
- Player accounts / progression / save state
- Asset-pipeline regenerating sprites in production (the seed set is human-curated upfront in Phase 2)

These boundaries keep v2 done finite and shippable. New asks land in `docs/v2-spec.md` as a "Phase 7+" appendix or in a separate spec doc.
