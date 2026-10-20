"""The short course: explicit task identities, small actions, durable evidence.

The receipt pattern follows table-for-n/kitchen/{state,progress}.py: a chapter
is earned by records produced by a run, and remains earned after moving on.
Current state is always shown separately from those historical receipts.

This module coordinates the existing solution stages through ADK's HTTP API.
It does not replace the agent, invent tool results, or answer a person's
question automatically. The browser sends a typed answer to a specific
pending interrupt, never to an implicit "latest session".
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from workbench import config
from workbench.services import procs, stage, task

VERSION = 1
STAGES = {"meet": 1, "wake": 2, "remember": 3, "resume": 4, "buy": 5}
REQUEST = "Get me and Sam two tickets to the Amsterdam show."
WATCH_REQUEST = "Keep an eye on the Amsterdam Saturday show for me and Sam."
MEMORY_REQUEST = "Remember this for next time — we always want aisle seats."
_state_lock = threading.RLock()
_operation = threading.Lock()
_timers: dict[str, threading.Timer] = {}
_busy: dict[str, str] = {}


class LearningError(Exception):
    """An actionable failure, shown by the current action rather than 60 checks."""


def _file() -> Path:
    return config.RUNS / "learning.json"


def _read() -> dict:
    with _state_lock:
        if not _file().exists():
            return {"version": VERSION, "active": {}, "attempts": {}}
        try:
            data = json.loads(_file().read_text())
        except (OSError, ValueError) as exc:
            raise LearningError("Learning records could not be read; they were not overwritten.") from exc
        if data.get("version") != VERSION:
            raise LearningError("These learning records use a different version.")
        return data


def _write(data: dict) -> None:
    with _state_lock:
        config.RUNS.mkdir(exist_ok=True)
        temp = _file().with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2))
        temp.replace(_file())


def _save(attempt: dict) -> None:
    with _state_lock:
        data = _read()
        saved = data["attempts"].get(attempt["id"], {})
        # A status poll may earn a receipt while an action is returning. Never
        # let that action's earlier copy erase the immutable completed record.
        if saved.get("receipt") and not attempt.get("receipt"):
            attempt["receipt"] = copy.deepcopy(saved["receipt"])
        data["attempts"][attempt["id"]] = copy.deepcopy(attempt)
        _write(data)


def _active(slug: str) -> dict | None:
    data = _read()
    return data["attempts"].get(data["active"].get(slug))


def _json(url: str, body: dict | None = None, timeout: float = 12) -> Any:
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:700]
        raise LearningError(f"Service returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise LearningError("The service did not return a result. Check its log before trying again.") from exc


def _venue(path: str, body: dict | None = None) -> dict:
    value = _json(procs.origin("venue") + path, body)
    if not isinstance(value, dict) or value.get("error") or value.get("ok") is False:
        raise LearningError(f"The venue did not complete {path}.")
    return value


def _session(sid: str | None) -> dict | None:
    # Exact match: short prefixes and whichever session was active last are
    # intentionally not accepted for any guided action.
    return next((s for s in task.sessions()
                 if s["id"] == sid and s["app_name"] == "concert" and s["user_id"] == "user"), None)


def _new_session(attempt: dict) -> str:
    sid = f"lab-{attempt['slug']}-{uuid.uuid4().hex[:12]}"
    _json(procs.origin("agent") + f"/apps/concert/users/user/sessions/{sid}", {})
    attempt["sessions"].append(sid)
    _save(attempt)
    return sid


def _run(attempt: dict, text: str = "", *, answer: dict | None = None) -> list:
    sid = attempt["sessions"][-1]
    session = _session(sid)
    if session is None:
        raise LearningError("This experiment's session is missing. Prepare a new experiment.")
    pending = task.pending_of(session)
    if answer is None:
        if pending:
            raise LearningError("This task is paused. Answer its question or resume its queue wait.")
        parts = [{"text": text}]
    else:
        if not pending:
            raise LearningError("This question has already been answered. Refresh the task.")
        parts = [{"function_response": {
            "id": pending["id"], "name": "adk_request_input", "response": answer}}]
    events = _json(procs.origin("agent") + "/run", {
        "app_name": "concert", "user_id": "user", "session_id": sid,
        "new_message": {"role": "user", "parts": parts},
    }, timeout=240)
    if not isinstance(events, list):
        raise LearningError("ADK returned no event list. Open the agent log.")
    errors = [e.get("error_message") or e.get("errorMessage")
              for e in events if e.get("error_message") or e.get("errorMessage")]
    if errors:
        raise LearningError(str(errors[-1])[:700])
    attempt["last_said"] = task._said(events)[-3:]
    attempt["updated_at"] = time.time()
    _save(attempt)
    return events


def _responses(session: dict | None, name: str) -> list[dict]:
    return [p["function_response"] for e in (session or {}).get("events", [])
            for p in task._parts(e) if (p.get("function_response") or {}).get("name") == name]


def _invocations(session: dict | None) -> set[str]:
    return {e["invocation_id"] for e in (session or {}).get("events", [])
            if e.get("invocation_id")}


def _fingerprint() -> str:
    files = sorted((config.ROOT / "agent" / "concert").glob("*.py"))
    return hashlib.sha256(b"".join(p.name.encode() + p.read_bytes() for p in files)).hexdigest()[:16]


def _archive(attempt: dict) -> str:
    directory = config.RUNS / "learning-evidence"
    directory.mkdir(exist_ok=True)
    path = directory / f"{attempt['id']}.json"
    evidence = {"attempt": attempt, "sessions": [_session(s) for s in attempt["sessions"]],
                "memory": _memory()}
    # Do not overwrite an existing archive with missing sessions after a later
    # stage load has cleared the live DB.
    if any(evidence["sessions"]) or not path.exists():
        path.write_text(json.dumps(evidence, indent=2))
    return str(path.relative_to(config.ROOT))


def _memory() -> str:
    path = config.ROOT / "memory" / "userx.md"
    return path.read_text() if path.exists() else ""


def _check(key: str, label: str, passed: bool, detail: str, source: str) -> dict:
    return {"id": key, "label": label, "passed": bool(passed), "detail": detail, "source": source}


def evidence(attempt: dict, venue: dict | None) -> list[dict]:
    """Facts for THIS experiment only; never fill absent data with sample values."""
    slug = attempt["slug"]
    sessions = [_session(s) for s in attempt["sessions"]]
    first = sessions[0] if sessions else None
    current = sessions[-1] if sessions else None
    state = task.state_of(current) if current else {}
    source = f"Session DB · {current['id']}" if current else "Session DB · session missing"
    marks = attempt.get("marks", {})
    if slug == "meet":
        probe = marks.get("environment", {})
        return [_check("ready", "Model, agent and venue answered", bool(probe),
                       probe.get("reply", "Prepare the environment to check it."),
                       "ADK response + agent and venue health")]
    if slug == "wake":
        timer = marks.get("timer", {})
        after = len(_invocations(current))
        return [
            _check("request", "A request started one invocation", bool(marks.get("request")),
                   f"{after} invocation(s) recorded in this session.", source),
            _check("timer", "An external timer started the next invocation",
                   timer.get("state") == "fired" and after > timer.get("before", after),
                   f"Timer: {timer.get('state', 'not started')}; invocation count: {after}.",
                   "Workbench one-shot timer + session invocation IDs"),
        ]
    if slug == "remember":
        recalls = _responses(first, "recall")
        maps = _responses(first, "get_seatmap")
        written = marks.get("memory", {})
        second_recalls = _responses(current, "recall") if len(sessions) > 1 else []
        remembered = any("aisle" in json.dumps(r.get("response", {})).lower() for r in second_recalls)
        return [
            _check("session", "The first session recorded recall and a seat map",
                   bool(recalls and maps), f"{len((first or {}).get('events', []))} events in the first session.",
                   f"Session DB · {(first or {}).get('id', 'not created')}"),
            _check("memory", "remember() added a durable aisle preference",
                   bool(written.get("added")) and "aisle" in written.get("after", "").lower(),
                   "\n".join(written.get("added", [])) or "No new memory line observed.",
                   "remember response + memory/userx.md before/after"),
            _check("new-session", "A new session recalled that preference",
                   len(sessions) == 2 and remembered,
                   "Different session IDs; recall returned the saved preference." if remembered
                   else "Create the second session and inspect its recall response.", source),
        ]
    if slug == "resume":
        kill = marks.get("kill", {})
        ticket = state.get("queue_ticket")
        tickets = {((e.get("actions") or {}).get("state_delta") or {}).get("queue_ticket")
                   for e in (current or {}).get("events", [])}
        tickets.discard(None)
        answers = _responses(current, "adk_request_input")
        resumed = any(str(r.get("id", "")).startswith("queue:") for r in answers)
        live_tickets = [q for q in (venue or {}).get("queue", []) if q.get("ticket") == ticket]
        return [
            _check("killed", "The process stopped; the queue ticket stayed",
                   bool(kill.get("stopped") and kill.get("ticket")),
                   f"PID {kill.get('pid', '—')} stopped; ticket {kill.get('ticket', '—')} remained.",
                   "Process stop result + venue queue response at the time of kill"),
            _check("resumed", "The same session resumed with the same ticket",
                   resumed and len(tickets) == 1 and ticket == kill.get("ticket"),
                   f"{len(_invocations(current))} invocations; {len(tickets)} ticket identity.", source),
            _check("ready", "Ready to buy, with no order",
                   bool(state.get("ready_to_buy")) and len(live_tickets) == 1
                   and venue is not None and venue.get("order_count") == 0,
                   f"ready_to_buy={bool(state.get('ready_to_buy'))}; orders="
                   f"{(venue or {}).get('order_count', 'unavailable')}.",
                   f"{source} + venue /admin/state"),
        ]
    if slug == "buy":
        responses = _responses(current, "purchase")
        refusal = [r for r in responses if r.get("response", {}).get("reason") == "stale_plan"]
        successes = [r.get("response", {}) for r in responses
                     if r.get("response", {}).get("id") and not r.get("response", {}).get("error")]
        keys = {r.get("idempotency_key") for r in successes}
        # Include every requested purchase identity, even if a response was
        # lost. A second operation in this session must not escape the count.
        for event in (current or {}).get("events", []):
            for part in task._parts(event):
                call = part.get("function_call", {})
                args = call.get("args", {})
                if call.get("name") == "purchase" and all(k in args for k in ("event_id", "section", "seats")):
                    raw = f"{current['id']}:{args['event_id']}:{args['section']}:{args['seats']}"
                    keys.add(hashlib.sha256(raw.encode()).hexdigest()[:24])
        keys.discard(None)
        orders = [o for o in (venue or {}).get("orders", []) if o.get("idem_key") in keys]
        order_ids = {o["id"] for o in orders}
        successful_ids = {r["id"] for r in successes}
        auth = state.get("authorization") or {}
        retry = [r for r in successes if r.get("attempts") == 2 and r.get("duplicate") is True]
        purchase_ok = (len(orders) == 1 and order_ids == successful_ids
                       and int(orders[0].get("seats") or 0) == int(auth.get("seats") or -1)
                       and float(orders[0].get("unit_price") or 0) <= float(auth.get("per_seat_max") or -1))
        return [
            _check("authorized", "You confirmed the limit for this task", auth.get("confirmed") is True,
                   task.describe(auth) or "Waiting for your answer.", source),
            _check("guard", "The guard refused the stale plan before purchase", bool(refusal),
                   json.dumps(refusal[-1]["response"]) if refusal else "No stale_plan refusal observed yet.",
                   f"{source} · purchase function_response"),
            _check("retry", "The tool retried once with the same key", bool(retry),
                   f"attempts=2; key={retry[-1].get('idempotency_key')}; duplicate=true" if retry
                   else "No successful two-attempt response observed.",
                   f"{source} · purchase function_response"),
            _check("order", "Exactly one matching order, within your limit",
                   venue is not None and purchase_ok,
                   f"{len(orders)} matching order(s): " + ", ".join(sorted(order_ids))
                   if venue is not None else "Venue unavailable; order count is unknown.",
                   "Venue order ID / Idempotency-Key matched to this session's purchase calls"),
        ]
    return []


def _record_if_complete(attempt: dict, checks: list[dict]) -> None:
    if checks and all(c["passed"] for c in checks) and not attempt.get("receipt"):
        attempt["receipt"] = {
            "at": time.time(), "attempt_id": attempt["id"], "sessions": attempt["sessions"][:],
            "stage": attempt["stage"], "fingerprint": attempt["fingerprint"],
            "version": VERSION, "checks": checks,
        }
        attempt["receipt"]["archive"] = _archive(attempt)
        _save(attempt)


def _next(attempt: dict, info: dict, checks: list[dict], loaded: bool) -> str:
    if attempt.get("receipt"):
        return "complete"
    if not loaded:
        return "prepare"
    marks, slug = attempt["marks"], attempt["slug"]
    if info.get("session_id") is None:
        return "prepare"
    if slug != "resume" and not procs.answering("agent"):
        return "restart-service"
    if (info.get("pending") or {}).get("kind") == "person":
        return "answer"
    if slug == "meet":
        return "prepare"
    if not info.get("events"):
        return "request"
    if slug == "wake":
        timer = marks.get("timer", {})
        return "waiting" if timer.get("state") == "waiting" else "clock" if not timer else "inspect"
    if slug == "remember":
        if not marks.get("memory"):
            return "remember"
        return "new-session" if len(attempt["sessions"]) == 1 else "inspect"
    if slug == "resume":
        if not marks.get("kill"):
            return "kill" if info.get("paused") == "queue" else "inspect"
        if not procs.answering("agent"):
            return "restart"
        return "resume" if info.get("paused") == "queue" else "inspect"
    if slug == "buy":
        if info.get("last_order"):
            return "inspect"
        if info.get("paused") != "queue":
            return "inspect"
        return "resume" if marks.get("scenario", {}).get("ready") else "scenario"
    return "inspect"


def status(slug: str) -> dict:
    if slug not in STAGES:
        raise LearningError("Unknown guided chapter.")
    attempt = _active(slug)
    historical = [a["receipt"] for a in _read()["attempts"].values()
                  if a["slug"] == slug and a.get("receipt")]
    if not attempt:
        return {"slug": slug, "attempt": None, "task": None, "checks": [], "next": "prepare",
                "busy": _busy.get(slug), "receipt": None, "history": historical}
    timer = attempt["marks"].get("timer", {})
    if timer.get("state") == "waiting" and attempt["id"] not in _timers and slug not in _busy:
        timer["state"] = "interrupted"
        attempt["error"] = "The workbench restarted before the timer finished. Start the clock again."
        _save(attempt)
    loaded = stage.current() == attempt["stage"] and _fingerprint() == attempt["fingerprint"]
    session = _session(attempt["sessions"][-1]) if attempt["sessions"] else None
    info = task.summary(session) if session else {"session_id": None}
    venue = None
    try:
        venue = _venue("/admin/state")
    except LearningError:
        pass
    checks = evidence(attempt, venue) if loaded else []
    if loaded:
        _record_if_complete(attempt, checks)
    return {
        "slug": slug, "attempt": attempt, "task": info, "checks": checks,
        "next": _next(attempt, info, checks, loaded), "loaded": loaded,
        "busy": _busy.get(slug), "receipt": attempt.get("receipt"), "history": historical,
        "venue": {"up": venue is not None, "orders": (venue or {}).get("order_count"),
                  "ticket": next((q for q in (venue or {}).get("queue", [])
                                  if q.get("ticket") == info.get("queue_ticket")), None)},
    }


def progress() -> dict:
    data = _read()
    return {"version": VERSION, "chapters": {
        slug: [a["receipt"] for a in data["attempts"].values()
               if a["slug"] == slug and a.get("receipt")]
        for slug in STAGES}}


def _prepare(slug: str) -> dict:
    # Preserve records before use-solution intentionally replaces the live DB.
    for attempt in _read()["attempts"].values():
        if any(_session(s) for s in attempt["sessions"]):
            try:
                checks = evidence(attempt, _venue("/admin/state"))
                if _fingerprint() == attempt["fingerprint"]:
                    _record_if_complete(attempt, checks)
            except LearningError:
                pass
            _archive(attempt)
    for timer in _timers.values():
        timer.cancel()
    _timers.clear()
    if procs.status("agent")["state"] == "external":
        raise LearningError("The agent was started outside this workbench. Stop it in its terminal before preparing.")
    procs.start("venue")
    _venue("/admin/reset", {})  # Fail closed before loading if the venue cannot reset.
    result = stage.load(STAGES[slug], reset_venue=False)
    if not result["ok"] or not procs.answering("agent"):
        raise LearningError("The chapter could not start. Open the agent log for the error.")
    attempt = {"id": f"{slug}-{uuid.uuid4().hex[:12]}", "slug": slug, "stage": STAGES[slug],
               "fingerprint": _fingerprint(), "created_at": time.time(), "updated_at": time.time(),
               "sessions": [], "marks": {}, "last_said": [], "error": "",
               "preparation": result["output"], "memory_before": _memory()}
    with _state_lock:
        data = _read()
        data["active"][slug] = attempt["id"]
        data["attempts"][attempt["id"]] = attempt
        _write(data)
    _new_session(attempt)
    if slug == "meet":
        _run(attempt, "Say you are ready to help with concert tickets. Do not call tools.")
        if not attempt["last_said"]:
            raise LearningError("No model reply was recorded; inspect the agent log.")
        attempt["marks"]["environment"] = {"at": time.time(), "reply": attempt["last_said"][-1]}
        _save(attempt)
    return attempt


def _queue(attempt: dict) -> tuple[dict, dict]:
    session = _session(attempt["sessions"][-1])
    if not session:
        raise LearningError("The session is missing. Prepare a new experiment.")
    pending, state = task.pending_of(session), task.state_of(session)
    if not pending or pending["kind"] != "queue":
        raise LearningError("This task must be waiting in the queue first. Answer any open question.")
    if not state.get("queue_ticket"):
        raise LearningError("This task has no queue ticket.")
    queue = _venue("/queue/" + urllib.parse.quote(state["queue_ticket"], safe=""))
    if queue.get("ticket") != state["queue_ticket"]:
        raise LearningError("The venue no longer has this ticket. Prepare a new experiment.")
    return state, queue


def _scenario(attempt: dict) -> None:
    state, queue = _queue(attempt)
    if not (state.get("authorization") or {}).get("confirmed"):
        raise LearningError("Confirm this task's budget first.")
    if state.get("last_order"):
        raise LearningError("This task already bought tickets. Do not arm another purchase.")
    # Stop at the first failure. Resume is gated on ready=True; partial
    # setup can be retried and never causes a purchase by itself.
    mark = attempt["marks"].setdefault("scenario", {"steps": [], "ready": False})
    for name, path, body in [
        ("Section A sold out", "/admin/sellout", {"event_id": state["queue_event_id"], "section": "A"}),
        ("Commit-then-503 armed", "/admin/hang-once", {}),
        ("This ticket moved to the front", "/admin/advance-queue", {"ticket": state["queue_ticket"]}),
    ]:
        _venue(path, body)
        if name not in mark["steps"]:
            mark["steps"].append(name)
        _save(attempt)
    mark["ready"] = True
    mark["ticket"] = queue["ticket"]
    mark["at"] = time.time()
    _save(attempt)


def _timer_fire(attempt_id: str) -> None:
    if not _operation.acquire(blocking=False):
        attempt = _active("wake")
        if attempt and attempt["id"] == attempt_id:
            attempt["marks"]["timer"]["state"] = "blocked"
            attempt["error"] = "The timer found another operation running. Start the clock again."
            _save(attempt)
        return
    try:
        attempt = _active("wake")
        if not attempt or attempt["id"] != attempt_id or _fingerprint() != attempt["fingerprint"]:
            return
        _busy["wake"] = "clock"
        _run(attempt, "Check whether the Amsterdam shows still have seats, and tell me what you find.")
        attempt["marks"]["timer"].update(state="fired", fired_at=time.time())
        _save(attempt)
        status("wake")
    except LearningError as exc:
        if attempt:
            attempt["marks"]["timer"]["state"] = "failed"
            attempt["error"] = str(exc)
            _save(attempt)
    finally:
        _busy.pop("wake", None)
        _timers.pop(attempt_id, None)
        _operation.release()


def act(slug: str, action: str, payload: dict) -> dict:
    if slug not in STAGES:
        raise LearningError("Unknown guided chapter.")
    if not _operation.acquire(blocking=False):
        raise LearningError("Another experiment action is still running. Wait for its result.")
    _busy[slug] = action
    attempt = None
    try:
        if action == "prepare":
            current = _active(slug)
            if current and not payload.get("fresh"):
                raise LearningError("An experiment already exists. Use Start a fresh experiment to replace it.")
            attempt = _prepare(slug)
        else:
            attempt = _active(slug)
            if not attempt or payload.get("attempt_id") != attempt["id"]:
                raise LearningError("This page belongs to an older experiment. Refresh it before acting.")
            before = status(slug)
            if not before["loaded"]:
                raise LearningError("A different chapter is loaded. Prepare this chapter before continuing.")
            expected = before["next"]
            if action != expected and not (action == "clock" and expected == "inspect"
                                          and slug == "wake" and not attempt.get("receipt")):
                raise LearningError(f"The next action for this task is {expected}, not {action}.")
            attempt["error"] = ""
            _save(attempt)
            if action == "request":
                _run(attempt, WATCH_REQUEST if slug == "wake" else REQUEST)
                attempt["marks"]["request"] = {"at": time.time()}
            elif action == "answer":
                answer = str(payload.get("text") or "").strip()
                if not answer:
                    raise LearningError("Type your own answer to the current question.")
                session = _session(attempt["sessions"][-1])
                pending = task.pending_of(session)
                if not pending or pending["kind"] != "person" or payload.get("interrupt_id") != pending["id"]:
                    raise LearningError("That is not the current question. Refresh before answering.")
                _run(attempt, answer={"result": answer})
            elif action == "remember":
                before_memory = _memory()
                _run(attempt, MEMORY_REQUEST)
                after_memory = _memory()
                written = _responses(_session(attempt["sessions"][-1]), "remember")
                added = [line for line in after_memory.splitlines() if line and line not in before_memory.splitlines()]
                if not written or not added or "aisle" not in "\n".join(added).lower():
                    raise LearningError("No new aisle preference was written. Inspect the remember response.")
                attempt["marks"]["memory"] = {"at": time.time(), "before": before_memory,
                                              "after": after_memory, "added": added}
            elif action == "new-session":
                _new_session(attempt)
                _run(attempt, REQUEST)
            elif action == "kill":
                state, queue = _queue(attempt)
                process = procs.status("agent")
                if not process["pid"]:
                    raise LearningError("Start the agent from this workbench before the kill experiment.")
                result = procs.stop("agent", hard=True)
                after_queue = _venue("/queue/" + state["queue_ticket"])
                if result["state"] != "stopped" or after_queue.get("ticket") != queue["ticket"]:
                    raise LearningError("Could not verify both a stopped process and the surviving ticket.")
                attempt["marks"]["kill"] = {"at": time.time(), "pid": process["pid"], "stopped": True,
                                            "ticket": queue["ticket"], "position": after_queue.get("position")}
            elif action in ("restart", "restart-service"):
                procs.start("agent")
                if not procs.answering("agent"):
                    raise LearningError("The agent did not restart. Open its log.")
                attempt["marks"]["restart"] = {"at": time.time()}
            elif action == "scenario":
                _scenario(attempt)
            elif action == "resume":
                state, _ = _queue(attempt)
                if slug == "resume":
                    _venue("/admin/advance-queue", {"ticket": state["queue_ticket"]})
                elif not attempt["marks"].get("scenario", {}).get("ready"):
                    raise LearningError("Finish preparing the fault scenario first.")
                _run(attempt, answer={"checked": True})
                attempt["marks"]["resume"] = {"at": time.time()}
            elif action == "clock":
                old = _timers.pop(attempt["id"], None)
                if old:
                    old.cancel()
                attempt["marks"]["timer"] = {
                    "state": "waiting", "due_at": time.time() + 10,
                    "before": len(_invocations(_session(attempt["sessions"][-1]))),
                }
                timer = threading.Timer(10, _timer_fire, (attempt["id"],))
                timer.daemon = True
                _timers[attempt["id"]] = timer
                timer.start()
            else:
                raise LearningError("No action is available here; inspect the evidence.")
            _save(attempt)
        return {"ok": True, **status(slug)}
    except LearningError as exc:
        if attempt:
            attempt["error"] = str(exc)
            _save(attempt)
        raise
    finally:
        _busy.pop(slug, None)
        _operation.release()


def records(slug: str) -> dict:
    attempt = _active(slug)
    if not attempt:
        return {"sessions": [], "memory": _memory()}
    sessions = [_session(s) for s in attempt["sessions"]]
    memory, archived = _memory(), False
    if not any(sessions):
        path = config.RUNS / "learning-evidence" / f"{attempt['id']}.json"
        if path.exists():
            try:
                snapshot = json.loads(path.read_text())
                sessions, memory, archived = snapshot["sessions"], snapshot["memory"], True
            except (OSError, ValueError, KeyError) as exc:
                raise LearningError("The archived records could not be read.") from exc
    return {"attempt_id": attempt["id"], "sessions": sessions, "memory": memory,
            "archived": archived, "memory_change": attempt["marks"].get("memory"),
            "receipt": attempt.get("receipt")}


def shutdown() -> None:
    for timer in _timers.values():
        timer.cancel()
    _timers.clear()
