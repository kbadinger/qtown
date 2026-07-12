# Qtown v2 Area / Tech / Teaching Plan

> **Status:** Draft locked as the Step 1 planning frame on 2026-06-15.  
> **Purpose:** Before deriving assets or building rooms, define what each Qtown area is *for*: the technology it demonstrates, the job-skill story it supports, the teaching surface it exposes, and the downstream asset implications.

## North Star

Qtown v2 is not just an AI-town game/sim. It is a **portfolio-grade AI systems lab disguised as a living town**.

Kevin should be able to point to Qtown in an interview and say:

> “I have built that kind of AI system. Here is the area of Qtown where it runs, here is the code, here is the proof, and here is the teaching view that explains how it works.”

That means every important area must earn its place by demonstrating at least one serious capability:

- ML / predictive modeling
- LLM systems / RAG / evals
- autonomous agents / local model orchestration
- distributed systems / event streaming / real-time services
- observability / tracing / reliability
- safety / verification / policy enforcement
- multimodal generation / asset pipelines
- security / auth / threat modeling
- polyglot engineering across Python, Go, Rust, TypeScript, protobuf, infra, and data tooling

The town map is therefore a **curriculum map** as much as a product map.

---

## Planning Rule

Do **not** start from assets.

The correct order is:

1. **Lock the areas that matter.**
2. **Define the technology demonstrated by each area.**
3. **Define what that area teaches.**
4. **Define the visible behaviors required to prove it.**
5. **Derive rooms, NPC roles, props, and UI/proof panels.**
6. **Only then generate assets.**
7. **Only then build implementation stories.**

Assets are downstream of pedagogy and tech goals.

---

## Teaching Surface Pattern

Each area should contain three layers:

### 1. Simulation Layer

The actual in-world behavior.

Examples:

- Traders exchange goods.
- NPCs gossip in the tavern.
- The clinic predicts burnout risk.
- The tower displays service health.

### 2. Proof Layer

A panel or room feature that shows the underlying system is real.

Examples:

- p95/p99 latency graph
- Kafka topic events
- retrieved RAG citations
- ML feature importance
- model evaluation score
- trace waterfall
- policy decision log

### 3. Teaching Layer

A human-readable explanation of the concept.

Examples:

- “What is an embedding?”
- “How does an order book match trades?”
- “What is drift in ML?”
- “Why use WASM for deterministic validation?”
- “How do OpenTelemetry traces show cross-service latency?”

This layer is what turns Qtown from a demo into a learning artifact.

---

## Tech Pillars

### Pillar A — ML / Predictive Modeling

**Goal:** Qtown must demonstrate real machine learning beyond LLM prompting.

Candidate techniques:

- feature extraction from sim history
- supervised risk prediction
- anomaly detection
- demand forecasting
- recommender systems
- evaluation metrics
- model lifecycle / artifact versioning
- drift monitoring

Best-fit areas:

- Clinic
- Market
- Warehouse
- Bank
- Tower

### Pillar B — LLM / RAG / Agent Intelligence

**Goal:** Qtown must demonstrate modern LLM application architecture, not generic chatbot wrappers.

Candidate techniques:

- embeddings
- vector search
- retrieval-augmented generation
- structured outputs
- tool calling
- memory and summarization
- golden evals / rubric evals
- local model routing

Best-fit areas:

- Academy
- Tavern
- Workshop
- Library-like parts of Academy

### Pillar C — Autonomous Agents / Coding Agents

**Goal:** Qtown must demonstrate agentic work loops under human supervision.

Candidate techniques:

- task queues
- model routing
- local Ollama worker loop
- code generation
- test execution
- human intervention protocol
- patch review
- cleanup passes

Best-fit areas:

- Workshop / Maker Space
- Tower control room

### Pillar D — Distributed Systems / Real-Time Backend

**Goal:** Qtown must demonstrate production-ish backend engineering across multiple services.

Candidate techniques:

- gRPC
- Kafka
- GraphQL gateway
- event sourcing
- service contracts
- p99 latency measurement
- load tests
- idempotent consumers
- backpressure / lag

Best-fit areas:

- Market
- Warehouse
- Town Square / Overhead Map
- Tower

### Pillar E — Safety / Verification / Governance

**Goal:** Qtown must demonstrate safe AI/system behavior, explainability, and validation.

Candidate techniques:

- WASM validation
- policy-as-code
- audit logs
- deterministic replay
- rule explanations
- dispute resolution workflows
- threat modeling

