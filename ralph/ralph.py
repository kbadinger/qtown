"""Ralph — the main orchestrator loop.

Reads failing tests, sends them to Qwen, applies code, commits on pass.
Full pipeline: test → Qwen → apply → test → commit → push → deploy → snapshot.

Supports safe shutdown via HUMAN.md (action: pause) or SIGINT/SIGTERM.
"""

import json
import os
import random
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import requests
import yaml

from ralph.alerter import notify, warn, alert
from ralph.changelog import log_human_intervention
from ralph.cost_tracker import log_cost
from ralph.deployer import push_and_wait
from ralph.file_writer import apply_files, parse_file_blocks, apply_patch
from ralph.metrics import log_metric
from ralph.prompt_builder import build_prompt, build_conflict_prompt, _extract_story_tests
from ralph.snapshot import take_all_snapshots
from ralph.story_generator import (
    import_approved,
    needs_generation,
    build_generation_prompt,
    save_proposed,
    request_review,
)
from ralph.learnings import append_learning, build_learning_prompt
from ralph.test_runner import run_tests, run_regression_tests
from ralph.asset_gen import check_comfyui_health

PRD_FILE = Path("prd.json")
HUMAN_MD = Path("HUMAN.md")
HELP_FILE = Path(".ralph-needs-help.json")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:27b")
MAX_ATTEMPTS = 12
HELP_WAIT_SECONDS = 600  # 10 minutes

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print("\n[Ralph] Shutdown requested — finishing current story...")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ---------------------------------------------------------------------------
# Auto-fix known Qwen mistakes before testing
# ---------------------------------------------------------------------------

def _autofix_postgres_compat():
    """Fix known Postgres-incompatible patterns Qwen keeps writing."""
    import re
    fixes_applied = 0
    sim_dir = Path("engine/simulation")
    for py_file in sim_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        text = py_file.read_text(encoding="utf-8")
        original = text
        # Fix boolean comparisons: == False → == 0, == True → == 1
        text = re.sub(r'(\w+\.is_dead)\s*==\s*False', r'\1 == 0', text)
        text = re.sub(r'(\w+\.is_dead)\s*==\s*True', r'\1 == 1', text)
        text = re.sub(r'(\w+\.is_bankrupt)\s*==\s*False', r'\1 == 0', text)
        text = re.sub(r'(\w+\.is_bankrupt)\s*==\s*True', r'\1 == 1', text)
        text = re.sub(r'(\w+\.resolved)\s*==\s*False', r'\1 == 0', text)
        text = re.sub(r'(\w+\.resolved)\s*==\s*True', r'\1 == 1', text)
        text = re.sub(r'(\w+\.achieved)\s*==\s*False', r'\1 == 0', text)
        text = re.sub(r'(\w+\.achieved)\s*==\s*True', r'\1 == 1', text)
        text = re.sub(r'(\w+\.illness)\s*==\s*False', r'\1 == 0', text)
        text = re.sub(r'(\w+\.illness)\s*==\s*True', r'\1 == 1', text)
        if text != original:
            py_file.write_text(text, encoding="utf-8")
            fixes_applied += 1
            print(f"  [autofix] Postgres compat fixes applied to {py_file.name}")
    return fixes_applied


# ---------------------------------------------------------------------------
# Help file: pause for external fix, then retry
# ---------------------------------------------------------------------------

