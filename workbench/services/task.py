"""The current task: what the newest session is doing, and resuming it.

The course is one task from start to finish (two tickets in Amsterdam), and
the page keeps a short read-only summary of it: which session it is, whether
it is paused and on what, the queue ticket, the authorization, the order.
Everything here is read straight from the session stores, so a page reload, a
workbench restart or a killed agent changes nothing.

    current()   -> the summary (same fields as monstertix.handlers.task_summary,
                   plus where it was read from)
    resume()    -> answer a queue wait, and only a queue wait

Two session stores are read, the same two `workbench.probe` reads: sessions.db
at the root, and any agent/*/.adk/session.db left behind by an `adk web` that
was given no --session_service_uri. The seeded `two-days-ago` conversation is
never the current task.

Resuming goes through `adk web`'s own API (POST /run) with a function_response
for the pending `adk_request_input`, which is exactly what the dev UI's answer
box sends, so the run continues inside the same session. When adk web is not
running, MonsterTix's POST /wake does the same from its own Runner.
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from workbench import config

SEEDED = "two-days-ago"
APP_NAME = "concert"
ADK_WEB = "http://127.0.0.1:8000"
MONSTERTIX = "http://127.0.0.1:8090"

# Interrupt ids the course's workflow uses (concert/nightly.py).
QUEUE_PREFIX = "queue:"
PERSON_PREFIX = "budget:"

STATE_KEYS = ("queue_ticket", "queue_event_id", "plan", "authorization", "ready_to_buy", "last_order")


# ── reading the stores ───────────────────────────────────────────────────────

def stores() -> list[Path]:
    found = [config.ROOT / "sessions.db"]
    found += sorted((config.ROOT / "agent").glob("*/.adk/session.db"))
    return [p for p in found if p.exists()]


def _rows(store: Path, sql: str, args: tuple = ()) -> Iterable[sqlite3.Row]:
    try:
        connection = sqlite3.connect(f"file:{store}?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            yield from connection.execute(sql, args)
        finally:
            connection.close()
    except sqlite3.Error:
        return


def _json(text: Any) -> dict[str, Any]:
    if isinstance(text, dict):
        return text
    try:
        value = json.loads(text or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _events_of(store: Path, session_id: str) -> list[dict[str, Any]]:
    out = []
    for row in _rows(store, "SELECT event_data FROM events WHERE session_id = ?", (session_id,)):
        data = _json(row["event_data"])
        if data:
            out.append(data)
    out.sort(key=lambda e: e.get("timestamp") or 0)
    return out


def sessions() -> list[dict[str, Any]]:
    """Every session in every store, with its events, newest activity first."""
    found = []
    for store in stores():
        for row in _rows(store, "SELECT app_name, user_id, id, state FROM sessions"):
            if row["id"] == SEEDED:
                continue
            events = _events_of(store, row["id"])
            found.append({
                "store": store.name if store.parent == config.ROOT else str(store.relative_to(config.ROOT)),
                "app_name": row["app_name"],
                "user_id": row["user_id"],
                "id": row["id"],
                "stored_state": _json(row["state"]),
                "events": events,
                "updated": max((e.get("timestamp") or 0 for e in events), default=0),
            })
    found.sort(key=lambda s: s["updated"], reverse=True)
    return found


def find(session_id: str | None = None) -> dict[str, Any] | None:
    """The newest session that has events, or the one asked for (by id or prefix)."""
    for session in sessions():
        if session_id:
            if session["id"] == session_id or session["id"].startswith(session_id):
                return session
        elif session["events"]:
            return session
    return None


# ── what a session says ──────────────────────────────────────────────────────

def _parts(event: dict[str, Any]) -> list[dict[str, Any]]:
    return ((event.get("content") or {}).get("parts")) or []


def state_of(session: dict[str, Any]) -> dict[str, Any]:
    """Session state: the stored column, then every delta the events recorded,
    latest wins. `temp:` keys never persist and are skipped."""
    state = {k: v for k, v in session["stored_state"].items() if not k.startswith("temp:")}
    for event in session["events"]:
        for key, value in ((event.get("actions") or {}).get("state_delta") or {}).items():
            if not key.startswith("temp:"):
                state[key] = value
    return state


def kind_of(interrupt_id: str) -> str:
    if interrupt_id.startswith(QUEUE_PREFIX):
        return "queue"
    if interrupt_id.startswith(PERSON_PREFIX):
        return "person"
    return "other"


def pending_of(session: dict[str, Any]) -> dict[str, str] | None:
    """The newest `adk_request_input` nobody has answered: {id, kind, message}."""
    answered = set()
    for event in reversed(session["events"]):
        for part in _parts(event):
            response = part.get("function_response") or {}
            if response.get("name") == "adk_request_input":
                answered.add(response.get("id"))
        for part in _parts(event):
            call = part.get("function_call") or {}
            if call.get("name") == "adk_request_input" and call.get("id") not in answered:
                return {"id": call["id"], "kind": kind_of(call["id"]),
                        "message": str((call.get("args") or {}).get("message") or "")}
    return None


def describe(auth: Any) -> str:
    """`budget.describe` without importing the student's code: it may not be loaded yet."""
    if not isinstance(auth, dict):
        return ""
    seats, cap = auth.get("seats"), auth.get("per_seat_max")
    text = ""
    if seats is not None and cap is not None:
        try:
            text = f"{int(seats)} seat{'s' if int(seats) != 1 else ''}, up to ${float(cap):g} each"
        except (TypeError, ValueError):
            text = str(auth.get("text") or "")
    else:
        text = str(auth.get("text") or "")
    if auth.get("confirmed"):
        stamp = auth.get("confirmed_at")
        when = ""
        if isinstance(stamp, (int, float)):
            when = time.strftime("%H:%M", time.localtime(stamp))
        elif isinstance(stamp, str):
            when = stamp[11:16] if len(stamp) >= 16 and stamp[10] in "T " else stamp
        text += f" (confirmed{' ' + when if when else ''})"
    return text


