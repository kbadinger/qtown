"""Parse Qwen's output and apply file changes. Extended blocklist for safety."""

import ast
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
    "engine/sprites.py",
    "engine/templates/dashboard.html",
    "engine/templates/timeline.html",
    "engine/templates/base.html",
    "docs/",
    "HUMAN.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "COST_METHODOLOGY.md",
    "prd.json",
    ".env",
    ".gitignore",
    "requirements.txt",
    "Procfile",
    "railway.json",
    ".claude/",
]


def _normalize(filepath: str) -> str:
    """Normalize a filepath for safe blocklist comparison.

    Resolves ./segments, collapses separators, lowercases on Windows.
    """
    cleaned = filepath.replace("\\", "/")
    cleaned = os.path.normpath(cleaned).replace("\\", "/")
    # Windows is case-insensitive — normalize to lowercase
    if os.name == "nt":
        cleaned = cleaned.lower()
    return cleaned


def is_blocked(filepath: str) -> bool:
    """Check if a filepath is on the blocklist or attempts path traversal."""
    raw = filepath.replace("\\", "/")

    # Block path traversal (check BEFORE normalization so .. can't sneak through)
    if ".." in raw:
        print(f"  [BLOCKED] Path traversal rejected: {filepath}")
        return True
    if raw.startswith("/"):
        print(f"  [BLOCKED] Absolute path rejected: {filepath}")
        return True

    normalized = _normalize(filepath)

    for blocked in BLOCKLIST:
        b = blocked.lower() if os.name == "nt" else blocked
        if b.endswith("/"):
            if normalized.startswith(b) or normalized.startswith(b.rstrip("/")):
                return True
        else:
            if normalized == b:
                return True
    return False


def _extract_top_level_defs(source: str) -> dict[str, str]:
    """Extract top-level function and class definitions from Python source.

    Returns {name: source_text} for each top-level def/class.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    lines = source.split("\n")
    defs = {}

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1  # 0-indexed
            end = node.end_lineno  # 1-indexed, exclusive
            # Include decorators
            if node.decorator_list:
                start = min(d.lineno for d in node.decorator_list) - 1
            block = "\n".join(lines[start:end])
            defs[node.name] = block

    return defs


def _merge_dropped_definitions(filepath: str, old_content: str, new_content: str) -> str:
    """Merge back any top-level definitions that Qwen dropped from a Python file.

    If Qwen's new version is missing functions/classes that exist in the old
    version, append them to the end of the new content.
    """
    old_defs = _extract_top_level_defs(old_content)
    new_defs = _extract_top_level_defs(new_content)

    dropped = set(old_defs.keys()) - set(new_defs.keys())
    if not dropped:
        return new_content

    # Sort dropped definitions by their original order in the file
    old_order = list(old_defs.keys())
    dropped_sorted = sorted(dropped, key=lambda name: old_order.index(name))

    restored_parts = []
    for name in dropped_sorted:
        restored_parts.append(old_defs[name])

    print(f"  [MERGE] Restored {len(dropped)} dropped definitions in {filepath}: {', '.join(dropped_sorted)}")

    # Append dropped definitions to end of new content
    merged = new_content.rstrip("\n") + "\n\n\n" + "\n\n\n".join(restored_parts) + "\n"
    return merged


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
    For Python files, automatically merges back any dropped definitions.
    """
    file_blocks = parse_file_blocks(response)
    written = []

    for filepath, content in file_blocks:
        if is_blocked(filepath):
            print(f"  [BLOCKED] Skipping protected file: {filepath}")
            continue

        # Reject obviously bad filenames (hallucinated paths, quotes, spaces in name)
        if any(c in filepath for c in '"\'<>|') or filepath != filepath.strip():
            print(f"  [BLOCKED] Invalid filename: {filepath!r}")
            continue

        # Resolve to catch symlink attacks
        try:
            target = Path(filepath).resolve()
        except (OSError, ValueError):
            print(f"  [BLOCKED] Unresolvable path: {filepath!r}")
            continue
        repo_root = Path(".").resolve()
        if not str(target).startswith(str(repo_root)):
            print(f"  [BLOCKED] Path escapes repo: {filepath}")
            continue

        # For Python files that already exist, merge back dropped definitions
        if filepath.endswith(".py") and Path(filepath).exists():
            try:
                old_content = Path(filepath).read_text(encoding="utf-8")
                content = _merge_dropped_definitions(filepath, old_content, content)
            except (OSError, UnicodeDecodeError):
                pass  # If we can't read old file, just write new content

        # Create parent directories if needed
        parent = Path(filepath).parent
        if parent != Path("."):
            os.makedirs(parent, exist_ok=True)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            print(f"  [BLOCKED] Cannot write file {filepath!r}: {e}")
            continue

        written.append(filepath)
        print(f"  [WROTE] {filepath}")

    return written