def _request_help(story_id, story_title, error_msg, test_file, attempt):
    """Write .ralph-needs-help.json and wait for external fix."""
    help_data = {
        "story_id": story_id,
        "story_title": story_title,
        "error": error_msg,
        "test_file": test_file,
        "attempt": attempt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    HELP_FILE.write_text(json.dumps(help_data, indent=2), encoding="utf-8")
    alert("needs_help", f"Story {story_id} needs help — waiting {HELP_WAIT_SECONDS // 60}min for fix\n`{error_msg[:120]}`")
    print(f"  [help] Wrote {HELP_FILE} — waiting {HELP_WAIT_SECONDS // 60} minutes for external fix...")

    # Wait, checking for shutdown every 30s
    waited = 0
    while waited < HELP_WAIT_SECONDS:
        if _shutdown_requested:
            return False
        time.sleep(30)
        waited += 30
        # If help file was deleted, someone handled it early
        if not HELP_FILE.exists():
            print(f"  [help] Help file removed early — someone fixed it!")
            break

    # Pull any fixes
    print(f"  [help] Wait complete — pulling latest changes...")
    subprocess.run(["git", "pull", "--rebase", "origin", "main"], capture_output=True)

    # Clean up help file
    if HELP_FILE.exists():
        HELP_FILE.unlink()

    return True



def should_stop() -> bool:
    """Check if Ralph should stop (signal or HUMAN.md pause)."""
    if _shutdown_requested:
        return True
    intervention = read_intervention()
    return intervention.get("action") in ("pause", "review_stories")


# ---------------------------------------------------------------------------
# Human intervention
# ---------------------------------------------------------------------------


def read_intervention() -> dict:
    """Read HUMAN.md YAML frontmatter for intervention instructions."""
    if not HUMAN_MD.exists():
        return {"action": "none"}
    content = HUMAN_MD.read_text(encoding="utf-8")
    # Extract YAML frontmatter between --- delimiters
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                return yaml.safe_load(parts[1]) or {"action": "none"}
            except yaml.YAMLError:
                pass
    return {"action": "none"}


def clear_oneshot_action():
    """Clear one-shot actions (skip, retry, instruction, approve_stories) after use."""
    if not HUMAN_MD.exists():
        return
    content = HUMAN_MD.read_text(encoding="utf-8")
    import re

    content = re.sub(r"action:\s*\w+", "action: none", content)
    content = re.sub(r"message:\s*.+", "message: null", content)
    HUMAN_MD.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Qwen interaction
# ---------------------------------------------------------------------------


def _ts() -> str:
    """Compact UTC timestamp for log lines."""
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def call_qwen(prompt: str, label: str = "qwen", think: bool = True) -> tuple[str, int, int, float]:
    """Call Qwen via Ollama /api/chat with exponential backoff on infra failures.

    Returns (response_text, tokens_in, tokens_out, duration_sec).
    Retries up to 5 times on network errors with backoff: 15s, 35s, 65s, 125s, 245s.
    Returns ("", 0, 0, 0.0) only after all retries are exhausted.
    Bad JSON responses return immediately (no retry — that's a Qwen problem).
    """
    max_retries = 5
    base_delay = 15  # seconds
    prompt_chars = len(prompt)
    think_str = "think" if think else "no-think"
    print(f"  [{_ts()}] Ollama call starting ({label}, {prompt_chars} chars, {think_str})")

    # Thinking vs non-thinking use different recommended params
    if think:
        options = {"num_ctx": 16384, "num_predict": 16384, "temperature": 0.6,
                   "top_p": 0.95, "repeat_penalty": 1.1, "presence_penalty": 1.5}
    else:
        options = {"num_ctx": 16384, "num_predict": 8192, "temperature": 0.7,
                   "top_p": 0.8, "repeat_penalty": 1.1, "presence_penalty": 1.5}

    for attempt in range(max_retries + 1):
        try:
            start = time.time()
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "think": think,
                    "options": options,
                },
                timeout=7200,
            )
            duration = time.time() - start
            data = resp.json()

            msg = data.get("message", {})
            response_text = msg.get("content", "")
            tokens_in = data.get("prompt_eval_count", 0)
            tokens_out = data.get("eval_count", 0)

            think_chars = len(msg.get("thinking", "") or "")
            print(f"  [{_ts()}] Ollama done ({label}, {duration:.0f}s, {tokens_in} in, {tokens_out} out, {len(response_text)} chars response, {think_chars} chars thinking)")

            # Thinking spiral detection: if think mode used all tokens on thinking
            # with 0 actual response, retry once with think=False
            if think and len(response_text.strip()) == 0 and think_chars > 5000:
                print(f"  [{_ts()}] Thinking spiral detected ({think_chars} chars thinking, 0 response) — retrying with think=False")
                return call_qwen(prompt, label=label + " (no-think retry)", think=False)

            return response_text, tokens_in, tokens_out, duration

        except requests.RequestException as e:
            elapsed = time.time() - start
            print(f"  [{_ts()}] Ollama error after {elapsed:.0f}s: {e}")
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                warn(
                    "ollama_retry",
                    f"Ollama unreachable (attempt {attempt + 1}/{max_retries + 1}): {e}\nRetrying in {delay:.0f}s",
                )
                time.sleep(delay)
            else:
                alert(
                    "critical",
                    f"Ollama unreachable after {max_retries + 1} attempts — giving up\nLast error: {e}",
                )
                return "", 0, 0, 0.0

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            elapsed = time.time() - start
            print(f"  [{_ts()}] Ollama bad response after {elapsed:.0f}s: {e}")
            warn("ollama_bad_response", f"Ollama bad response: {e}")
            return "", 0, 0, 0.0

    return "", 0, 0, 0.0


# ---------------------------------------------------------------------------
# Startup preflight checks
# ---------------------------------------------------------------------------


