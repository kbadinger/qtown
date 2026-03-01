"""Prompt assembly — loads AGENTS.md, story context, docs library, intervention messages."""

import json
from pathlib import Path

from ralph.learnings import load_learnings

AGENTS_MD = Path("AGENTS.md")
DOCS_INDEX = Path("docs/index.json")
CHAR_BUDGET = 100_000  # Max chars to load from context files


def build_prompt(
    story: dict,
    test_output: str,
    intervention_message: str | None = None,
    deploy_error: str | None = None,
) -> str:
    """Build the full prompt for Qwen.

    Args:
        story: The story dict from prd.json.
        test_output: The failing test output.
        intervention_message: Optional human instruction from HUMAN.md.
        deploy_error: Optional deploy error logs to feed back.

    Returns:
        The assembled prompt string.
    """
    parts = []

    # 1. AGENTS.md — always first
    if AGENTS_MD.exists():
        parts.append("=== DEVELOPER HANDBOOK (AGENTS.md) ===")
        parts.append(AGENTS_MD.read_text(encoding="utf-8"))
        parts.append("")

    # 2. Learnings from previous stories
    learnings = load_learnings()
    if learnings:
        parts.append("=== LEARNINGS FROM PREVIOUS STORIES ===")
        parts.append(learnings)
        parts.append("")

    # 3. Human intervention message
    if intervention_message:
        parts.append("=== HUMAN INSTRUCTION ===")
        parts.append(intervention_message)
        parts.append("")

    # 4. Deploy error context (for fix cycles)
    if deploy_error:
        parts.append("=== DEPLOY ERROR (FIX THIS) ===")
        parts.append(deploy_error)
        parts.append("")

    # 5. Story details
    parts.append("=== CURRENT STORY ===")
    parts.append(f"Story {story['id']}: {story['title']}")
    parts.append(f"Description: {story['description']}")
    parts.append(f"Acceptance: {story.get('acceptance', 'See test file')}")
    parts.append(f"Test file: {story['test_file']}")
    parts.append("")

    # 6. Context files (explicit from story + auto-discovered from docs)
    context_files = list(story.get("context_files", []))

    # Auto-discover docs by matching story tags with docs index
    story_tags = set(story.get("tags", []))
    if story_tags and DOCS_INDEX.exists():
        try:
            index = json.loads(DOCS_INDEX.read_text(encoding="utf-8"))
            for doc in index.get("docs", []):
                doc_tags = set(doc.get("tags", []))
                if story_tags & doc_tags:  # Intersection
                    doc_path = doc["path"]
                    if doc_path not in context_files:
                        context_files.append(doc_path)
        except (json.JSONDecodeError, KeyError):
            pass

    # Load context files within budget
    total_chars = 0
    for filepath in context_files:
        p = Path(filepath)
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")
        if total_chars + len(content) > CHAR_BUDGET:
            parts.append(f"=== {filepath} (SKIPPED — budget exceeded) ===")
            continue
        parts.append(f"=== {filepath} ===")
        parts.append(content)
        parts.append("")
        total_chars += len(content)

    # 7. Failing test output
    parts.append("=== FAILING TEST OUTPUT ===")
    parts.append(test_output)
    parts.append("")

    # 8. Instructions
    parts.append("=== YOUR TASK ===")
    parts.append(
        "Write the code to make the failing tests pass. "
        "Output your code using ### FILE: path/to/file.py blocks. "
        "Include the COMPLETE file contents in each block. "
        "Do NOT modify any files on the blocklist (see AGENTS.md)."
    )

    return "\n".join(parts)
