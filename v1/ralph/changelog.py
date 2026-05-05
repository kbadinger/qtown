"""Changelog — auto-log human interventions to CHANGELOG.md."""

from datetime import datetime, timezone
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")


def log_human_intervention(action: str, detail: str):
    """Append an entry to CHANGELOG.md.

    Called automatically by Ralph when HUMAN.md actions are triggered.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"\n### {ts} — Human (via HUMAN.md) — {action}\n{detail}\n"

    try:
        if CHANGELOG.exists():
            with open(CHANGELOG, "a", encoding="utf-8") as f:
                f.write(entry)
        else:
            with open(CHANGELOG, "w", encoding="utf-8") as f:
                f.write("# Human Intervention Log\n\n---\n")
                f.write(entry)
    except OSError as e:
        print(f"[Ralph] Could not write to CHANGELOG.md: {e}")
