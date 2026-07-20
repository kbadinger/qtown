# Qwen Town — Complete Spec v2

> A self-evolving 2D town simulation built by a local Qwen 3.5:35b model.
> One GPU thinks. One GPU draws. No cloud. No API keys.

---

## 1. What We're Building

A **Ralph-style autonomous loop** that:
1. Reads a backlog of stories (the PRD)
2. Runs the tests for the next story
3. Sends the failing test + relevant code to Qwen
4. Applies Qwen's code changes
5. Re-runs tests — if pass, git commit. If fail, retry.
6. Repeats until every story is done

The human writes **the loop + a thin launchpad (~200 lines)**. Qwen writes **everything else** — all sim logic, all game mechanics, all UI, all API routes.

**MVP target: a living village** — grid world, 5-10 building types, NPCs with daily routines, basic economy, random events. Visually interesting, demonstrates autonomous growth.

**Public exposure: Phase 2.** First we prove the loop works.

**Domain: qtown.ai**

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│                   Your Desktop                   │
│                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │  Ollama   │   │ ComfyUI  │   │  Ralph Loop  │ │
│  │ qwen3.5   │   │  SDXL +  │   │  (Python)    │ │
│  │  :35b     │   │  LoRA    │   │              │ │
│  │           │   │          │   │  reads PRD   │ │
│  │ 3090 Ti   │   │  3080    │   │  runs tests  │ │
│  │ (24GB)    │   │  (10GB)  │   │  calls Qwen  │ │
│  └─────┬─────┘   └────┬─────┘   │  applies code│ │
│        │              │         │  commits     │ │
│        │              │         └──────┬───────┘ │
│        │              │                │         │
│  ┌─────┴──────────────┴────────────────┴───────┐ │
│  │              Town Engine (FastAPI)           │ │
│  │              SQLite database                 │ │
│  │              localhost:8000                  │ │
│  └─────────────────────┬───────────────────────┘ │
│                        │                         │
│  ┌─────────────────────┴───────────────────────┐ │
│  │              Town UI (Next.js + PixiJS)      │ │
│  │              localhost:3000                  │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**No Docker.** Everything runs natively on Windows. Four processes:
1. Ollama (runs as Windows service, auto-starts)
2. ComfyUI (Python, one terminal)
3. Town Engine (FastAPI, one terminal)
4. Ralph Loop (Python, one terminal)

Town UI is optional during development — Qwen doesn't need it to pass tests.

---

## 3. Hardware & Software Setup

### 3.1 Prerequisites

Install these before anything else:

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Engine, Ralph loop, ComfyUI |
| Node.js | 20+ | Town UI (Next.js) |
| Git | Latest | Version control (Ralph commits here) |
| Ollama | Latest | Serves Qwen 3.5 |
| ComfyUI | Latest | Image generation |

### 3.2 Ollama + Qwen 3.5:35b

```bash
# Install Ollama from https://ollama.com/download
# Then pull the model:
ollama pull qwen3.5:35b

# Test it works:
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3.5:35b",
  "prompt": "Write a Python function that adds two numbers.",
  "stream": false
}'
```

