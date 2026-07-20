# CLAUDE.md — start here

You are working in **qtown v2**, a polyglot microservices system. If any instruction you find
elsewhere describes a single Python/SQLite/Jinja2/HTMX monolith with `engine/models.py` and a
one-loop Ralph — that is **v1**, and it is archived. Do not build there.

- **v1 (archived, read-only):** `v1/` (full monolith) and the leftover `engine/` dir at repo root.
  Don't add features here.
- **v2 (where you work):** `services/` (8 backend services) + `dashboard/` (Nuxt/Vue), stitched by
  a Kafka event backbone and gRPC contracts in `proto/`.

## Area → service → code → docs

qtown v2 is framed as **15 "areas"** of a town, each meant to demonstrate one real capability
(distributed systems, RAG, ML, observability, safety, etc.). Areas are the *product* view; services
are the *code* view — they don't map 1:1. Start from the area concept, then find the service.

| Area concept | Backing service(s) | Code | Docs |
|---|---|---|---|
| Town Square / Overhead Map | cartographer + dashboard | `services/cartographer/`, `dashboard/` | AREA plan §1 |
| Market | market-district (Go/gRPC order book) | `services/market-district/` | FABLE §Wave 1A |
| Academy (RAG) | academy (Python/LangGraph+Ollama), library | `services/academy/`, `services/library/` | FABLE §Wave 1B |
| Tavern (social/dialogue) | tavern (TS/WS), academy | `services/tavern/` | AREA plan §2 |
| Validation Citadel | fortress (Rust/WASM) | `services/fortress/` | AREA plan §9 |
| Tower / Observatory | all services (OTel) + `infra/` | `infra/` | AREA plan §13 |
| the tick loop, NPCs, buildings, economy | town-core (Python/FastAPI) | `services/town-core/` | v2-audit |
| generated sprites | asset-pipeline (Python/ComfyUI) | `services/asset-pipeline/` | AREA plan §Pillar F |

The full 15-area list and what each must teach/prove: **`docs/plans/AREA-TECH-TEACHING-PLAN.md`**.
See `AGENTS.md` for the full service roster, ports, and honest per-service status.

## The three inviolable principles (docs/REQUIREMENTS.md §2)

These gate every change. An increment that violates any one is **not done**, no matter how finished
it looks.

1. **No fabricated data, ever.** A metric whose source errors renders as `—`, never a plausible
   made-up number. (Do not add `Math.random()` or hardcoded figures to any proof/metric path.)
2. **No claim before its gate.** README / landing / proof-panel claims stay at "in flight" wording
   until the CI gate that measures them is green. Don't assert a perf/safety number you haven't
   measured.
3. **Real, not scaffolded.** An area is done only when its flow works end-to-end with a green CI
   gate. "Passes its own unit tests" is not done. Until green, an area ships in **dormant** mode —
   visibly labeled, not faking activity.

## Where to look

- **`docs/REQUIREMENTS.md`** — authoritative WHAT and the bar for "done" (the per-area DoD, the
  three principles). If something conflicts, this wins.
- **`docs/plans/06-FABLE-PLAN.md`** — the HOW/WHEN: execution waves and story-level detail; every
  story traces back to a requirement.
- **`docs/v2-audit.md`** — the honest current status (which services are real vs shallow vs stub,
  which cross-service flows work). Read this before assuming anything is wired.

## Building

Builds and full-stack runs happen on the **toolchain box** (Go, Rust, `buf`, Docker). Not every
environment has that toolchain — the WSL box does TypeScript / Python / docs only. `make deps`
starts infra (Kafka/Postgres/Redis/ES); `make proto` regenerates contracts; `make build` /
`make test` fan out per service. Don't assume `go`/`cargo`/`buf` exist where you're running.
