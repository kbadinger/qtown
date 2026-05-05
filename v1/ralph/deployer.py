"""Deploy monitoring — push, health check, error capture."""

import os
import re
import subprocess
import time

DEPLOY_URL = os.getenv("DEPLOY_URL", "https://your-app.up.railway.app")
DEPLOY_TIMEOUT = int(os.getenv("DEPLOY_TIMEOUT", "300"))
HEALTH_ENDPOINT = "/health"


def push_to_remote() -> tuple[bool, str, str]:
    """Push to GitHub (if remote exists) and deploy to Railway via CLI.

    Returns (success, output, deploy_id).
    deploy_id is extracted from railway up output for log retrieval.
    """
    output_parts = []
    deploy_id = ""

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
            capture_output=True, text=True, timeout=120, shell=True,
        )
        combined = result.stdout + result.stderr
        output_parts.append(combined)

        # Extract deploy ID from output (appears in build log URL as ?id=...)
        id_match = re.search(r'[?&]id=([a-f0-9-]+)', combined)
        if id_match:
            deploy_id = id_match.group(1)

        if result.returncode != 0:
            return False, "\n".join(output_parts), deploy_id
    except FileNotFoundError:
        return False, "Railway CLI not installed — cannot deploy", ""

    return True, "\n".join(output_parts), deploy_id


def _wait_for_build(deploy_id: str, timeout: int = 300) -> tuple[bool, str]:
    """Wait for Railway build to complete by polling deployment list.

    Returns (success, status_message).
    Polls `railway deployment list` until the deployment shows SUCCESS or FAILED.
    """
    start = time.time()
    # Short deploy ID prefix for matching (Railway shows full UUIDs)
    id_prefix = deploy_id[:12] if deploy_id else ""

    print(f"  [DEPLOY] Waiting for build to complete (timeout: {timeout}s)")

    while time.time() - start < timeout:
        try:
            result = subprocess.run(
                ["railway", "deployment", "list"],
                capture_output=True, text=True, timeout=30, shell=True,
            )
            for line in result.stdout.split("\n"):
                # Match lines with deployment status
                if id_prefix and id_prefix in line:
                    if "SUCCESS" in line:
                        elapsed = round(time.time() - start, 1)
                        return True, f"Build succeeded after {elapsed}s"
                    elif "FAILED" in line:
                        elapsed = round(time.time() - start, 1)
                        return False, f"Build FAILED after {elapsed}s"
                    # Still building — continue polling
                    break
                elif not id_prefix and ("SUCCESS" in line or "FAILED" in line):
                    # No deploy_id — check the first (most recent) deployment
                    if "SUCCESS" in line:
                        elapsed = round(time.time() - start, 1)
                        return True, f"Build succeeded after {elapsed}s"
                    elif "FAILED" in line:
                        elapsed = round(time.time() - start, 1)
                        return False, f"Build FAILED after {elapsed}s"
        except Exception as e:
            print(f"  [DEPLOY] Error checking build status: {e}")

        time.sleep(15)

    return False, f"Build timed out after {timeout}s"


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


def get_deploy_errors(deploy_id: str = "") -> str:
    """Capture Railway build AND runtime logs on failure.

    Checks build logs first (build/healthcheck failures), then runtime logs.
    Returns formatted error string for Qwen context.
    """
    sections = []

    # 1. Build logs (captures healthcheck failures, build errors)
    if deploy_id:
        try:
            result = subprocess.run(
                ["railway", "logs", "--build", deploy_id],
                capture_output=True, text=True, timeout=30, shell=True,
            )
            logs = result.stdout + result.stderr
            lines = logs.strip().split("\n")
            # Get last 30 lines of build log (healthcheck results are at the end)
            if len(lines) > 30:
                lines = lines[-30:]
            sections.append("--- Railway Build Logs ---\n" + "\n".join(lines))
        except FileNotFoundError:
            sections.append("Could not fetch build logs: 'railway' CLI not installed")
        except Exception as e:
            sections.append(f"Could not fetch build logs: {e}")

    # 2. Runtime logs (captures startup crashes, import errors)
    if deploy_id:
        try:
            result = subprocess.run(
                ["railway", "logs", "--deployment", deploy_id],
                capture_output=True, text=True, timeout=30, shell=True,
            )
            logs = result.stdout + result.stderr
            lines = logs.strip().split("\n")
            if len(lines) > 30:
                lines = lines[-30:]
            sections.append("--- Railway Runtime Logs ---\n" + "\n".join(lines))
        except Exception as e:
            sections.append(f"Could not fetch runtime logs: {e}")
    else:
        # Fallback: get latest logs without deploy ID
        try:
            result = subprocess.run(
                ["railway", "logs"],
                capture_output=True, text=True, timeout=30, shell=True,
            )
            logs = result.stdout + result.stderr
            lines = logs.strip().split("\n")
            if len(lines) > 50:
                lines = lines[-50:]
            sections.append("--- Railway Logs (latest) ---\n" + "\n".join(lines))
        except FileNotFoundError:
            sections.append("Could not fetch Railway logs: 'railway' CLI not installed")
        except Exception as e:
            sections.append(f"Could not fetch Railway logs: {e}")

    return "\n\n".join(sections)


def push_and_wait() -> tuple[bool, str]:
    """Full deploy pipeline: push → wait for build → verify health → return status.

    Returns (success, message). On failure, message includes error context
    from both build and runtime logs.
    """
    push_ok, push_output, deploy_id = push_to_remote()
    if not push_ok:
        error_logs = get_deploy_errors(deploy_id)
        return False, f"Deploy push failed:\n{push_output}\n\n{error_logs}"

    # Wait for build to complete (SUCCESS or FAILED) before health checking
    build_ok, build_status = _wait_for_build(deploy_id)
    if not build_ok:
        error_logs = get_deploy_errors(deploy_id)
        return False, f"Build failed: {build_status}\n\n{error_logs}"

    print(f"  [DEPLOY] {build_status}")

    # Build succeeded — verify health endpoint responds
    healthy, status = wait_for_deploy(timeout=60)
    if healthy:
        return True, status

    # Deploy failed — capture both build and runtime logs
    error_logs = get_deploy_errors(deploy_id)
    return False, f"Deploy unhealthy: {status}\n\n{error_logs}"
