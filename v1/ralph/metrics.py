"""Logs story attempts and outcomes to metrics.jsonl."""

import json
import time
from pathlib import Path

METRICS_FILE = Path("metrics.jsonl")


def log_metric(
    story_id: str,
    attempt: int,
    passed: bool,
    duration_sec: float,
    error: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
):
    """Append a single metric entry to metrics.jsonl."""
    entry = {
        "story_id": story_id,
        "attempt": attempt,
        "passed": passed,
        "duration_sec": round(duration_sec, 2),
        "error": error,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(METRICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
