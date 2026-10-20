"""Paths, ports, and the environment every process the workbench starts runs in."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
STEPS = CONTENT / "steps"
SOLUTIONS = ROOT / "solutions"
WEB_DIST = ROOT / "web" / "dist"
RUNS = ROOT / "runs"

PORT = int(os.environ.get("WORKBENCH_PORT", "4800"))
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8000"))
VENUE_PORT = int(os.environ.get("VENUE_PORT", "8080"))
TRIGGER_PORT = int(os.environ.get("TRIGGER_PORT", "8090"))
DEFAULT_LANG = "en"

RUNS.mkdir(exist_ok=True)


SHELL_WINS = ("VENUE_URL", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_REGION",
              "GOOGLE_CLOUD_LOCATION", "ADK_MODEL")


def _dotenv() -> dict[str, str]:
    """.env as a dict. Read on every call, so a value setup.sh writes later
    (VENUE_URL after the venue deploys) reaches the next process started."""
    path = ROOT / ".env"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def workshop_env() -> dict[str, str]:
    """What `. ./set_env.sh` gives a terminal, so a process started here
    behaves exactly like one a student starts by hand."""
    env = dict(os.environ)
    env.update(_dotenv())
    # As in set_env.sh: an export made in the shell beats a line .env remembers.
    for key in SHELL_WINS:
        if os.environ.get(key):
            env[key] = os.environ[key]
    venv = ROOT / ".venv" / "bin"
    env["PATH"] = f"{venv}{os.pathsep}{env.get('PATH', '')}"
    env["VIRTUAL_ENV"] = str(ROOT / ".venv")
    env["WORKSHOP"] = str(ROOT)
    env.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    env.setdefault("GOOGLE_CLOUD_REGION", "us-central1")
    env.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    env.setdefault("ADK_MODEL", "gemini-2.5-flash")
    if not env.get("GOOGLE_CLOUD_PROJECT"):
        project = Path.home() / "project_id.txt"
        if project.exists():
            env["GOOGLE_CLOUD_PROJECT"] = project.read_text().strip()
    env["AGENT_URL"] = env.get("AGENT_URL") or f"http://127.0.0.1:{AGENT_PORT}"
    # No venue named means the one the workbench runs on :8080 (`. ./set_env.sh local`).
    env["VENUE_URL"] = (env.get("VENUE_URL") or f"http://127.0.0.1:{VENUE_PORT}").rstrip("/")
    env["MEMORY_DIR"] = str(ROOT / "memory")
    env["MEMORY_USER"] = "userx"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def python() -> str:
    """The workshop's interpreter: .venv's when there is one."""
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def venue_url() -> str:
    """Where the venue is. Empty means nobody has said, and then the
    workbench runs one locally on :8080."""
    return (workshop_env().get("VENUE_URL") or "").rstrip("/")
