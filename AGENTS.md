# qtown v2 — Agent Handbook

You are a coding agent working on **qtown v2**: a polyglot microservices system disguised as a
living town — a portfolio-grade AI-systems lab. This handbook orients you to what v2 actually is,
where the code lives, and how honest to be about status. Read `CLAUDE.md` (repo root) first for the
one-screen version; read `docs/REQUIREMENTS.md` for the authoritative bar for "done."

> **If you were told qtown is a single Python/SQLite/Jinja2/HTMX monolith with `engine/models.py`,
> one router-per-domain, and a single-loop Ralph — that description is v1, and v1 is archived.**
> That is the wrong architecture to build in. Everything below supersedes it.

## v1 is archived; v2 lives in `services/`

- **v1 (archived, read-only):** the original monolith is under **`v1/`** (FastAPI + SQLAlchemy +
  SQLite + Jinja2/HTMX + PixiJS, plus its own Ralph and snapshots). A partial leftover copy of the
  old sim also sits at repo-root **`engine/`**. Do not add features to either — they exist for
  reference and parity checks only.
- **v2 (where you work):** **`services/`** holds 8 backend services; **`dashboard/`** is the
  frontend. They are stitched together by a **Kafka event backbone** and **gRPC/protobuf contracts**
  in **`proto/qtown/`**. This is a distributed system, not a monolith with a nametag.

## The v2 system

### 8 services + dashboard

| # | Service | Language / stack | Role | Default port |
|---|---|---|---|---|
| 1 | **town-core** | Python · FastAPI | The sim: tick loop (30s), NPCs/needs/goals, buildings, economy; Kafka producer | 8000 |
| 2 | **market-district** | Go · gRPC | Order-book / matching engine; emits trade events | 50051 |
| 3 | **fortress** | Rust · WASM + gRPC + Kafka | Deterministic validation / safety boundary ("Validation Citadel") | 8080 / 50052 |
| 4 | **academy** | Python · LangGraph + Ollama | LLM/RAG dialogue & tutoring; local-model routing | 8001 |
| 5 | **library** | Python · Elasticsearch | Search / indexing / RAG corpus store | 8003 |
| 6 | **tavern** | TypeScript · WebSocket + Redis + Kafka | Real-time social broadcast to clients | 3001 |
| 7 | **cartographer** | TypeScript · Apollo GraphQL | Gateway: GraphQL fan-out over gRPC to backing services | 4000 |
| 8 | **asset-pipeline** | Python · ComfyUI + Kafka | Generative sprite/asset pipeline | — |
|   | **dashboard** | Nuxt 3 / Vue | Frontend; talks GraphQL to cartographer + WebSocket to tavern | 3000 (see status) |

**Event backbone:** services communicate over **Kafka** topics (e.g. `qtown.economy.trade.settled`,
`qtown.ai.content.generated`, `qtown.validation.result`) *and* synchronous **gRPC** where a
request/response is needed. Wire contracts are defined once in **`proto/qtown/`**
(`market.proto`, `academy.proto`, `fortress.proto`, `town_core.proto`, `common.proto`) and codegen'd
per language — `proto/` is the intended single source of truth for cross-service shapes.

### The 15 areas

The *product* is framed as **15 "areas"** of a town (Market, Academy, Tavern, Validation Citadel,
Tower/Observatory, Clinic, Workshop, Bank, Warehouse, Courthouse, Town Hall, etc.). Each area is a
"technical proof room" meant to demonstrate one real capability (distributed systems, RAG, classical
ML, observability, safety/WASM, agentic loops, generative pipelines). **Areas do not map 1:1 to
services** — one service can back several areas, and some areas span multiple services. The
authoritative definition of every area — its tech pillar, what it must teach, and what it must
prove — is in **`docs/plans/AREA-TECH-TEACHING-PLAN.md`**. Start there when a task names an "area."

## Honest status — real vs planned

Be truthful about what works. The current honest audit is **`docs/v2-audit.md`**; treat it as the
source of truth for status and read it before assuming anything is wired.

