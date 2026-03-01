"""Alert module — sends notifications on failures via webhook or local log."""

import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ALERT_LOG = Path("alerts.log")
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")


def send_alert(title: str, message: str):
    """Send an alert via webhook (if configured) and always write to alerts.log.

    Supports Discord webhooks, ntfy.sh, and generic POST endpoints.
    Never raises — failures are swallowed and printed.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log_line = f"[{timestamp}] {title}: {message}\n"

    # Always write to log file
    try:
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(log_line)
    except OSError as e:
        print(f"[ALERT] Could not write to {ALERT_LOG}: {e}")

    # Always print loud
    print(f"\n{'!'*60}")
    print(f"[ALERT] {title}")
    print(f"        {message}")
    print(f"{'!'*60}\n")

    # Try webhook if configured
    if not WEBHOOK_URL:
        return

    try:
        if "discord.com/api/webhooks" in WEBHOOK_URL:
            # Discord webhook format
            requests.post(
                WEBHOOK_URL,
                json={"content": f"**{title}**\n{message}"},
                timeout=10,
            )
        elif "ntfy.sh" in WEBHOOK_URL:
            # ntfy.sh format
            requests.post(
                WEBHOOK_URL,
                data=message.encode("utf-8"),
                headers={"Title": title},
                timeout=10,
            )
        else:
            # Generic POST
            requests.post(
                WEBHOOK_URL,
                json={"title": title, "message": message},
                timeout=10,
            )
    except Exception as e:
        print(f"[ALERT] Webhook delivery failed: {e}")
