"""The workbench API. Nothing here holds a student's progress: every answer is
read from the world (which step is loaded, what the session store says, what
the venue sold), so a reload or a restart loses nothing."""

from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from workbench import config
from workbench.services import checks, cloud_demo, content, jobs, learning, procs, prompts, stage, task, workspace

router = APIRouter(prefix="/api")

@router.get("/cloud-demo")
async def cloud_demo_status() -> dict:
    try:
        return await asyncio.to_thread(cloud_demo.status)
    except learning.LearningError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/cloud-demo/{action}")
async def cloud_demo_action(action: str, payload: dict = Body(default={})) -> dict:
    try:
        return await asyncio.to_thread(cloud_demo.act, action, payload)
    except learning.LearningError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/learning/progress")
def learning_progress() -> dict:
    try:
        return learning.progress()
    except learning.LearningError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/learning/{slug}")
async def learning_status(slug: str) -> dict:
    try:
        return await asyncio.to_thread(learning.status, slug)
    except learning.LearningError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/learning/{slug}/records")
async def learning_records(slug: str) -> dict:
    try:
        return await asyncio.to_thread(learning.records, slug)
    except learning.LearningError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/learning/{slug}/{action}")
async def learning_action(slug: str, action: str, payload: dict = Body(default={})) -> dict:
    try:
        return await asyncio.to_thread(learning.act, slug, action, payload)
    except learning.LearningError as exc:
        raise HTTPException(409, str(exc)) from exc


# ── the course ───────────────────────────────────────────────────────────────

@router.get("/course")
def get_course(lang: str = "") -> dict[str, Any]:
    lang = content.clean(lang)
    return {"course": content.course(lang), "steps": content.all_steps(lang),
            "languages": content.languages(), "lang": lang}


@router.get("/steps/{slug}")
def get_step(slug: str, lang: str = "") -> dict[str, Any]:
    found = content.step(slug, content.clean(lang))
    if not found:
        raise HTTPException(404, f"no step named {slug}")
    return found


@router.post("/check/{slug}")
async def run_checks(slug: str, part: str | None = None) -> dict[str, Any]:
    specs = content.checks(slug, part)
    results = await asyncio.gather(*(asyncio.to_thread(checks.evaluate, s) for s in specs))
    for result in results:
        result["command"] = checks.display(result["command"])
    return {"results": list(results)}


# ── the processes ────────────────────────────────────────────────────────────

@router.get("/services")
async def services() -> dict[str, Any]:
    listed = await asyncio.to_thread(procs.all_status)
    return {"services": listed, "stage": await asyncio.to_thread(stage.detect)}


ACTIONS = {"start", "stop", "kill", "restart"}


@router.post("/services/{name}/{action}")
async def service_action(name: str, action: str, settings: dict = Body(default={})) -> dict[str, Any]:
    if name not in procs.SERVICES or action not in ACTIONS:
        raise HTTPException(404, "unknown service or action")
    if name == "clock" and action in ("start", "restart"):
        procs.CLOCK["delay"] = float(settings.get("delay", procs.CLOCK["delay"]))
        procs.CLOCK["every"] = float(settings.get("every", 0) or 0)
        procs.CLOCK["trigger"] = bool(settings.get("trigger", False))
    if action == "start":
        return await asyncio.to_thread(procs.start, name)
    if action == "stop":
        return await asyncio.to_thread(procs.stop, name)
    if action == "kill":
        return await asyncio.to_thread(procs.stop, name, True)
    return await asyncio.to_thread(procs.restart, name)


@router.get("/services/{name}/log")
def service_log(name: str) -> dict[str, Any]:
    if name not in procs.SERVICES:
        raise HTTPException(404, "unknown service")
    return {"log": procs.read_log(name)}


# ── the steps' code ──────────────────────────────────────────────────────────

@router.get("/stage")
def stage_status() -> dict[str, Any]:
    return {**stage.detect(), "steps": list(stage.steps())}


@router.get("/stage/changes")
def stage_changes(since: int, to: int) -> dict[str, Any]:
    return stage.changes(since, to)


@router.post("/stage")
async def stage_load(step: int = Body(..., embed=True),
                     resetVenue: bool = Body(True, embed=True),
                     scope: str = Body("all", embed=True)) -> dict[str, Any]:
    """Load a step's code. `scope: "venue"` only resets the venue: the code,
    the sessions, the memory file and every process stay as they are."""
    if scope not in ("all", "venue"):
        raise HTTPException(400, "scope is 'all' or 'venue'")
    return await asyncio.to_thread(stage.load, step, resetVenue, scope)


# ── the current task ─────────────────────────────────────────────────────────

@router.get("/task")
async def task_current(session_id: str | None = None) -> dict[str, Any]:
    """The newest session, read from the store: paused on what, ticket, authorization, order."""
    return await asyncio.to_thread(task.current, session_id)


@router.post("/task/resume")
async def task_resume(payload: dict = Body(default={})) -> dict[str, Any]:
    """Answer the current task's queue wait. A wait on a person is refused."""
    return await asyncio.to_thread(task.resume, payload.get("session_id") or None)


# ── the venue's buttons ──────────────────────────────────────────────────────

VENUE = {"reset", "advance-queue", "sellout", "hang-once", "clock"}


@router.get("/venue/state")
def venue_state() -> dict[str, Any]:
    """What the venue buttons need to know: is anyone in line, and how many orders."""
    try:
        with urllib.request.urlopen(f"{procs.origin('venue')}/admin/state", timeout=5) as response:
            state = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return {"up": False, "queue": 0, "orders": 0}
    return {"up": True, "queue": len(state.get("queue") or []), "orders": len(state.get("orders") or [])}


