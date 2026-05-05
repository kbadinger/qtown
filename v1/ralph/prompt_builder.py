"""Prompt assembly — loads AGENTS.md, story context, docs library, intervention messages."""

import json
import re
from pathlib import Path

from ralph.learnings import load_learnings

AGENTS_MD = Path("AGENTS.md")
DOCS_INDEX = Path("docs/index.json")
CHAR_BUDGET = 100_000  # Max chars to load from context files


def _extract_function_inventory(filepath: str, content: str) -> str | None:
    """Scan a Python file for function/class/route/constant definitions and return an inventory string."""
    defs = []
    for line in content.split("\n"):
        stripped = line.strip()
        # Match module-level constants (UPPER_CASE = ...)
        m = re.match(r'^([A-Z][A-Z_]+)\s*=\s*', stripped)
        if m:
            defs.append(f"  - constant {m.group(1)}  [lives in {filepath}]")
            continue
        # Match class definitions (models, etc.)
        m = re.match(r'^class (\w+)\(', stripped)
        if m:
            defs.append(f"  - class {m.group(1)}")
            continue
        # Match function definitions
        m = re.match(r'^def (\w+)\(', stripped)
        if m:
            defs.append(f"  - {m.group(1)}()")
            continue
        # Match FastAPI route decorators
        m = re.match(r'^@router\.(get|post|put|delete|patch)\("([^"]+)"', stripped)
        if m:
            defs.append(f"  - {m.group(1).upper()} {m.group(2)}")
    if len(defs) >= 2:  # Only warn if file has multiple definitions
        lines = [
            f"=== WARNING: PRESERVE ALL EXISTING CODE IN {filepath} ===",
            f"{filepath} currently contains these definitions:",
        ]
        lines.extend(defs)
        lines.append(f"Use ### PATCH: {filepath} with ADD/UPDATE sections — do NOT rewrite the entire file.")
        lines.append(f"IMPORTANT: Constants like BUILDING_TYPES live in {filepath}. Update them there, NOT in engine/models.py.")
        lines.append("You MUST preserve ALL existing functions. Dropping any will cause regression test failure.")
        lines.append("")
        return "\n".join(lines)
    return None


def _extract_relevant_code(filepath: str, content: str, story: dict, test_source: str | None) -> str | None:
    """For large files, extract only the functions/constants relevant to this story.

    Looks at function names mentioned in the story description, test source,
    and always includes imports + constants like BUILDING_TYPES.
    """
    import ast

    # Collect function names referenced in story description + test source
    desc = story.get("description", "") + " " + story.get("acceptance", "")
    if test_source:
        desc += " " + test_source

    # Find all identifiers that look like function calls or imports from this file
    referenced = set(re.findall(r'\b([a-z_][a-z_0-9]+)\b', desc))

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    lines = content.split("\n")
    sections = []

    # Always include: imports (top of file), module-level constants
    # Find where imports end
    last_import = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import = i

    # Include imports + constants block (up to first function)
    first_func = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            first_func = node.lineno - 1
            break

    header_end = first_func if first_func else last_import + 1
    if header_end > 0:
        sections.append("\n".join(lines[:header_end]))

    # Extract matching functions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in referenced:
                start = node.lineno - 1
                if node.decorator_list:
                    start = min(d.lineno for d in node.decorator_list) - 1
                end = node.end_lineno
                sections.append("\n".join(lines[start:end]))

    if len(sections) <= 1:
        return None  # Only header, no relevant functions found

    return "\n\n\n".join(sections)


def _extract_story_tests(test_file: str, story_id: str) -> str | None:
    """Extract test functions for a specific story from the test file.

    Finds all functions matching test_s{story_id}_* and returns their source.
    This lets Qwen see exactly what the tests assert without modifying them.
    """
    p = Path(test_file)
    if not p.exists():
        return None

    content = p.read_text(encoding="utf-8")
    prefix = f"test_s{story_id}_"

    # Split into top-level functions and extract matching ones
    lines = content.split("\n")
    tests = []
    current = []
    in_test = False

    for line in lines:
        if line.startswith("def "):
            if in_test and current:
                tests.append("\n".join(current))
            if prefix in line:
                in_test = True
                current = [line]
            else:
                in_test = False
                current = []
        elif in_test:
            current.append(line)

    if in_test and current:
        tests.append("\n".join(current))

    if not tests:
        return None

    return "\n\n".join(tests)


