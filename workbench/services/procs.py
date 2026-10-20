"""The workshop's processes: the venue, the agent, MonsterTix and the clock.

Each one is a separate process, started with the same command a student would
type in a terminal, and it can be stopped, or killed outright, from the page.
That matters more here than in most labs: step 6 kills the agent mid-run, and
the workbench has to survive it.

Process ids are written to runs/<name>.pid, so a workbench that restarts can
still stop what the previous one started. Output goes to runs/<name>.log,
which the services panel shows.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from workbench import config


@dataclass
class Service:
    name: str
    label: str
    port: int | None
    health: str | None                     # path that answers 200 when it is up
    argv: Callable[[], list[str]]          # built when started: flags depend on the step
    #: The path the page frames and the proxy forwards: /svc/<name>/
    framable: bool = True
    note: str = ""
    extra_env: Callable[[], dict[str, str]] = field(default=lambda: {})


def _python(*args: str) -> list[str]:
    return [config.python(), *args]


def _agent_argv() -> list[str]:
    # Both service URIs, always: every chapter's sessions live in the one
    # sessions.db at the root, which is what the checks, the task summary and
    # MonsterTix read, and every restart uses the same flags.
    argv = ["adk", "web", "agent", "--port", "8000", "--allow_origins", "*",
            f"--session_service_uri=sqlite+aiosqlite:///{config.ROOT}/sessions.db",
            f"--artifact_service_uri=file://{config.ROOT}/artifacts"]
    # The dev UI is framed through the workbench at /svc/agent/, and this is
    # how it learns where its own API is from there.
    argv += ["--url_prefix", "/svc/agent"]
    return argv


CLOCK = {"delay": 10.0, "every": 0.0, "trigger": False}


def _clock_argv() -> list[str]:
    argv = _python("-m", "monstertix.clock", "--in", f"{CLOCK['delay']:g}")
    if CLOCK["every"]:
        argv += ["--every", f"{CLOCK['every']:g}"]
    # Chapter 6's rehearsal: post to /trigger/wake, the scheduler's entrance,
    # which resumes a waiting task and never starts a conversation.
    if CLOCK["trigger"]:
        argv += ["--trigger"]
    return argv


SERVICES: dict[str, Service] = {
    "venue": Service("venue", "Venue", 8080, "/health", lambda: _python("-m", "venue"),
                     note="the ticket seller"),
    "agent": Service("agent", "Agent · adk web", 8000, "/list-apps", _agent_argv,
                     note="the ADK web UI"),
    "monstertix": Service("monstertix", "MonsterTix", 8090, "/health",
                          lambda: _python("-m", "monstertix.server"),
                          note="your own server and page"),
    "clock": Service("clock", "Clock", None, None, _clock_argv, framable=False,
                     note="calls /wake on a timer"),
}

_children: dict[str, subprocess.Popen] = {}
# Two clicks on a switch arrive as two requests. Without a lock each starts a
# process and only one pid is kept, leaving the other running unseen.
_locks = {name: threading.Lock() for name in SERVICES}
_notes: dict[str, str] = {}          # what last happened, shown under the row


def _log(name: str):
    return config.RUNS / f"{name}.log"


def _pidfile(name: str):
    return config.RUNS / f"{name}.pid"


def _recorded_pid(name: str) -> int | None:
    child = _children.get(name)
    if child is not None and child.poll() is None:
        return child.pid
    try:
        pid = int(_pidfile(name).read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    # A pid can be reused. Only claim it if it is still one of ours.
    try:
        command = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return pid
    return pid if str(config.ROOT) in command or "adk" in command or "monstertix" in command or "venue" in command else None


def remote_venue() -> str:
    """The venue's URL when it is not on this machine: Cloud Run, usually."""
    url = config.venue_url()
    return "" if (not url or "127.0.0.1" in url or "localhost" in url) else url


def origin(name: str) -> str:
    if name == "venue" and remote_venue():
        return remote_venue()
    service = SERVICES[name]
    return f"http://127.0.0.1:{service.port}"


