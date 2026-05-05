"""Alert module — Telegram activity feed + local log.

Notification levels:
  - notify(): routine events (start, stop, story complete)
  - warn(): issues that need attention (story failed, deploy retry)
  - alert(): critical problems (3 failures, deploy broken, loop detected)
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ALERT_LOG = Path("alerts.log")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Icons for Telegram messages
_ICONS = {
    "start": "\U0001f7e2",      # green circle
    "stop": "\U0001f534",       # red circle
    "story_start": "\U0001f4d6", # open book
    "story_done": "\u2705",      # check mark
    "story_fail": "\u274c",      # X mark
    "deploy_ok": "\U0001f680",   # rocket
    "deploy_fail": "\U0001f6a8", # rotating light
    "warning": "\u26a0\ufe0f",   # warning
    "critical": "\U0001f6a8",    # rotating light
    "loop": "\U0001f503",        # cycle arrows
    "info": "\u2139\ufe0f",      # info
}


def _send_telegram(text: str):
    """Send a message to Telegram. Never raises."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[ALERT] Telegram delivery failed: {e}")


def _log(title: str, message: str):
    """Write to alerts.log and console."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log_line = f"[{timestamp}] {title}: {message}\n"
    try:
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(log_line)
    except OSError:
        pass
    print(f"[ALERT] {title}: {message}")


def notify(event: str, message: str):
    """Routine event — logged + Telegram."""
    icon = _ICONS.get(event, _ICONS["info"])
    _log(event, message)
    _send_telegram(f"{icon} *{event}*\n{message}")


def warn(event: str, message: str):
    """Issue needing attention — logged + Telegram."""
    icon = _ICONS.get(event, _ICONS["warning"])
    _log(f"WARN {event}", message)
    _send_telegram(f"{icon} *{event}*\n{message}")


def alert(event: str, message: str):
    """Critical problem — logged + loud console + Telegram."""
    icon = _ICONS.get(event, _ICONS["critical"])
    _log(f"CRITICAL {event}", message)
    print(f"\n{'!'*60}")
    print(f"[CRITICAL] {event}")
    print(f"           {message}")
    print(f"{'!'*60}\n")
    _send_telegram(f"{icon} *CRITICAL: {event}*\n{message}")


# Keep backward compatibility — send_alert maps to alert()
def send_alert(title: str, message: str):
    """Legacy wrapper — maps to alert()."""
    alert(title, message)
