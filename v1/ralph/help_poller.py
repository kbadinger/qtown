#!/usr/bin/env python3
"""
Poll for .ralph-needs-help.json and print diagnostics.

Run this in a separate terminal:
    python ralph/help_poller.py

When Ralph hits a loop, it writes .ralph-needs-help.json and waits 10 minutes.
This script detects the file, prints the error context, and waits for you
(or an automated fixer) to resolve it.

After fixing, delete .ralph-needs-help.json (or just let Ralph's timer expire).
Ralph will pull latest, re-run autofix, and retry.
"""

import json
import time
import sys
from pathlib import Path

HELP_FILE = Path(".ralph-needs-help.json")
POLL_INTERVAL = 15  # seconds


def main():
    print("[help-poller] Watching for .ralph-needs-help.json ...")
    print("[help-poller] Press Ctrl+C to stop.\n")

    last_seen = None

    while True:
        try:
            if HELP_FILE.exists():
                data = json.loads(HELP_FILE.read_text(encoding="utf-8"))
                sig = (data.get("story_id"), data.get("timestamp"))

                if sig != last_seen:
                    last_seen = sig
                    print("=" * 60)
                    print(f"[HELP NEEDED] Story {data.get('story_id')}: {data.get('story_title')}")
                    print(f"  Attempt:   {data.get('attempt')}")
                    print(f"  Test file: {data.get('test_file')}")
                    print(f"  Timestamp: {data.get('timestamp')}")
                    print(f"  Error:")
                    for line in data.get("error", "").split("\n"):
                        print(f"    {line}")
                    print("=" * 60)
                    print("[help-poller] Fix the issue, commit, push. Ralph will pull in ~10min.")
                    print("[help-poller] Or delete .ralph-needs-help.json to signal early.\n")
            else:
                if last_seen is not None:
                    print("[help-poller] Help file cleared — Ralph should resume.\n")
                    last_seen = None

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n[help-poller] Stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"[help-poller] Error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
