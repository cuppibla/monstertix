"""What the endpoints DO, with no opinion about who is serving them.

Nothing here builds a Runner, a FastAPI app, or a session service. Every one of
these takes what it needs as an argument, which is the only reason this file
exists: there are two entrypoints and they must not drift apart.

    monstertix/server.py    Chapter 2 · Wake the Agent — your own Runner behind
                            your own endpoint, on your laptop
    agent/main.py           Chapter 6 · Run It While You Sleep — the same routes
                            bolted onto the app that `get_fast_api_app` builds,
                            in one Cloud Run container

Chapter 6 is the reason it matters. `get_fast_api_app` builds its own session
and artifact services from the URIs you give it, and in production those point
at Cloud SQL and a bucket. If it imported `server.py` to reuse a handler it
would drag along a second set pointed at SQLite on a container filesystem that
is destroyed when the instance goes away — which is exactly the failure Chapter
6 exists to teach.

Two kinds of pause, and only one of them may be ended by a machine:

    queue:*    the run is waiting for the venue's queue to move. A clock, a
               scheduler, or a button may say "check again".
    budget:*   the run is waiting for a PERSON to answer a question. Nothing
               automatic is allowed to answer on their behalf.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import uuid

from google.adk.workflow.utils._workflow_hitl_utils import (
    create_request_input_response,
    get_request_input_interrupt_ids,
)
from google.genai import types

# One identity, everywhere. `adk web` hardcodes userId=user and cannot be told
# otherwise; so the page, the clock, the scheduler and the seed all use the same
# one, and every surface sees the same sessions. MEMORY_USER names the memory
# FILE (memory/userx.md) and is not a user id.
APP_NAME = "concert"
USER_ID = os.environ.get("ADK_USER_ID", "user")

# What a caller gets when it does not say what it wants. The clock in Chapter 2
# sends this; a bare POST /wake from curl gets the same.
DEFAULT_MESSAGE = (
    "Check whether the Amsterdam shows still have seats, and tell me what you find."
)

# The seeded conversation from two days ago. It is a session like any other,
# but it is never "the task you are working on", so the summary skips it when
# there is anything newer.
SEEDED_SESSIONS = {"two-days-ago"}


def new_session_id() -> str:
    """A fresh session. Nothing is deleted.

    A new session means a new conversation and, from Chapter 5 on, a new
    authorization — session state starts empty, so the agent asks again.
    Anything under `user:` survives, and so does the memory file.
    """
    return f"web-{uuid.uuid4().hex[:8]}"


def kind_of(interrupt_id: str) -> str:
    """Who is this pause waiting for?

    The workflow names its interrupts with a prefix for exactly this reason:
    `queue:wait` may be answered by anything with a clock; `budget:ask` and
    `budget:confirm` may only be answered by the person whose money it is.
    """
    if interrupt_id.startswith("queue:"):
        return "queue"
    if interrupt_id.startswith("budget:"):
        return "person"
    return "other"


def _pending_in(session) -> tuple[str, str, str] | None:
    """(interrupt_id, kind, message) for an unanswered request_input, or None.

    Walks the session's events newest-first: the first interrupt id with no
    matching function_response after it is the one still waiting. Deliberately
    stateless — the session store already knows, and a dict of ids in this
    process would not survive the container restarting.
    """
    answered: set[str] = set()
    for event in reversed(session.events or []):
        parts = (event.content.parts if event.content else []) or []
        for part in parts:
            response = getattr(part, "function_response", None)
            if response and response.name == "adk_request_input":
                answered.add(response.id)
        for interrupt_id in get_request_input_interrupt_ids(event):
            if interrupt_id in answered:
                continue
            message = ""
            for part in parts:
                call = getattr(part, "function_call", None)
                if call and call.id == interrupt_id:
                    message = str((call.args or {}).get("message") or "")
            return interrupt_id, kind_of(interrupt_id), message
    return None


async def pending_interrupt(session_service, app_name: str, user_id: str,
                            session_id: str) -> tuple[str, str] | None:
    """`(interrupt_id, kind)` if the run is parked on a question, else None."""
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if not session:
        return None
    found = _pending_in(session)
    return (found[0], found[1]) if found else None


def message_from(payload, default: str = DEFAULT_MESSAGE) -> str:
    """The sentence a caller sent, whatever shape the caller used.

    A browser posts `{"message": "..."}`. A Pub/Sub push subscription posts an
    envelope — `{"message": {"data": "<base64>", ...}, "subscription": ...}` —
    where "message" is a dict and the data is whatever the Scheduler job was
    told to publish. That data is not an instruction for the agent, so it is
    ignored and the default is used instead.
    """
    if not isinstance(payload, dict):
        return default
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return default


def session_id_from(payload) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("session_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _looks_structured(text: str) -> bool:
    """A JSON object an agent node produced for the NEXT node, not for a person.

    `pick_show` answers with a Plan as JSON (output_schema). The graph reads it;
    the person at the page should not have to. Anything else — including a
    sentence that happens to contain a brace — is said as-is.
    """
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return False
    try:
        return isinstance(json.loads(stripped), dict)
    except ValueError:
        return False


# One run per session at a time, in this process. Two callers that arrive
# together — the page's Resume and the clock, say, or Pub/Sub delivering a
# message twice, which it is allowed to do — would otherwise both read "parked
# on queue:wait" and both answer it; the second answer starts a second
# invocation. The lock makes the second caller wait, re-read the session, and
# find nothing left to resume. Per process only: on Cloud Run with more than
# one instance this is a courtesy, and idempotency in the tools is the guarantee.
_locks: dict[str, asyncio.Lock] = {}


def _lock_for(session_id: str) -> asyncio.Lock:
    return _locks.setdefault(session_id, asyncio.Lock())


async def wake(runner, session_service, app_name: str, user_id: str,
               message: str, session_id: str | None = None,
               log=print, only_if_pending: tuple[str, ...] | None = None) -> dict:
    """Run the agent once.

    Whoever calls this does not have to know what an agent is. They send a
    sentence and get sentences back.

    `only_if_pending`: when given, the run happens only if the session is
    parked on an interrupt of one of these kinds — checked under the session's
    lock, so a second caller does not start a fresh invocation after the first
    one has already answered the question. Returns `{"skipped": reason}` then.
    """
    session_id = session_id or f"wake-{uuid.uuid4().hex[:8]}"
    async with _lock_for(session_id):
        return await _wake_locked(runner, session_service, app_name, user_id,
                                  message, session_id, log, only_if_pending)


async def _wake_locked(runner, session_service, app_name, user_id, message,
                       session_id, log, only_if_pending) -> dict:
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if not session:
        session = await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

    if only_if_pending is not None:
        now = _pending_in(session)
        if not now:
            return {"session_id": session_id, "skipped": "nothing is waiting"}
        if now[1] not in only_if_pending:
            return {"session_id": session_id, "skipped": f"waiting on {now[1]}",
                    "kind": now[1]}

    # Is the run parked on a question? If so this message is the ANSWER to it,
    # not a new request. Sending it as ordinary text starts a fresh invocation
    # and replays the graph from the top, which looks like the agent asking the
    # same question forever.
    pending = _pending_in(session)
    kind = None
    if pending:
        interrupt_id, kind, _ = pending
        # A queue wait does not want a sentence; it wants to be told to look
        # again. A person-wait gets the person's words.
        answer = {"checked": True} if kind == "queue" else {"result": message}
        new_message = types.Content(
            role="user",
            parts=[create_request_input_response(interrupt_id, answer)],
        )
        log(f"[server] answering {kind} interrupt {interrupt_id[:24]}")
    else:
        new_message = types.Content(role="user", parts=[types.Part(text=message)])

    log(f"\n[server] woken · session {session_id}")
    said: list[str] = []
    awaiting = False
    awaiting_kind = None

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=new_message
    ):
        for part in (event.content.parts if event.content else []) or []:
            call = getattr(part, "function_call", None)
            if call:
                if call.name == "adk_request_input":
                    awaiting = True
                    awaiting_kind = kind_of(call.id or "")
                    asked = (call.args or {}).get("message")
                    if asked:
                        said.append(str(asked))
                log(f"[server]   called {call.name}")
            elif getattr(part, "text", None):
                text = part.text.strip()
                if text and not _looks_structured(text):
                    said.append(text)
                    log(f"[server]   said   {text[:160]}")
                elif text:
                    log(f"[server]   output {text[:80]!r}  (structured, not said)")

    return {
        "session_id": session_id,
        "said": said,
        # Did the run stop on a question? The page marks that reply so a parked
        # run does not look like an ordinary answer — and says who it waits for.
        "awaiting_input": awaiting,
        "awaiting_kind": awaiting_kind,
        "answered": kind,
    }


async def _newest_first(session_service, app_name: str, user_id: str) -> list:
    listing = await session_service.list_sessions(app_name=app_name, user_id=user_id)
    return sorted(listing.sessions or [],
                  key=lambda s: s.last_update_time or 0.0, reverse=True)


async def resume_waiting(runner, session_service, app_name: str, user_id: str,
                         *, session_id: str | None = None,
                         allow: tuple[str, ...] = ("queue",),
                         message: str = "Checking on your behalf.",
                         log=print) -> dict:
    """Continue a parked run — but only one a machine is allowed to continue.

    This is what the clock, Cloud Scheduler and the page's Resume button call.
    ADK ships a trigger endpoint at /apps/<app>/trigger/pubsub, and for this
    workshop it is the wrong one. Read its source and you find:

        session_id = str(uuid.uuid4())               a brand new session
        user_id    = subscription.replace("/", "--") a different user

    That is correct for "fire an agent at something", and useless for "go and
    finish the thing you started". A fresh session has no queue ticket, no
    authorization, and no memory of the conversation, so it starts a second
    task instead of completing the first.

    This does the opposite: it finds the session that is already waiting and
    answers the question it parked on — if the kind of question is in `allow`.
    A `queue:` wait is answered with "checked". A `budget:` wait is a person's
    question, and a timer firing at 3am is not that person, so it is left alone
    and the caller is told why.

    Returns `{"woke": session_id | None, "kind": ..., "reason": ...}`.
    """
    if session_id:
        candidates = [session_id]
    else:
        candidates = [s.id for s in await _newest_first(session_service, app_name, user_id)]
        if not candidates:
            return {"woke": None, "kind": None, "reason": "no sessions to resume"}

    # Newest first. A parked run is almost always the most recent thing here,
    # and anything older has either finished or been abandoned.
    for sid in candidates:
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=sid
        )
        if not session:
            continue
        pending = _pending_in(session)
        if not pending:
            continue
        interrupt_id, kind, _ = pending
        if kind not in allow:
            reason = ("waiting for a person to answer" if kind == "person"
                      else f"waiting on {interrupt_id}, which a trigger may not answer")
            log(f"[server] not resuming {sid}: {reason}")
            return {"woke": None, "kind": kind, "session_id": sid, "reason": reason}
        result = await wake(runner, session_service, app_name, user_id,
                            message=message, session_id=sid, log=log,
                            only_if_pending=allow)
        if result.get("skipped"):
            # Somebody else answered it between our look and our lock. Nothing
            # to do, and nothing to report as a failure.
            log(f"[server] not resuming {sid}: {result['skipped']} (already handled)")
            return {"woke": None, "kind": result.get("kind"), "session_id": sid,
                    "reason": result["skipped"]}
        return {"woke": sid, "kind": kind, "reason": "resumed", **result}

    return {"woke": None, "kind": None, "reason": "nothing is waiting"}


def _position_in(message: str) -> int | None:
    found = re.search(r"#\s?([\d,]+)", message or "")
    return int(found.group(1).replace(",", "")) if found else None


def _summarise(session) -> dict:
    state = dict(session.state or {})
    pending = _pending_in(session)
    invocations = {e.invocation_id for e in (session.events or []) if e.invocation_id}
    return {
        "session_id": session.id,
        "pending": ({"id": pending[0], "kind": pending[1], "message": pending[2]}
                    if pending else None),
        "queue_ticket": state.get("queue_ticket"),
        "queue_event_id": state.get("queue_event_id"),
        "queue_position": _position_in(pending[2]) if pending and pending[1] == "queue" else None,
        "plan": state.get("plan"),
        "authorization": state.get("authorization"),
        "ready_to_buy": bool(state.get("ready_to_buy")),
        "last_order": state.get("last_order"),
        "invocations": len(invocations),
        "updated": session.last_update_time,
    }


def _empty_summary(session_id: str | None) -> dict:
    return {
        "session_id": session_id, "pending": None, "queue_ticket": None,
        "queue_event_id": None, "queue_position": None, "plan": None,
        "authorization": None, "ready_to_buy": False, "last_order": None,
        "invocations": 0, "updated": None,
    }


async def task_summary(session_service, app_name: str, user_id: str,
                       session_id: str | None = None) -> dict:
    """One task, read straight out of session state. Nothing is run.

    With a session id: that session. Without one: the newest session that is
    parked on a question, else the newest one with anything in it — skipping the
    seeded two-days-ago conversation, which is history rather than a task.

    This is what the MonsterTix banner and the workbench's task card show. All
    of it comes from the session store, which is the point: the task IS the
    state, and whatever process reads that state sees the same task.
    """
    if session_id:
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        return _summarise(session) if session else _empty_summary(session_id)

    fallback = None
    for row in await _newest_first(session_service, app_name, user_id):
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=row.id
        )
        if not session or not session.events:
            continue
        if _pending_in(session):
            return _summarise(session)
        if fallback is None and session.id not in SEEDED_SESSIONS:
            fallback = session
    return _summarise(fallback) if fallback else _empty_summary(None)


async def session_messages(session_service, app_name: str, user_id: str,
                           session_id: str, since: float = 0.0) -> dict:
    """Everything the agent has said in this session since `since`.

    The page polls this. Without it a scheduled run completes on the server and
    the browser goes on showing a queue position for ever — the work finished
    and the only person who cared never found out.
    """
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if not session:
        return {"said": [], "awaiting_input": False, "awaiting_kind": None, "now": 0.0}

    # "Awaiting" is the session's CURRENT state, not "was a question asked in
    # this window" — a question asked and then answered is not pending.
    pending = _pending_in(session)
    said, latest = [], since
    for event in session.events or []:
        stamp = getattr(event, "timestamp", 0.0) or 0.0
        if stamp <= since:
            continue
        latest = max(latest, stamp)
        for part in (event.content.parts if event.content else []) or []:
            call = getattr(part, "function_call", None)
            if call and call.name == "adk_request_input":
                asked = (call.args or {}).get("message")
                if asked:
                    said.append(str(asked))
            elif getattr(part, "text", None) and event.author != "user":
                text = part.text.strip()
                if text and not _looks_structured(text):
                    said.append(text)
    return {"said": said, "awaiting_input": pending is not None,
            "awaiting_kind": pending[1] if pending else None, "now": latest}


async def wipe(session_service, app_name: str, user_id: str, log=print) -> dict:
    """Delete every session and the memory file. Irreversible.

    Written to work wherever the state actually lives, because by Chapter 6 it
    could be anywhere:

        sessions   sqlite OR Cloud SQL — same session-service API either way, so
                   this never touches SQL or knows which one it is.

        memory     a local file OR an object in a bucket, decided by whether
                   MEMORY_DIR looks like gs://.
    """
    removed_sessions, removed_memory = 0, []

    listing = await session_service.list_sessions(app_name=app_name, user_id=user_id)
    for session in listing.sessions or []:
        await session_service.delete_session(
            app_name=app_name, user_id=user_id, session_id=session.id
        )
        removed_sessions += 1

    memory_dir = os.environ.get("MEMORY_DIR", "./memory")
    who = os.environ.get("MEMORY_USER", "userx")

    if memory_dir.startswith("gs://"):
        # Imported here rather than at module scope so a laptop with no cloud
        # libraries installed can still run Chapter 2.
        from google.cloud import storage                        # noqa: PLC0415

        bucket_name, _, prefix = memory_dir[5:].partition("/")
        blob_name = f"{prefix.rstrip('/')}/{who}.md".lstrip("/")
        blob = storage.Client().bucket(bucket_name).blob(blob_name)
        if blob.exists():
            blob.delete()
            removed_memory.append(f"gs://{bucket_name}/{blob_name}")
    else:
        path = pathlib.Path(memory_dir) / f"{who}.md"
        if path.exists():
            path.unlink()
            removed_memory.append(str(path))

    log(f"[server] WIPED {removed_sessions} sessions, memory: {removed_memory}")
    return {
        "sessions_deleted": removed_sessions,
        "memory_deleted": removed_memory,
        "session_id": new_session_id(),
    }