Best-fit areas:

- Validation Citadel
- Courthouse
- Town Hall
- Restoration Center

### Pillar F — Multimodal / Generative Asset Pipeline

**Goal:** Qtown must demonstrate AI generation workflows beyond text.

Candidate techniques:

- ComfyUI
- Flux
- LoRA selection
- IP-Adapter for identity consistency
- ControlNet/OpenPose for pose control
- generated asset manifests
- visual QA contact sheets
- possible CLIP/image-embedding QA

Best-fit areas:

- Asset pipeline itself
- Town Square
- all visible building interiors
- possible in-world Art Studio or Workshop explainer

### Pillar G — Security / Platform / Operations

**Goal:** Qtown must demonstrate that Kevin understands deployability and trust boundaries.

Candidate techniques:

- authn/authz
- rate limits
- secret scanning
- Trivy/dependency scans
- service-to-service policy
- gateway hardening
- threat model
- CI gates

Best-fit areas:

- Validation Citadel
- Tower
- Gateway / Town Gate metaphor

---

## Area Matrix

### 1. Town Square / Overhead Map

**Product role:** The front door to the living town.

**Primary tech demonstrated:**

- real-time state aggregation
- spatial simulation
- GraphQL/API gateway fanout
- asset manifest usage
- live frontend rendering

**Languages / stack:**

- TypeScript / Nuxt / Vue
- GraphQL
- protobuf contracts as applicable
- backend service aggregation

**Teaching goal:**

Explain how distributed services become one coherent UI state.

**Proof surface:**

- live service/source badges per visible entity
- “this NPC position came from town-core at tick N”
- event stream feed
- stale-data indicators

**Visible behavior:**

- NPCs move between areas
- buildings indicate live/dormant status
- clickable buildings route to interiors

**Asset implications:**

- overhead map tiles
- building exteriors for all kept areas
- overhead NPC sprites
- props / roads / terrain
- status/proof UI overlays

---

### 2. Tavern

**Product role:** Social hub where AI agents feel alive.

**Primary tech demonstrated:**

- multi-agent dialogue
- NPC memory
- relationship/social graph
- event summarization
- grounded LLM behavior

**Languages / stack:**

- Python for agent/dialogue services
- vector/memory store as selected
- TypeScript frontend for room display

**Teaching goal:**

Teach how LLM agents can be grounded in state and memory instead of producing generic roleplay.

**Proof surface:**

- current conversation context
- memory snippets used
- relationship deltas
- “why this NPC said this” explanation
- dialogue eval score / consistency checks

**Visible behavior:**

- NPCs talk about recent town events
- rumors spread
- relationship scores change
- tavern conversations influence future behavior

**Asset implications:**

- tavern exterior
- bar room, kitchen, cellar backgrounds
- sitting/talking/drinking/eating sprites
- relationship/proof panel UI
- speech bubbles / conversation log UI

---

### 3. Market

**Product role:** Economic engine and real-time systems showcase.

**Primary tech demonstrated:**

- Go order book / matching engine
- gRPC service interfaces
- Kafka trade events
- load testing
- p99 latency proof
- economic simulation

**Languages / stack:**

- Go
- protobuf / gRPC
- Kafka
- k6 or ghz load testing
- TypeScript dashboard integration

**Teaching goal:**

Teach how real-time markets, matching engines, and latency claims work.

**Proof surface:**

- order book depth
- recent trades
- p50/p95/p99 latency
- Kafka trade events
- load test report link

**Visible behavior:**

- traders haggle
- prices move
- scarcity affects behavior
- trade settlement appears in logs/ledger

**Asset implications:**

- market exterior
- trading floor background
- stockroom background
- trader/farmer/customer poses
- price board / market display props
- proof panel for latency/order book

---

### 4. Academy

**Product role:** Learning/RAG/evals hub.

**Primary tech demonstrated:**

- RAG
- embeddings
- vector search
- LLM tutoring
- eval harness
- structured educational outputs

**Languages / stack:**

- Python
- vector DB or pgvector/Qdrant/LanceDB
- local Ollama endpoint
- eval tooling
- TypeScript frontend

**Teaching goal:**

Teach how RAG works: chunking, embeddings, retrieval, citations, generation, and evaluation.

**Proof surface:**

- retrieved chunks
- citation links
- embedding similarity scores
- answer rubric score
- eval pass/fail history

**Visible behavior:**