**Key settings:**
- Model: `qwen3.5:35b` (24GB, fits entirely on 3090 Ti)
- Context: 256K tokens available (we'll use ~32K per prompt to stay fast)
- API: OpenAI-compatible at `http://localhost:11434/v1/chat/completions`
- GPU: Bind to 3090 Ti only (Ollama uses GPU 0 by default — make sure 3090 Ti is GPU 0 in NVIDIA settings)

**Verify GPU assignment:**
```bash
nvidia-smi
# GPU 0 should be the 3090 Ti (24GB)
# GPU 1 should be the 3080 (10GB)
# If swapped, change in NVIDIA Control Panel > Manage 3D Settings
```

**Set Ollama environment variables** (Windows System Environment Variables):
```
OLLAMA_NUM_GPU=999          # Use all layers on GPU
CUDA_VISIBLE_DEVICES=0      # Only use GPU 0 (3090 Ti)
```

### 3.3 ComfyUI + SDXL

```bash
# Clone ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

# Download SDXL base model → ComfyUI/models/checkpoints/
# Download file: sd_xl_base_1.0.safetensors
# From: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0

# Download isometric LoRA → ComfyUI/models/loras/
# Download file: zavy-ctsmtrc-sdxl.safetensors
# From: https://civitai.com/models/xxxxxx (search "zavy ctsmtrc isometric")

# Start ComfyUI on GPU 1 (the 3080):
set CUDA_VISIBLE_DEVICES=1
python main.py --listen 0.0.0.0 --port 8188
```

**Test it works:**
```bash
# Queue the building workflow from our repo:
curl -X POST http://localhost:8188/prompt -H "Content-Type: application/json" -d @building_api.json
# Should generate an image in ComfyUI/output/
```

---

## 4. Repository Layout

```
qwen-town/
├── ralph/                    # THE LOOP (human-written, ~300 lines)
│   ├── ralph.py              # Main orchestrator loop
│   ├── prompt_builder.py     # Builds prompts for Qwen
│   ├── file_writer.py        # Parses + applies Qwen's output
│   ├── test_runner.py        # Runs pytest, captures output
│   ├── metrics.py            # Logs iteration data to metrics.jsonl
│   └── snapshot.py           # Captures town screenshots
│
├── engine/                   # TOWN BACKEND (Qwen builds this)
│   ├── main.py               # FastAPI entry — human writes skeleton
│   ├── models.py             # DB models — human writes Grid, Qwen adds rest
│   ├── db.py                 # SQLite setup — human writes this
│   └── routers/              # API routes — Qwen builds all of these
│
├── ui/                       # TOWN FRONTEND (Qwen builds this)
│   ├── app/                  # Next.js app router
│   ├── components/           # React + PixiJS components
│   └── lib/                  # API client, helpers
│
├── tests/                    # TEST SUITE (human writes initial batch)
│   ├── conftest.py           # Fixtures — human writes this
│   ├── test_grid.py          # Grid tests
│   ├── test_buildings.py     # Building tests
│   ├── test_npcs.py          # NPC tests
│   ├── test_tick.py          # Simulation tick tests
│   ├── test_economy.py       # Economy tests
│   ├── test_events.py        # Event tests
│   └── test_api.py           # API endpoint tests
│
├── assets/                   # GENERATED ART (ComfyUI output)
│   ├── buildings/
│   ├── npcs/
│   └── terrain/
│
├── snapshots/                # AUTO-CAPTURED TOWN SCREENSHOTS
│
├── prd.json                  # STORY BACKLOG (human writes initial batch)
├── AGENTS.md                 # CONVENTIONS FOR QWEN (human writes)
├── metrics.jsonl             # ITERATION LOG (auto-generated)
├── requirements.txt          # Python dependencies
├── package.json              # Node dependencies (ui/)
└── start_all.bat             # Starts all services
```

---

## 5. The Launchpad (Human-Written Code)

This is the minimal skeleton — ~200 lines total. It exists so Qwen has a working app to build on and patterns to follow.

### 5.1 `engine/db.py` — Database Connection

```python
"""SQLite database setup. Qwen: do not modify this file."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./town.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
```

### 5.2 `engine/models.py` — Starter Model

```python
"""Database models. Qwen: ADD new models here. Do not remove existing ones."""

from sqlalchemy import Column, Integer, String
from engine.db import Base


class Tile(Base):
    __tablename__ = "tiles"

    id = Column(Integer, primary_key=True)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    terrain = Column(String, default="grass")  # grass, water, dirt, stone
```

### 5.3 `engine/main.py` — FastAPI Skeleton

```python
"""Town Engine API. Qwen: add routers via app.include_router()."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from engine.db import init_db

app = FastAPI(title="Qwen Town Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
```

### 5.4 `tests/conftest.py` — Test Fixtures

```python
"""Shared test fixtures. Qwen: do not modify this file."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from engine.db import Base

TEST_DATABASE_URL = "sqlite:///./test_town.db"


@pytest.fixture
def db():
    """Fresh database for each test."""
    test_engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)
```

### 5.5 `start_all.bat` — Launch Everything

```batch
@echo off
echo Starting Qwen Town...
echo.

echo [1/3] Ollama should already be running as a service.
echo       Verify: curl http://localhost:11434/api/tags
echo.

echo [2/3] Starting ComfyUI on GPU 1...
start "ComfyUI" cmd /k "cd /d C:\path\to\ComfyUI && set CUDA_VISIBLE_DEVICES=1 && python main.py --port 8188"

echo [3/3] Starting Town Engine...
start "Engine" cmd /k "cd /d C:\path\to\qwen-town && python -m uvicorn engine.main:app --reload --port 8000"

echo.
echo All services starting. Wait 30 seconds, then run Ralph:
echo   python ralph/ralph.py
```

---

## 6. The Ralph Loop (Human-Written — DETAILED)

This is the brain of the whole operation. ~300 lines of Python across 5 files.

### 6.1 `ralph/ralph.py` — Main Orchestrator

This is the main loop. It runs forever until all stories pass.

```python
"""
Ralph — the dumb orchestrator.
Reads stories from prd.json, runs tests, calls Qwen, applies code, commits.
"""

import json
import time
import subprocess
from pathlib import Path
from ralph.prompt_builder import build_prompt
from ralph.file_writer import apply_changes
from ralph.test_runner import run_tests
from ralph.metrics import log_metric
from ralph.snapshot import maybe_snapshot

# --- Config ---
PRD_PATH = Path("prd.json")
MAX_RETRIES = 10          # Max attempts per story before skipping
QWEN_MODEL = "qwen3.5:35b"
QWEN_URL = "http://localhost:11434/v1/chat/completions"
STORIES_BETWEEN_SNAPSHOTS = 5


def load_prd():
    """Load the story backlog."""
    with open(PRD_PATH) as f:
        return json.load(f)


def save_prd(prd):
    """Save updated story statuses."""
    with open(PRD_PATH, "w") as f:
        json.dump(prd, f, indent=2)


def pick_next_story(prd):
    """Find the next pending story by priority."""
    pending = [s for s in prd["stories"] if s["status"] == "pending"]
    if not pending:
        return None
    return sorted(pending, key=lambda s: s["priority"])[0]


def call_qwen(prompt: str) -> str:
    """Send a prompt to Qwen and get the response."""
    import requests

    response = requests.post(
        QWEN_URL,
        json={
            "model": QWEN_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,      # Low temp for code
            "max_tokens": 16384,     # Enough for full file outputs
            "stream": False,
        },
        timeout=300,  # 5 min timeout
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def git_commit(story):
    """Commit the current changes with a message referencing the story."""
    subprocess.run(["git", "add", "-A"], check=True)
    msg = f"[Ralph] Story {story['id']}: {story['title']}"
    subprocess.run(["git", "commit", "-m", msg], check=True)


def git_tag_if_milestone(completed_count):
    """Tag every 25 completed stories."""
    if completed_count % 25 == 0:
        tag = f"milestone-{completed_count}"
        subprocess.run(["git", "tag", tag], check=True)
        print(f"  Tagged: {tag}")


def main():
    print("=" * 60)
    print("  RALPH — Qwen Town Autonomous Builder")
    print("=" * 60)

    completed_count = 0

    while True:
        prd = load_prd()
        story = pick_next_story(prd)

        if story is None:
            print("\n ALL STORIES COMPLETE!")
            break

        story_id = story["id"]
        print(f"\n--- Story {story_id}: {story['title']} ---")
        print(f"    Attempt {story.get('attempts', 0) + 1}/{MAX_RETRIES}")

        # Step 1: Run the tests to confirm they fail
        test_result = run_tests(story["test_file"])

        if test_result["passed"]:
            # Tests already pass — story is done (maybe from a previous partial run)
            print(f"  Tests already pass! Marking complete.")
            story["status"] = "complete"
            save_prd(prd)
            completed_count += 1
            git_tag_if_milestone(completed_count)
            maybe_snapshot(completed_count, STORIES_BETWEEN_SNAPSHOTS)
            continue

        # Step 2: Build the prompt
        prompt = build_prompt(story, test_result["output"])

        # Step 3: Call Qwen
        print(f"  Calling Qwen...")
        start_time = time.time()
        try:
            response = call_qwen(prompt)
        except Exception as e:
            print(f"  Qwen call failed: {e}")
            log_metric(story_id, False, 0, str(e))
            time.sleep(5)  # Brief pause before retry
            continue
        elapsed = time.time() - start_time
        print(f"  Qwen responded in {elapsed:.1f}s")

        # Step 4: Apply the changes
        files_changed = apply_changes(response)
        if not files_changed:
            print(f"  No valid file blocks in response. Retrying.")
            story["attempts"] = story.get("attempts", 0) + 1
            save_prd(prd)
            log_metric(story_id, False, elapsed, "no_file_blocks")
            continue

        print(f"  Applied changes to: {', '.join(files_changed)}")

        # Step 5: Re-run tests
        test_result = run_tests(story["test_file"])

        # Step 6: Commit or retry
        if test_result["passed"]:
            print(f"  PASSED! Committing.")
            git_commit(story)
            story["status"] = "complete"
            save_prd(prd)
            completed_count += 1
            git_tag_if_milestone(completed_count)
            maybe_snapshot(completed_count, STORIES_BETWEEN_SNAPSHOTS)
            log_metric(story_id, True, elapsed, "")
        else:
            story["attempts"] = story.get("attempts", 0) + 1
            if story["attempts"] >= MAX_RETRIES:
                print(f"  SKIPPED after {MAX_RETRIES} attempts.")
                story["status"] = "skipped"
            save_prd(prd)
            log_metric(story_id, False, elapsed, test_result["output"][:500])

    print(f"\nDone. {completed_count} stories completed.")


if __name__ == "__main__":
    main()
```

### 6.2 `ralph/prompt_builder.py` — Prompt Assembly

This builds the prompt Qwen sees. It includes: the story, the failing test output, the relevant source files, and strict output format instructions.

```python
"""Builds prompts for Qwen. Reads context files and assembles everything."""

from pathlib import Path

# Hard ceiling on context sent to Qwen (in characters, ~4 chars per token)
MAX_CONTEXT_CHARS = 100_000  # ~25K tokens, leaves room for output

AGENTS_MD = Path("AGENTS.md").read_text() if Path("AGENTS.md").exists() else ""


def build_prompt(story: dict, test_output: str) -> str:
    """
    Build the full prompt for Qwen.

    Includes:
    - System instructions (from AGENTS.md)
    - The story description and acceptance criteria
    - The failing test output
    - Contents of relevant source files
    - Output format instructions
    """
    # Read context files
    file_contents = []
    char_budget = MAX_CONTEXT_CHARS
    for file_path in story.get("context_files", []):
        p = Path(file_path)
        if p.exists():
            content = p.read_text()
            if len(content) <= char_budget:
                file_contents.append(f"### FILE: {file_path}\n```\n{content}\n```")
                char_budget -= len(content)
            else:
                file_contents.append(
                    f"### FILE: {file_path}\n(truncated — {len(content)} chars, budget exceeded)"
                )

    # Read the test file too (so Qwen knows what it's targeting)
    test_path = Path(story["test_file"])
    if test_path.exists():
        test_content = test_path.read_text()
        file_contents.append(f"### TEST FILE: {story['test_file']}\n```\n{test_content}\n```")

    files_section = "\n\n".join(file_contents) if file_contents else "(no files)"

    prompt = f"""You are a senior developer building Qwen Town, a 2D town simulation.

{AGENTS_MD}

---

## YOUR TASK

**Story {story['id']}:** {story['title']}

{story['description']}

**Acceptance criteria:**
{story.get('acceptance', 'All tests pass.')}

---

## FAILING TEST OUTPUT

```
{test_output[:3000]}
```

---

## RELEVANT SOURCE FILES

{files_section}

---

## OUTPUT FORMAT

Respond ONLY with file blocks. No explanation, no commentary.

For each file you create or modify, output:

### FILE: path/to/file.py
```
(complete file contents here)
```

RULES:
- Output the COMPLETE file contents (not diffs, not patches, not snippets)
- Only include files you are creating or modifying
- Do NOT modify any test files
- Do NOT modify files in ralph/
- Make the SMALLEST change possible to pass the tests
- If you need to add a new import to an existing file, include the whole file
"""
    return prompt
```

### 6.3 `ralph/file_writer.py` — Parse & Apply Qwen's Output

This parses the file blocks from Qwen's response and writes them to disk.

```python
"""Parses Qwen's output and writes files to disk."""

import re
from pathlib import Path

# Matches: ### FILE: some/path.py followed by a code block
FILE_BLOCK_PATTERN = re.compile(
    r'###\s*FILE:\s*(.+?)\s*\n\s*```[\w]*\n(.*?)\n```',
    re.DOTALL
)


def apply_changes(response: str) -> list[str]:
    """
    Parse file blocks from Qwen's response and write them.

    Returns list of file paths that were written.
    """
    blocks = FILE_BLOCK_PATTERN.findall(response)

    if not blocks:
        return []

    written = []
    for file_path, content in blocks:
        file_path = file_path.strip()

        # Safety: never write outside the project
        if ".." in file_path or file_path.startswith("/"):
            print(f"  BLOCKED: Refusing to write to {file_path}")
            continue

        # Safety: never overwrite ralph/ or test files
        if file_path.startswith("ralph/"):
            print(f"  BLOCKED: Cannot modify ralph/ — {file_path}")
            continue
        if file_path.startswith("tests/"):
            print(f"  BLOCKED: Cannot modify tests/ — {file_path}")
            continue

        # Create parent directories if needed
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        p.write_text(content.strip() + "\n")
        written.append(file_path)

    return written
```

### 6.4 `ralph/test_runner.py` — Run Tests

```python
"""Runs pytest for a specific test file and captures output."""

import subprocess


def run_tests(test_file: str) -> dict:
    """
    Run pytest on a single test file.

    Returns:
        {"passed": bool, "output": str}
    """
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", test_file, "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout per test run
            cwd=".",
        )
        output = result.stdout + "\n" + result.stderr
        passed = result.returncode == 0
    except subprocess.TimeoutExpired:
        output = "TIMEOUT: Tests took longer than 60 seconds."
        passed = False
    except Exception as e:
        output = f"ERROR running tests: {e}"
        passed = False

    return {"passed": passed, "output": output}
```

### 6.5 `ralph/metrics.py` — Logging

```python
"""Logs iteration metrics to metrics.jsonl."""

import json
import time
from pathlib import Path

METRICS_PATH = Path("metrics.jsonl")


def log_metric(story_id: str, passed: bool, duration: float, error: str = ""):
    """Append one line to the metrics log."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "story_id": story_id,
        "passed": passed,
        "duration_sec": round(duration, 1),
        "error": error[:500] if error else "",
    }
    with open(METRICS_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

### 6.6 `ralph/snapshot.py` — Progress Capture

```python
"""Captures town state snapshots for timelapse."""

import json
import requests
from pathlib import Path

SNAPSHOT_DIR = Path("snapshots")
ENGINE_URL = "http://localhost:8000"


def maybe_snapshot(completed_count: int, interval: int):
    """Take a snapshot every N completed stories."""
    if completed_count % interval != 0:
        return

    SNAPSHOT_DIR.mkdir(exist_ok=True)

    try:
        # Grab the world state from the engine API
        resp = requests.get(f"{ENGINE_URL}/api/world", timeout=10)
        if resp.ok:
            snapshot_path = SNAPSHOT_DIR / f"snapshot_{completed_count:04d}.json"
            with open(snapshot_path, "w") as f:
                json.dump(resp.json(), f, indent=2)
            print(f"  Snapshot saved: {snapshot_path}")
    except Exception as e:
        print(f"  Snapshot failed (non-fatal): {e}")
```

---

## 7. The PRD — Story Backlog

### 7.1 Story Format

Each story in `prd.json` has:

```json
{
  "id": "001",
  "title": "Short imperative title",
  "description": "What Qwen needs to build. Be specific.",
  "acceptance": "What 'done' looks like.",
  "test_file": "tests/test_something.py",
  "context_files": ["engine/models.py", "engine/db.py"],
  "priority": 1,
  "status": "pending",
  "attempts": 0
}
```

- **context_files**: The files Qwen will see. Keep this small and targeted.
- **priority**: Lower number = do first. Stories are attempted in priority order.
- **status**: `pending` → `complete` or `skipped`

### 7.2 Initial Story Batch

These are the ~25 stories the human writes to take the town from empty skeleton to living village. Each story is small (one concept, one test file).

**Phase 1: Foundation (priority 1-10)**

| ID | Title | Test File | Priority |
|----|-------|-----------|----------|
| 001 | Initialize 50x50 grid | tests/test_grid.py | 1 |
| 002 | Add Building model | tests/test_buildings.py | 2 |
| 003 | Add NPC model | tests/test_npcs.py | 3 |
| 004 | Seed initial buildings | tests/test_buildings.py | 4 |
| 005 | Seed initial NPCs | tests/test_npcs.py | 5 |
| 006 | World state API endpoint | tests/test_api.py | 6 |
| 007 | Tick endpoint — advance simulation | tests/test_tick.py | 7 |
| 008 | NPC daily movement | tests/test_tick.py | 8 |
| 009 | Buildings API — CRUD | tests/test_api.py | 9 |
| 010 | NPCs API — CRUD | tests/test_api.py | 10 |

**Phase 2: Behaviors (priority 11-20)**

| ID | Title | Test File | Priority |
|----|-------|-----------|----------|
| 011 | Basic economy — gold transactions | tests/test_economy.py | 11 |
| 012 | NPC hunger and needs | tests/test_tick.py | 12 |
| 013 | Eating at the market resets hunger | tests/test_economy.py | 13 |
| 014 | Sleeping at home resets energy | tests/test_tick.py | 14 |
| 015 | Resource production — merchants earn gold | tests/test_economy.py | 15 |
| 016 | New building construction | tests/test_buildings.py | 16 |
| 017 | Population growth | tests/test_tick.py | 17 |
| 018 | Weather system | tests/test_events.py | 18 |
| 019 | Event log | tests/test_events.py | 19 |
| 020 | Town stats endpoint | tests/test_api.py | 20 |

**Phase 3: UI + Polish (priority 21-25)**

| ID | Title | Test File | Priority |
|----|-------|-----------|----------|
| 021 | UI — render tile grid | tests/test_ui.py | 21 |
| 022 | UI — render buildings on grid | tests/test_ui.py | 22 |
| 023 | UI — render NPCs on grid | tests/test_ui.py | 23 |
| 024 | UI — stats panel | tests/test_ui.py | 24 |
| 025 | UI — event feed | tests/test_ui.py | 25 |

See `prd.json` for full story details including descriptions, acceptance criteria, and context files.

### 7.3 Initial Test Files

The human writes these tests. They must exist BEFORE Ralph starts. Each test is simple — just assert the behavior described in the story.

Example — `tests/test_grid.py`:
```python
from engine.db import Base
from engine.models import Tile


def test_init_grid_creates_2500_tiles(db):
    from engine.simulation import init_grid
    init_grid(db)
    tiles = db.query(Tile).all()
    assert len(tiles) == 2500  # 50 * 50


def test_init_grid_all_grass(db):
    from engine.simulation import init_grid
    init_grid(db)
    tiles = db.query(Tile).all()
    assert all(t.terrain == "grass" for t in tiles)


def test_init_grid_no_duplicates(db):
    from engine.simulation import init_grid
    init_grid(db)
    init_grid(db)  # Call twice
    tiles = db.query(Tile).all()
    assert len(tiles) == 2500  # Still 2500, not 5000
```

Example — `tests/test_buildings.py`:
```python
from engine.models import Building


def test_create_building(db):
    b = Building(name="Town Hall", building_type="town_hall", x=25, y=25)
    db.add(b)
    db.commit()
    assert db.query(Building).count() == 1


def test_seed_creates_five_buildings(db):
    from engine.simulation import seed_town
    seed_town(db)
    assert db.query(Building).count() == 5


def test_seed_town_hall_position(db):
    from engine.simulation import seed_town
    seed_town(db)
    hall = db.query(Building).filter_by(building_type="town_hall").first()
    assert hall is not None
    assert hall.x == 25
    assert hall.y == 25
```

*(Human writes similar tests for all initial story test files.)*

---

## 8. AGENTS.md — Rules for Qwen

This file is included at the top of every prompt. It teaches Qwen the codebase conventions.

```markdown
# Qwen Town — Developer Conventions

You are building a 2D town simulation. Follow these rules exactly.

## Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy, SQLite
- Frontend: Next.js 14 (App Router), TypeScript, PixiJS
- Tests: pytest

## Code Style
- Python: type hints on function signatures. No docstrings unless logic is non-obvious.
- TypeScript: functional components, no class components.
- Keep functions under 50 lines. Split if longer.
- One model per concept. One router per resource.

## Architecture Rules
- ALL state lives in SQLite. No global variables, no in-memory caches.
- New API routes go in engine/routers/ and get included in engine/main.py.
- New models go in engine/models.py (one file, all models).
- Simulation logic goes in engine/simulation.py.
- Frontend components go in ui/components/.

## Output Format
Respond ONLY with file blocks. No explanation text.

For each file you create or modify:

### FILE: path/to/file.py
(complete file contents in a code block)

RULES:
- Output the COMPLETE file contents every time
- Only include files you are creating or modifying
- Do NOT modify test files (tests/)
- Do NOT modify ralph/ files
- Do NOT modify AGENTS.md
- Make the smallest change possible to pass the tests
```

---

## 9. Progress Capture

Built into the Ralph loop automatically:

| What | How | Where |
|------|-----|-------|
| Every code change | Git commit on each passing story | `.git/` |
| Iteration metrics | One JSON line per attempt | `metrics.jsonl` |
| Milestones | Git tag every 25 stories | `git tag milestone-N` |
| Town snapshots | JSON dump every 5 stories | `snapshots/` |

### Generating the Timelapse (after the run)

```bash
# If you add a /api/screenshot endpoint later (renders grid to PNG):
ffmpeg -framerate 2 -pattern_type glob -i 'snapshots/*.png' -c:v libx264 timelapse.mp4
```

### Quick Stats (during the run)

```bash
# How many stories completed?
git log --oneline | grep "\[Ralph\]" | wc -l

# Pass rate?
python -c "
import json
lines = open('metrics.jsonl').readlines()
entries = [json.loads(l) for l in lines]
passed = sum(1 for e in entries if e['passed'])
print(f'{passed}/{len(entries)} attempts passed ({100*passed//len(entries)}%)')
"
```

---

## 10. Kickoff Checklist

Run through this in order:

```
[ ] 1. Install Python 3.11+, Node.js 20+, Git
[ ] 2. Install Ollama, pull qwen3.5:35b, verify with curl
[ ] 3. Verify 3090 Ti is GPU 0 (nvidia-smi), set CUDA_VISIBLE_DEVICES
[ ] 4. Install ComfyUI, download SDXL + LoRA, test image generation
[ ] 5. Create the repo: git init qwen-town && cd qwen-town
[ ] 6. Write the launchpad files (Section 5)
[ ] 7. Write the Ralph loop files (Section 6)
[ ] 8. Write the test files (Section 7.3)
[ ] 9. Write prd.json with the initial 25 stories (Section 7.2)
[ ] 10. Write AGENTS.md (Section 8)
[ ] 11. pip install fastapi uvicorn sqlalchemy requests pytest
[ ] 12. npm create next-app@latest ui (accept defaults + TypeScript)
[ ] 13. git add -A && git commit -m "Initial launchpad — human scaffolding"
[ ] 14. Start Ollama (should be running already)
[ ] 15. Start town engine: python -m uvicorn engine.main:app --port 8000
[ ] 16. Run Ralph: python ralph/ralph.py
[ ] 17. Watch it go.
```

---

## 11. What Happens Next (Phase 2 — Later)

Not part of the initial build. Only after the village is alive:

- **Auto-tick**: Add a cron/scheduler that calls POST /api/tick every N seconds so the town runs continuously
- **Asset generation**: Add "asset" story types that call ComfyUI to generate sprites
- **Public viewer**: Static site that reads snapshot JSON and renders the town
- **Feature voting**: Simple form where people suggest new features → auto-converted to PRD stories
- **Self-expanding PRD**: Have Qwen propose new stories when the current batch is complete

---

## Appendix: Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Qwen outputs malformed file blocks | file_writer.py returns empty list → loop retries with same prompt |
| Qwen breaks existing functionality | Tests for ALL previous stories still run (add regression check) |
| Story stuck after 10 retries | Marked "skipped", loop moves on. Come back manually later. |
| Growing codebase exceeds context | context_files are explicit per story. Prompt builder enforces 25K token budget. |
| Model hallucinates imports/modules | Tests catch import errors immediately. Prompt includes real file contents. |
| Git repo gets corrupted | Ralph only does `git add -A` and `git commit`. No force pushes, no resets. |