def preflight() -> bool:
    """Verify prerequisites before entering the main loop.

    Returns True if all checks pass, False otherwise.
    """
    ok = True

    # 1. prd.json exists and is valid JSON
    if not PRD_FILE.exists():
        print(f"[PREFLIGHT FAIL] {PRD_FILE} not found")
        ok = False
    else:
        try:
            json.loads(PRD_FILE.read_text(encoding="utf-8"))
            print(f"[PREFLIGHT OK] {PRD_FILE} is valid JSON")
        except (json.JSONDecodeError, OSError) as e:
            print(f"[PREFLIGHT FAIL] {PRD_FILE} is not valid JSON: {e}")
            ok = False

    # 2. Ollama is reachable
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        resp.raise_for_status()
        tags_data = resp.json()
        models = [m.get("name", "") for m in tags_data.get("models", [])]
        # 3. Model is available — check prefix match (ollama may append :latest)
        model_found = any(
            m == OLLAMA_MODEL or m.startswith(OLLAMA_MODEL + ":")
            for m in models
        )
        if model_found:
            print(f"[PREFLIGHT OK] Ollama reachable, model '{OLLAMA_MODEL}' available")
        else:
            print(f"[PREFLIGHT FAIL] Model '{OLLAMA_MODEL}' not found. Available: {models}")
            ok = False
    except Exception as e:
        print(f"[PREFLIGHT FAIL] Cannot reach Ollama at {OLLAMA_URL}: {e}")
        ok = False

    # 4. git status succeeds (we're in a repo)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print("[PREFLIGHT OK] Git repository OK")
        else:
            print(f"[PREFLIGHT FAIL] git status failed: {result.stderr.strip()}")
            ok = False
    except Exception as e:
        print(f"[PREFLIGHT FAIL] git not available: {e}")
        ok = False

    # 5. ComfyUI is reachable (optional — sprites will be skipped if down)
    if check_comfyui_health():
        print("[PREFLIGHT OK] ComfyUI reachable")
    else:
        print("[PREFLIGHT WARN] ComfyUI not reachable — sprites will be skipped")

    return ok


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------


def git_commit(message: str):
    """Stage Qwen-writable paths and commit. Never stages .env or secrets."""
    safe_paths = ["engine/", "assets/", "prd.json", "cost_tracking.json",
                  "metrics.jsonl", "progress.txt", "alerts.log"]
    for p in safe_paths:
        subprocess.run(["git", "add", p], capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        check=True,
        capture_output=True,
    )


def git_commit_snapshots(story_id: str):
    """Commit snapshot files."""
    subprocess.run(["git", "add", "snapshots/"], capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"[Ralph] Snapshot: Story {story_id}"],
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def load_prd() -> dict:
    """Load the PRD file."""
    return json.loads(PRD_FILE.read_text(encoding="utf-8"))


def save_prd(prd: dict):
    """Save the PRD file."""
    with open(PRD_FILE, "w", encoding="utf-8") as f:
        json.dump(prd, f, indent=2)


def get_next_story(prd: dict) -> dict | None:
    """Get the next story to work on — resume in_progress first, then pending."""
    # Resume any story left in_progress from a crash/restart
    in_progress = [s for s in prd["stories"] if s["status"] == "in_progress"]
    if in_progress:
        return sorted(in_progress, key=lambda s: s.get("priority", 999))[0]
    pending = [s for s in prd["stories"] if s["status"] == "pending"]
    if not pending:
        return None
    return sorted(pending, key=lambda s: s.get("priority", 999))[0]