- scholar teaches students
- students ask questions grounded in town history
- lesson content cites retrieved sources
- evaluations show whether answers improved

**Asset implications:**

- academy exterior
- classroom, library, laboratory backgrounds
- scholar/student teaching/studying/reading sprites
- retrieval/citation proof panel
- blackboard/hologram teaching props

---

### 5. Clinic

**Product role:** ML/prediction teaching area.

**Primary tech demonstrated:**

- supervised ML or anomaly detection
- feature engineering from simulation history
- risk scoring
- model evaluation
- model drift / monitoring

**Languages / stack:**

- Python
- pandas / scikit-learn or LightGBM/XGBoost
- FastAPI or service endpoint
- model artifact storage
- TypeScript visualization

**Teaching goal:**

Teach how classical ML works end-to-end: dataset → features → train/test split → model → metrics → prediction → monitoring.

**Proof surface:**

- feature vector for selected NPC
- predicted risk score
- top contributing features
- precision/recall/AUC or relevant metrics
- model version and training date
- “prediction vs outcome” history

**Visible behavior:**

- healer checks NPC risk
- high-risk NPC gets intervention recommendation
- town sees whether intervention worked

**Asset implications:**

- clinic exterior
- examination and dispensary backgrounds
- healer examining/treating/preparing sprites
- diagnostic dashboard prop
- ML explainer/proof panel UI

---

### 6. Workshop / Maker Space

**Product role:** Agentic work and build/test/repair loop.

**Primary tech demonstrated:**

- autonomous coding agents
- local model orchestration
- task decomposition
- tests as guardrails
- human-in-the-loop review

**Languages / stack:**

- Python for orchestrator logic
- shell/git/test tooling
- remote Ollama at `http://100.99.74.72:11434`
- mixed repo languages depending on story

**Teaching goal:**

Teach how coding agents are useful but bounded: they need tests, scopes, review, and cleanup.

**Proof surface:**

- current agent task
- prompt/story context
- generated diff
- tests run
- failure/retry count
- human intervention notes

**Visible behavior:**

- artisan/agent works at benches
- tasks move through queued/running/review/done
- failed jobs require human intervention

**Asset implications:**

- workshop exterior
- maker-space interior
- crafting/fixing/learning/collaborating sprites
- task-board UI prop
- diff/test result proof panel

---

### 7. Warehouse

**Product role:** Logistics and event streaming showcase.

**Primary tech demonstrated:**

- inventory modeling
- Kafka topology
- topic lag / throughput
- idempotent consumers
- supply chain simulation

**Languages / stack:**

- likely Go/Python services
- Kafka
- Prometheus/kafka-exporter
- TypeScript dashboard

**Teaching goal:**

Teach how event-driven systems move state through a distributed architecture.

**Proof surface:**

- topic map
- lag indicators
- inventory movement events
- replay/idempotency explanation

**Visible behavior:**

- goods move into/out of storage
- market stock changes
- lag or stockout visibly affects town behavior

**Asset implications:**

- warehouse exterior
- storage floor background
- moving/organizing sprites
- crates/shelves/lanes props
- Kafka/topic proof panel

---

### 8. Bank

**Product role:** Ledger, consistency, and anomaly/fraud detection.

**Primary tech demonstrated:**

- append-only ledger
- transaction reconciliation
- consistency checks
- fraud/anomaly detection
- auditability

**Languages / stack:**

- Go or Python service
- database/ledger design
- ML anomaly model optional
- TypeScript proof UI

**Teaching goal:**

Teach why financial systems need ledgers, reconciliation, and anomaly detection.

**Proof surface:**

- transaction ledger
- balance reconciliation
- suspicious transaction score
- invariant checks

**Visible behavior:**

- NPCs transact
- suspicious activity is flagged
- ledger entries link back to market trades

**Asset implications:**

- bank exterior
- lobby and vault backgrounds
- official/trader/guard poses
- ledger/vault UI props
- anomaly proof panel

---

### 9. Validation Citadel

**Product role:** Deterministic validation and safety boundary.

**Primary tech demonstrated:**

- Rust
- WASM
- validation rules
- deterministic execution
- audit logs
- safety boundaries

**Languages / stack:**

- Rust
- WASM
- protobuf contracts
- validation service
- TypeScript visualization

**Teaching goal:**

Teach why some logic should be deterministic, isolated, and auditable.

**Proof surface:**

- input event
- validation rule applied
- WASM module/version
- pass/fail result
- audit trail
- unsafe boundary notes

