"""Parse Qwen's output and apply file changes. Extended blocklist for safety."""

import ast
import os
import re
from dataclasses import dataclass, field
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


def _extract_top_level_defs(source: str) -> dict[str, dict]:
    """Extract top-level function and class definitions from Python source.

    Returns {name: {"body": str, "start": int, "end": int}} for each
    top-level def/class.  start/end are 0-indexed line numbers (end exclusive).
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
            defs[node.name] = {"body": block, "start": start, "end": end}

    return defs


def _extract_new_functions_regex(old_names: set[str], source: str) -> list[str]:
    """Extract new function/class bodies from source using regex.

    Fallback for when AST parsing fails (syntax errors in Qwen's output).
    Returns a list of function body strings for functions not in old_names.
    """
    # Match top-level def/class (no leading whitespace) through to next top-level
    # def/class or end of file
    chunks = re.split(r"\n(?=(?:def |class |@))", source)
    new_bodies = []
    for chunk in chunks:
        # Get function/class name from this chunk
        m = re.match(r"(?:@\w+.*\n)*(?:def|class)\s+(\w+)", chunk.strip())
        if m and m.group(1) not in old_names:
            new_bodies.append(chunk.strip())
    return new_bodies


def _merge_list_constants(old_content: str, new_content: str) -> str:
    """Merge module-level list constants (e.g. BUILDING_TYPES) from Qwen's output.

    If Qwen's version of a list constant is a superset of the old one (same items
    plus new ones), update it in the old content. This handles the common case
    where Qwen adds a new type to BUILDING_TYPES but the syntax-error fallback
    reverted to the old file.
    """
    def _find_list_constants(content):
        """Find NAME = [...] patterns, handling both single and multi-line lists."""
        result = {}
        for m in re.finditer(r'^([A-Z_]+)\s*=\s*\[', content, re.MULTILINE):
            name = m.group(1)
            # Find matching closing bracket
            start = m.start()
            bracket_start = content.index('[', start)
            depth = 0
            for i in range(bracket_start, len(content)):
                if content[i] == '[':
                    depth += 1
                elif content[i] == ']':
                    depth -= 1
                    if depth == 0:
                        result[name] = content[bracket_start:i + 1]
                        break
        return result

    old_lists = _find_list_constants(old_content)
    new_lists = _find_list_constants(new_content)

    result = old_content
    for name in old_lists:
        if name not in new_lists:
            continue
        try:
            old_items = ast.literal_eval(old_lists[name])
            new_items = ast.literal_eval(new_lists[name])
        except (ValueError, SyntaxError):
            continue
        if not isinstance(old_items, list) or not isinstance(new_items, list):
            continue
        # Only merge if new is a superset (all old items present + new ones added)
        if set(old_items).issubset(set(new_items)) and len(new_items) > len(old_items):
            added = set(new_items) - set(old_items)
            result = result.replace(old_lists[name], new_lists[name], 1)
            print(f"  [MERGE] Updated {name}: added {added}")

    return result


def _merge_dropped_definitions(filepath: str, old_content: str, new_content: str) -> str:
    """Protect existing definitions from corruption when Qwen rewrites a file.

    Strategy:
    - OLD file is always the trusted base for existing definitions.
    - NEW file is only trusted for genuinely new functions and intentional
      modifications (where the new body references a new-only function).
    - If new file has syntax errors, fall back to old file + regex-extracted
      new functions appended.
    """
    old_defs = _extract_top_level_defs(old_content)
    new_defs = _extract_top_level_defs(new_content)

    if not old_defs:
        return new_content  # Can't parse old file — nothing to protect

    # --- FAILSAFE: If Qwen's output doesn't parse, use old file as base ---
    if not new_defs:
        print(f"  [MERGE] Qwen's {filepath} has syntax errors — using old file as base")
        result = old_content
        # Merge module-level list constants (e.g. BUILDING_TYPES)
        result = _merge_list_constants(result, new_content)
        # Extract and append new functions
        new_bodies = _extract_new_functions_regex(set(old_defs.keys()), new_content)
        if new_bodies:
            print(f"  [MERGE] Recovered {len(new_bodies)} new function(s) via regex")
            result = result.rstrip("\n") + "\n\n\n" + "\n\n\n".join(new_bodies) + "\n"
        # Verify the result still parses
        try:
            ast.parse(result)
            if result.strip() != old_content.strip():
                return result
            print(f"  [MERGE] No recoverable changes — keeping old file unchanged")
            return old_content
        except SyntaxError:
            print(f"  [MERGE] Recovered content has syntax errors — keeping old file unchanged")
            return old_content

    dropped = set(old_defs) - set(new_defs)
    new_only = set(new_defs) - set(old_defs)
    shared = set(old_defs) & set(new_defs)

    # --- Detect corrupted shared functions ---
    corrupted = []
    for name in shared:
        old_body = old_defs[name]["body"].strip()
        new_body = new_defs[name]["body"].strip()
        if old_body != new_body:
            # Allow the change if new body references any new-only function
            # (e.g. process_tick calling produce_church_resources)
            references_new = any(
                re.search(r"\b" + re.escape(nn) + r"\b", new_body)
                for nn in new_only
            )
            if not references_new:
                corrupted.append(name)

    # --- Replace corrupted function bodies (bottom-up to keep line numbers) ---
    if corrupted:
        lines = new_content.split("\n")
        for name in sorted(corrupted, key=lambda n: new_defs[n]["start"], reverse=True):
            start = new_defs[name]["start"]
            end = new_defs[name]["end"]
            old_lines = old_defs[name]["body"].split("\n")
            lines[start:end] = old_lines
        new_content = "\n".join(lines)
        print(f"  [MERGE] Preserved old bodies for {len(corrupted)} corrupted definitions in {filepath}: {', '.join(corrupted)}")

    # --- Append dropped definitions ---
    if dropped:
        old_order = list(old_defs.keys())
        dropped_sorted = sorted(dropped, key=lambda name: old_order.index(name))
        restored_parts = [old_defs[name]["body"] for name in dropped_sorted]
        print(f"  [MERGE] Restored {len(dropped)} dropped definitions in {filepath}: {', '.join(dropped_sorted)}")
        new_content = new_content.rstrip("\n") + "\n\n\n" + "\n\n\n".join(restored_parts) + "\n"

    # --- Final syntax check: if merge result is broken, prefer old + new functions ---
    try:
        ast.parse(new_content)
    except SyntaxError:
        print(f"  [MERGE] Post-merge syntax error in {filepath} — falling back to old + new functions only")
        new_bodies = [new_defs[name]["body"] for name in sorted(new_only)]
        if new_bodies:
            result = old_content.rstrip("\n") + "\n\n\n" + "\n\n\n".join(new_bodies) + "\n"
            try:
                ast.parse(result)
                return result
            except SyntaxError:
                print(f"  [MERGE] New functions also broken — keeping old file unchanged")
                return old_content
        return old_content

    return new_content


@dataclass
class PatchSection:
    action: str   # "add_import", "add_function", "update_function", "update_constant"
    target: str   # function/constant name (empty for add_import)
    body: str     # the code


@dataclass
class FileBlock:
    filepath: str
    content: str
    mode: str = "full"  # "full" or "patch"
    sections: list[PatchSection] = field(default_factory=list)


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from a block of text."""
    # Remove all ```python / ``` pairs, keeping inner content
    text = re.sub(r"```\w*\n", "", text)
    text = re.sub(r"\n```", "", text)
    return text.strip()