def build_prompt(
    story: dict,
    test_output: str,
    intervention_message: str | None = None,
    deploy_error: str | None = None,
    regression_error: str | None = None,
) -> str:
    """Build the full prompt for Qwen.

    Args:
        story: The story dict from prd.json.
        test_output: The failing test output.
        intervention_message: Optional human instruction from HUMAN.md.
        deploy_error: Optional deploy error logs to feed back.
        regression_error: Optional regression test error from previous attempt.

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

    # 4b. Regression error context (previous attempt broke earlier stories)
    if regression_error:
        parts.append("=== REGRESSION ERROR (YOUR PREVIOUS CODE BROKE THIS) ===")
        parts.append("Your last attempt passed the current story's tests but BROKE a previously completed story.")
        parts.append("You MUST fix the current story WITHOUT breaking the following test:")
        parts.append(regression_error)
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

    # Pre-extract test source (needed by _extract_relevant_code below)
    test_source = _extract_story_tests(story["test_file"], story["id"])

    # Load context files within budget
    # For large files (>10K), send inventory + only relevant functions
    total_chars = 0
    inventories = []
    LARGE_FILE_THRESHOLD = 10_000

    for filepath in context_files:
        p = Path(filepath)
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")

        # Build function inventory for Python files
        if filepath.endswith(".py"):
            inv = _extract_function_inventory(filepath, content)
            if inv:
                inventories.append(inv)

        # For large Python files, extract only relevant functions
        if filepath.endswith(".py") and len(content) > LARGE_FILE_THRESHOLD:
            trimmed = _extract_relevant_code(filepath, content, story, test_source)
            if trimmed and total_chars + len(trimmed) <= CHAR_BUDGET:
                parts.append(f"=== {filepath} (relevant sections — full file has {len(content)} chars) ===")
                parts.append(trimmed)
                parts.append("")
                total_chars += len(trimmed)
                continue
            # If trimming returned None or over budget, skip the full file —
            # the function inventory (already collected above) is enough context.
            # Sending the full 64K file would overflow Qwen's 16K token context.
            parts.append(f"=== {filepath} (SKIPPED — too large, see inventory above) ===")
            continue

        if total_chars + len(content) > CHAR_BUDGET:
            parts.append(f"=== {filepath} (SKIPPED — budget exceeded) ===")
            continue
        parts.append(f"=== {filepath} ===")
        parts.append(content)
        parts.append("")
        total_chars += len(content)

    # Inject function inventories as warnings
    if inventories:
        for inv in inventories:
            parts.append(inv)

    # 7. Test source code — show Qwen exactly what the tests do
    if test_source:
        parts.append("=== TEST SOURCE CODE (read-only — DO NOT modify) ===")
        parts.append(test_source)
        parts.append("")

    # 8. Failing test output
    parts.append("=== FAILING TEST OUTPUT ===")
    parts.append(test_output)
    parts.append("")

    # 9. Instructions
    parts.append("=== YOUR TASK ===")
    parts.append(
        "Write the code to make the failing tests pass. "
        "For EXISTING files, use ### PATCH: path/to/file.py with these sections:\n"
        "  ADD IMPORT — new import lines\n"
        "  ADD FUNCTION — new function or class definition\n"
        "  ADD CLASS — new SQLAlchemy model class\n"
        "  UPDATE FUNCTION: name — replace an existing function (include COMPLETE body)\n"
        "  UPDATE CLASS: name — replace an existing class\n"
        "  UPDATE CONSTANT: name — add items to a list constant\n"
        "Output ONLY new or changed code. "
        "For NEW files, use ### FILE: path/to/file.py with complete contents. "
        "Do NOT modify any files on the blocklist (see AGENTS.md).\n\n"
        "CRITICAL: When using UPDATE FUNCTION, you MUST include the COMPLETE function body — "
        "including ALL existing logic. Do NOT remove or shorten existing code. "
        "Dropping existing code causes regressions."
    )

    return "\n".join(parts)


def build_conflict_prompt(
    current_story: dict,
    current_test_source: str,
    reg_story_id: str,
    reg_test_source: str,
    test_file: str,
) -> str:
    """Build a focused prompt asking Qwen to fix a test conflict.

    When the current story's test contradicts a regression test (e.g. different
    naming conventions), this prompt shows both tests and asks Qwen to fix
    only the current story's test to be consistent with the regression test.
    """
    story_id = current_story["id"]
    title = current_story["title"]
    desc = current_story.get("description", "")

    return f"""=== TEST CONFLICT DETECTED ===
Your code for Story {story_id} passes its own test but breaks Story {reg_story_id}.
This has happened multiple times — the tests contradict each other.

The regression test (Story {reg_story_id}) is CORRECT — it passed when that story was completed.
You must fix the CURRENT story's test (Story {story_id}) to be consistent.

=== CURRENT STORY ===
Story {story_id}: {title}
Description: {desc}

=== CURRENT STORY TEST (needs fixing) ===
{current_test_source}

=== REGRESSION TEST (correct, do not change) ===
{reg_test_source}

=== YOUR TASK ===
Fix the current story's test function(s) so they are consistent with the regression test.
Do NOT change the test's intent — only fix naming/format mismatches.

Output your fix as:
### PATCH: {test_file}

For each function that needs fixing, use:
### UPDATE FUNCTION: function_name
(complete fixed function body)
"""
