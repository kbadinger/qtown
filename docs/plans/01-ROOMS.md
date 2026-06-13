# Plan 01 — Rooms: Building→Service Map, Per-Room Spec, Sim Model, Drill-In UX

> Part of the v2 plan pack (`00-MASTER-PLAN.md`). Owns Phase 7-B.
> Locked inputs: `asset-gen/taxonomy.yaml` (19 buildings, 35 rooms, 10 NPC roles,
> `locked: true`), `asset-gen/style-spec.md`, `docs/v2-phase-7-rooms.md`.
> This doc answers the seed's 7 open design questions and turns the taxonomy into
> buildable specs with story IDs.

## 1. The building → backing-system map

The thesis from the master plan: every building demonstrates a real part of the stack.
"Sim" means the room is driven by town-core simulation state (still real data — NPC
needs/goals/actions — just not a dedicated microservice).

| Building | Backing system | What the room *visibly proves* |
|---|---|---|
| **Tavern** | `tavern` (TS · WebSocket + Redis + Kafka) | Real-time event broadcast: every drink poured is a real Kafka→WS event reaching your browser |
| **Market** | `market-district` (Go · gRPC order book) | Real orders matched by the Go engine; measured match latency on the holo-board |
| **Academy** | `academy` (Python · LangGraph + Ollama) + `library` (Python · Elasticsearch) | LLM-generated dialogue with visible RAG citations; the library room IS the search service |
| **Validation Citadel** | `fortress` (Rust · WASM sandbox) | Live accept/reject verdicts from the WASM validators |
| **Town Hall** | `town-core` (Python · FastAPI tick loop) | The tick loop, elections, policies — the sim's beating heart |
| **Tower** | Observability stack (Jaeger/Prometheus/Grafana) + `cartographer` (GraphQL gateway) | A real distributed trace of one trade fanning across 5 services |
| **Warehouse** | Kafka (27 topics) | The event backbone: storage lanes = topics, holo-tags = live lag/throughput |
| **Clinic** | Health/readiness model (Plan 03 §3) | The 9-service health board; the healer literally examines services |
| **Workshop** | `asset-pipeline` (Python · ComfyUI) | Sprites being generated; the skill-share board shows the newest generated assets |
| **Bank** | town-core economy (wallets, trade settlements) | Real wallet deltas from `economy.trade.settled`; the vault holds world snapshots (P6-020) |
| **Theater** | `academy` content gen + newspaper router | Generated narratives performed on stage; tonight's show = today's newspaper |
| **Temple** | town-core gossip/rumor graph | The town's collective belief state, visualized in the sanctuary |
| **Courthouse** | town-core justice events + validation rejections | What happens after fortress says "no" — rejected actions adjudicated |
| **Restoration Center** | town-core crime/justice loop | Restorative outcomes for NPC offenders (sim) |
| **Home** (×N) | town-core NPC state | One NPC's needs/goals/sleep cycle up close (sim) |
| **Bakery / Blacksmith / Farm** | town-core production chains | Goods produced here are the goods traded at Market (sim) |
| **Park** | — overhead only (`overhead_only: true`) | — |

Rule for Opus: **a room may not fake its feed.** If the backing data isn't flowing yet
(Phase 6 gate not green), the room ships in "dormant" mode — visibly labeled, NPCs idle,
proof panel says "awaiting Phase 6 wiring" — never with fabricated activity. (CLAUDE.md
rule 10: no fake data.)

## 2. Sim-data model (town-core)

### 2.1 Room state

Buildings get rooms; NPCs get a location triple. New module
`services/town-core/engine/simulation/rooms.py`:

- `Room {building_id, room_id, activities: [str], capacity: int}` — loaded at startup
  from a checked-in `rooms.yaml` generated from `asset-gen/taxonomy.yaml` (single source
  of truth; a small script syncs them, never hand-duplicate).
- NPC gains `current_building`, `current_room`, `current_activity`, `activity_since`.
- **Activity mapping:** the sim already produces NPC actions (needs/goals framework in
  `engine/simulation/npcs.py`). A deterministic mapping table converts existing action
  types → (building, room, activity): e.g. action `eat` at tavern → (`tavern`,
  `bar_room`, `eating`); action `work` for role `cook` → (`tavern`, `kitchen`,
  `cooking`). The table lives in `rooms.yaml` next to the room defs. No new AI here —
  it's a projection of state the sim already computes.