def summary(session: dict[str, Any]) -> dict[str, Any]:
    state = state_of(session)
    pending = pending_of(session)
    paused = {"queue": "queue", "person": "you"}.get(pending["kind"], "other") if pending else None
    last_order = state.get("last_order")
    if pending and pending["kind"] == "queue":
        label = "waiting in the queue"
    elif pending and pending["kind"] == "person":
        label = "waiting for you"
    elif pending:
        label = "waiting"
    elif isinstance(last_order, dict) and (last_order.get("order_id") or last_order.get("id")):
        label = f"done · order {last_order.get('order_id') or last_order.get('id')}"
    elif isinstance(last_order, str) and last_order:
        label = f"done · order {last_order}"
    elif last_order:
        label = "done · order placed"
    elif state.get("ready_to_buy"):
        label = "ready to buy"
    else:
        label = "running" if session["events"] else "new"
    events = session["events"]
    return {
        "session_id": session["id"],
        "user_id": session["user_id"],
        "app_name": session["app_name"],
        "store": session["store"],
        "pending": {"id": pending["id"], "kind": pending["kind"]} if pending else None,
        "pending_message": pending["message"] if pending else "",
        "paused": paused,
        "kind_label": label,
        **{key: state.get(key) for key in STATE_KEYS},
        "authorization_text": describe(state.get("authorization")),
        "invocations": len({e.get("invocation_id") for e in events if e.get("invocation_id")}),
        "started": min((e.get("timestamp") or 0 for e in events), default=0),
        "updated": session["updated"],
        "events": len(events),
    }


def current(session_id: str | None = None) -> dict[str, Any]:
    session = find(session_id)
    if session is None:
        return {"session_id": None, "pending": None, "paused": None, "kind_label": "no task yet",
                "store": "", "user_id": "", "app_name": APP_NAME,
                **{key: None for key in STATE_KEYS}, "authorization_text": "",
                "invocations": 0, "started": 0, "updated": 0, "events": 0}
    return summary(session)