def answering(name: str) -> bool:
    service = SERVICES[name]
    if not service.health:
        return False
    try:
        with urllib.request.urlopen(origin(name) + service.health, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def status(name: str) -> dict[str, Any]:
    service = SERVICES[name]
    pid = _recorded_pid(name)
    remote = name == "venue" and bool(remote_venue())
    up = answering(name) if service.health else pid is not None
    if remote:
        state = "remote" if up else "unreachable"
    elif up and pid is None:
        state = "external"          # someone started it in a terminal
    elif up:
        state = "running"
    elif pid is not None:
        state = "starting"          # alive, not answering yet
    else:
        state = "stopped"
    return {
        "name": name,
        "label": service.label,
        "note": service.note,
        "port": service.port,
        "state": state,
        "pid": pid,
        "remote": remote_venue() if remote else "",
        "url": f"/svc/{name}/" if service.framable else "",
        "command": " ".join(_display(service.argv())),
        "last": _notes.get(name, ""),
    }


def _display(argv: list[str]) -> list[str]:
    shown = []
    for arg in argv:
        if arg == config.python():
            arg = "python"
        arg = arg.replace(str(config.ROOT), "$WORKSHOP")
        shown.append(f'"{arg}"' if arg == "*" else arg)
    return shown


def all_status() -> list[dict[str, Any]]:
    return [status(name) for name in SERVICES]


def start(name: str) -> dict[str, Any]:
    with _locks[name]:
        return _start(name)


def _start(name: str) -> dict[str, Any]:
    service = SERVICES[name]
    if name == "venue" and remote_venue():
        return {**status(name), "detail": "the venue runs on Cloud Run"}
    if _recorded_pid(name) is not None or (service.health and answering(name)):
        return {**status(name), "detail": "already running"}

    log = open(_log(name), "a", encoding="utf-8")
    argv = service.argv()
    log.write(f"\n$ {' '.join(_display(argv))}\n")
    log.flush()
    env = {**config.workshop_env(), **service.extra_env()}
    if name == "venue":
        env["VENUE_URL"] = "http://127.0.0.1:8080"
    # No terminal on stdin: a child that would ask a question (adk's
    # telemetry prompt on a tty) must not sit waiting for an answer nobody can give.
    child = subprocess.Popen(argv, cwd=config.ROOT, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, env=env, start_new_session=True)
    _children[name] = child
    _pidfile(name).write_text(str(child.pid))
    # Kept after it stops: checks ask "since the agent last started".
    (config.RUNS / f"{name}.started").write_text(f"{time.time():.3f}")
    _notes[name] = ""

    if service.health:
        for _ in range(60):          # adk web takes a few seconds to import
            if answering(name):
                break
            try:
                child.wait(timeout=0.25)
                break                # it exited; the log says why
            except subprocess.TimeoutExpired:
                continue
    if child.poll() is not None and name != "clock":
        _notes[name] = f"exited with code {child.returncode}"
    return {**status(name), "detail": "started" if child.poll() is None else "exited"}


def _signal_group(pid: int, sig: int) -> None:
    try:
        os.killpg(os.getpgid(pid), sig)
    except OSError:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    child = next((c for c in _children.values() if c.pid == pid), None)
    return child is not None and child.poll() is not None


def stop(name: str, hard: bool = False) -> dict[str, Any]:
    """Ctrl-C, or with hard=True, kill -9: no shutdown hooks, no flush."""
    with _locks[name]:
        return _stop(name, hard)


def _stop(name: str, hard: bool) -> dict[str, Any]:
    pid = _recorded_pid(name)
    if pid is None:
        state = status(name)["state"]
        detail = "started outside the workbench; stop it in its terminal" if state == "external" else "was not running"
        return {**status(name), "detail": detail}
    if hard:
        _signal_group(pid, signal.SIGKILL)
        _notes[name] = "killed with SIGKILL"
        with open(_log(name), "a", encoding="utf-8") as log:
            log.write("\n[workbench] kill -9: the process got no chance to clean up\n")
    else:
        _signal_group(pid, signal.SIGINT)
        for _ in range(24):
            if _gone(pid):
                break
            time.sleep(0.25)
        else:
            _signal_group(pid, signal.SIGKILL)
        _notes[name] = "stopped"
    for _ in range(20):
        if _gone(pid):
            break
        time.sleep(0.1)
    child = _children.pop(name, None)
    if child is not None:
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
    _pidfile(name).unlink(missing_ok=True)
    return {**status(name), "detail": _notes[name]}


def restart(name: str) -> dict[str, Any]:
    stop(name)
    return start(name)


def read_log(name: str, limit: int = 16000) -> str:
    path = _log(name)
    return path.read_text(errors="replace")[-limit:] if path.exists() else ""


def clear_log(name: str) -> None:
    _log(name).write_text("")


def stop_all() -> None:
    for name in SERVICES:
        if _recorded_pid(name) is not None:
            stop(name)