### 2.2 Propagation (design choice from the seed, decided)

**Snapshot over GraphQL, deltas over the existing tavern WebSocket. No new transport.**

- town-core emits `qtown.town.room.activity` to Kafka once per tick (30s), one message
  per *occupied* room: `{building_id, room_id, occupants: [{npc_id, role, activity,
  since}], tick}`.
- tavern already consumes Kafka and broadcasts to WS channels — add channel
  `room:<building_id>` (pattern exists in `services/tavern/src/kafka-consumer.ts`).
- cartographer adds query `roomState(buildingId)` → town-core gRPC (the P6-001 server)
  for the initial page load; the WS channel keeps it live afterward.
- New proto: `proto/qtown/town/v1/rooms.proto` — `RoomState`, `Occupant`,
  `GetRoomStateRequest/Response`. Run `buf` codegen for Python + TS.

Why this shape: it reuses every pipe Phase 6 just fixed (gRPC snapshot path, Kafka topic,
tavern fan-out) — the rooms feature becomes a continuous proof that the Phase 6 wiring
works. One new topic, one new RPC, zero new infrastructure.

## 3. The 7 open design questions — answered

1. **Art style?** Locked: solarpunk + tech accents (`asset-gen/style-spec.md`, Guardian
   `2f7c20c8`). Not re-open.
2. **Room taxonomy?** Locked: `asset-gen/taxonomy.yaml` — 19 buildings, 35 rooms, the
   per-room activity lists. Not re-open.
3. **Sim-data fidelity?** Sim does NOT currently track rooms. Add the projection layer
   in §2.1 — room granularity is *derived* from existing actions, not a new simulation
   system. (Smallest change that makes rooms truthful.)
4. **Drill-in UX?** Full-page route `/town/<building_id>` (deep-linkable, browser history
   works, shareable — matters for the portfolio use). Animated zoom: overhead camera
   tweens to the building footprint (~400ms), crossfade to interior. Esc / back-arrow /
   browser-back zooms out. No modal — interiors are a place, not a popup.
5. **Render strategy?** One convention for all buildings: **side-view "dollhouse"
   interior, 2.5D parallax** (background plate → mid-ground props → NPC layer →
   foreground accents at differing scroll factors). Matches the locked asset classes
   (side-view 1280×720 backgrounds, 384×512 front-facing activity poses). A new
   `InteriorRenderer.client.vue` PixiJS scene, separate from the overhead isometric
   renderer. Per-building variation comes from the art + props + panel content, not from
   different view conventions — consistency reads as polish.
6. **NPC pose count?** Static frames: 6 overhead poses per role (locked in taxonomy) +
   curated interior activity poses (~2 roles per room-activity, manifest in Plan 02).
   Liveness comes from cheap PixiJS tweens (idle bob ±2px, walk slide, occasional flip)
   and speech bubbles — not sprite-sheet animation. Animation loops are a Phase 8
   option, listed in Plan 05.
7. **Performance budget?** ≤15 NPCs per interior; 60fps on an M-series MacBook /
   30fps floor on mid mobile; ≤2.5MB transferred per room first-visit (WebP: bg
   ~250–400KB + ~8 poses ~60KB each + panel data); rooms lazy-load on drill-in, LRU
   cache of 3 visited rooms; overhead view unloads while inside.

## 4. Per-room specification

Format per room: **Contents** (props beyond the generated background — interactive/
dynamic elements), **Cast** (NPC roles + activities, from taxonomy), **Feed** (where the
data really comes from), **Proof panel** (the in-world holo display; full proof-panel
framework in Plan 03 §4), **Docs hook** (what the ⓘ panel teaches; content spec in
Plan 04 §6).

### 4.1 Flagship five (build first — Gate D)

#### Tavern · `bar_room`
- **Contents:** long copper bar, tap that visibly pours when a drink event fires,
  communal tables, lantern glow cycle synced to town time-of-day, speech bubbles over
  talking NPCs.
- **Cast:** cook (serving), traders/farmers/smiths (drinking, talking, eating, idling),
  child (watching).
- **Feed:** WS channel `room:tavern` (occupants); WS event feed (the tavern service's
  actual broadcasts — trades settled, dialogue generated) renders as bar chatter:
  dialogue events become speech bubbles verbatim.
