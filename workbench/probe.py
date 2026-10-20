"""Read-only questions about the world, for the workbench's checks.

    python -m workbench.probe tool join_queue
    python -m workbench.probe state user:prefs
    python -m workbench.probe orders --count 1 --section C
    python -m workbench.probe task --kind queue
    python -m workbench.probe tool purchase --current

Each prints what it found and exits 0 when the answer is yes, 1 when it is no.
Nothing here writes: it reads the session stores, the memory file, the venue's
public state and the workbench's own logs. A student could run any of these in
a terminal and see the same thing the page shows.

The session stores it reads are the two the workshop can have: sessions.db at
the root (what `adk web` and MonsterTix are given), and a per-agent
agent/concert/.adk/session.db left behind by an `adk web` started by hand with
no --session_service_uri. The seeded `two-days-ago` conversation is left out
unless asked for, so a check only ever sees what the student did.

THE CURRENT SESSION. The course is one task, but a student may start it more
than once, and an old session must not pass a check for a new experiment.
`--current` on `tool`, `response`, `state`, `nodes` and `pending` looks only
at the newest session (the one with the latest event); `orders
--since-session` counts only orders the venue took after that session's first
event; `task`, `authorization`, `guard`, `retry` and `resumed` always look at
the current session.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
SEEDED = "two-days-ago"


def _stores() -> list[Path]:
    found = [ROOT / "sessions.db"]
    found += sorted((ROOT / "agent").glob("*/.adk/session.db"))
    return [p for p in found if p.exists()]


def _rows(sql: str, args: tuple = ()) -> Iterable[tuple[Path, sqlite3.Row]]:
    for store in _stores():
        try:
            connection = sqlite3.connect(f"file:{store}?mode=ro", uri=True, timeout=2)
            connection.row_factory = sqlite3.Row
            for row in connection.execute(sql, args):
                yield store, row
            connection.close()
        except sqlite3.Error:
            continue


def events(include_seeded: bool = False, session: str = "") -> list[dict[str, Any]]:
    out = []
    for store, row in _rows("SELECT session_id, event_data FROM events"):
        if not include_seeded and row["session_id"] == SEEDED:
            continue
        if session and not row["session_id"].startswith(session):
            continue
        try:
            data = json.loads(row["event_data"])
        except (TypeError, ValueError):
            continue
        data["_session"] = row["session_id"]
        data["_store"] = store.name
        out.append(data)
    out.sort(key=lambda e: e.get("timestamp") or 0)
    return out


def current_session() -> str:
    """The newest session: the one the latest event belongs to. Never the seeded one."""
    found = events()
    return found[-1]["_session"] if found else ""


def _scope(args) -> dict[str, str]:
    """`--current`: only the newest session's events."""
    return {"session": current_session()} if getattr(args, "current", False) else {}


def _parts(event: dict[str, Any]) -> list[dict[str, Any]]:
    return ((event.get("content") or {}).get("parts")) or []


def calls(name: str, **kw) -> list[dict[str, Any]]:
    return [p["function_call"] | {"_session": e["_session"]} for e in events(**kw)
            for p in _parts(e) if (p.get("function_call") or {}).get("name") == name]


def responses(name: str, **kw) -> list[dict[str, Any]]:
    return [p["function_response"] | {"_session": e["_session"]} for e in events(**kw)
            for p in _parts(e) if (p.get("function_response") or {}).get("name") == name]


def _venue() -> str:
    url = os.environ.get("VENUE_URL", "")
    env = ROOT / ".env"
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("VENUE_URL="):
                url = line.split("=", 1)[1].strip().strip('"')
    return (url or "http://127.0.0.1:8080").rstrip("/")


def venue_state() -> dict[str, Any]:
    with urllib.request.urlopen(_venue() + "/admin/state", timeout=8) as response:
        return json.loads(response.read())


def say(ok: bool, message: str) -> int:
    print(message)
    return 0 if ok else 1