- **Per-service:** the services are **scaffolded, not fully delivered.** Some logic is real
  (town-core tick loop, market-district order-book matching, fortress Kafka consumer + WASM sandbox,
  academy Ollama client, cartographer resolvers, tavern WebSocket layer); other parts are shallow or
  stubbed (e.g. town-core has **no gRPC server** yet; market-district's gRPC handler is **not
  registered**; fortress gRPC codegen is **pending**; academy's LangGraph graph and Kafka producer
  are **not built**; library's search/index pipeline is **unverified**).
- **Cross-service flows:** of the three flagship end-to-end flows — **Market Trade, AI Dialogue,
  Validation — 0/3 currently work end-to-end.** The bricks exist; the mortar between them (missing
  gRPC servers, one-sided Kafka topology, no origination entrypoints) is being wired now.
- **The AI layer is under repair.** Academy passes unit tests but paths exist where it never
  actually calls the model; fixing that facade is active WAVE-0 work (see `06-FABLE-PLAN.md`).
- **Not deployed.** No v2 service is hosted anywhere yet.

When you touch anything, **mark real vs planned honestly** and do not present aspiration as fact.
An area/service is "done" only per the per-area DoD in `docs/REQUIREMENTS.md §3.1` (wired · gated ·
proven with real data · explained · documented · honest) — not when its own unit tests pass.

## The three inviolable principles (docs/REQUIREMENTS.md §2)

These gate every increment. Violating any one means it is **not done**:

1. **No fabricated data, ever.** A metric whose source errors renders as `—`, never a plausible
   made-up number. Do not introduce `Math.random()` or hardcoded numbers into any proof/metric path.
2. **No claim before its gate.** README / landing / proof-panel claims stay at "in flight" wording
   until the CI gate that measures them is green. Don't assert a perf or safety number you can't
   point at a committed measurement for.
3. **Real, not scaffolded.** A flow is done only when it works end-to-end with a green CI gate.
   Until then the area ships in **dormant** mode — visibly labeled, NPCs idle, proof panel says
   "awaiting wiring" — never faking activity.

## Working conventions

- **Contracts first.** Cross-service shapes live in `proto/qtown/`. Change the proto, regenerate
  (`make proto`), then implement — don't hand-write divergent message types per service.
- **Stay in the right service.** A task usually targets one service (or the dashboard). Match the
  language/stack of that service; don't reach across service boundaries except through the
  Kafka/gRPC/GraphQL contracts.
- **Don't edit v1.** Never add features under `v1/` or repo-root `engine/`. If you need v1 behavior
  for parity, read it, then implement fresh in the v2 service.
- **Prefer editing existing files.** Don't scatter new files, and don't create docs/READMEs unless
  the task asks for them.

## Building & running

Builds and full-stack runs happen on the **toolchain box** (Go, Rust, `buf`, Docker). **Not every
environment has that toolchain** — the WSL dev box does TypeScript / Python / docs only, so
`go` / `cargo` / `buf` may not exist where you're running. Check before assuming.

Common entry points (see the `Makefile`):

- `make deps` — start infra (Kafka, Postgres, Redis, Elasticsearch) via `docker-compose.deps.yml`.
- `make proto` / `make proto-lint` — regenerate / lint protobuf contracts for all languages.
- `make build` / `make build-<service>` — build all or one service.
- `make test` / `make test-<service>` — run per-service tests.
- `docker-compose.yml` — the full v2 stack.

## Where to go next

- **`docs/REQUIREMENTS.md`** — authoritative WHAT and the bar for "done" (the per-area DoD, the three
  principles). Conflicts resolve in favor of this doc.
- **`docs/plans/06-FABLE-PLAN.md`** — the HOW/WHEN: execution waves and story-level detail.
- **`docs/plans/AREA-TECH-TEACHING-PLAN.md`** — the 15-area definitions (tech + teaching + proof).
- **`docs/v2-audit.md`** — honest current status, service by service and flow by flow.
