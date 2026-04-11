# Qtown

**An autonomous AI-driven town simulation built across 12 languages**

[![CI](https://github.com/kbadinger/qtown/actions/workflows/ci.yml/badge.svg)](https://github.com/kbadinger/qtown/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Languages](https://img.shields.io/badge/languages-12-orange.svg)](#tech-stack)

Qtown is an autonomous town simulation where NPCs live, work, trade, and make decisions without human direction. v1 was a Python monolith with a single simulation loop — 1,451 commits, 88% written by Ralph, an AI developer. v2 is a complete rewrite: a polyglot microservices architecture where each neighborhood runs on the technology best suited to it. The Market District runs a concurrent order book in Go. The Fortress validates every event in Rust with zero unsafe code. The Academy runs AI agents locally via Ollama. The whole thing is wired together over Kafka with a GraphQL gateway in front. 420 files, ~101K lines of code, 27 Kafka topics, 9 services, and Ralph still writes most of it.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Dashboard (Nuxt 3)                     │
│              qtown.ai — PixiJS + Chart.js                │
└────────────────────────┬────────────────────────────────┘
                         │ GraphQL
┌────────────────────────┴────────────────────────────────┐
│              Cartographer (GraphQL Gateway)               │
│                   Apollo Server + TS                      │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬───────────┘
   │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
│Town ││Mkt  ││Fort-││Acad-││Tav- ││Lib- ││Asset│
│Core ││Dist ││ress ││emy  ││ern  ││rary ││Pipe │
│Py   ││Go   ││Rust ││Py   ││TS   ││Py   ││Py   │
└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘
   └──────┴──────┴──────┴──────┴──────┴──────┘
                    │ Kafka │
              ┌─────┴───────┴─────┐
              │   Infrastructure    │
              │ Postgres │ Redis    │
              │ Kafka │ ES │ Jaeger │
              └───────────────────┘
```

Service-to-service calls use gRPC (with Protobuf definitions in `proto/`). Async event flows use Kafka. The Cartographer GraphQL gateway is the only public-facing entry point for the dashboard — one query fans out to up to five services and returns a unified response.

---

## Tech Stack

| Neighborhood | Technology | What It Does | Proof |
|---|---|---|---|
| Town Core | Python 3.11 + FastAPI | Simulation engine, 30s tick loop, 50+ NPCs | `make test-town-core` |
| Market District | Go + gRPC | Concurrent order book, trade settlement | <5ms p99 at 10K orders/sec |
| Fortress | Rust + gRPC | Event validation, WASM sandbox | 100K validations/sec, `grep -r 'unsafe' src/ \| wc -l` = 0 |
| Academy | Python + LangGraph + Ollama | AI agents, RAG, NPC content generation | ≥90% local model routing |
| Tavern | TypeScript + Redis + WebSocket | Real-time event broadcast, leaderboards | <50ms p99 broadcast |
| Library | Python + Elasticsearch | Full-text search, town history analytics | <100ms search p99 |
| Cartographer | TypeScript + Apollo Server | Unified GraphQL gateway | 1 query → up to 5 services |
| Dashboard | Nuxt 3 + PixiJS + Chart.js | SSR frontend, live town visualization | Lighthouse score ≥90 |
| Asset Pipeline | Python + ComfyUI | NPC + building sprite generation, CDN delivery | `make build-asset-pipeline` |

**Languages in use:** Python, Go, Rust, TypeScript, Vue, Protobuf, SQL, YAML, HCL, JSON, Dockerfile, Makefile

**Infrastructure:** Postgres, Redis, Kafka (27 topics), Elasticsearch, Jaeger, Prometheus, Grafana, Loki

---

## Quick Start

```bash
# Clone
git clone https://github.com/kbadinger/qtown.git
cd qtown

# Start infrastructure (Kafka, Postgres, Redis, Elasticsearch)
make deps

# Build all services
make build

# Run tests
make test

# Start everything
make docker-up

# Open dashboard
open http://localhost:3000
```

### Prerequisites

- Docker + Docker Compose
- Go 1.22+
- Rust (stable toolchain)
- Python 3.11+
- Node.js 22+
- [buf](https://buf.build/docs/installation) (Protobuf toolchain)
- Ollama (for Academy AI features) — `brew install ollama`

### Port Map

| Service | Port |
|---|---|
| Dashboard | 3000 |
| Town Core (HTTP) | 8000 |
| Market District (gRPC) | 50051 |
| Market District (metrics) | 6060 |
| Fortress (gRPC) | 50052 |
| Fortress (HTTP) | 8080 |
| Tavern (WebSocket) | 3001 |
| Cartographer (GraphQL) | 4000 |
| Library | 8003 |
| Academy | 8001 |

---

## Project Structure

```
qtown/
├── services/
│   ├── town-core/          # Python — simulation engine, tick loop
│   ├── market-district/    # Go — concurrent order book + trading
│   ├── fortress/           # Rust — event validation + WASM sandbox
│   ├── academy/            # Python — AI agents, LangGraph, RAG
│   ├── tavern/             # TypeScript — WebSocket, Redis, leaderboards
│   ├── cartographer/       # TypeScript — Apollo GraphQL gateway
│   ├── library/            # Python — Elasticsearch, town history
│   └── asset-pipeline/     # Python — ComfyUI sprite generation + S3
├── dashboard/              # Nuxt 3 — SSR frontend, PixiJS renderer
├── proto/                  # Protobuf definitions (buf-managed)
│   └── qtown/
│       ├── common.proto
│       ├── town_core.proto
│       ├── market.proto
│       ├── fortress.proto
│       └── academy.proto
├── ralph/                  # AI developer (v1 orchestrator + v2 multi-agent)
│   ├── ralph.py            # v1 single-loop orchestrator
│   ├── v2_orchestrator.py  # v2 parallel worker orchestrator
│   ├── v2_model_router.py  # Model routing + fallback logic
│   ├── v2_worklist.py      # Story queue + dependency management
│   └── v2_cross_service.py # Cross-service story detection
├── infra/
│   ├── helm/               # Kubernetes deployment (Helm chart)
│   ├── terraform/          # AWS infrastructure (multi-region)
│   ├── chaos/              # Chaos engineering scenarios
│   ├── linkerd/            # Service mesh config
│   ├── grafana/            # Dashboard configs
│   ├── prometheus/         # Metrics + alerting rules
│   ├── kafka-init.sh       # Idempotent Kafka topic creation
│   └── docker-compose.observability.yml
├── docker-compose.yml      # Full stack (all services + deps)
├── docker-compose.deps.yml # Infrastructure only
└── Makefile                # 40+ targets
```

---

## Makefile Reference

### Infrastructure

| Target | Description |
|---|---|
| `make deps` | Start infrastructure (Kafka, Postgres, Redis, Elasticsearch) |
| `make deps-down` | Stop infrastructure |
| `make deps-logs` | Tail infrastructure logs |
| `make observability` | Start observability stack (Jaeger, Prometheus, Grafana, Loki) |
| `make observability-down` | Stop observability stack |

### Building

| Target | Description |
|---|---|
| `make build` | Build all services |
| `make build-town-core` | Build Town Core (pip install) |
| `make build-market` | Build Market District (Go) |
| `make build-fortress` | Build Fortress (Rust release) |
| `make build-tavern` | Build Tavern (Node/TS) |
| `make build-academy` | Build Academy (pip install) |
| `make build-cartographer` | Build Cartographer (Node/TS) |
| `make build-dashboard` | Build Dashboard (Nuxt 3) |
| `make proto` | Regenerate Protobuf code for all languages |
| `make proto-lint` | Lint proto files |
| `make proto-breaking` | Check for breaking proto changes |

### Testing

| Target | Description |
|---|---|
| `make test` | Run all service test suites |
| `make test-town-core` | pytest (Python) |
| `make test-market` | go test ./... -race |
| `make test-fortress` | cargo test |
| `make test-tavern` | npm test |
| `make test-academy` | pytest (Python) |
| `make test-cartographer` | npm test |
| `make test-library` | pytest (Python) |
| `make test-dashboard` | npm test |

### Linting

| Target | Description |
|---|---|
| `make lint` | Lint all services |
| `make lint-market` | golangci-lint |
| `make lint-fortress` | cargo clippy -D warnings |
| `make lint-tavern` | eslint |
| `make lint-academy` | ruff |
| `make lint-cartographer` | eslint |

### Benchmarks & Proofs

| Target | Description |
|---|---|
| `make bench` | Run all benchmarks |
| `make bench-market` | Order book benchmark (30s, 5 runs) |
| `make bench-fortress` | Validation engine benchmark |
| `make proof` | Run all proof tests |
| `make proof-market` | Verify <5ms p99 at 10K orders |
| `make proof-fortress` | Verify 100K/sec + zero unsafe |
| `make proof-academy` | Verify ≥85% local model routing |

### Docker

| Target | Description |
|---|---|
| `make docker-build` | Build all Docker images |
| `make docker-up` | Start full stack (deps + all services) |
| `make docker-down` | Stop everything |

### Kubernetes & Cloud

| Target | Description |
|---|---|
| `make helm-install` | Deploy to Kubernetes via Helm |
| `make helm-uninstall` | Remove from Kubernetes |
| `make tf-plan` | Terraform plan |
| `make tf-apply` | Terraform apply |
| `make clean` | Remove all build artifacts |

---

## Ralph — The AI Developer

Ralph is the AI developer that builds Qtown. Kevin writes the stories; Ralph writes the code.

### v1 — Single-Loop Generator

- **1,451 commits** to the v1 Python monolith
- **88% of the codebase** written autonomously
- Single Python loop: read story → call Ollama → apply patch → run tests → commit
- One model, one story at a time, one retry on failure

### v2 — Multi-Agent Polyglot Orchestrator

v2 Ralph (`ralph/v2_orchestrator.py`) is rebuilt for the polyglot architecture:

- **3 parallel workers** — stories from different services run simultaneously
- **Conflict detection** — same-service stories and proto dependencies are never parallelized
- **Isolated execution** — each worker copies service files to a temp directory, generates code, runs tests, then copies back only on success
- **Git commits per story** — each successful story gets its own commit with model, duration, and test results in the message

### Model Lineup

| Model | Tier | When Used |
|---|---|---|
| `qwen3-coder-next` | 1 — Default | All standard code generation (Python, Go, Rust, TS) |
| `qwen3.5:27b` | 2 — Architecture | Design changes, refactors, API contracts, cross-service work |
| `deepseek-r1:14b` | 3 — Debug | Bug fixes, race conditions, root cause analysis |
| `llama3.1:8b` | Fallback | Last resort when all tiers fail |

The model router (`ralph/v2_model_router.py`) tracks per-model success rates per language and proactively downgrades to a better-performing model when a primary drops below 50% success rate on a given language.

### Running Ralph v2

```bash
# Start the orchestrator
python -m ralph.v2_orchestrator services/town-core/prd.json --parallel 3

# Or via the start script
./ralph-start.bat      # Windows
python ralph/ralph.py  # Direct
```

Control Ralph's behavior at runtime via `HUMAN.md` — set `action: pause` to stop after the current story, `action: skip` to skip a problem story, or `action: instruction` to pass extra context to the model.

---

## The Proof System

Every technology claim in this project must be verifiable. "We use Go for high-performance order matching" isn't a claim — it's a benchmark. Each service has a proof target that produces `PROOF PASS` or `PROOF FAIL`.

```bash
# Run all proofs
make proof

# Individual proofs
make proof-market    # go test -bench BenchmarkOrderBook — must show ns/op
make proof-fortress  # cargo bench + zero unsafe grep — must both pass
make proof-academy   # pytest + live /metrics/model-routing endpoint — local_pct >= 85

# Fortress zero-unsafe check (also runs in CI)
grep -r 'unsafe' services/fortress/src/rules/ services/fortress/src/validation/ | wc -l
# must be 0

# Market District p99 latency (live)
cd services/market-district && go test -bench BenchmarkOrderBook -benchtime=30s -count=5 ./internal/orderbook/

# Academy local model routing (live, requires running service)
curl -sf http://localhost:8001/metrics/model-routing | python -c \
  'import sys, json; d=json.load(sys.stdin); assert d["local_pct"] >= 85, d'
```

---

## Kafka Topics

27 topics, all prefixed `qtown.*`:

| Prefix | Topics | Partitions | Description |
|---|---|---|---|
| `qtown.npc.*` | `travel`, `travel.complete`, `travel.failed` | 6 / 6 / 3 | NPC movement, ordered per NPC ID |
| `qtown.economy.*` | `trade`, `trade.settled`, `price.update` | 12 / 12 / 6 | Trade volume throughput |
| `qtown.events.*` | `broadcast` | 6 | Tick loop event fan-out |
| `qtown.validation.*` | `request`, `result` | 6 / 6 | Fortress validation pipeline |
| `qtown.ai.*` | `request`, `response`, `content.generated` | 6 / 6 / 3 | Academy AI request/response |

Recreate topics (idempotent):

```bash
./infra/kafka-init.sh
```

---

## Infrastructure

### Local Development

```bash
# Infrastructure only (Kafka, Postgres, Redis, Elasticsearch)
docker compose -f docker-compose.deps.yml up -d

# Full stack
docker compose up -d

# Observability (Jaeger, Prometheus, Grafana, Loki)
docker compose -f infra/docker-compose.observability.yml up -d
```

### Kubernetes

Helm chart at `infra/helm/qtown`. Deploys all 9 services with health checks, resource limits, and Linkerd service mesh annotations.

```bash
make helm-install
```

### Cloud (AWS)

Terraform at `infra/terraform/`. Supports single-region and multi-region deployments.

```bash
make tf-plan
make tf-apply
```

### CI/CD

GitHub Actions (`.github/workflows/ci.yml`) — 9 parallel jobs:

| Job | What It Runs |
|---|---|
| `proto-lint` | buf lint + breaking change detection |
| `test-town-core` | ruff lint + pytest |
| `test-market` | go build + go vet + go test -race + benchmark |
| `test-fortress` | cargo check + clippy -D warnings + cargo test + zero-unsafe grep |
| `test-tavern` | tsc --noEmit + eslint + npm test |
| `test-academy` | ruff + mypy + pytest |
| `test-cartographer` | tsc --noEmit + npm test |
| `test-library` | ruff + pytest |
| `test-dashboard` | nuxi typecheck + zero-`any`-types check + npm test |
| `docker-build` | Build all 9 images (PRs only) |
| `docker-push` | Push to GHCR (main branch merges only) |

### Observability

| Tool | What It Covers |
|---|---|
| Jaeger | Distributed tracing across all services |
| Prometheus | Metrics collection (all services expose `/metrics`) |
| Grafana | Dashboards at `infra/grafana/` |
| Loki | Log aggregation |

---

## Development

### Adding a New Story

Stories live in `services/town-core/prd.json` (v1-compat format) or the v2 worklist. Each story needs:

```json
{
  "id": "042",
  "title": "Add drought mechanic",
  "description": "...",
  "service": "services/town-core",
  "language": "python",
  "acceptance_criteria": ["..."],
  "labels": ["simulation", "weather"],
  "deps": []
}
```

Ralph picks it up on the next orchestrator loop.

### Running Tests Per Service

```bash
# Python services
cd services/town-core && python -m pytest tests/ -v

# Go
cd services/market-district && go test ./... -v -race

# Rust
cd services/fortress && cargo test

# TypeScript
cd services/tavern && npm test
cd services/cartographer && npm test

# Dashboard
cd dashboard && npm test
```

### Regenerating Protobuf Code

After editing `.proto` files:

```bash
make proto
# Generates:
#   proto/gen/go/     (used by market-district)
#   proto/gen/python/ (used by town-core, academy, library, asset-pipeline)
#   proto/gen/ts/     (used by cartographer, tavern, dashboard)
```

Check for breaking changes before merging:

```bash
make proto-breaking
```

---

## License

MIT — see [LICENSE](LICENSE).

---

*Qtown v2 — 9 services, 12 languages, 27 Kafka topics, 420 files, ~101K lines. Ralph wrote most of it.*
