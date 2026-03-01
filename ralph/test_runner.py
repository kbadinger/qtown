"""Runs pytest for a given test file and returns pass/fail + output."""

import subprocess


def run_tests(test_file: str) -> tuple[bool, str]:
    """Run pytest on a single test file.

    Returns (passed: bool, output: str).
    """
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", test_file, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + "\n" + result.stderr
        passed = result.returncode == 0
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "Test timed out after 120s"