- **Proof panel:** "Tonight at the Tavern" holo-board — live WS connection count,
  events broadcast in the last 5 min, current Kafka consumer lag. The bar IS the
  broadcast hub, so the board is its own ops dashboard.
- **Docs hook:** how an event travels Kafka → tavern consumer → Redis → WS → this
  browser tab, with the real file paths.

#### Market · `trading_floor`
- **Contents:** stall rows, goods that reflect actual top-of-book symbols, holographic
  price displays showing the real order book (bid/ask ladders), a "trade gong" flash on
  each settlement.
- **Cast:** traders (haggling, selling), others (browsing). A haggle pair animates when
  an order match occurs — the haggle is the match.
- **Feed:** snapshot `roomState(market)` + cartographer `orderBook`/`recentTrades`
  queries (already exist, `dashboard/pages/market.vue`); WS deltas for new settlements
  via `economy.trade.settled` (P6-006).
- **Proof panel:** measured match latency (p50/p99 from the perf run, Plan 03 §2),
  orders/sec right now, total trades settled today. The README's headline claim,
  displayed live, in-world.
- **Docs hook:** the Go order-book matching algorithm and why Go (ADR-01).

#### Academy · `classroom`
- **Contents:** holo-projector at the front rendering the *current generated lesson*
  (live Ollama output, streamed token-by-token if Phase 8 streaming lands), desks,
  plant-lined walls.
- **Cast:** scholar (teaching), children + others (studying, discussing).
- **Feed:** dialogue trigger (P6-011) → academy `GenerateDialogue` → `ai.content.
  generated` (P6-007) → tavern WS. The projector shows the latest generated content with
  its RAG citations (P6-012 library client) listed beneath — the citations are clickable
  and jump to the Library room with that search pre-run.
- **Proof panel:** model name (real Ollama model), tokens/sec of last generation, RAG
  hit count, eval-harness pass rate once Phase 8 lands (Plan 05 G-02).
- **Docs hook:** the LangGraph agent graph (P6-013) rendered as a diagram, and how
  routing picks a model.

#### Validation Citadel · `verification_chamber`
- **Contents:** central holographic ledger showing the live stream of validation
  verdicts (event type, ✅/❌, WASM rule that fired), copper verification stations that
  glow per verdict.
- **Cast:** officials (validating, reviewing), guard (observing).
- **Feed:** `qtown.validation.result` — fortress's real output (works today per audit
  Flow 3); occupancy via `room:validation_citadel`.
- **Proof panel:** validations/min, accept rate, p99 WASM sandbox execution time,
  "unsafe blocks: N, confined to `wasm_sandbox` module" (the truthful claim, post
  P6-003).
- **Docs hook:** why Rust + WASM for untrusted rule execution (ADR-02), what the
  sandbox boundary actually is.

#### Tower · `observation_deck`
- **Contents:** panoramic glass floor with the live overhead town visible below
  (mini-map), central holo-array rendering a **real Jaeger trace waterfall** of the most
  recent market-trade flow; a second holo showing cartographer's GraphQL fan-out (one
  query → 5 services) as animated light beams down into the town toward each building.
- **Cast:** scholar (observing), official (communicating).
- **Feed:** Jaeger HTTP API (query: last trace tagged `flow=market-trade`); Prometheus
  for the beam metrics. Requires Plan 03 §5 (OTel spans in town-core, market-district,
  tavern).
- **Proof panel:** end-to-end trade latency from the trace, span count, services
  touched. This room is the architecture diagram, animated, with real numbers.
- **Docs hook:** distributed tracing across 3 languages; how one trace ID crosses
  gRPC + Kafka boundaries.

### 4.2 Second ring (build after Gate D, order by data-readiness)

#### Warehouse · `storage_floor`
- **Contents:** 27 storage lanes — one per Kafka topic — stacked-goods height = topic
  depth; holo-inventory tags show topic name, msg/min, consumer lag; a "goods cart" NPC
  walks a lane when a message flows.
- **Cast:** artisans/farmers (moving, organizing).
- **Feed:** Kafka admin API metrics scraped by a tiny town-core endpoint (or Prometheus
  kafka-exporter if Plan 03 adds it).