**Visible behavior:**

- contracts/trades/laws are validated
- invalid transitions are rejected
- validators certify records

**Asset implications:**

- validation citadel exterior
- verification chamber and arbitration backgrounds
- official validating/reviewing/certifying sprites
- holographic ledger props
- validation proof panel

---

### 10. Courthouse

**Product role:** Explainable dispute resolution.

**Primary tech demonstrated:**

- policy-as-code
- evidence/provenance linking
- explainable decision generation
- rule interpretation
- appeal/review workflows

**Languages / stack:**

- Python or TypeScript policy layer
- event log queries
- LLM explanation generation guarded by source evidence

**Teaching goal:**

Teach the difference between deterministic rules, evidence, and AI-generated explanations.

**Proof surface:**

- evidence list
- rule/policy matched
- explanation with citations
- appeal/review status

**Visible behavior:**

- NPC files dispute
- evidence is reviewed
- decision is explained

**Asset implications:**

- courthouse exterior
- courtroom background
- judging/testifying/listening sprites
- evidence display props
- explanation/provenance panel

---

### 11. Town Hall

**Product role:** Governance and collective decision-making.

**Primary tech demonstrated:**

- proposal lifecycle
- voting/consensus
- preference modeling
- policy changes affecting simulation
- decision ledger

**Languages / stack:**

- Python/TypeScript service logic
- event sourcing
- dashboard UI

**Teaching goal:**

Teach how governance workflows become state machines and how policy changes propagate through a system.

**Proof surface:**

- proposal state machine
- vote tally
- decision ledger
- downstream policy diff

**Visible behavior:**

- proposals are debated
- NPCs vote
- accepted policy changes town behavior

**Asset implications:**

- town hall exterior
- assembly and office backgrounds
- speaking/listening/debating sprites
- voting/proposal board props

---

### 12. Restoration Center

**Product role:** Behavioral change and restorative AI society loop.

**Primary tech demonstrated:**

- social behavior modeling
- intervention tracking
- memory updates
- conflict resolution outcomes
- longitudinal evaluation

**Languages / stack:**

- Python for behavior model
- knowledge graph / relationship store
- dashboard timeline UI

**Teaching goal:**

Teach how long-term agent behavior can change through interventions and memory updates.

**Proof surface:**

- incident timeline
- intervention chosen
- relationship/memory deltas
- future behavior comparison

**Visible behavior:**

- conflict leads to mediation
- agent reflects or restores trust
- relationships update over time

**Asset implications:**

- restoration center exterior
- counseling and reflection garden backgrounds
- counseling/listening/restoring/reflecting sprites
- intervention timeline UI

---

### 13. Tower / Observatory

**Product role:** System observability and operator control room.

**Primary tech demonstrated:**

- OpenTelemetry
- traces
- metrics
- logs
- health checks
- service dependency graph
- failure injection/recovery

**Languages / stack:**

- OTel SDKs across services
- Prometheus/Grafana or embedded dashboard views
- TypeScript visualization

**Teaching goal:**

Teach how to debug distributed systems using traces, metrics, and health models.

**Proof surface:**

- 9-service health matrix
- trace waterfall
- error budget / latency indicators
- Kafka lag summaries
- failure/recovery timeline

**Visible behavior:**

- tower operators observe town/system state
- service failures visibly degrade areas
- recovery restores town behavior

**Asset implications:**

- tower exterior
- observation deck background
- observing/communicating sprites
- control panels/holographic map props
- observability proof panel

---

### 14. Farm / Bakery / Blacksmith Production Chain

**Product role:** Resource production and transformation loop.

**Primary tech demonstrated:**

- domain modeling
- production graphs
- dependency propagation
- scheduling/planning
- emergent economic behavior

**Languages / stack:**

- Python/Go simulation services
- event streaming
- database-backed state

**Teaching goal:**

Teach how simple domain rules compound into emergent system behavior.

**Proof surface:**

- recipe/resource graph
- production queue
- input/output events
- shortage propagation

**Visible behavior:**

- farm produces crops
- bakery transforms crops into bread
- blacksmith repairs/tools production affects other work
- market prices reflect supply

**Asset implications:**

- farm, bakery, blacksmith exteriors
- barn/greenhouse/bakehouse/shopfront/forge/showroom backgrounds
- farmer/cook/smith/artisan poses
- resource graph UI panel

---

### 15. Temple / Park / Theater Culture Loop

**Product role:** Non-economic social life and emotional state.

