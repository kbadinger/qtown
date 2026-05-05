# Activating Ralph v2 on Phase 6

The v2 audit (`docs/v2-audit.md`) added 26 stories to `ralph/worklist.json` (P6-001 through P6-026). Ralph v2 is currently idle because all 194 prior stories are marked complete. To turn him back on for Phase 6:

## Pre-flight

### 1. Ollama + models

Ralph v2 routes stories across 5 local Ollama models. From the verification I just ran on the new worklist:

```
qwen3.5:27b           → 9 architect/refactor stories
qwen3-coder-next      → 13 default code-gen stories
deepseek-r1:14b       → 4 debug/investigate stories
```

`ralph/v2_setup_models.sh` pulls all 5 (the embedding model `nomic-embed-text` and the content model `qwen3.5:35b-a3b` aren't strictly needed for Phase 6 but install them anyway for future stories).

```sh
# from repo root
./ralph/v2_setup_models.sh
```

This is ~60GB. Coffee-break-long the first time, instant after that.

### 2. Infrastructure deps

Phase 6 stories touch Kafka topology, gRPC, ES indexing, Redis pub/sub, Postgres. Bring up the deps:

```sh
docker compose -f docker-compose.deps.yml up -d
```

Wait until `docker compose ps` shows postgres + redis + kafka + elasticsearch all `healthy`. Roughly 60–90s.

### 3. Sanity check the worklist

```sh
python3 -c "
import sys
sys.path.insert(0, 'ralph')
from v2_worklist import Worklist
w = Worklist('ralph/worklist.json')
print('Total stories:', len(w.all_stories()))
print('Pending:', sum(1 for s in w.all_stories() if s.status == 'pending'))
print('Next available:', len(w.next_available(w.completed_ids())))
"
```

Expected output:
```
Total stories: 220
Pending: 26
Next available: 16
```

The 16 are the P6 stories whose deps are already satisfied (most of them — only a few P6 stories block on other P6 stories).

## Dry run

`ralph/v2_start.sh` supports `--dry-run`. Always do this first after a worklist change:

```sh
./ralph/v2_start.sh --dry-run
```

Watch the output: it should list P6 stories as next-up, name the model each will route to, and exit without making code changes. If any story fails routing or is rejected by the validator, fix it in `ralph/worklist.json` before going live.

## Live run

```sh
./ralph/v2_start.sh
```

This kicks off the autonomous loop. It will:

1. Pick the next available P6 story
2. Route to the right Ollama model
3. Generate code changes
4. Run the per-service test suite (Make targets / pytest / cargo / go test / npm test)
5. On green tests, commit with story ID prefix and mark complete
6. On red, retry up to a configured limit, then mark failed and move on
7. Repeat until no available stories remain

By default the orchestrator runs in parallel across services with conflict detection (services that don't share files run in parallel; same-service stories serialize). Tune via `--max-parallel`.

## What you should monitor

### First story closes
P6-005 ("Register market-district gRPC service in cmd/server/main.go") is the simplest. If Ralph's first commit looks reasonable on `git log -1 -p`, the loop is healthy.

### Test runner output
Per-service `make test` is the success gate. If Ralph keeps failing on a specific service, it's usually:
- Missing dependency (run `make install-<service>`)
- Service couldn't reach an infra dep (check `docker compose ps`)
- Story acceptance criteria too vague (edit `ralph/worklist.json` story description and the `acceptance_criteria` array, retry)

### Dependency-blocked stories unlock
P6-006 ("Emit qtown.economy.trade.settled") is gated by P6-005. When P6-005 completes, run the dry-run again to confirm P6-006 is now in the next-available list.

### Commit cadence
Ralph v2 should average 1 commit per 5–15 minutes per worker. If it's slower, models are likely thrashing against context — check Ollama's logs for OOMs.

## How to stop

```sh
# graceful — finishes current story then exits
touch ralph/STOP

# hard — kill the orchestrator process
pkill -f v2_orchestrator.py
```

Either is safe — the worklist's `status` field tracks current state, so you can resume by re-running `./ralph/v2_start.sh`.

## When Phase 6 closes

The integration tests at the end of the worklist (P6-022, P6-023, P6-024) are the verdict. If all three pass, the three flagship cross-service flows (Market Trade, AI Dialogue, Validation) actually work — the system the README describes is the system that exists.

After that, P6-019 (`Design v2 production deployment`) gates the qtown.ai flip from coming-soon → real v2 dashboard. Coordinate with `docs/handover-domain-flip.md` step 4 once the deploy URL is stable.

## When something is blocking Ralph

If a P6 story has gone through 5+ attempts and keeps failing, it usually means the story is wrong, not that Ralph is wrong. Common rewrites:
- Acceptance criteria assume a file/symbol that doesn't exist → fix the criteria
- Story spans too many services → split into sub-stories with explicit `deps`
- Implementation requires a design choice Ralph can't reasonably make → demote the story to a human task and remove it from worklist

If you see this pattern, look at `ralph/v2_orchestrator.py` logs for the rejected approaches; the patterns will tell you what's missing.