def _split_multi_function_body(body: str) -> list[str]:
    """Split a body that contains multiple top-level function defs into separate bodies."""
    # Split on top-level def (no leading whitespace)
    chunks = re.split(r"\n(?=def |\nasync def |@)", body)
    # First chunk might start with def already
    results = []
    current = ""
    for chunk in chunks:
        stripped = chunk.strip()
        if not stripped:
            continue
        if (stripped.startswith("def ") or stripped.startswith("async def ") or stripped.startswith("@")):
            if current.strip():
                results.append(current.strip())
            current = chunk
        else:
            current += "\n" + chunk
    if current.strip():
        results.append(current.strip())
    return results if len(results) > 1 else [body]


def parse_patch_sections(content: str) -> list[PatchSection]:
    """Parse patch sections from a ### PATCH: block's content.

    Recognized headers (case-insensitive, 3 or 4 hashes):
      ### ADD IMPORT
      ### ADD FUNCTION
      ### UPDATE FUNCTION: name
      ### UPDATE CONSTANT: name
    """
    # Split on section headers — allow ###, ####, or no hashes (Qwen varies)
    header_re = re.compile(
        r"^(?:#{3,4}\s+)?"
        r"(ADD\s+IMPORT|ADD\s+FUNCTION|UPDATE\s+FUNCTION|(?:UPDATE|ADD)\s+CONSTANT)"
        r"(?:\s*:\s*(\w+))?"  # optional : name
        r":?\s*$",  # allow trailing colon with no name
        re.IGNORECASE | re.MULTILINE,
    )

    sections: list[PatchSection] = []
    splits = list(header_re.finditer(content))

    for i, m in enumerate(splits):
        raw_action = re.sub(r"\s+", "_", m.group(1).strip().lower())
        # Normalize add_constant → update_constant
        if raw_action == "add_constant":
            raw_action = "update_constant"
        target = m.group(2) or ""
        start = m.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(content)
        body = _strip_code_fences(content[start:end])
        if not body:
            continue

        # If ADD FUNCTION contains multiple defs, split them
        if raw_action == "add_function":
            func_bodies = _split_multi_function_body(body)
            for fb in func_bodies:
                fname = _guess_func_name(fb)
                sections.append(PatchSection(action="add_function", target=fname, body=fb))
        else:
            sections.append(PatchSection(action=raw_action, target=target, body=body))

    return sections


