"""Ralph — the main orchestrator loop.

Reads failing tests, sends them to Qwen, applies code, commits on pass.
Full pipeline: test → Qwen → apply → test → commit → push → deploy → snapshot.

Supports safe shutdown via HUMAN.md (action: pause) or SIGINT/SIGTERM.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

from ralph.alerter import notify, warn, alert
from ralph.changelog import log_human_intervention
from ralph.cost_tracker import log_cost
from ralph.deployer import push_and_wait
from ralph.file_writer import apply_files
from ralph.metrics import log_metric
from ralph.prompt_builder import build_prompt
from ralph.snapshot import take_all_snapshots
from ralph.story_generator import (
    import_approved,
    needs_generation,
    build_generation_prompt,
    save_proposed,
    request_review,
)
from ralph.learnings import append_learning, build_learning_prompt
from ralph.test_runner import run_tests

PRD_FILE = Path("prd.json")
HUMAN_MD = Path("HUMAN.md")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:35b")
MAX_ATTEMPTS = 5

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


def call_qwen(prompt: str) -> tuple[str, int, int, float]:
    """Call Qwen via Ollama API.

    Returns (response_text, tokens_in, tokens_out, duration_sec).
    Returns ("", 0, 0, 0.0) on any network or parse error so the retry loop continues.
    """
    try:
        start = time.time()
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": 32768,
                    "temperature": 0.3,
                },
            },
            timeout=600,
        )
        duration = time.time() - start
        data = resp.json()

        response_text = data.get("response", "")
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)

        return response_text, tokens_in, tokens_out, duration
    except requests.RequestException as e:
        alert("warning", f"Ollama unreachable: {e} — retrying in 60s")
        time.sleep(60)
        return "", 0, 0, 0.0
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        warn("warning", f"Ollama bad response: {e}")
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

    return ok


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------


def git_commit(message: str):
    """Stage all changes and commit."""
    subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
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
    """Get the next pending story by priority."""
    pending = [s for s in prd["stories"] if s["status"] == "pending"]
    if not pending:
        return None
    return sorted(pending, key=lambda s: s.get("priority", 999))[0]


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

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if should_stop():
            print("[Ralph] Stop requested during story — pausing")
            return False

        print(f"\n  [Attempt {attempt}/{MAX_ATTEMPTS}]")

        # 1. Run tests (expect failure on first attempt)
        passed, test_output = run_tests(test_file)
        if passed and attempt == 1:
            print("  Tests already pass — skipping story")
            return True

        if passed:
            break

        # Loop detection — extract error signature (first failure line)
        error_sig = ""
        for line in test_output.split("\n"):
            if "Error" in line or "FAILED" in line or "assert" in line.lower():
                error_sig = line.strip()[:120]
                break
        if error_sig:
            recent_errors.append(error_sig)
            # Same error 3 times in a row = loop
            if len(recent_errors) >= 3 and len(set(recent_errors[-3:])) == 1:
                alert("loop", f"Story {story_id}: same error 3x in a row\n`{error_sig}`")

        # 2. Build prompt
        prompt = build_prompt(
            story,
            test_output,
            intervention_message=intervention_msg,
        )

        # 3. Call Qwen
        print(f"  Calling Qwen ({OLLAMA_MODEL})...")
        idle_start = time.time()
        response, tokens_in, tokens_out, gpu_time = call_qwen(prompt)
        idle_time = max(0, time.time() - idle_start - gpu_time)

        # 4. Log cost (every call, pass or fail)
        log_cost(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            gpu_time_sec=gpu_time,
            idle_time_sec=idle_time,
            story_completed=False,
        )

        print(f"  Qwen responded: {tokens_in} tokens in, {tokens_out} tokens out, {gpu_time:.1f}s")

        # 5. Apply file changes
        written = apply_files(response)
        if not written:
            print("  No files written — Qwen may have returned empty/invalid output")
            log_metric(story_id, attempt, False, gpu_time, "No files written", tokens_in, tokens_out)
            continue

        # 6. Re-run tests
        passed, test_output = run_tests(test_file)
        log_metric(story_id, attempt, passed, gpu_time, None if passed else test_output[:500], tokens_in, tokens_out)

        if passed:
            print(f"  PASSED on attempt {attempt}")
            break
        else:
            print(f"  FAILED — will retry")
    else:
        print(f"  Story {story_id} FAILED after {MAX_ATTEMPTS} attempts")
        warn("story_fail", f"Story {story_id} failed after {MAX_ATTEMPTS} attempts: {story['title']}")
        return False

    # Story passed — mark complete cost
    log_cost(tokens_in=0, tokens_out=0, gpu_time_sec=0, story_completed=True)

    # 7. Reflection — ask Qwen what it learned
    print(f"  Reflecting on learnings...")
    learn_prompt = build_learning_prompt(story_id, story["title"])
    learn_text, learn_tin, learn_tout, learn_time = call_qwen(learn_prompt)
    log_cost(tokens_in=learn_tin, tokens_out=learn_tout, gpu_time_sec=learn_time)
    append_learning(story_id, story["title"], story.get("attempts", 1), learn_text)
    print(f"  Learnings saved to progress.txt")

    # 8. Git commit
    print(f"  Committing...")
    try:
        git_commit(f"[Ralph] Story {story_id}: {story['title']}")
    except subprocess.CalledProcessError as e:
        print(f"  Git commit failed: {e}")

    # 9. Deploy pipeline
    print(f"  Deploying...")
    deploy_ok, deploy_msg = push_and_wait()

    if deploy_ok:
        print(f"  Deploy healthy: {deploy_msg}")
        notify("deploy_ok", f"Story {story_id} deployed: {deploy_msg}")
        # 10. Take snapshots
        snapshot_files = take_all_snapshots(story_id)
        if snapshot_files:
            git_commit_snapshots(story_id)
            # Push snapshot commit
            subprocess.run(["git", "push", "origin", "main"], capture_output=True)
    else:
        print(f"  Deploy FAILED: {deploy_msg}")
        warn("deploy_fail", f"Story {story_id} deploy failed — starting fix cycle")
        # Feed deploy error back to Qwen as a fix cycle
        print(f"  Starting deploy-fix cycle...")
        fix_prompt = build_prompt(story, "", deploy_error=deploy_msg)
        fix_response, fix_tin, fix_tout, fix_time = call_qwen(fix_prompt)
        log_cost(tokens_in=fix_tin, tokens_out=fix_tout, gpu_time_sec=fix_time)
        apply_files(fix_response)
        # Re-test, commit, and try deploy again
        fix_passed, _ = run_tests(test_file)
        if fix_passed:
            try:
                git_commit(f"[Ralph] Deploy fix: Story {story_id}")
            except subprocess.CalledProcessError:
                pass
            deploy_ok2, deploy_msg2 = push_and_wait()
            if deploy_ok2:
                notify("deploy_ok", f"Story {story_id} deploy fixed on retry")
                snapshot_files = take_all_snapshots(story_id)
                if snapshot_files:
                    git_commit_snapshots(story_id)
                    subprocess.run(["git", "push", "origin", "main"], capture_output=True)
            else:
                alert(
                    "deploy_fail",
                    f"Story {story_id} deploy failed twice — Ralph pausing\n{deploy_msg2[:200]}",
                )

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

    consecutive_failures = 0

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

        # Get next story
        prd = load_prd()
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

        # Track consecutive failures and alert
        if success:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                alert(
                    "critical",
                    f"3 consecutive failures — Ralph auto-pausing\nLast: Story {story['id']}: {story['title']}",
                )
                print("[Ralph] 3 consecutive failures — auto-pausing")
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
