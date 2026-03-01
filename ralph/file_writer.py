"""Parse Qwen's output and apply file changes. Extended blocklist for safety."""

import os
import re
from pathlib import Path

# Files/directories Qwen must NEVER modify
BLOCKLIST = [
    "ralph/",
    "tests/",
    "engine/auth.py",
    "engine/main.py",
    "engine/db.py",
    "engine/templates/dashboard.html",
    "docs/",
    "HUMAN.md",
    "AGENTS.md",
    "prd.json",
    ".env",
    ".gitignore",
    "requirements.txt",
]


def is_blocked(filepath: str) -> bool:
    """Check if a filepath is on the blocklist or attempts path traversal."""
    normalized = filepath.replace("\\", "/")

    # Block path traversal
    if ".." in normalized:
        print(f"  [BLOCKED] Path traversal rejected: {filepath}")
        return True
    if normalized.startswith("/"):
        print(f"  [BLOCKED] Absolute path rejected: {filepath}")
        return True

    for blocked in BLOCKLIST:
        if blocked.endswith("/"):
            if normalized.startswith(blocked):
                return True
        else:
            if normalized == blocked:
                return True
    return False


def parse_file_blocks(response: str) -> list[tuple[str, str]]:
    """Parse '### FILE: path' blocks from Qwen's response.

    Returns list of (filepath, content) tuples.
    """
    # Match ### FILE: path/to/file.py blocks
    pattern = r"### FILE:\s*(.+?)\s*\n(.*?)(?=### FILE:|$)"
    matches = re.findall(pattern, response, re.DOTALL)

    files = []
    for filepath, content in matches:
        filepath = filepath.strip()
        # Strip markdown code fences if present
        content = re.sub(r"^```\w*\n", "", content.strip())
        content = re.sub(r"\n```\s*$", "", content)
        files.append((filepath, content))

    return files


def apply_files(response: str) -> list[str]:
    """Parse and write all file blocks from Qwen's response.

    Returns list of written filepaths. Skips blocked files.
    """
    file_blocks = parse_file_blocks(response)
    written = []

    for filepath, content in file_blocks:
        if is_blocked(filepath):
            print(f"  [BLOCKED] Skipping protected file: {filepath}")
            continue

        # Create parent directories if needed
        parent = Path(filepath).parent
        if parent != Path("."):
            os.makedirs(parent, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        written.append(filepath)
        print(f"  [WROTE] {filepath}")

    return written
