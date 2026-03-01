"""Append-only learnings log — Qwen writes what it learned after each story.

progress.txt is fed into every prompt so Qwen avoids repeating mistakes.
"""

import time
from pathlib import Path

PROGRESS_FILE = Path("progress.txt")
MAX_LEARNINGS_CHARS = 8_000  # Budget for prompt inclusion — keep it tight


def load_learnings() -> str:
    """Load progress.txt for prompt injection. Trims to tail if over budget."""
    if not PROGRESS_FILE.exists():
        return ""
    text = PROGRESS_FILE.read_text(encoding="utf-8")
    if len(text) > MAX_LEARNINGS_CHARS:
        # Keep the most recent entries (tail)
        text = "...(earlier learnings trimmed)...\n" + text[-MAX_LEARNINGS_CHARS:]
    return text


def append_learning(story_id: str, title: str, attempts: int, learning: str):
    """Append a learning entry after a completed story."""
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n--- Story {story_id}: {title} (attempts: {attempts}, {timestamp}) ---\n"
        f"{learning.strip()}\n"
    )
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(entry)


LEARNING_PROMPT = """You just completed Story {story_id}: {title}

Reflect briefly on what you learned. Write 2-4 bullet points covering:
- What was tricky or non-obvious
- Patterns or conventions you discovered in this codebase
- Mistakes you made and corrected

Be concise. This will be read by your future self before each new story.
"""


def build_learning_prompt(story_id: str, title: str) -> str:
    """Build the reflection prompt sent to Qwen after a story passes."""
    return LEARNING_PROMPT.format(story_id=story_id, title=title)