def resolve_test_conflict(story: dict, reg_output: str, test_file: str) -> bool:
    """Attempt to resolve a test conflict by asking Qwen to fix the current story's test.

    When the current story's test contradicts a regression test (e.g. "Tool" vs "Tools"),
    this sends both tests to Qwen and asks it to fix the current story's test.

    Returns True if the fix was applied and validated, False otherwise.
    """
    import re as _re

    story_id = story["id"]

    # Parse regression story ID from output: "REGRESSION in Story 071: ..."
    m = _re.match(r"REGRESSION in Story (\d+):", reg_output)
    if not m:
        print("  [CONFLICT] Could not parse regression story ID — skipping")
        return False
    reg_story_id = m.group(1)

    # Determine which test file the regression story lives in
    prd = load_prd()
    reg_story = None
    for s in prd["stories"]:
        if s["id"] == reg_story_id:
            reg_story = s
            break
    if not reg_story:
        print(f"  [CONFLICT] Regression story {reg_story_id} not found in PRD — skipping")
        return False
    reg_test_file = reg_story["test_file"]

    # Extract test sources
    current_test_source = _extract_story_tests(test_file, story_id)
    reg_test_source = _extract_story_tests(reg_test_file, reg_story_id)

    if not current_test_source or not reg_test_source:
        print(f"  [CONFLICT] Could not extract test sources — skipping")
        return False

    print(f"  [CONFLICT] Detected repeated regression failure against Story {reg_story_id}")
    print(f"  [CONFLICT] Asking Qwen to fix Story {story_id}'s test to match Story {reg_story_id}")

    # Build and send the conflict prompt
    prompt = build_conflict_prompt(story, current_test_source, reg_story_id, reg_test_source, test_file)
    response, tokens_in, tokens_out, gpu_time = call_qwen(prompt, label=f"conflict {story_id} vs {reg_story_id}")
    log_cost(tokens_in=tokens_in, tokens_out=tokens_out, gpu_time_sec=gpu_time)

    if not response:
        print(f"  [CONFLICT] Qwen returned empty response — skipping")
        return False

    # Debug: save conflict response
    try:
        debug_dir = Path("ralph/debug_responses")
        debug_dir.mkdir(exist_ok=True)
        debug_file = debug_dir / f"{story_id}_conflict_vs_{reg_story_id}.txt"
        debug_file.write_text(response, encoding="utf-8")
    except Exception:
        pass

    # Parse the response for test file patches
    file_blocks = parse_file_blocks(response)
    if not file_blocks:
        print(f"  [CONFLICT] No file blocks in Qwen's response — skipping")
        return False

    # Apply ONLY patches targeting the current story's test file
    applied = False
    for block in file_blocks:
        norm_path = block.filepath.replace("\\", "/")
        norm_test = test_file.replace("\\", "/")
        if norm_path != norm_test:
            print(f"  [CONFLICT] Ignoring patch for {block.filepath} (expected {test_file})")
            continue
        if block.mode == "patch" and block.sections:
            try:
                new_content = apply_patch(test_file, block.sections)
                Path(test_file).write_text(new_content, encoding="utf-8")
                applied = True
                print(f"  [CONFLICT] Applied test fix to {test_file}")
            except Exception as e:
                print(f"  [CONFLICT] Failed to apply patch: {e}")
                return False

    if not applied:
        print(f"  [CONFLICT] No applicable patches found — skipping")
        return False

    # Validate: run both the current story's test and the regression test
    from ralph.test_runner import run_tests as _run_tests

    current_ok, _ = _run_tests(test_file, story_id)
    if not current_ok:
        print(f"  [CONFLICT] Fixed test doesn't pass for current story — reverting")
        subprocess.run(["git", "checkout", test_file], capture_output=True)
        return False

    reg_ok, _ = _run_tests(reg_test_file, reg_story_id)
    if not reg_ok:
        print(f"  [CONFLICT] Fixed test breaks regression story {reg_story_id} — reverting")
        subprocess.run(["git", "checkout", test_file], capture_output=True)
        return False

    # Success — stage the test fix
    subprocess.run(["git", "add", test_file], capture_output=True)
    print(f"  [CONFLICT] Test conflict resolved! Staged {test_file}")
    notify("conflict_resolved", f"Story {story_id}: Auto-resolved test conflict with Story {reg_story_id}")
    return True