def _merge_imports(existing_source: str, import_block: str) -> str:
    """Merge new import lines into existing source, deduplicating."""
    existing_lines = existing_source.split("\n")
    new_import_lines = [l.strip() for l in import_block.split("\n") if l.strip()]

    # Find where imports end in existing file (last import/from line before first def/class)
    last_import_idx = -1
    for i, line in enumerate(existing_lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import_idx = i

    # Collect existing import strings for dedup
    existing_imports = set()
    for line in existing_lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            existing_imports.add(stripped)

    # Filter to truly new imports
    to_add = [l for l in new_import_lines if l not in existing_imports]
    if not to_add:
        return existing_source

    insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0
    for j, imp in enumerate(to_add):
        existing_lines.insert(insert_at + j, imp)

    print(f"  [PATCH] Added {len(to_add)} import(s)")
    return "\n".join(existing_lines)


def _find_function_range(source: str, func_name: str) -> tuple[int, int] | None:
    """Find the line range (start, end exclusive, 0-indexed) of a top-level function by name."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            start = node.lineno - 1
            if node.decorator_list:
                start = min(d.lineno for d in node.decorator_list) - 1
            end = node.end_lineno  # 1-indexed = exclusive 0-indexed
            return (start, end)
    return None


def _find_constant_range(source: str, const_name: str) -> tuple[int, int] | None:
    """Find the line range of a module-level constant assignment NAME = [...]."""
    lines = source.split("\n")
    pattern = re.compile(rf"^{re.escape(const_name)}\s*=\s*")
    for i, line in enumerate(lines):
        if pattern.match(line):
            # Find end — either bracket-balanced or single line
            if "[" in line:
                depth = 0
                for j in range(i, len(lines)):
                    depth += lines[j].count("[") - lines[j].count("]")
                    if depth <= 0:
                        return (i, j + 1)
            # dict or simple value — find next non-continuation line
            if line.rstrip().endswith(("{", "\\")) or "{" in line:
                depth = line.count("{") - line.count("}")
                depth += line.count("[") - line.count("]")
                for j in range(i + 1, len(lines)):
                    depth += lines[j].count("{") - lines[j].count("}")
                    depth += lines[j].count("[") - lines[j].count("]")
                    if depth <= 0:
                        return (i, j + 1)
            return (i, i + 1)
    return None


def _smart_update_constant(source: str, name: str, new_body: str, rng: tuple[int, int]) -> str:
    """Update a constant, with special handling for list constants.

    Qwen often sends just the new item(s) instead of the full list.
    This detects that case and appends to the existing list instead of replacing.
    """
    lines = source.split("\n")
    old_text = "\n".join(lines[rng[0]:rng[1]])
    body = new_body.strip()

    # Case 1: Qwen sent a complete assignment (NAME = [...])
    if re.match(rf"^{re.escape(name)}\s*=\s*", body):
        try:
            old_val = ast.literal_eval(old_text.split("=", 1)[1].strip())
            new_val = ast.literal_eval(body.split("=", 1)[1].strip())
            if isinstance(old_val, list) and isinstance(new_val, list):
                # If new is a superset, use it directly
                if set(old_val).issubset(set(new_val)):
                    lines[rng[0]:rng[1]] = body.split("\n")
                    added = set(new_val) - set(old_val)
                    print(f"  [PATCH] Updated constant {name}: added {added}")
                    return "\n".join(lines)
                # If new is a subset or disjoint, it's likely corruption — append new items
                added = [item for item in new_val if item not in old_val]
                if added:
                    merged = old_val + added
                    new_list_str = _format_list_constant(name, merged)
                    lines[rng[0]:rng[1]] = new_list_str.split("\n")
                    print(f"  [PATCH] Updated constant {name}: appended {added} (protected existing items)")
                    return "\n".join(lines)
                # No new items — no-op
                print(f"  [PATCH] Constant {name}: no new items to add")
                return source
        except (ValueError, SyntaxError):
            pass
        # Non-list or unparseable — direct replacement
        lines[rng[0]:rng[1]] = body.split("\n")
        print(f"  [PATCH] Updated constant {name}")
        return "\n".join(lines)

    # Case 2: Qwen sent just the new items (e.g. `"theater",`)
    # — no NAME = prefix, looks like list items
    try:
        old_val = ast.literal_eval(old_text.split("=", 1)[1].strip())
        if isinstance(old_val, list):
            # Parse bare items: wrap in list brackets and eval
            items_str = body.rstrip(",").strip()
            new_items = ast.literal_eval(f"[{items_str}]")
            added = [item for item in new_items if item not in old_val]
            if added:
                merged = old_val + added
                new_list_str = _format_list_constant(name, merged)
                lines[rng[0]:rng[1]] = new_list_str.split("\n")
                print(f"  [PATCH] Updated constant {name}: appended {added} (from bare items)")
                return "\n".join(lines)
            print(f"  [PATCH] Constant {name}: items already present")
            return source
    except (ValueError, SyntaxError, IndexError):
        pass

    # Case 3: Fallback — direct replacement
    lines[rng[0]:rng[1]] = body.split("\n")
    print(f"  [PATCH] Updated constant {name}")
    return "\n".join(lines)


def _format_list_constant(name: str, items: list) -> str:
    """Format a list constant as a multi-line Python assignment."""
    lines = [f"{name} = ["]
    for item in items:
        lines.append(f"    {item!r},")
    lines.append("]")
    return "\n".join(lines)


def apply_patch(filepath: str, sections: list[PatchSection]) -> str:
    """Apply patch sections to an existing file. Returns the patched content."""
    if not Path(filepath).exists():
        # File doesn't exist — assemble from sections as a new file
        parts = []
        for s in sections:
            parts.append(s.body)
        return "\n\n\n".join(parts) + "\n"

    source = Path(filepath).read_text(encoding="utf-8")
    original = source

    # Process imports first
    for s in sections:
        if s.action == "add_import":
            source = _merge_imports(source, s.body)

    # Process constants
    for s in sections:
        if s.action == "update_constant":
            rng = _find_constant_range(source, s.target)
            if rng:
                source = _smart_update_constant(source, s.target, s.body, rng)
            else:
                # Constant not found — insert before first function def
                lines = source.split("\n")
                insert_at = len(lines)
                for i, line in enumerate(lines):
                    if line.startswith("def ") or line.startswith("class "):
                        insert_at = i
                        break
                new_lines = ["", ""] + s.body.strip().split("\n") + ["", ""]
                lines[insert_at:insert_at] = new_lines
                source = "\n".join(lines)
                print(f"  [PATCH] Added constant {s.target}")

    # Process functions (update first, then add)
    for s in sections:
        if s.action == "update_function":
            rng = _find_function_range(source, s.target)
            if rng:
                lines = source.split("\n")
                new_lines = s.body.strip().split("\n")
                lines[rng[0]:rng[1]] = new_lines
                source = "\n".join(lines)
                print(f"  [PATCH] Updated function {s.target}")
            else:
                # Not found — treat as add
                source = source.rstrip("\n") + "\n\n\n" + s.body.strip() + "\n"
                print(f"  [PATCH] Added function {s.target} (was UPDATE but not found)")

    for s in sections:
        if s.action == "add_function":
            # Check if it already exists (Qwen said ADD but it's already there)
            rng = _find_function_range(source, s.target or _guess_func_name(s.body))
            if rng:
                # Treat as update
                lines = source.split("\n")
                new_lines = s.body.strip().split("\n")
                lines[rng[0]:rng[1]] = new_lines
                source = "\n".join(lines)
                print(f"  [PATCH] Updated function (ADD for existing) {s.target or '?'}")
            else:
                source = source.rstrip("\n") + "\n\n\n" + s.body.strip() + "\n"
                print(f"  [PATCH] Added function {s.target or '?'}")

    # Validate syntax
    try:
        ast.parse(source)
        return source
    except SyntaxError as e:
        print(f"  [PATCH] Syntax error after patching {filepath}: {e}")
        # Fallback: old file + only new functions appended
        fallback = original
        for s in sections:
            if s.action in ("add_function", "add_import"):
                if s.action == "add_import":
                    fallback = _merge_imports(fallback, s.body)
                else:
                    fallback = fallback.rstrip("\n") + "\n\n\n" + s.body.strip() + "\n"
        # Try merging constants too
        for s in sections:
            if s.action == "update_constant":
                rng = _find_constant_range(fallback, s.target)
                if rng:
                    lines = fallback.split("\n")
                    lines[rng[0]:rng[1]] = s.body.strip().split("\n")
                    fallback = "\n".join(lines)
        try:
            ast.parse(fallback)
            print(f"  [PATCH] Fallback succeeded: old file + new additions")
            return fallback
        except SyntaxError:
            print(f"  [PATCH] Fallback also broken — keeping original file")
            return original


def _guess_func_name(body: str) -> str:
    """Extract function name from a function body string."""
    m = re.match(r"(?:@\w+.*\n)*(?:async\s+)?def\s+(\w+)", body.strip())
    return m.group(1) if m else ""


def parse_file_blocks(response: str) -> list[FileBlock]:
    """Parse '### FILE:' and '### PATCH:' blocks from Qwen's response.

    Returns list of FileBlock objects.
    """
    # Match both ### FILE: and ### PATCH: markers
    pattern = r"###\s+(FILE|PATCH):\s*(.+?)\s*\n(.*?)(?=###\s+(?:FILE|PATCH):|$)"
    matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)

    blocks: list[FileBlock] = []
    for mode_tag, filepath, content in matches:
        filepath = filepath.strip()
        mode = "patch" if mode_tag.upper() == "PATCH" else "full"

        # Strip markdown code fences if present (for full mode)
        content_clean = re.sub(r"^```\w*\n", "", content.strip())
        content_clean = re.sub(r"\n```\s*$", "", content_clean)

        if mode == "patch":
            sections = parse_patch_sections(content)
            blocks.append(FileBlock(filepath=filepath, content=content_clean, mode="patch", sections=sections))
        else:
            blocks.append(FileBlock(filepath=filepath, content=content_clean, mode="full"))

    return blocks


def _redirect_misplaced_sections(file_blocks: list[FileBlock]) -> list[FileBlock]:
    """Redirect patch sections that target the wrong file.

    Common Qwen mistake: writing BUILDING_TYPES to engine/models.py when it
    lives in engine/simulation.py. Detect and redirect.
    """
    # Constants that live in engine/simulation.py, NOT engine/models.py
    SIM_CONSTANTS = {"BUILDING_TYPES"}

    sim_block = None
    for b in file_blocks:
        if b.filepath.replace("\\", "/") == "engine/simulation.py" and b.mode == "patch":
            sim_block = b
            break

    for block in file_blocks:
        if block.mode != "patch":
            continue
        norm = block.filepath.replace("\\", "/")
        if norm == "engine/simulation.py":
            continue

        redirected = []
        kept = []
        for s in block.sections:
            if s.action == "update_constant" and s.target in SIM_CONSTANTS:
                redirected.append(s)
            else:
                kept.append(s)

        if redirected:
            names = [s.target for s in redirected]
            print(f"  [REDIRECT] Moving {names} from {block.filepath} -> engine/simulation.py")
            block.sections = kept

            if sim_block is None:
                sim_block = FileBlock(filepath="engine/simulation.py", content="", mode="patch", sections=[])
                file_blocks.append(sim_block)
            sim_block.sections = redirected + sim_block.sections

    return file_blocks


def apply_files(response: str) -> list[str]:
    """Parse and write all file blocks from Qwen's response.

    Returns list of written filepaths. Skips blocked files.
    For Python files, automatically merges back any dropped definitions.
    """
    file_blocks = parse_file_blocks(response)
    file_blocks = _redirect_misplaced_sections(file_blocks)
    written = []

    for block in file_blocks:
        filepath = block.filepath

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

        content = block.content

        if block.mode == "patch" and block.sections:
            # Patch mode: apply surgical changes
            print(f"  [PATCH] Applying {len(block.sections)} section(s) to {filepath}")
            try:
                content = apply_patch(filepath, block.sections)
            except Exception as e:
                print(f"  [PATCH] Error applying patch to {filepath}: {e}")
                continue
        elif block.mode == "patch" and not block.sections:
            # Patch block with no valid sections — skip
            print(f"  [PATCH] No valid sections in patch for {filepath} — skipping")
            continue
        else:
            # Full mode: existing behavior with merge protection
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
