"""Auto-fixer for common Qwen mistakes.

Reads .ralph-needs-help.json, applies known pattern fixes,
resets story to pending in prd.json so Ralph can retry.

Run this alongside Ralph: python -m ralph.fix_common_errors
"""

import json
import re
import time
import subprocess
from pathlib import Path

HELP_FILE = Path(".ralph-needs-help.json")
PRD_FILE = Path("prd.json")
POLL_INTERVAL = 15  # seconds


def fix_missing_event_fields(filepath: str) -> bool:
    """Fix Event() calls missing description or tick."""
    path = Path(filepath)
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")
    original = content
    changed = False

    # Pattern: Event( with event_type but no description
    # Find Event constructor calls missing description=
    event_pattern = re.compile(
        r'(Event\s*\([^)]*event_type\s*=\s*["\'][^"\']+["\'])([^)]*\))',
        re.DOTALL,
    )
    for match in event_pattern.finditer(content):
        full = match.group(0)
        if 'description=' not in full:
            # Add a default description
            event_type_match = re.search(r"event_type\s*=\s*['\"]([^'\"]+)['\"]", full)
            etype = event_type_match.group(1) if event_type_match else "event"
            desc = etype.replace("_", " ").title()
            fix = full.replace("event_type=", f'description="{desc}",\n        event_type=')
            content = content.replace(full, fix)
            changed = True
            print(f"  [AUTOFIX] Added missing description to Event({etype})")

    # Pattern: Event( missing tick=
    event_pattern2 = re.compile(
        r'(Event\s*\([^)]*event_type\s*=\s*["\'][^"\']+["\'])([^)]*\))',
        re.DOTALL,
    )
    for match in event_pattern2.finditer(content):
        full = match.group(0)
        if 'tick=' not in full:
            # Add tick=0 as default
            fix = full.rstrip(")")
            fix += ",\n        tick=0\n    )"
            content = content.replace(full, fix)
            changed = True
            print(f"  [AUTOFIX] Added missing tick=0 to Event()")

    # Pattern: Transaction with wrong column names
    if "sender_npc_id" in content or "receiver_npc_id" in content:
        content = content.replace("sender_npc_id", "sender_id")
        content = content.replace("receiver_npc_id", "receiver_id")
        changed = True
        print("  [AUTOFIX] Fixed Transaction column names (sender_npc_id -> sender_id)")

    if "npc_id=" in content and "Transaction(" in content:
        # Check if npc_id is used in a Transaction context
        lines = content.split("\n")
        in_transaction = False
        for i, line in enumerate(lines):
            if "Transaction(" in line:
                in_transaction = True
            if in_transaction and "npc_id=" in line and "sender_id" not in line:
                lines[i] = line.replace("npc_id=", "sender_id=")
                changed = True
                print(f"  [AUTOFIX] Fixed Transaction.npc_id -> sender_id at line {i+1}")
            if in_transaction and ")" in line and "Transaction" not in line:
                in_transaction = False
        content = "\n".join(lines)

    # Pattern: Crime.npc_id -> Crime.criminal_npc_id
    if "Crime.npc_id" in content:
        content = content.replace("Crime.npc_id", "Crime.criminal_npc_id")
        changed = True
        print("  [AUTOFIX] Fixed Crime.npc_id -> Crime.criminal_npc_id")

    # Pattern: == False / == True for integer columns (Postgres compat)
    if re.search(r'\.is_dead\s*==\s*(False|True)', content):
        content = re.sub(r'\.is_dead\s*==\s*False', '.is_dead == 0', content)
        content = re.sub(r'\.is_dead\s*==\s*True', '.is_dead == 1', content)
        changed = True
        print("  [AUTOFIX] Fixed is_dead boolean comparison for Postgres")

    if re.search(r'\.is_bankrupt\s*==\s*(False|True)', content):
        content = re.sub(r'\.is_bankrupt\s*==\s*False', '.is_bankrupt == 0', content)
        content = re.sub(r'\.is_bankrupt\s*==\s*True', '.is_bankrupt == 1', content)
        changed = True
        print("  [AUTOFIX] Fixed is_bankrupt boolean comparison for Postgres")

    if changed:
        path.write_text(content, encoding="utf-8")
    return changed


def reset_story(story_id: str):
    """Reset a story from 'failed' to 'pending' in prd.json."""
    prd = json.loads(PRD_FILE.read_text(encoding="utf-8"))
    for s in prd["stories"]:
        if s["id"] == story_id:
            s["status"] = "pending"
            s.pop("attempts", None)
            print(f"  [RESET] Story {story_id} -> pending")
            break
    PRD_FILE.write_text(json.dumps(prd, indent=2), encoding="utf-8")


def run_test(test_file: str, story_id: str) -> bool:
    """Run the story's test to see if the autofix worked."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", test_file, "-k", f"s{story_id}", "-xq", "--tb=short"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def process_help_request():
    """Read help file, attempt fixes, reset if successful."""
    data = json.loads(HELP_FILE.read_text(encoding="utf-8"))
    story_id = data["story_id"]
    title = data["title"]
    context_files = data.get("context_files", [])
    test_file = data.get("test_file", "")

    print(f"\n[FIXER] Story {story_id}: {title}")
    print(f"  Context: {context_files}")
    print(f"  Test: {test_file}")

    fixed = False
    for cf in context_files:
        if Path(cf).exists():
            if fix_missing_event_fields(cf):
                fixed = True

    if fixed and test_file and run_test(test_file, story_id):
        print(f"  [SUCCESS] Autofix worked! Resetting story {story_id}")
        reset_story(story_id)
        HELP_FILE.unlink(missing_ok=True)
        return True
    elif fixed:
        print(f"  [PARTIAL] Applied fixes but test still fails")
        # Still reset so Ralph retries with the partial fixes
        reset_story(story_id)
        HELP_FILE.unlink(missing_ok=True)
        return True
    else:
        print(f"  [NO FIX] No known pattern matched — needs manual fix")
        return False


def main():
    print("[FIXER] Monitoring for Ralph help requests...")
    print(f"  Polling {HELP_FILE} every {POLL_INTERVAL}s")
    while True:
        if HELP_FILE.exists():
            try:
                process_help_request()
            except Exception as e:
                print(f"  [ERROR] {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