@router.post("/venue/{action}")
def venue(action: str, payload: dict = Body(default={})) -> dict[str, Any]:
    """The same POST the panel's buttons make."""
    if action not in VENUE:
        raise HTTPException(404, "not a venue button")
    request = urllib.request.Request(f"{procs.origin('venue')}/admin/{action}",
                                     data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {"ok": True, "result": json.loads(response.read() or b"{}")}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return {"ok": False, "error": str(error)}


# ── one-off commands from a step ─────────────────────────────────────────────

def _command(slug: str, task_id: str, index: int) -> str:
    task = content.task(slug, task_id)
    items = (task or {}).get("items") or []
    if not task or not 0 <= index < len(items) or not items[index].get("run"):
        raise HTTPException(404, "no such command in this step")
    return items[index]["run"]


@router.post("/jobs/{slug}/{task_id}/{index}")
def job_start(slug: str, task_id: str, index: int) -> dict[str, Any]:
    return jobs.start(f"{slug}/{task_id}/{index}", _command(slug, task_id, index))


@router.get("/jobs/{slug}/{task_id}/{index}")
def job_status(slug: str, task_id: str, index: int) -> dict[str, Any]:
    _command(slug, task_id, index)
    return jobs.status(f"{slug}/{task_id}/{index}") or {"state": "idle", "log": ""}


# ── step 2's prompt lab ──────────────────────────────────────────────────────

def _prompt_task(slug: str, task_id: str) -> dict[str, Any]:
    task = content.task(slug, task_id)
    if not task or task.get("kind") != "prompts" or not task.get("file"):
        raise HTTPException(404, "no prompt lab in this step")
    return task


@router.get("/prompts/{slug}/{task_id}")
def prompt_lab(slug: str, task_id: str) -> dict[str, Any]:
    task = _prompt_task(slug, task_id)
    try:
        now = prompts.current(task["file"])
    except prompts.PromptError as error:
        now = {"text": "", "using": False, "error": str(error)}
    return {**now, "tries": prompts.results()}


@router.post("/prompts/{slug}/{task_id}")
async def prompt_swap(slug: str, task_id: str, text: str = Body(..., embed=True),
                      label: str = Body("", embed=True)) -> dict[str, Any]:
    task = _prompt_task(slug, task_id)
    try:
        return await asyncio.to_thread(prompts.swap, task["file"], text, label)
    except prompts.PromptError as error:
        return {"ok": False, "error": str(error)}


@router.post("/prompts/{slug}/{task_id}/restore")
async def prompt_restore(slug: str, task_id: str) -> dict[str, Any]:
    task = _prompt_task(slug, task_id)
    if not task.get("original"):
        raise HTTPException(404, "this prompt lab names no original to restore")
    return await asyncio.to_thread(prompts.restore, task["file"], task["original"])


# ── :::terminal blocks in the reading ────────────────────────────────────────

TERMINAL = re.compile(r"^:::terminal[^\n]*\n(.*?)\n:::\s*$", re.M | re.S)


def split_commands(block: str) -> list[str]:
    """One command per line; a line ending in a backslash continues on the next."""
    commands, current = [], []
    for line in block.strip().splitlines():
        if not line.strip() and not current:
            continue
        current.append(line)
        if not line.rstrip().endswith("\\"):
            commands.append("\n".join(current).strip())
            current = []
    if current:
        commands.append("\n".join(current).strip())
    return commands


def _terminal_commands(slug: str) -> set[str]:
    found = content.step(slug, config.DEFAULT_LANG)
    if not found:
        return set()
    return {command for part in found["parts"] for m in TERMINAL.finditer(part.get("body", ""))
            for command in split_commands(m.group(1))}


@router.post("/terminal/{slug}")
async def terminal(slug: str, command: str = Body(..., embed=True)) -> dict[str, Any]:
    """Run a command the step's reading shows in a :::terminal block, from the
    workshop folder, as a terminal would. Only those commands: the page names
    one, the server finds it in the content."""
    command = command.strip()
    if command not in _terminal_commands(slug):
        raise HTTPException(404, "that command is not in this step")

    def run() -> dict[str, Any]:
        import subprocess
        try:
            done = subprocess.run(["bash", "-c", command], cwd=config.ROOT, capture_output=True,
                                  text=True, timeout=30, env=config.workshop_env())
        except subprocess.TimeoutExpired:
            return {"code": 124, "output": "timed out after 30 seconds"}
        return {"code": done.returncode, "output": (done.stdout + done.stderr).rstrip("\n")}

    return await asyncio.to_thread(run)


# ── files ────────────────────────────────────────────────────────────────────

@router.get("/files/tree")
def files_tree(start: str = "", depth: int = 4, stage: int | None = None) -> dict[str, Any]:
    if stage is not None:
        return workspace.stage_tree(stage, start)
    try:
        return workspace.tree(start, depth)
    except workspace.Outside:
        raise HTTPException(400, "outside the project")


@router.get("/files/read")
def files_read(path: str, stage: int | None = None) -> dict[str, Any]:
    if stage is not None:
        return workspace.stage_read(stage, path)
    try:
        return workspace.read(path)
    except workspace.Outside:
        raise HTTPException(400, "outside the project")


@router.get("/env")
def env() -> dict[str, Any]:
    values = config.workshop_env()
    return {"project": values.get("GOOGLE_CLOUD_PROJECT", ""), "model": values.get("ADK_MODEL", ""),
            "venue": procs.origin("venue"), "remoteVenue": bool(procs.remote_venue())}
