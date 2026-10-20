"""Read-only cloud configuration and health checks. Never provisions resources."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def settings():
    # Like the deploy scripts, saved cloud settings override local workbench URLs.
    env = dict(os.environ)
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            tokens = shlex.split(value, comments=True)
            env[key.strip()] = tokens[0] if tokens else ""
    return env


def remote_url(value):
    parsed = urllib.parse.urlparse(value)
    return (parsed.scheme == "https" and bool(parsed.hostname)
            and parsed.hostname not in {"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def get_health(url):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=30) as response:
            result = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise ValueError(f"Health request failed ({type(exc).__name__}). No success was verified.") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError("Health response did not contain ok: true.")
    return result


def check(env):
    errors = []
    if not env.get("GOOGLE_CLOUD_PROJECT"):
        errors.append("No project configured. Run ./setup.sh first.")
    if not remote_url(env.get("VENUE_URL", "")):
        errors.append("VENUE_URL is missing or local. Run ./deploy-venue.sh first.")
    uri = env.get("CLOUD_SESSION_SERVICE_URI", "")
    conn = env.get("SQL_CONNECTION_NAME", "")
    bucket = env.get("STATE_BUCKET", "")
    if not (uri.startswith("postgresql+asyncpg://") and conn
            and f"host=/cloudsql/{conn}" in uri
            and bucket.startswith("gs://") and len(bucket) > 5
            and env.get("CLOUD_ARTIFACT_SERVICE_URI") == bucket.rstrip("/") + "/artifacts"):
        errors.append("Durable storage is incomplete. Run ./setup-cloud-state.sh first.")
    if not (ROOT / "agent/main.py").is_file():
        errors.append("Load chapter 6 before deploying the agent.")
    if errors:
        raise ValueError("\n".join(errors))
    get_health(env["VENUE_URL"])
    print("✓ Cloud configuration is complete and the cloud Venue answers.")
    print("  This checks prerequisites, not a completed Agent deployment.")


def health(env):
    url = env.get("AGENT_SERVICE_URL", "")
    if not remote_url(url):
        raise ValueError("No cloud AGENT_SERVICE_URL. Finish ./deploy-agent.sh first.")
    result = get_health(url)
    if result.get("app") != "concert" or "/cloudsql/" not in result.get("sessions", ""):
        raise ValueError("The service is not the expected concert agent with Cloud SQL.")
    if not result.get("memory", "").startswith("gs://"):
        raise ValueError("The service is not using cloud memory.")
    if result.get("venue", "").rstrip("/") != env.get("VENUE_URL", "").rstrip("/"):
        raise ValueError("The agent points at a different venue. Redeploy after fixing VENUE_URL.")
    get_health(result["venue"])
    # /task exercises the Session Service, unlike the configuration-only /health.
    try:
        with urllib.request.urlopen(url + "/task", timeout=30) as response:
            task = json.load(response)
        if not isinstance(task, dict) or "session_id" not in task:
            raise ValueError()
    except (OSError, ValueError, urllib.error.URLError):
        raise ValueError("The agent answered /health but could not read its session store via /task.") from None
    print(json.dumps(result, indent=2))
    print("✓ Agent, session-store read, and cloud Venue checks passed.")
    print("  A purchase and Scheduler delivery still need the hands-on test in 6b.")


def main():
    env = settings()
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "check":
        check(env)
    elif mode == "health":
        health(env)
    elif mode == "urls":
        for key, suffix in (("AGENT_SERVICE_URL", ""), ("VENUE_URL", "/panel")):
            if not remote_url(env.get(key, "")):
                raise ValueError(f"{key} is missing or local. Complete 6a first.")
            print(f"{key}: {env[key].rstrip('/')}{suffix}")
    else:
        raise ValueError("Use check, health, or urls.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        sys.exit(1)