**Primary tech demonstrated:**

- sentiment/morale modeling
- narrative event generation
- preference modeling
- social cohesion metrics
- recommender-like event selection

**Languages / stack:**

- Python simulation logic
- LLM summarization/narrative optional
- TypeScript UI

**Teaching goal:**

Teach that simulations need human/social variables, not just transactions and jobs.

**Proof surface:**

- morale score
- social cohesion metric
- event recommendation rationale
- narrative summary with source events

**Visible behavior:**

- theater performances affect town mood
- park visits improve relationships
- temple gatherings change morale/social state

**Asset implications:**

- temple/theater/park exteriors
- sanctuary/garden/stage/audience backgrounds
- watching/applauding/performing/meditating/walking sprites
- culture/morale proof panel

---

## Missing or Thin Technology Coverage

Qtown already has substantial distributed-systems and agentic-coding ambition. The biggest gaps to intentionally add are:

### 1. Real ML beyond LLMs

Best homes:

- Clinic: NPC risk/burnout/health prediction
- Market: demand/price forecasting
- Warehouse: stockout prediction
- Bank: fraud/anomaly detection

Minimum credible deliverable:

- dataset generated from sim history
- feature pipeline
- trained model
- metrics report
- model artifact/version
- inference endpoint
- dashboard explainer showing prediction + features

### 2. RAG + evals that are demonstrably real

Best home:

- Academy

Minimum credible deliverable:

- corpus/chunks
- embeddings
- vector index
- retrieval endpoint
- citations
- golden eval set
- CI eval report

### 3. Knowledge graph / agent memory

Best homes:

- Tavern
- Academy
- Courthouse
- Town Hall

Minimum credible deliverable:

- entity/event/relationship graph
- memory update pipeline
- query endpoint
- provenance links

### 4. Multimodal QA

Best home:

- Asset pipeline / Workshop

Minimum credible deliverable:

- contact sheets
- style checklist
- possible CLIP/image-embedding check
- prompt/seed/model provenance

### 5. Security / gateway hardening

Best homes:

- Validation Citadel
- Tower

Minimum credible deliverable:

- threat model
- auth/rate-limit plan
- gitleaks/trivy/dependency CI gates
- service trust-boundary diagram

### 6. MCP / external agent interface

Best home:

- Tower / Town Hall

Minimum credible deliverable:

- MCP server exposing town state
- tools for querying NPCs/events/market/health
- external-agent demo using the server

---

## Asset Derivation Inputs

Only after this plan is reviewed should we derive assets.

For each area, asset derivation must capture:

1. Exterior building asset
2. Interior room backgrounds
3. NPC roles present
4. Activity pose sprites
5. Room props
6. Teaching/proof-panel UI elements
7. Any area-specific diagrams or overlays
8. Whether the asset is required for first visible build, later complete build, or teaching-only overlay

The asset inventory should therefore be generated from this shape:

```yaml
area:
  id: clinic
  tech_pillar: ML / predictive modeling
  teaching_goal: classical ML lifecycle
  rooms:
    - examination
    - dispensary
  npc_roles:
    - healer
    - patient
  activity_poses:
    - examining
    - treating
    - preparing
  proof_ui:
    - feature_vector_panel
    - risk_score_panel
    - model_metrics_panel
  props:
    - diagnostic_table
    - model_card_display
```

---

## Next Planning Deliverables

### Deliverable 1 — Area Lock Review

Review every area in this doc and classify it:

- `core`: must exist for Qtown v2’s portfolio goal
- `supporting`: valuable but can be lighter initially
- `merge`: combine with another area
- `defer`: not needed for the main tech story yet
- `rename`: concept is right, framing needs adjustment

### Deliverable 2 — Area-to-Asset Manifest

After the area lock review, produce:

`docs/plans/AREA-ASSET-MANIFEST.md`

This should list every required asset by area:

- exteriors
- rooms
- NPC roles
- activity poses
- props
- proof/teaching panels

### Deliverable 3 — Build Sequencing Plan

Only after the asset manifest exists, produce:

`docs/plans/BUILD-SEQUENCE.md`

This should decide which areas build first based on:

- portfolio value
- dependency order
- asset readiness
- service readiness
- teaching value

---

## Core Decision

Qtown areas are not decorative. They are **technical proof rooms**.

If an area does not demonstrate, teach, or support a real capability, it should be renamed, merged, or cut. If a capability matters for Kevin’s AI-career story and has no area, the map is incomplete.
