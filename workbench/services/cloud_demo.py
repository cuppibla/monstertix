"""Read a configured cloud task and dispatch its existing Scheduler job.

This never deploys or deletes resources. The default course ends with an
instructor demonstration; independent deployment remains in the study pages.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.parse

from workbench import config
from workbench.services import learning


def _settings() -> dict:
    env = config.workshop_env()
    return {"url": env.get("AGENT_SERVICE_URL", "").rstrip("/"),
            "project": env.get("PROJECT") or env.get("GOOGLE_CLOUD_PROJECT", ""),
            "region": env.get("REGION") or env.get("GOOGLE_CLOUD_REGION", "us-central1"),
            "job": env.get("PRESALE_TOPIC", "")}


def _path():
    return config.RUNS / "cloud-demo.json"


def _read() -> dict:
    if not _path().exists():
        return {}
    try:
        return json.loads(_path().read_text())
    except (OSError, ValueError) as exc:
        raise learning.LearningError("The saved cloud demonstration could not be read.") from exc


def _save(data: dict) -> None:
    temp = _path().with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2))
    temp.replace(_path())


def _task(settings: dict, sid: str) -> dict:
    if not settings["url"]:
        raise learning.LearningError("No AGENT_SERVICE_URL is configured. Use the instructor's prepared deployment or the optional deployment route.")
    info = learning._json(settings["url"] + "/task?session_id=" + urllib.parse.quote(sid, safe=""))
    if info.get("session_id") != sid or not info.get("updated"):
        raise learning.LearningError("That session does not exist in the configured cloud service.")
    return info


def status() -> dict:
    settings, demo = _settings(), _read()
    info, error = None, ""
    if demo.get("session_id") and settings["url"] == demo.get("url"):
        try:
            info = _task(settings, demo["session_id"])
        except learning.LearningError as exc:
            error = str(exc)
    return {"configured": bool(settings["url"]), "url": settings["url"],
            "demo": demo, "task": info, "error": error}


def act(action: str, payload: dict) -> dict:
    if not learning._operation.acquire(blocking=False):
        raise learning.LearningError("Another lab action is running. Wait for it to finish.")
    try:
        settings, demo = _settings(), _read()
        sid = str(payload.get("session_id") or demo.get("session_id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", sid):
            raise learning.LearningError("Enter the exact session ID shown on the cloud page.")
        info = _task(settings, sid)
        if action == "inspect":
            if demo.get("session_id") != sid or demo.get("url") != settings["url"]:
                demo = {"session_id": sid, "url": settings["url"]}
            demo.update(checked_at=time.time(), inspected_task=info)
        elif action == "dispatch":
            if demo.get("session_id") != sid or demo.get("url") != settings["url"]:
                raise learning.LearningError("Inspect this cloud task before triggering it.")
            if (info.get("pending") or {}).get("kind") != "queue":
                raise learning.LearningError("The cloud task must be waiting on the queue, not on a person.")
            if not (info.get("authorization") or {}).get("confirmed"):
                raise learning.LearningError("The cloud task needs the person's confirmed authorization.")
            latest = learning._json(settings["url"] + "/task")
            if latest.get("session_id") != sid:
                raise learning.LearningError("Another cloud session is more recent. This demo expects one active task; resolve it on the cloud page first.")
            job = settings["job"]
            env = config.workshop_env()
            if not job:
                account = subprocess.run(["gcloud", "config", "get-value", "account"],
                                         capture_output=True, text=True, timeout=15, env=env)
                if account.returncode:
                    raise learning.LearningError("Could not read the gcloud account. Set PRESALE_TOPIC to the existing Scheduler job.")
                who = re.sub(r"[^a-z0-9-]", "-", account.stdout.strip().split("@")[0].lower()).rstrip("-")[:24]
                job = f"presale-{who or 'student'}"
            command = ["gcloud", "scheduler", "jobs", "run", job,
                       "--location", settings["region"], "--project", settings["project"]]
            result = subprocess.run(command, capture_output=True, text=True, timeout=45, env=env)
            if result.returncode:
                raise learning.LearningError("Scheduler did not accept the dispatch: " + result.stderr[-600:])
            demo["dispatch"] = {"at": time.time(), "job": job, "before_invocations": info.get("invocations"),
                                "note": "Scheduler accepted the request. Inspect Cloud Run logs to verify the caller."}
        else:
            raise learning.LearningError("Unknown cloud demo action.")
        _save(demo)
        return {"ok": True, **status()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise learning.LearningError("gcloud did not finish. Check the Scheduler job before dispatching again.") from exc
    finally:
        learning._operation.release()
