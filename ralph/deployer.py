"""Deploy monitoring — push, health check, error capture."""

import os
import subprocess
import time

DEPLOY_URL = os.getenv("DEPLOY_URL", "https://your-app.up.railway.app")
DEPLOY_TIMEOUT = int(os.getenv("DEPLOY_TIMEOUT", "300"))
HEALTH_ENDPOINT = "/health"


def push_to_remote() -> tuple[bool, str]:
    """Push to GitHub (if remote exists) and deploy to Railway via CLI.

    Returns (success, output).
    """
    output_parts = []

    # 1. Push to GitHub if origin remote is configured
    git_check = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if git_check.returncode == 0:
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True, text=True, timeout=60,
        )
        output_parts.append(result.stdout + result.stderr)
        if result.returncode != 0:
            output_parts.append("WARNING: git push failed, deploying via CLI anyway")

    # 2. Deploy to Railway via CLI (primary deploy path)
    try:
        result = subprocess.run(
            ["railway", "up", "--detach"],
            capture_output=True, text=True, timeout=120,
        )
        output_parts.append(result.stdout + result.stderr)
        if result.returncode != 0:
            return False, f"Railway deploy failed:\n{''.join(output_parts)}"
    except FileNotFoundError:
        return False, "Railway CLI not installed — cannot deploy"

    return True, "\n".join(output_parts)


def wait_for_deploy(timeout: int | None = None) -> tuple[bool, str]:
    """Poll health endpoint until deploy succeeds or times out.

    Returns (healthy, status_message).
    """
    import requests

    timeout = timeout or DEPLOY_TIMEOUT
    url = DEPLOY_URL.rstrip("/") + HEALTH_ENDPOINT
    start = time.time()
    last_error = ""

    print(f"  [DEPLOY] Waiting for {url} (timeout: {timeout}s)")

    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    elapsed = round(time.time() - start, 1)
                    return True, f"Healthy after {elapsed}s"
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as e:
            last_error = str(e)

        time.sleep(10)

    return False, f"Timed out after {timeout}s. Last error: {last_error}"


def get_deploy_errors() -> str:
    """Capture Railway deploy logs on failure.

    Returns formatted error string for Qwen context.
    """
    try:
        result = subprocess.run(
            ["railway", "logs", "--latest"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        logs = result.stdout + result.stderr
        # Trim to last 50 lines to keep prompt manageable
        lines = logs.strip().split("\n")
        if len(lines) > 50:
            lines = lines[-50:]
        return "--- Railway Deploy Logs ---\n" + "\n".join(lines)
    except FileNotFoundError:
        return "Could not fetch Railway logs: 'railway' CLI not installed"
    except Exception as e:
        return f"Could not fetch Railway logs: {e}"


def push_and_wait() -> tuple[bool, str]:
    """Full deploy pipeline: push → wait for health → return status.

    Returns (success, message). On failure, message includes error context.
    """
    push_ok, push_output = push_to_remote()
    if not push_ok:
        return False, f"Git push failed:\n{push_output}"

    healthy, status = wait_for_deploy()
    if healthy:
        return True, status

    # Deploy failed — capture logs
    error_logs = get_deploy_errors()
    return False, f"Deploy unhealthy: {status}\n\n{error_logs}"