- **Proof panel:** total events today, busiest topic, any topic with zero consumers
  (the audit's "one-sided topology" made visible — should be zero after Phase 6).
- **Docs hook:** the full topic catalog with producer → consumer mapping (Plan 04 §6).

#### Academy · `library`
- **Contents:** shelves + holo-reading consoles; a working search console — visitors
  type a query, real `library` service results render as glowing books pulled from
  shelves.
- **Cast:** scholars (reading, researching).
- **Feed:** library service search endpoints (P6-015) via cartographer.
- **Proof panel:** documents indexed, last index write, search p50; hybrid retrieval
  badge once Plan 05 G-04 lands.
- **Docs hook:** Kafka → Elasticsearch indexing pipeline; BM25 vs vector retrieval.

#### Town Hall · `assembly`
- **Contents:** amphitheater, speaker platform; during a sim election the candidates'
  NPCs stand on stage with live vote tallies on the agenda holo.
- **Cast:** official (speaking), residents (listening, debating).
- **Feed:** town-core elections/policies routers (exist, per audit parity table).
- **Proof panel:** current tick number, ticks/day uptime, election schedule — the tick
  loop's own heartbeat.
- **Docs hook:** the 30s tick loop and the needs/goals/actions framework.

#### Town Hall · `office` — policies/wages admin view; feed: policies + wages routers; proof panel: active policies count, last policy change, wage table.
#### Bank · `lobby` — tellers process real wallet deltas from trade settlements; feed: town-core wallets; proof panel: money supply, settlements today, richest NPC. **`vault`** — world snapshots (P6-020) shelved as glowing archive cells; proof panel: snapshot count, last snapshot age, restore-tested ✅/❌ (Plan 03 §3).
#### Workshop · `workspace` — artisans craft at benches; the skill-share holo-board cycles the latest asset-pipeline outputs (real generated sprite files); feed: asset-pipeline storage listing (P6-016); proof panel: assets generated, last gen duration, queue depth.
#### Theater · `stage`/`audience` — performer NPC "reads" the latest newspaper edition / generated narrative; feed: newspaper router + `ai.content.generated`; proof panel: editions published, stories generated this week.
#### Clinic · `examination` — the healer's holo-diagnostic table is the 9-service health board (Plan 03 §3): green/amber/red per service; a sick "patient" NPC appears when a service is degraded. **`dispensary`** — remediation runbook links per failure mode. Proof panel: overall system status, slowest health check, last incident.
#### Temple · `sanctuary` — the gossip/rumor graph as a constellation above the altar: nodes = NPCs, edges = active rumors; meditating NPCs sit beneath their own belief clusters. Feed: town-core gossip state. Proof panel: active rumors, most-believed rumor, decay rate. **`garden`** — ambient, sim-only.
#### Courthouse · `courtroom` — adjudication of validation rejections: docket = recent ❌ verdicts from fortress that town-core acted on (P6-008/P6-024); proof panel: cases this week, overturn rate.
#### Restoration Center · `counseling`/`reflection_garden` — sim crime/justice outcomes; proof panel: incidents, restoration completion rate.
#### Home · `living_room`/`bedroom`/`kitchen` — drill into a *specific resident NPC*: needs bars, current goal, today's action log; bedroom shows real sleep state during night ticks. Feed: town-core NPC state (npcs router exists).
#### Blacksmith `forge`/`showroom`, Bakery `bakehouse`/`shopfront`, Farm `barn`/`greenhouse` — production-chain rooms: goods produced per tick, inventory, and "sold at Market" counters that reconcile with market-district settlements (a cross-service consistency proof). Sim-fed.
#### Market · `stockroom`, Tavern · `kitchen`/`cellar`, Academy · `laboratory`, Tower (single room), Town Hall office covered above. Academy `laboratory` is reserved as the **eval lab** — it becomes the home of the LLM eval harness visualization when Plan 05 G-02 lands (experiments = eval runs, observing = reading rubric scores).

## 5. Dashboard implementation spec

New/changed files (all under `dashboard/`):

| File | Purpose |
|---|---|
| `pages/town/[building].vue` | Drill-in route; loads building template + room tabs |
| `components/InteriorRenderer.client.vue` | PixiJS side-view scene: parallax layers, NPC sprite layer, tween system |
| `components/ProofPanel.vue` | The holo proof-panel widget — one component, data-driven per room (Plan 03 §4 schema) |
| `components/RoomDocs.vue` | The ⓘ docs drawer per room (Plan 04 §6 content schema) |
| `composables/useRoomState.ts` | snapshot via GraphQL `roomState` + live updates via WS `room:<id>` channel |
| `components/ZoomTransition.client.vue` | overhead→interior camera tween + crossfade |
| overhead view (existing PixiRenderer) | add building click-targets + hover affordance ("press to enter") |

Multi-room buildings render rooms as horizontal sections in one scrollable interior
(dollhouse cutaway) — tabs jump-scroll; occupancy badge per room tab.

Existing pages `market.vue`, `fortress.vue`, `academy.vue` etc. remain as the "ops"
views; each room's proof panel links to the matching ops page ("open the full
dashboard"). Rooms are the show; pages are the console.

## 6. Story list — Phase 7-B (`P7-0xx`, append to `ralph/worklist.json` or run via Opus)

Acceptance criteria are the definition of done; "touches" tells Opus where to start.

**Group 7.1 — Sim room model (ordered)**
| ID | Story | Touches | Done when |
|---|---|---|---|
| P7-001 | Architect room/activity projection in town-core (`rooms.yaml` + `simulation/rooms.py`, action→room mapping) | `services/town-core/engine/simulation/` | Unit test: every taxonomy room reachable; every sim action maps to a valid (building, room, activity) |
| P7-002 | Add `rooms.proto` + buf codegen (Py/TS) | `proto/qtown/town/v1/` | `buf generate` clean; generated stubs imported by town-core + cartographer |
| P7-003 | Emit `qtown.town.room.activity` per tick; register topic in kafka-init | `engine/kafka_producer.py`, `infra/kafka-init.sh` | Topic shows ≥1 msg/tick with valid schema in integration test |
| P7-004 | Implement `GetRoomState` RPC on town-core gRPC server (depends P6-001) | `engine/grpc_server.py` | grpcurl returns occupants matching sim state |

**Group 7.2 — Gateway + fan-out (ordered, after 7.1)**
| ID | Story | Touches | Done when |
|---|---|---|---|
| P7-005 | Cartographer `roomState(buildingId)` query | `services/cartographer/src/resolvers.ts`, schema | GraphQL query returns live data; error is loud if town-core down (P6-017 pattern) |
| P7-006 | Tavern `room:<building>` WS channels from the new topic | `services/tavern/src/kafka-consumer.ts` | WS test client receives room deltas within 1 tick |

**Group 7.3 — Dashboard (∥ within group after 7.2)**
| ID | Story | Touches | Done when |
|---|---|---|---|
| P7-007 | Drill-in route + ZoomTransition + overhead click-targets | `dashboard/pages/town/`, PixiRenderer | Click tavern → animated zoom → interior route; back returns; deep-link works |
| P7-008 | InteriorRenderer: parallax scene + NPC sprite layer + tweens | `components/InteriorRenderer.client.vue` | Renders a room from manifest assets at 60fps with 15 sprites (perf budget §3.7) |
| P7-009 | `useRoomState` composable (snapshot+WS merge) | `composables/` | Occupants update without refresh; dormant mode when feed absent |
| P7-010 | ProofPanel component + per-room panel configs | `components/ProofPanel.vue` | Panel renders real metrics for the 5 flagship rooms; never renders fabricated values |
| P7-011 | RoomDocs drawer + content loader | `components/RoomDocs.vue` | ⓘ opens the room's doc (content from Plan 04 §6) |

**Group 7.4 — Flagship integration (ordered)**
| ID | Story | Touches | Done when |
|---|---|---|---|
| P7-012..016 | Wire flagship five (tavern bar, market floor, classroom, verification chamber, observation deck) — one story each | per §4.1 | Each room shows live data; cross-checked against source API in an e2e test |
| P7-017 | E2E room test: sim tick → room.activity topic → WS → DOM assertion | `tests/e2e/` (Plan 03 layout) | Green in CI; becomes Gate D check |

**Group 7.5 — Second ring (∥, one story per building, P7-018..P7-031)**
Order by data-readiness: warehouse, library, town hall, bank, clinic, workshop, theater,
temple, courthouse, restoration center, home, blacksmith, bakery, farm. Same per-room
done-when pattern: real feed or labeled dormant; proof panel live; docs hook present.

~31 stories total, matching the seed's 25–40 estimate.