def short(value: Any, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


def _find(value: Any, key: str) -> Any:
    """The first `key` anywhere inside a tool's response (ADK wraps some in {"result": …})."""
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for inner in value.values():
            found = _find(inner, key)
            if found is not None:
                return found
    return None


def _session_started(session: str) -> float:
    found = events(session=session) if session else []
    return float(found[0].get("timestamp") or 0) if found else 0.0


# ── the questions ────────────────────────────────────────────────────────────

def q_tool(args) -> int:
    found = calls(args.name, include_seeded=args.seeded, **_scope(args))
    if not found:
        return say(False, f"no call to {args.name} yet" + (" in the current session" if args.current else ""))
    last = found[-1]
    ok = args.exactly is None or len(found) == args.exactly
    return say(ok, f"{len(found)} call(s) to {args.name}; last: {short(last.get('args'))}")


def q_response(args) -> int:
    found = responses(args.name, **_scope(args))
    hits = [r for r in found if not args.contains or args.contains.lower() in json.dumps(r.get("response")).lower()]
    if not hits:
        return say(False, f"no {args.name} response" + (f" containing {args.contains!r}" if args.contains else "") + " yet")
    return say(True, f"{args.name} said: {short(hits[-1].get('response'))}")


def q_turns(args) -> int:
    """How many times the agent was run, and whether any run started without a person."""
    runs = {e["invocation_id"] for e in events() if e.get("invocation_id")}
    ok = len(runs) >= args.at_least
    return say(ok, f"{len(runs)} run(s) in the session store")


def q_session(args) -> int:
    ids = sorted({sid for _, row in _rows("SELECT id FROM sessions") for sid in [row["id"]]
                  if sid.startswith(args.prefix)})
    if not ids:
        return say(False, f"no session whose id starts with {args.prefix!r}")
    # The seeded conversation is left out of every other question; asking for
    # it by name is the one time it should count.
    seeded = SEEDED.startswith(args.prefix)
    count = len([e for e in events(include_seeded=seeded, session=args.prefix) if e.get("author") != "user"])
    ok = count > 0
    return say(ok, f"{len(ids)} session(s): {', '.join(ids[:3])}; {count} agent event(s) in them")


def _state(session: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    """The newest session's state, and the user: state. With `session`, that
    session's stored state and only its own deltas."""
    session_state: dict[str, Any] = {}
    newest = -1.0
    for _, row in _rows("SELECT id, state, update_time FROM sessions"):
        if row["id"] == SEEDED:
            continue
        if session and not row["id"].startswith(session):
            continue
        stamp = row["update_time"]
        stamp = stamp if isinstance(stamp, (int, float)) else 0
        try:
            state = json.loads(row["state"] or "{}")
        except ValueError:
            continue
        if stamp >= newest:
            newest, session_state = stamp, state
    user: dict[str, Any] = {}
    for _, row in _rows("SELECT state FROM user_states"):
        try:
            user.update({f"user:{k}" if not k.startswith("user:") else k: v
                         for k, v in json.loads(row["state"] or "{}").items()})
        except ValueError:
            continue
    # Session state as events record it: the deltas, latest wins.
    for event in events(session=session):
        for key, value in ((event.get("actions") or {}).get("state_delta") or {}).items():
            if key.startswith("user:"):
                user[key] = value
            elif not key.startswith("temp:"):
                session_state[key] = value
    return session_state, user


def q_state(args) -> int:
    session_state, user = _state(**_scope(args))
    merged = {**session_state, **user}
    if args.absent:
        if args.after_tool and not calls(args.after_tool, **_scope(args)):
            return say(False, f"{args.after_tool} has not run yet, so there is nothing to have lost")
        present = args.key in merged
        return say(not present, f"{args.key} is {'still there: ' + short(merged[args.key]) if present else 'not in state'}")
    if args.key not in merged:
        return say(False, f"{args.key} is not in state yet")
    value = merged[args.key]
    if args.contains and args.contains.lower() not in json.dumps(value).lower():
        return say(False, f"{args.key} = {short(value)}  (no {args.contains!r} in it)")
    return say(True, f"{args.key} = {short(value)}")


def q_memory(args) -> int:
    path = ROOT / "memory" / "userx.md"
    if not path.exists():
        return say(False, "memory/userx.md does not exist")
    text = path.read_text()
    if args.contains and args.contains.lower() not in text.lower():
        return say(False, f"memory/userx.md has no {args.contains!r} in it yet")
    return say(True, text.strip()[-600:])


def q_artifacts(args) -> int:
    folder = ROOT / "artifacts"
    files = [p for p in folder.rglob("*") if p.is_file()] if folder.exists() else []
    if not files:
        return say(False, "artifacts/ is empty")
    return say(True, "\n".join(str(p.relative_to(ROOT)) for p in files[:12]))


def q_compaction(args) -> int:
    found = [e for e in events() if (e.get("actions") or {}).get("compaction")]
    if not found:
        return say(False, "no compaction has run in your session yet")
    summary = found[-1]["actions"]["compaction"].get("compacted_content") or {}
    text = " ".join(p.get("text", "") for p in summary.get("parts", []))
    return say(True, f"{len(found)} compaction(s). The latest summary:\n{text.strip()}")


def _orders_since(orders: list[dict[str, Any]], started: float) -> list[dict[str, Any]]:
    return [o for o in orders if float(o.get("created_at") or 0) >= started]


def _order_line(o: dict[str, Any]) -> str:
    line = f"{o.get('seats', '?')} × section {o.get('section', '?')} · {o.get('event_id', '')}"
    if isinstance(o.get("total"), (int, float)):
        line += f" · ${o['total']:g}"
    if o.get("id"):
        line += f" · {o['id']}"
    return line


def q_orders(args) -> int:
    try:
        state = venue_state()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return say(False, f"the venue did not answer: {error}")
    orders = state.get("orders") or []
    if args.since_start:
        try:
            started = float((ROOT / "runs" / f"{args.since_start}.started").read_text())
        except (OSError, ValueError):
            return say(False, f"{args.since_start} has not been started from the workbench")
        orders = _orders_since(orders, started)
    if args.since_session:
        session = current_session()
        if not session:
            return say(False, "no session yet, so nothing counts as this session's orders")
        orders = _orders_since(orders, _session_started(session))
    lines = [_order_line(o) for o in orders]
    ok = len(orders) == args.count if args.count is not None else len(orders) >= args.at_least
    if ok and args.section:
        ok = any(str(o.get("section")) == args.section for o in orders)
    if ok and args.qty:
        ok = any(int(o.get("seats") or 0) == args.qty for o in orders)
    scope = " since this session started" if args.since_session else ""
    return say(ok, f"{len(orders)} order(s){scope}" + (":\n" + "\n".join(lines) if lines else ""))


def q_tickets(args) -> int:
    """How many places in line the venue has handed out."""
    try:
        queue = venue_state().get("queue") or []
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return say(False, f"the venue did not answer: {error}")
    lines = [f"{q.get('ticket', '?')} · position {q.get('position', '?')}" for q in queue]
    ok = len(queue) == args.count if args.count is not None else bool(queue)
    return say(ok, f"{len(queue)} queue ticket(s)" + (":\n" + "\n".join(lines) if lines else ""))


def q_queue(args) -> int:
    """Queue positions the agent was told, in order. Passes when the newest is
    lower than the first: the line moved while the agent was not there."""
    positions = []
    for response in responses("join_queue") + responses("check_queue"):
        body = response.get("response") or {}
        if isinstance(body, dict) and "result" in body and isinstance(body["result"], dict):
            body = body["result"]
        if isinstance(body, dict) and isinstance(body.get("position"), (int, float)):
            positions.append(int(body["position"]))
    if len(positions) < 2:
        return say(False, f"positions seen: {positions or 'none'}; ask where you are in line")
    return say(positions[-1] < positions[0], f"positions seen, in order: {positions}")


def q_killed(args) -> int:
    log = ROOT / "runs" / f"{args.service}.log"
    text = log.read_text(errors="replace") if log.exists() else ""
    marker = "[workbench] kill -9"
    if marker not in text:
        return say(False, f"{args.service} has not been killed")
    after = text.rsplit(marker, 1)[1]
    restarted = "\n$ " in after
    if args.restarted and not restarted:
        return say(False, f"{args.service} was killed and has not been started again")
    return say(True, f"{args.service} was killed" + (", then started again" if restarted else ""))


def _log_lines(name: str) -> list[str]:
    log = ROOT / "runs" / f"{name}.log"
    return log.read_text(errors="replace").splitlines() if log.exists() else []


def q_wake(args) -> int:
    if args.trigger:
        # Chapter 6's local rehearsal: the clock posts to /trigger/wake, the
        # scheduler's entrance, which resumes a waiting task and never starts
        # a conversation. The clock's own log is the evidence: after
        # "firing → POST /trigger/wake" it prints "done. the agent ran…", or
        # "nothing resumed: …" / "nothing listening…" when it did not.
        # MonsterTix's log is the fallback when the clock ran in a terminal.
        lines = _log_lines("clock")
        fired = [i for i, line in enumerate(lines) if "firing" in line and "/trigger/wake" in line]
        if not fired:
            served = [line for line in _log_lines("monstertix")
                      if "/trigger/wake" in line or "answering queue interrupt" in line]
            if served:
                return say(any("answering queue interrupt" in line or " 200" in line for line in served),
                           "\n".join(served[-3:]))
            return say(False, "nothing has called /trigger/wake yet")
        after = [line for line in lines[fired[-1] + 1:fired[-1] + 4] if "[clock]" in line]
        if not after:
            return say(False, lines[fired[-1]] + "\n(still waiting for the answer)")
        verdict = after[0]
        ok = "done" in verdict and "nothing" not in verdict and "returned" not in verdict
        return say(ok, lines[fired[-1]] + "\n" + verdict)
    if args.clock:
        hits = [line for line in _log_lines("clock") if "the agent ran" in line]
        if not hits:
            return say(False, "the clock has not woken the agent yet")
        return say(True, "\n".join(hits[-3:]))
    hits = [line for line in _log_lines("monstertix") if "POST /wake" in line or "woken" in line.lower()]
    if not hits:
        return say(False, "MonsterTix has not been woken")
    return say(True, "\n".join(hits[-4:]))


def q_setting(args) -> int:
    """One setting from .env, set or not. Credentials inside a value (a
    database URI's user:password@) are blanked, since the page shows this."""
    env = ROOT / ".env"
    values = {}
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"')
    value = values.get(args.key, "")
    if not value:
        return say(False, f"{args.key} is not set in .env yet")
    shown = re.sub(r"//[^/@\s]+@", "//…@", value)
    if any(word in args.key.upper() for word in ("PASSWORD", "SECRET", "TOKEN", "KEY")):
        shown = "(set)"
    return say(True, f"{args.key}={shown}")


def q_prompts(args) -> int:
    """Chapter 2's prompt lab: how many wordings were tried, and what each did."""
    try:
        tries = json.loads((ROOT / "runs" / "prompt-tries.json").read_text())
    except (OSError, ValueError):
        tries = []
    if len(tries) < args.at_least:
        return say(False, f"{len(tries)} prompt(s) tried; try {args.at_least}")
    return say(True, "\n".join(f"{i + 1}. {t.get('label') or t['text'].splitlines()[0][:60]}"
                                for i, t in enumerate(tries)))


def q_file(args) -> int:
    path = (ROOT / args.path).resolve()
    if path.name == ".env":
        return say(False, "use `setting KEY` for .env: it holds credentials")
    if ROOT not in path.parents or not path.is_file():
        return say(False, f"{args.path} not found")
    text = path.read_text(errors="replace")
    lines = [line.strip() for line in text.splitlines() if args.contains in line]
    if args.absent:
        return say(not lines, "\n".join(lines) or f"no {args.contains!r} in {args.path}")
    return say(bool(lines), "\n".join(lines[:4]) or f"no {args.contains!r} in {args.path}")


def q_pending(args) -> int:
    """Is a run waiting on a person? An adk_request_input call with no answer."""
    asked = calls("adk_request_input", **_scope(args))
    answered = {r.get("id") for r in responses("adk_request_input", **_scope(args))}
    waiting = [c for c in asked if c.get("id") not in answered]
    if args.answered:
        ok = bool(asked) and len(waiting) < len(asked)
        return say(ok, f"{len(asked)} question(s) asked, {len(asked) - len(waiting)} answered")
    if not waiting:
        return say(False, "nothing is waiting on you" if not asked else "every question has been answered")
    return say(True, f"waiting for an answer: {short((waiting[-1].get('args') or {}).get('message') or waiting[-1].get('args'))}")


def q_nodes(args) -> int:
    seen = []
    for event in events(**_scope(args)):
        path = ((event.get("node_info") or {}).get("path")) or ""
        # A path is segments like "concert_nightly@1/pick_show@1": compare names exactly.
        names = {segment.split("@")[0] for segment in path.split("/") if segment}
        for node in args.names:
            if node in names and node not in seen:
                seen.append(node)
    missing = [n for n in args.names if n not in seen]
    return say(not missing, f"nodes that ran: {seen or 'none'}" + (f"; not yet: {missing}" if missing else ""))


def q_url(args) -> int:
    try:
        with urllib.request.urlopen(args.url, timeout=8) as response:
            body = response.read(400).decode(errors="replace")
            return say(response.status == 200, f"{response.status} {body}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return say(False, f"no answer from {args.url}: {error}")


# ── the current task (chapters 4–6) ──────────────────────────────────────────

def _task() -> dict[str, Any]:
    # The same reader the page's task card uses, so both say the same thing.
    from workbench.services import task
    return task.current()


def _task_lines(info: dict[str, Any]) -> str:
    pending = info.get("pending") or {}
    lines = [f"session {info.get('session_id')} · {info.get('kind_label')}"
             + (f" · {pending.get('id')}" if pending else "")]
    if info.get("queue_ticket"):
        lines.append(f"ticket {info['queue_ticket']} · {info.get('queue_event_id') or ''}".rstrip(" ·"))
    if info.get("authorization_text"):
        lines.append(f"authorization: {info['authorization_text']}")
    if info.get("ready_to_buy"):
        lines.append("ready to buy")
    if info.get("last_order"):
        lines.append(f"last order: {short(info['last_order'], 160)}")
    lines.append(f"{info.get('invocations', 0)} invocation(s)")
    return "\n".join(lines)


def q_task(args) -> int:
    """The current task: paused on the queue, on a person, or not paused."""
    info = _task()
    if not info.get("session_id"):
        return say(False, "no task yet: no session has any events")
    pending = info.get("pending") or {}
    ok = True
    if args.kind:
        ok = (pending.get("kind") or "none") == args.kind
    if ok and args.ready:
        ok = bool(info.get("ready_to_buy"))
    if ok and args.ticket:
        ok = bool(info.get("queue_ticket"))
    return say(ok, _task_lines(info))


def q_authorization(args) -> int:
    """This task's authorization, as `agree_budget` stored it in session state."""
    info = _task()
    auth = info.get("authorization")
    if not isinstance(auth, dict):
        return say(False, "no authorization in the current session yet")
    text = info.get("authorization_text") or short(auth)
    if args.confirmed and not auth.get("confirmed"):
        return say(False, f"{text} — read back, not confirmed yet")
    return say(True, text + (f" · {auth.get('text')!r}" if auth.get("text") else ""))


def q_guard(args) -> int:
    """A `purchase` in the current session was stopped by the guard with this reason.

    Any purchase, not only the last: the whole point of the guard is that the
    refused call is followed by a second, successful one."""
    found = responses("purchase", session=current_session())
    if not found:
        return say(False, "no purchase call in the current session yet")
    reasons = [_find(r.get("response"), "reason") for r in found]
    hits = [r for r, reason in zip(found, reasons) if reason == args.reason]
    if hits:
        return say(True, f"{len(found)} purchase call(s); refused once with {args.reason!r}: "
                         f"{short(hits[0].get('response'))}")
    return say(False, f"{len(found)} purchase call(s), none refused with {args.reason!r} "
                      f"(reasons seen: {[r for r in reasons if r]})\nlast: {short(found[-1].get('response'))}")


def q_retry(args) -> int:
    """The last purchase took two attempts, and the venue still has one order since this session."""
    session = current_session()
    found = responses("purchase", session=session)
    if not found:
        return say(False, "no purchase call in the current session yet")
    response = found[-1].get("response")
    attempts = _find(response, "attempts")
    try:
        attempts = int(attempts or 0)
    except (TypeError, ValueError):
        attempts = 0
    if attempts < 2:
        return say(False, f"last purchase took {attempts or 'one'} attempt(s): {short(response, 200)}")
    try:
        orders = _orders_since(venue_state().get("orders") or [], _session_started(session))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return say(False, f"the venue did not answer: {error}")
    lines = "\n".join(_order_line(o) for o in orders)
    return say(len(orders) == 1,
               f"{attempts} attempts, key {_find(response, 'idempotency_key')}; "
               f"{len(orders)} order(s) since this session started" + (":\n" + lines if lines else ""))


def q_resumed(args) -> int:
    """The current session was woken again and carried on with the SAME place in line.

    Woken again = its `queue:wait` request_input has an answer (a function_response
    with that id: the button, the clock, MonsterTix and the dev UI's box all
    send one). Same place = one `queue_ticket` ever written in this session,
    and one `joined` in the venue's activity since the session started."""
    session = current_session()
    if not session:
        return say(False, "no session yet")
    found = events(session=session)
    invocations = {e.get("invocation_id") for e in found if e.get("invocation_id")}
    answered = [r for r in responses("adk_request_input", session=session)
                if str(r.get("id") or "").startswith("queue:")]
    tickets = []
    for event in found:
        ticket = ((event.get("actions") or {}).get("state_delta") or {}).get("queue_ticket")
        if ticket and ticket not in tickets:
            tickets.append(ticket)
    joined = None
    try:
        started = _session_started(session)
        joined = [a for a in venue_state().get("agent_events") or []
                  if a.get("kind") == "queue" and str(a.get("message", "")).startswith("joined")
                  and float(a.get("ts") or 0) >= started]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        pass
    ok = bool(answered) and len(tickets) == 1 and (joined is None or len(joined) == 1)
    report = (f"{len(answered)} queue wait(s) answered, {len(invocations)} invocation(s), "
              f"ticket(s) in state: {tickets or 'none'}"
              + (f", {len(joined)} join(s) at the venue since the session started" if joined is not None else ""))
    if not answered:
        report += "\n(not resumed yet: the queue wait has no answer)"
    elif len(tickets) != 1 or (joined is not None and len(joined) != 1):
        report += "\n(it joined the queue again)"
    return say(ok, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m workbench.probe")
    sub = parser.add_subparsers(dest="question", required=True)
    current = dict(action="store_true", help="only the newest session")

    p = sub.add_parser("tool"); p.add_argument("name"); p.add_argument("--seeded", action="store_true")
    p.add_argument("--exactly", type=int); p.add_argument("--current", **current); p.set_defaults(fn=q_tool)
    p = sub.add_parser("response"); p.add_argument("name"); p.add_argument("--contains", default="")
    p.add_argument("--current", **current); p.set_defaults(fn=q_response)
    p = sub.add_parser("turns"); p.add_argument("--at-least", type=int, default=1); p.set_defaults(fn=q_turns)
    p = sub.add_parser("session"); p.add_argument("prefix"); p.set_defaults(fn=q_session)
    p = sub.add_parser("state"); p.add_argument("key"); p.add_argument("--contains", default=""); p.add_argument("--absent", action="store_true")
    p.add_argument("--after-tool", default="", help="with --absent: only once this tool has been called")
    p.add_argument("--current", **current); p.set_defaults(fn=q_state)
    p = sub.add_parser("memory"); p.add_argument("--contains", default=""); p.set_defaults(fn=q_memory)
    p = sub.add_parser("artifacts"); p.set_defaults(fn=q_artifacts)
    p = sub.add_parser("compaction"); p.set_defaults(fn=q_compaction)
    p = sub.add_parser("orders"); p.add_argument("--count", type=int); p.add_argument("--at-least", type=int, default=1)
    p.add_argument("--section", default=""); p.add_argument("--qty", type=int, default=0)
    p.add_argument("--since-start", default="", help="only orders made since this service last started")
    p.add_argument("--since-session", action="store_true", help="only orders made since the newest session's first event")
    p.set_defaults(fn=q_orders)
    p = sub.add_parser("queue"); p.set_defaults(fn=q_queue)
    p = sub.add_parser("tickets"); p.add_argument("--count", type=int); p.set_defaults(fn=q_tickets)
    p = sub.add_parser("killed"); p.add_argument("service"); p.add_argument("--restarted", action="store_true"); p.set_defaults(fn=q_killed)
    p = sub.add_parser("wake"); p.add_argument("--clock", action="store_true", help="woken by the clock, not the page")
    p.add_argument("--trigger", action="store_true", help="the clock called /trigger/wake, the scheduler's entrance"); p.set_defaults(fn=q_wake)
    p = sub.add_parser("file"); p.add_argument("path"); p.add_argument("contains"); p.add_argument("--absent", action="store_true"); p.set_defaults(fn=q_file)
    p = sub.add_parser("pending"); p.add_argument("--answered", action="store_true"); p.add_argument("--current", **current); p.set_defaults(fn=q_pending)
    p = sub.add_parser("nodes"); p.add_argument("names", nargs="+"); p.add_argument("--current", **current); p.set_defaults(fn=q_nodes)
    p = sub.add_parser("url"); p.add_argument("url"); p.set_defaults(fn=q_url)
    p = sub.add_parser("prompts"); p.add_argument("--at-least", type=int, default=1); p.set_defaults(fn=q_prompts)
    p = sub.add_parser("setting"); p.add_argument("key"); p.set_defaults(fn=q_setting)
    p = sub.add_parser("task", help="the current task: session, pause, ticket, authorization, order")
    p.add_argument("--kind", choices=["queue", "person", "none"], help="what it is paused on")
    p.add_argument("--ready", action="store_true", help="ready_to_buy is set")
    p.add_argument("--ticket", action="store_true", help="it holds a queue ticket"); p.set_defaults(fn=q_task)
    p = sub.add_parser("authorization", help="this session's authorization"); p.add_argument("--confirmed", action="store_true"); p.set_defaults(fn=q_authorization)
    p = sub.add_parser("guard", help="the guard stopped the last purchase with this reason"); p.add_argument("reason"); p.set_defaults(fn=q_guard)
    p = sub.add_parser("retry", help="two attempts, one order"); p.set_defaults(fn=q_retry)
    p = sub.add_parser("resumed", help="woken again, same ticket, no second join"); p.set_defaults(fn=q_resumed)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
