"""Runs pytest for a given test file and returns pass/fail + output."""

import json
import subprocess
from pathlib import Path


def run_tests(test_file: str, story_id: str = "") -> tuple[bool, str]:
    """Run pytest on a single test file, optionally filtering by story ID.

    Returns (passed: bool, output: str).
    """
    try:
        cmd = ["python", "-m", "pytest", test_file, "-v", "--tb=short"]
        if story_id:
            cmd.extend(["-k", f"s{story_id}"])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + "\n" + result.stderr
        # Exit code 5 = no tests collected (missing test prefix, wrong file, etc.)
        if result.returncode == 5:
            return False, f"NO TESTS COLLECTED — pytest found no tests matching '-k s{story_id}' in {test_file}. Check that test functions are named test_s{story_id}_*.\n{output}"
        passed = result.returncode == 0
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "Test timed out after 120s"


def run_regression_tests(prd_path: str = "prd.json") -> tuple[bool, str]:
    """Run tests for all completed stories to detect regressions.

    Returns (passed, message). On first failure, returns immediately
    with the story ID and truncated output.
    """
    prd_file = Path(prd_path)
    if not prd_file.exists():
        return True, "No prd.json found — skipping regression check"

    prd = json.loads(prd_file.read_text(encoding="utf-8"))
    done_stories = [s for s in prd["stories"] if s["status"] == "done"]

    if not done_stories:
        return True, "No completed stories to regress"

    for story in done_stories:
        passed, output = run_tests(story["test_file"], story["id"])
        if not passed:
            # Skip "no tests collected" during regression — means tests were removed/renamed
            if "NO TESTS COLLECTED" in output:
                continue
            return False, f"REGRESSION in Story {story['id']}: {output[:500]}"

    return True, f"All {len(done_stories)} regression tests passed"
