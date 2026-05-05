"""Auto-generate new stories when the backlog runs low."""

import json
from pathlib import Path

PRD_FILE = Path("prd.json")
PROPOSED_FILE = Path("proposed_stories.json")
PROMPT_TEMPLATE = Path("docs/generate-stories-prompt.md")
HUMAN_MD = Path("HUMAN.md")

MIN_PENDING = 10  # Generate more when fewer than this many pending


def needs_generation() -> bool:
    """Check if we need to generate more stories."""
    if not PRD_FILE.exists():
        return False
    prd = json.loads(PRD_FILE.read_text(encoding="utf-8"))
    pending = [s for s in prd.get("stories", []) if s.get("status") == "pending"]
    return len(pending) < MIN_PENDING


def get_completed_stories() -> list[dict]:
    """Get list of completed stories for context."""
    if not PRD_FILE.exists():
        return []
    prd = json.loads(PRD_FILE.read_text(encoding="utf-8"))
    return [s for s in prd.get("stories", []) if s.get("status") == "done"]


def build_generation_prompt() -> str:
    """Build the meta-prompt for Qwen to generate new stories."""
    parts = []

    # Load the story format template
    if PROMPT_TEMPLATE.exists():
        parts.append(PROMPT_TEMPLATE.read_text(encoding="utf-8"))
    else:
        parts.append("Generate 10 new stories in the standard prd.json format.")

    # Include completed stories for context
    completed = get_completed_stories()
    if completed:
        parts.append("\n## Already Completed Stories")
        for s in completed:
            parts.append(f"- {s['id']}: {s['title']}")

    # Include current model/router files for awareness
    parts.append("\n## Current Codebase Files")
    for pattern in ["engine/models.py", "engine/simulation/constants.py", "engine/simulation/tick.py", "engine/routers/*.py"]:
        for p in Path(".").glob(pattern):
            parts.append(f"\n### {p}")
            try:
                parts.append(p.read_text(encoding="utf-8")[:5000])
            except Exception:
                parts.append("(could not read)")

    parts.append(
        "\n## Generate\n"
        "Create 10 new stories with incrementing IDs. "
        "Output as a JSON array of story objects. "
        "For each story, also generate the corresponding test file contents."
    )

    return "\n".join(parts)


def save_proposed(stories: list[dict]):
    """Save proposed stories for human review."""
    with open(PROPOSED_FILE, "w", encoding="utf-8") as f:
        json.dump(stories, f, indent=2)
    print(f"  [GENERATOR] Saved {len(stories)} proposed stories to {PROPOSED_FILE}")


def request_review():
    """Set HUMAN.md to review_stories action."""
    content = HUMAN_MD.read_text(encoding="utf-8") if HUMAN_MD.exists() else ""
    # Replace the YAML frontmatter action
    import re

    new_content = re.sub(
        r"action:\s*\w+",
        "action: review_stories",
        content,
    )
    HUMAN_MD.write_text(new_content, encoding="utf-8")
    print("  [GENERATOR] Set HUMAN.md action to review_stories — waiting for human")


def import_approved():
    """Import approved stories from proposed_stories.json into prd.json."""
    if not PROPOSED_FILE.exists():
        print("  [GENERATOR] No proposed_stories.json found")
        return

    proposed = json.loads(PROPOSED_FILE.read_text(encoding="utf-8"))
    prd = json.loads(PRD_FILE.read_text(encoding="utf-8"))

    for story in proposed:
        story["status"] = "pending"
        story["attempts"] = 0
        prd["stories"].append(story)

    with open(PRD_FILE, "w", encoding="utf-8") as f:
        json.dump(prd, f, indent=2)

    # Clean up
    PROPOSED_FILE.unlink()
    print(f"  [GENERATOR] Imported {len(proposed)} stories into prd.json")