def run_story(story: dict) -> bool:
    """Run a single story through the full pipeline.

    Returns True if the story passed, False otherwise.
    """
    story_id = story["id"]
    test_file = story["test_file"]
    intervention = read_intervention()
    intervention_msg = None
    if intervention.get("action") == "instruction":
        intervention_msg = intervention.get("message")
        log_human_intervention(
            "instruction",
            f"Story {story_id}: \"{intervention_msg}\"",
        )

    notify("story_start", f"Story {story_id}: {story['title']}")

    print(f"\n{'='*60}")
    print(f"[Ralph] Story {story_id}: {story['title']}")
    print(f"{'='*60}")

    # Loop detection — track recent error signatures
    recent_errors: list[str] = []
    prev_test_output: str | None = None  # Post-write test output from previous attempt
    attempt = 0
    consecutive_infra_failures = 0
    regression_feedback: str | None = None  # Fed back to Qwen after regression revert
    regression_fail_counts: dict[str, int] = {}  # {reg_story_id: consecutive_fail_count}
    last_written: list[str] = []  # Files written by previous attempt (for targeted revert)
    passed = False

    while attempt < MAX_ATTEMPTS:
        attempt += 1

        if should_stop():
            print("[Ralph] Stop requested during story — pausing")
            return False

        print(f"\n  [Attempt {attempt}/{MAX_ATTEMPTS}]")

        if attempt == 5:
            warn("story_fail", f"Story {story_id} struggling — attempt 5/{MAX_ATTEMPTS}\n{story['title']}")

        # 0. Reset to clean state — undo changes from prior attempt only.
        #    On attempt 1: broad checkout to handle crash recovery.
        #    On retries: only revert files this story touched (preserves prior story models).
        if attempt == 1 or not last_written:
            subprocess.run(["git", "checkout", "engine/"], capture_output=True)
            subprocess.run(["git", "checkout", "assets/"], capture_output=True)
        else:
            for fpath in last_written:
                subprocess.run(["git", "checkout", fpath], capture_output=True)

        # 1. Get test output for Qwen
        #    On retries: use the POST-WRITE test output from the previous attempt
        #    so Qwen sees its actual mistakes (e.g. "assert 8 == 6") instead of
        #    the same ImportError every time.
        if prev_test_output is not None:
            test_output = prev_test_output
            test_passed = False
            print(f"  [{_ts()}] Using post-write test output from previous attempt")
            prev_test_output = None
        else:
            print(f"  [{_ts()}] Running tests...")
            test_passed, test_output = run_tests(test_file, story_id)
            print(f"  [{_ts()}] Tests {'PASSED' if test_passed else 'FAILED'}")

        if test_passed and attempt == 1:
            print("  Tests already pass — skipping to deploy")
            passed = True
            break

        if test_passed:
            passed = True
            break

        # Detect "no tests collected" — bail immediately, this is a scaffolding problem
        if "NO TESTS COLLECTED" in test_output:
            alert("critical", f"Story {story_id}: NO TESTS EXIST — cannot proceed\nQwen cannot fix this. Check tests/test_*.py for test_s{story_id}_* functions.")
            return False

        # Extract error signature for loop detection (used AFTER Qwen's fix attempt)
        pre_error_sig = ""
        for line in test_output.split("\n"):
            if "Error" in line or "FAILED" in line or "assert" in line.lower():
                pre_error_sig = line.strip()[:120]
                break

        # 2. Build prompt
        prompt = build_prompt(
            story,
            test_output,
            intervention_message=intervention_msg,
            regression_error=regression_feedback,
        )
        regression_feedback = None  # Only include once

        # 3. Call Qwen
        print(f"  [{_ts()}] Calling Qwen ({OLLAMA_MODEL})...")
        idle_start = time.time()
        response, tokens_in, tokens_out, gpu_time = call_qwen(prompt, label=f"story {story_id} attempt {attempt}")
        idle_time = max(0, time.time() - idle_start - gpu_time)

        # Check for infrastructure failure (Ollama down after all retries)
        if not response and tokens_in == 0:
            consecutive_infra_failures += 1
            attempt -= 1  # Don't count infra failures as story attempts
            print(f"  Ollama infrastructure failure ({consecutive_infra_failures}/3) — not counting as attempt")
            if consecutive_infra_failures >= 3:
                alert(
                    "critical",
                    f"Story {story_id}: Ollama down for 3 consecutive calls — bailing\n{story['title']}",
                )
                return False
            continue
        consecutive_infra_failures = 0

        # 4. Log cost (every call, pass or fail)
        log_cost(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            gpu_time_sec=gpu_time,
            idle_time_sec=idle_time,
            story_completed=False,
        )

        print(f"  Qwen responded: {tokens_in} tokens in, {tokens_out} tokens out, {gpu_time:.1f}s")

        # Debug: log raw response to file for diagnosis
        try:
            debug_dir = Path("ralph/debug_responses")
            debug_dir.mkdir(exist_ok=True)
            debug_file = debug_dir / f"{story_id}_attempt{attempt}.txt"
            debug_file.write_text(response, encoding="utf-8")
            print(f"  [DEBUG] Response saved to {debug_file}")
        except Exception as e:
            print(f"  [DEBUG] Failed to save response: {e}")

        # 5. Apply file changes
        written = apply_files(response)
        last_written = written  # Track for targeted revert on next attempt
        if written:
            _autofix_postgres_compat()  # Fix == False/True before testing
        if not written:
            print("  No files written — Qwen may have returned empty/invalid output")
            log_metric(story_id, attempt, False, gpu_time, "No files written", tokens_in, tokens_out)
            # Track consecutive empty outputs — 3 in a row means Qwen can't parse the story
            recent_errors.append("NO_FILES_WRITTEN")
            prev_test_output = None  # No code written, fall back to fresh test run
            if len(recent_errors) >= 3 and all(e == "NO_FILES_WRITTEN" for e in recent_errors[-3:]):
                alert("loop", f"Story {story_id}: Qwen returned empty/unparseable output 3x — requesting help")
                helped = _request_help(story_id, story["title"], "Qwen returned empty/unparseable output 3x in a row", test_file, attempt)
                if not helped:
                    return False  # Shutdown requested
                _autofix_postgres_compat()
                recent_errors.clear()
                # Test again after help
                test_ok, test_output = run_tests(test_file, story_id)
                if test_ok:
                    print(f"  [help] External fix resolved the issue!")
                    passed = True
                    break
                prev_test_output = test_output
                print(f"  [help] Still failing — continuing attempts")
            continue

        # 6. Re-run tests
        test_passed, test_output = run_tests(test_file, story_id)
        log_metric(story_id, attempt, test_passed, gpu_time, None if test_passed else test_output[:500], tokens_in, tokens_out)

        if test_passed:
            # Regression gate: check all previous stories still pass
            print(f"  [{_ts()}] Story tests passed — running regression check...")
            reg_passed, reg_output = run_regression_tests()
            if not reg_passed:
                print(f"  REGRESSION detected — {reg_output[:200]}")

                # Track which regression story keeps failing
                import re as _re
                reg_match = _re.match(r"REGRESSION in Story (\d+):", reg_output)
                if reg_match:
                    reg_sid = reg_match.group(1)
                    regression_fail_counts[reg_sid] = regression_fail_counts.get(reg_sid, 0) + 1

                    # If same regression story failed 2+ times, try auto-resolving
                    if regression_fail_counts[reg_sid] >= 2:
                        print(f"  [CONFLICT] Same regression (Story {reg_sid}) failed {regression_fail_counts[reg_sid]}x — attempting auto-resolve")
                        # Revert only files this story touched
                        for fpath in last_written:
                            subprocess.run(["git", "checkout", fpath], capture_output=True)
                        resolved = resolve_test_conflict(story, reg_output, test_file)
                        if resolved:
                            regression_fail_counts.clear()
                            regression_feedback = None
                            prev_test_output = None
                            recent_errors.clear()
                            attempt = 0  # Reset attempts — fresh start with fixed test
                            print(f"  [CONFLICT] Resolved — restarting story with fixed test")
                            continue

                print(f"  Undoing changes, will retry")
                for fpath in last_written:
                    subprocess.run(["git", "checkout", fpath], capture_output=True)
                log_metric(story_id, attempt, False, gpu_time, f"REGRESSION: {reg_output[:300]}", tokens_in, tokens_out)
                regression_feedback = reg_output  # Feed back to Qwen on next attempt
                prev_test_output = None  # Regression feedback takes priority
                recent_errors.clear()  # Reset loop detection — regression is a different problem
                continue  # Retry — Qwen will get the regression error in next prompt
            print(f"  PASSED on attempt {attempt} (no regressions)")
            passed = True
            break
        else:
            # Loop detection — track POST-WRITE errors (not pre-write, which are always the same)
            post_error_sig = ""
            for line in test_output.split("\n"):
                if "Error" in line or "FAILED" in line or "assert" in line.lower():
                    post_error_sig = line.strip()[:120]
                    break
            if post_error_sig:
                recent_errors.append(post_error_sig)
                if len(recent_errors) >= 5 and len(set(recent_errors[-5:])) == 1:
                    alert("loop", f"Story {story_id}: same error 5x in a row — requesting help\n`{post_error_sig}`")
                    # Request help and wait 10 minutes for external fix
                    helped = _request_help(story_id, story["title"], post_error_sig, test_file, attempt)
                    if not helped:
                        return False  # Shutdown requested during wait
                    # Auto-fix Postgres compat after pull
                    _autofix_postgres_compat()
                    # Retry: reset errors and give Qwen 3 more attempts
                    recent_errors.clear()
                    prev_test_output = None
                    # Run the test again to see if external fix resolved it
                    test_ok, test_output = run_tests(test_file, story_id)
                    if test_ok:
                        print(f"  [help] External fix resolved the issue!")
                        passed = True
                        break
                    print(f"  [help] Still failing after help — giving Qwen 3 more attempts")
                    MAX_HELP_RETRIES = 3
                    for help_attempt in range(1, MAX_HELP_RETRIES + 1):
                        print(f"\n  [Attempt {attempt + help_attempt}/{MAX_ATTEMPTS} (post-help)]")
                        prompt = build_prompt(story, test_output, regression_error=regression_feedback)
                        response, tin, tout, gpu_time = call_qwen(prompt, label=f"story {story_id} post-help {help_attempt}")
                        log_cost(tokens_in=tin, tokens_out=tout, gpu_time_sec=gpu_time)
                        last_written = apply_files(response)
                        if last_written:
                            _autofix_postgres_compat()
                        test_ok, test_output = run_tests(test_file, story_id)
                        if test_ok:
                            passed = True
                            break
                    if passed:
                        break
                    # Truly stuck — stop for real
                    alert("critical", f"Story {story_id}: still failing after help + 3 retries — stopping\n`{post_error_sig}`")
                    return False
            # Save post-write output so next attempt sees the REAL error
            prev_test_output = test_output
            print(f"  FAILED — will retry")

    if not passed:
        print(f"  Story {story_id} FAILED after {MAX_ATTEMPTS} attempts")
        warn("story_fail", f"Story {story_id} failed after {MAX_ATTEMPTS} attempts: {story['title']}")
        return False

    # Story passed — mark complete cost
    log_cost(tokens_in=0, tokens_out=0, gpu_time_sec=0, story_completed=True)

    # 7. Reflection — ask Qwen what it learned
    print(f"  [{_ts()}] Reflecting on learnings...")
    learn_prompt = build_learning_prompt(story_id, story["title"])
    learn_text, learn_tin, learn_tout, learn_time = call_qwen(learn_prompt, label=f"story {story_id} reflection", think=False)
    log_cost(tokens_in=learn_tin, tokens_out=learn_tout, gpu_time_sec=learn_time)
    append_learning(story_id, story["title"], story.get("attempts", 1), learn_text)
    print(f"  [{_ts()}] Learnings saved to progress.txt")

    # 8. Git commit
    print(f"  [{_ts()}] Committing...")
    try:
        git_commit(f"[Ralph] Story {story_id}: {story['title']}")
    except subprocess.CalledProcessError as e:
        print(f"  [{_ts()}] Git commit failed: {e}")
        warn("git_fail", f"Story {story_id}: git commit failed: {e}\nContinuing without commit.")

    # 9. Generate sprites for any new building/NPC types added by this story
    print(f"  [{_ts()}] Generating sprites for new assets...")
    try:
        import asyncio
        from ralph.asset_gen import ensure_default_assets
        generated = asyncio.run(ensure_default_assets())
        if generated:
            print(f"  [{_ts()}] Generated {generated} new sprites")
            # Stage and commit new sprites
            subprocess.run(["git", "add", "assets/"], capture_output=True)
            try:
                subprocess.run(
                    ["git", "commit", "-m", f"[Ralph] Sprites for Story {story_id}"],
                    check=True, capture_output=True,
                )
            except subprocess.CalledProcessError:
                pass  # Nothing to commit if no new sprites
        else:
            print(f"  [{_ts()}] No new sprites needed")
    except Exception as e:
        print(f"  [{_ts()}] Sprite generation skipped: {e}")
        warn("sprite_skip", f"Story {story_id}: Sprite generation skipped — {e}")

    # 10. Deploy pipeline
    print(f"  [{_ts()}] Deploying...")
    deploy_ok, deploy_msg = push_and_wait()

    if deploy_ok:
        print(f"  [{_ts()}] Deploy healthy: {deploy_msg}")
        notify("deploy_ok", f"Story {story_id} deployed: {deploy_msg}")
        # 11. Take snapshots
        print(f"  [{_ts()}] Taking snapshots...")
        snapshot_files = take_all_snapshots(story_id)
        if snapshot_files:
            git_commit_snapshots(story_id)
            # Push snapshot commit
            subprocess.run(["git", "push", "origin", "main"], capture_output=True)
        print(f"  [{_ts()}] Snapshots done")
    else:
        # Deploy failures are non-fatal — code is already committed and pushed.
        # Railway auto-deploys on push anyway; network timeouts are transient.
        print(f"  [{_ts()}] Deploy FAILED (non-fatal): {deploy_msg}")
        warn("deploy_fail", f"Story {story_id} deploy failed (non-fatal, will auto-deploy on next push): {deploy_msg[:120]}")

    notify("story_done", f"Story {story_id} complete: {story['title']}")
    return True