# ── resuming ─────────────────────────────────────────────────────────────────

def _post(url: str, body: dict[str, Any], timeout: float) -> tuple[int, Any]:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        try:
            return response.status, json.loads(raw or b"null")
        except ValueError:
            return response.status, raw.decode(errors="replace")


def _said(events: Any) -> list[str]:
    """What a run printed, from adk web's list of events: text parts, a
    workflow node's `output`, and the message of a new request_input."""
    said: list[str] = []

    def add(text: str) -> None:
        # The buyer's final message arrives as a node output AND a text part,
        # and streamed events repeat it; keep each sentence once.
        if text and text not in said:
            said.append(text)

    for event in events if isinstance(events, list) else []:
        if event.get("partial"):
            continue
        if isinstance(event.get("output"), str) and event["output"].strip():
            add(event["output"].strip())
        for part in _parts(event):
            if part.get("text"):
                add(part["text"].strip())
            call = part.get("function_call") or part.get("functionCall") or {}
            if call.get("name") == "adk_request_input" and (call.get("args") or {}).get("message"):
                add(str(call["args"]["message"]))
    return said


def resume(session_id: str | None = None) -> dict[str, Any]:
    """Answer the pending queue wait of the current task, in its own session.

    Refuses anything that is not a queue wait: a question for a person is
    answered by a person, in the chat, and never by a button or a clock."""
    session = find(session_id)
    if session is None:
        return {"ok": False, "reason": "nothing is paused", "session_id": None}
    pending = pending_of(session)
    if pending is None:
        return {"ok": False, "reason": "nothing is paused", "session_id": session["id"]}
    if pending["kind"] == "person":
        return {"ok": False, "reason": "waiting for you — answer in the chat",
                "session_id": session["id"], "pending": pending}
    if pending["kind"] != "queue":
        return {"ok": False, "reason": f"paused on {pending['id']}, which is not a queue wait",
                "session_id": session["id"], "pending": pending}

    # 1. adk web's own API: the same request the dev UI's answer box sends.
    body = {
        "app_name": session["app_name"] or APP_NAME,
        "user_id": session["user_id"] or "user",
        "session_id": session["id"],
        "new_message": {"role": "user", "parts": [{"function_response": {
            "id": pending["id"], "name": "adk_request_input", "response": {"checked": True}}}]},
    }
    try:
        status, payload = _post(f"{ADK_WEB}/run", body, timeout=240)
        after = current(session["id"])
        return {"ok": True, "via": "adk web · POST /run", "session_id": session["id"],
                "answered": pending["id"], "events": len(payload) if isinstance(payload, list) else 0,
                "said": _said(payload)[-3:], "status": status, "task": after}
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:400]
        return {"ok": False, "via": "adk web · POST /run", "session_id": session["id"],
                "reason": f"adk web answered {error.code}: {detail}"}
    except (urllib.error.URLError, TimeoutError, OSError):
        pass    # adk web is not running: MonsterTix can do it from its own Runner

    # 2. MonsterTix: POST /wake with the session id answers whatever is pending.
    try:
        status, payload = _post(f"{MONSTERTIX}/wake",
                                {"session_id": session["id"], "message": "Check the queue again."}, timeout=240)
        after = current(session["id"])
        said = payload.get("said") if isinstance(payload, dict) else None
        return {"ok": True, "via": "MonsterTix · POST /wake", "session_id": session["id"],
                "answered": pending["id"], "said": (said or [])[-3:], "status": status, "task": after}
    except urllib.error.HTTPError as error:
        return {"ok": False, "via": "MonsterTix · POST /wake", "session_id": session["id"],
                "reason": f"MonsterTix answered {error.code}"}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"ok": False, "session_id": session["id"],
                "reason": "neither adk web (:8000) nor MonsterTix (:8090) is running; start one and try again"}
