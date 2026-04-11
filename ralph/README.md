# Ralph v2 — Polyglot AI Developer

Ralph v2 is the AI developer that builds and maintains the **Qtown v2 polyglot monorepo** — an AI agent orchestration platform spanning 9 microservices, 12+ programming languages, and a full observability stack. Ralph reads stories from `worklist.json`, selects the right Ollama model, generates code, runs tests, and commits passing work autonomously.

---

## Architecture

```
                    worklist.json (194 stories)
                           │
                    v2_orchestrator.py
                    ┌──────┴──────────┐
                    │    schedules    │
                    │  (dep-aware)    │
                    └──────┬──────────┘
                           │ spawns up to N workers
          ┌────────────────┼────────────────┐
          │                │                │
    RalphWorker       RalphWorker      RalphWorker
    (story A)         (story B)        (story C)
          │                │                │
    v2_model_router.py (selects Ollama model per story)
          │                │                │
   qwen3-coder-next   qwen3.5:27b   deepseek-r1:14b
```

**Key files:**

| File | Role |
|---|---|
| `v2_orchestrator.py` | Main loop — spawns parallel workers, detects conflicts, commits results |
| `v2_worklist.py` | Loads/saves `worklist.json`, tracks story status and deps |
| `v2_model_router.py` | Routes each story to the best Ollama model |
| `v2_cross_service.py` | Detects proto and multi-service stories, plans sequencing |
| `v2_config.py` | All configuration — paths, models, service test/build commands |
| `worklist.json` | 194-story historical record and future story template |

---

## Model Lineup

| Model | Tag | Size | Role |
|---|---|---|---|
| `qwen3-coder-next` | Primary | 80B MoE, ~8GB (3B active) | All code generation (Python, Go, Rust, TypeScript, proto, YAML) |
| `qwen3.5:27b` | Heavy | 27B dense, ~20GB | Architecture decisions, schema design, refactors |
| `qwen3.5:35b-a3b` | Content | 35B MoE, ~16GB (3B active) | NPC dialogue, story narrative content |
| `deepseek-r1:14b` | Debug | 14B dense, ~16GB | Root cause analysis, debugging, race conditions |
| `nomic-embed-text` | Embeddings | — | RAG pipeline for library service |

Model routing rules (from `v2_model_router.py`):
- Default → `qwen3-coder-next`
- Story title contains `architect`, `design`, `refactor`, `schema`, `migrate` → `qwen3.5:27b`
- Story title contains `debug`, `fix`, `race condition`, `investigate`, `root cause` → `deepseek-r1:14b`
- If primary model has < 50% success rate → automatically route to fallback

---

## How to Start

### Step 1 — Pull all required models

```bash
./ralph/v2_setup_models.sh
```

This pulls all 5 Ollama models (≈60GB total). Run once.

### Step 2 — Start infrastructure

```bash
docker compose -f docker-compose.deps.yml up -d
```

Starts Postgres, Redis, Kafka, Zookeeper.

### Step 3 — Run Ralph v2

```bash
./ralph/v2_start.sh
# Or with options:
./ralph/v2_start.sh --max-parallel 5
./ralph/v2_start.sh --dry-run   # plan only, no code written
```

---

## Configuration

All settings are driven by environment variables (with sane defaults):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `RALPH_PRIMARY_MODEL` | `qwen3-coder-next` | Default code model |
| `RALPH_HEAVY_MODEL` | `qwen3.5:27b` | Architecture/design model |
| `RALPH_CONTENT_MODEL` | `qwen3.5:35b-a3b` | Narrative/dialogue model |
| `RALPH_DEBUG_MODEL` | `deepseek-r1:14b` | Debug/reasoning model |
| `RALPH_MAX_PARALLEL` | `3` | Max concurrent workers |
| `RALPH_MAX_ATTEMPTS` | `12` | Max attempts per story before escalation |
| `RALPH_HELP_WAIT` | `600` | Seconds to wait when a story needs human help |

Set via `.env` in the project root or export before running.

---

## How Stories Work

Stories live in `worklist.json`. Each story is a unit of work:

```json
{
  "id": "P1-005",
  "title": "Implement POST /api/tick — advances simulation by one tick",
  "service": "town-core",
  "language": "python",
  "deps": ["P1-004"],
  "status": "complete",
  "phase": 1,
  "group": "1.1"
}
```