def main():
    """Main Ralph loop — runs stories until complete or stopped."""
    print("[Ralph] Starting up...")
    print(f"[Ralph] Model: {OLLAMA_MODEL}")
    print(f"[Ralph] Ollama: {OLLAMA_URL}")
    print(f"[Ralph] Press Ctrl+C for graceful shutdown")
    print()

    # Auto-resume: if HUMAN.md says pause but no .ralph-paused marker exists,
    # this was a crash/reboot, not a human pause — clear it and continue.
    pause_marker = Path(".ralph-paused")
    intervention = read_intervention()
    if intervention.get("action") == "pause":
        if pause_marker.exists():
            print("[Ralph] Human-requested pause is active — exiting.")
            print("[Ralph] To resume: set HUMAN.md action to 'none' and run ralph-start.bat")
            return
        else:
            print("[Ralph] Stale pause detected (crash/reboot) — auto-resuming")
            clear_oneshot_action()

    # Startup preflight checks
    if not preflight():
        alert("critical", "Preflight checks failed — Ralph cannot start")
        sys.exit(1)
    print()

    prd = load_prd()
    done = sum(1 for s in prd["stories"] if s["status"] == "done")
    total = len(prd["stories"])
    notify("start", f"Ralph online — {done}/{total} stories complete")

    while True:
        if should_stop():
            intervention = read_intervention()
            action = intervention.get("action", "none")
            if action == "review_stories":
                print("[Ralph] Paused for story review — edit proposed_stories.json, then set HUMAN.md action to approve_stories")
                log_human_intervention("review_stories", "Ralph paused for human story review")
            elif action == "pause":
                print("[Ralph] Paused via HUMAN.md — set action to 'resume' to continue")
                msg = intervention.get("message") or "No reason given"
                log_human_intervention("pause", f"Human paused Ralph: {msg}")
                pause_marker.touch()  # Mark as intentional pause
            else:
                print("[Ralph] Shutdown requested — exiting cleanly")
                pause_marker.unlink(missing_ok=True)
            break

        # Check for intervention actions
        intervention = read_intervention()
        action = intervention.get("action", "none")

        if action == "approve_stories":
            print("[Ralph] Importing approved stories...")
            log_human_intervention("approve_stories", "Human reviewed and approved proposed stories")
            import_approved()
            clear_oneshot_action()
            continue

        if action == "skip":
            prd = load_prd()
            story = get_next_story(prd)
            if story:
                print(f"[Ralph] Skipping story {story['id']}")
                log_human_intervention("skip", f"Skipped story {story['id']}: {story['title']}")
                story["status"] = "skipped"
                save_prd(prd)
            clear_oneshot_action()
            continue

        # Check if we need to auto-generate stories
        if needs_generation():
            print("[Ralph] Backlog low — generating new stories...")
            gen_prompt = build_generation_prompt()
            gen_response, _, _, _ = call_qwen(gen_prompt)
            try:
                # Try to parse JSON from Qwen's response
                import re
                json_match = re.search(r'\[.*\]', gen_response, re.DOTALL)
                if json_match:
                    proposed = json.loads(json_match.group())
                    save_proposed(proposed)
                    request_review()
                    continue
            except (json.JSONDecodeError, AttributeError):
                print("[Ralph] Failed to parse generated stories — continuing with backlog")

        # Block if any stories are failed — wait for human to reset
        prd = load_prd()
        failed = [s for s in prd["stories"] if s["status"] == "failed"]
        if failed:
            ids = ", ".join(s["id"] for s in failed)
            alert("critical", f"Blocked by failed stories: {ids}\nReset to 'pending' in prd.json to retry")
            print(f"[Ralph] Blocked by failed stories: {ids} — needs human intervention")
            pause_marker.touch()
            break

        # Get next story
        story = get_next_story(prd)

        if not story:
            notify("stop", "All stories complete!")
            print("[Ralph] No pending stories — all done!")
            break

        # Run the story
        story["status"] = "in_progress"
        story["attempts"] = story.get("attempts", 0) + 1
        save_prd(prd)

        success = run_story(story)

        # Update status
        prd = load_prd()
        for s in prd["stories"]:
            if s["id"] == story["id"]:
                s["status"] = "done" if success else "failed"
                s["attempts"] = story["attempts"]
                break
        save_prd(prd)

        # Any failure → stop and alert for human debugging
        if not success:
            alert(
                "critical",
                f"Story {story['id']} failed: {story['title']}\nRalph stopped — needs human debugging",
            )
            print(f"[Ralph] Story {story['id']} failed — stopping for human debug")
            pause_marker.touch()
            break

        if action == "retry":
            log_human_intervention("retry", f"Human requested retry of story {story['id']}")
            clear_oneshot_action()

    prd = load_prd()
    done = sum(1 for s in prd["stories"] if s["status"] == "done")
    total = len(prd["stories"])
    notify("stop", f"Ralph offline — {done}/{total} stories complete")
    print("[Ralph] Goodbye.")


if __name__ == "__main__":
    main()