**Fields:**

| Field | Values | Description |
|---|---|---|
| `id` | `P{phase}-{num}` | Unique story ID, e.g. `P1-005` |
| `title` | string | What to build — precise, one sentence |
| `service` | see below | Which service this story lives in |
| `language` | see below | Primary language for model routing |
| `deps` | list of IDs | Stories that must be `complete` before this can start |
| `status` | `pending` / `in_progress` / `complete` / `failed` | Current state |
| `phase` | 0–5 | Build phase |
| `group` | `"1.2"` etc. | Logical group within phase |

**Services:** `town-core`, `market-district`, `fortress`, `academy`, `tavern`, `cartographer`, `library`, `asset-pipeline`, `dashboard`, `proto`, `infra`, `ralph`, `multi`

**Languages:** `python`, `go`, `rust`, `typescript`, `vue`, `protobuf`, `sql`, `yaml`, `dockerfile`, `makefile`, `shell`, `hcl`, `multi`

**Scheduling:** Ralph processes stories in dependency order. Stories with no unmet deps run in parallel (up to `RALPH_MAX_PARALLEL`). Two stories on the same service never run simultaneously. Proto stories always run before their dependents.

**Status lifecycle:**
```
pending → in_progress → complete
                      ↘ failed → pending (retry, up to MAX_ATTEMPTS)
                                       ↘ HUMAN.md escalation
```

---

## Monitoring

**Logs:** Ralph writes structured JSON logs to stdout. Pipe to `jq` for readability:
```bash
./ralph/v2_start.sh 2>&1 | tee ralph.log | jq '.'
```

**Metrics:** Each worker emits timing and success/failure metrics. View via Grafana (see `infra/grafana/dashboards/`).

**HUMAN.md escalation:** When a story fails all 12 attempts, Ralph writes to `.ralph-needs-help.json` and waits `RALPH_HELP_WAIT` seconds. To intervene:
1. Read `.ralph-needs-help.json` for the error
2. Fix the issue manually
3. Delete `.ralph-needs-help.json` to signal Ralph to continue
4. Or update `HUMAN.md` with `action: skip` to skip the story

**Progress check:**
```bash
python3 -c "
import json
d = json.load(open('ralph/worklist.json'))
s = d['stories']
by_status = {}
for story in s:
    by_status.setdefault(story['status'], []).append(story['id'])
for status, ids in sorted(by_status.items()):
    print(f'{status}: {len(ids)}')
print(f'Total: {len(s)}')
"
```

---

## v1 vs v2 Comparison

| Feature | Ralph v1 | Ralph v2 |
|---|---|---|
| **Services** | 1 (town-core Python only) | 9 + dashboard (polyglot) |
| **Languages** | Python only | 12+ (Python, Go, Rust, TypeScript, Vue, proto, HCL, ...) |
| **Concurrency** | Sequential, one story at a time | Parallel workers (N configurable) |
| **Story format** | `prd.json` (flat list, no deps) | `worklist.json` (dep graph, phases, groups) |
| **Model routing** | Single model (`qwen3.5:27b`) | 4 models + embeddings, routed by task type |
| **Conflict detection** | None | Service-level + proto + dep chain |
| **Cross-service stories** | Not supported | Auto-detected, sequenced proto-first |
| **Observability** | Print statements | OpenTelemetry + Prometheus + Grafana |
| **Test execution** | pytest only | pytest, go test, cargo test, jest |
| **Infrastructure** | Single Docker container | K8s, Terraform, Helm, Linkerd |
| **Fallback models** | None | Automatic fallback chain |
| **Success rate tracking** | None | Per-model, per-language |

---

## File Reference

```
ralph/
├── README.md              ← This file
├── worklist.json          ← 194-story historical record + future template
├── v2_config.py           ← All configuration (env-driven)
├── v2_orchestrator.py     ← Main orchestration loop
├── v2_worklist.py         ← Worklist parser and scheduler
├── v2_model_router.py     ← Model routing and fallback logic
├── v2_cross_service.py    ← Cross-service and proto story detection
├── v2_start.sh            ← Entry point script
├── v2_setup_models.sh     ← Pull all required Ollama models
├── tests/
│   └── test_v2_orchestrator.py
└── [v1 files kept for reference]
    ├── ralph.py
    ├── prompt_builder.py
    └── ...
```
