"""THE TRIGGER — a web server with a Runner behind it.

    python -m monstertix.server                 (Ctrl-C to stop)
    python -m monstertix.server --ephemeral     sessions in memory, nothing survives

This is your own server, not `adk web`. `adk web` is a development UI that
happens to be able to run an agent; this is the part underneath it.

Something has to be listening before anything can call it. That is all a trigger
is: an endpoint, and a Runner behind the endpoint.

    POST /wake          {"message": "...", "session_id": "..."}
                        run the agent once, return what it said. If the session
                        is parked on a question, the message is the answer.
    POST /trigger/wake  no body needed — find the newest run that is waiting in
                        the QUEUE and tell it to check again. A run waiting for a
                        person is left alone. This is the route Cloud Scheduler
                        reaches in Chapter 6; `clock.py --trigger` rehearses it.
    GET  /task          what the current task is doing, read from session state
    GET  /session/{id}/messages   what the agent has said since `?since=`
    POST /session/new   a fresh session id. Nothing is deleted.
    POST /admin/wipe    every session and the memory file. Irreversible.
    GET  /health
    GET  /              the MonsterTix page

It builds its services the same way `adk web` does, from the same URIs, using
ADK's own factory functions. Every flag you pass to `adk web` has a matching
argument on `Runner`, and this file is where you can see that they are the same
decision:

    adk web --session_service_uri=X   ≡   Runner(session_service=<built from X>)

In Chapter 6 this same shape is what `get_fast_api_app(...)` gives you on Cloud
Run, with Pub/Sub doing the POSTing.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore", message=r".*\[EXPERIMENTAL\].*")

WORKSHOP = pathlib.Path(os.environ.get("WORKSHOP", pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(WORKSHOP / "agent"))

import uvicorn                                                        # noqa: E402
from fastapi import Body, FastAPI                                     # noqa: E402
from fastapi.responses import FileResponse                            # noqa: E402
from google.adk.cli.utils.service_factory import (                    # noqa: E402
    create_artifact_service_from_options,
    create_session_service_from_options,
)
from google.adk.runners import Runner                                 # noqa: E402
from google.adk.sessions import InMemorySessionService                # noqa: E402

from concert import agent as concert_agent                            # noqa: E402

from . import handlers                                                # noqa: E402

try:
    from concert.memory import memory_service                         # noqa: E402
except ImportError:
    memory_service = None          # a concert/ without a memory service yet

root_agent = concert_agent.root_agent
# From Chapter 3 on, concert/agent.py also exports an `App`: the same root
# agent plus the things that are not an agent — resumability, compaction,
# plugins. A Runner built from the App gets all of them; one built from the
# bare agent gets none. Prefer the App when there is one.
concert_app = getattr(concert_agent, "app", None)

APP_NAME = handlers.APP_NAME
USER_ID = handlers.USER_ID
PORT = int(os.environ.get("TRIGGER_PORT", "8090"))

# The same two URIs you pass to `adk web`. Same files, same data — start this
# server and the dev UI together and they see each other's sessions.
SESSION_URI = os.environ.get(
    "SESSION_SERVICE_URI", f"sqlite+aiosqlite:///{WORKSHOP}/sessions.db"
)
ARTIFACT_URI = os.environ.get("ARTIFACT_SERVICE_URI", f"file://{WORKSHOP}/artifacts")

_args = argparse.ArgumentParser(add_help=False)
_args.add_argument("--ephemeral", action="store_true",
                   help="keep sessions in memory; nothing survives a restart")
OPTS, _ = _args.parse_known_args()

if OPTS.ephemeral:
    # What you get when nobody configures a session store. Every wake starts
    # from nothing. Worth seeing once, deliberately.
    session_service = InMemorySessionService()
    SESSION_DESC = "in memory — nothing survives a restart"
else:
    session_service = create_session_service_from_options(
        base_dir=WORKSHOP / "agent", session_service_uri=SESSION_URI
    )
    SESSION_DESC = SESSION_URI

artifact_service = create_artifact_service_from_options(
    base_dir=WORKSHOP / "agent", artifact_service_uri=ARTIFACT_URI
)

# THE RUNNER. This is what `adk web` has been doing for you: an agent, a name,
# and somewhere to keep sessions, artifacts and memory.
_services = dict(
    session_service=session_service,
    artifact_service=artifact_service,
    # A memory service belongs here. `adk web` cannot take an instance — it only
    # builds services from a URI at startup — but a Runner you construct
    # yourself takes the object directly.
    memory_service=memory_service,
)
if concert_app is not None:
    runner = Runner(app=concert_app, **_services)
else:
    runner = Runner(agent=root_agent, app_name=APP_NAME, **_services)

app = FastAPI(title="MonsterTix")

# The page sits next to the server that serves it. One folder, one thing to
# deploy: MonsterTix is the endpoint AND the front door, and in Chapter 6 both
# move to Cloud Run together.
STATIC = pathlib.Path(__file__).parent


def _log(message: str) -> None:
    print(message, flush=True)


@app.get("/")
def chat_ui():
    """The frontend.

    `adk web` is a development UI. It is excellent for looking inside a run —
    the State tab, the event stream, the graph — and it is not what you ship. It
    does not exist on Cloud Run, and you would not point a customer at it if it
    did.

    So this is the other surface: a page that knows nothing about ADK, talks to
    /wake and /task over HTTP, and would work against any endpoint that answers
    the same way. It is served from the same process as the Runner purely so
    there is one thing to start in a workshop.
    """
    return FileResponse(STATIC / "index.html")


@app.post("/wake")
async def wake(payload: dict = Body(default={})):
    """Run the agent once. The work is in handlers.py, shared with Chapter 6.

    A person — or the clock — is on the other end of this one. If the session
    is parked on a question, the message is the answer to it.
    """
    return await handlers.wake(
        runner, session_service, APP_NAME, USER_ID,
        message=handlers.message_from(payload),
        session_id=handlers.session_id_from(payload),
        log=_log,
    )


@app.post("/trigger/wake")
async def scheduled_wake(payload: dict = Body(default={})):
    """What a scheduler reaches. Resumes a QUEUE wait, never a person's question.

    Locally `python -m monstertix.clock --trigger` posts here; on Cloud Run it is
    Cloud Scheduler → Pub/Sub push → this same path. The body is ignored on
    purpose: a timer has nothing to say, only that time has passed.
    """
    return await handlers.resume_waiting(
        runner, session_service, APP_NAME, USER_ID,
        session_id=handlers.session_id_from(payload),
        allow=("queue",),
        log=_log,
    )


@app.get("/task")
async def task(session_id: str | None = None):
    """What the task is doing right now, read from session state. Runs nothing."""
    return await handlers.task_summary(session_service, APP_NAME, USER_ID, session_id)


@app.get("/session/{session_id}/messages")
async def session_messages(session_id: str, since: float = 0.0):
    """Everything the agent has said in this session since `since`."""
    return await handlers.session_messages(
        session_service, APP_NAME, USER_ID, session_id, since
    )


@app.post("/session/new")
def new_session():
    """Hand the page a fresh session id. Nothing is deleted."""
    return {"session_id": handlers.new_session_id()}


@app.post("/admin/wipe")
async def wipe(payload: dict = Body(default={})):
    """Delete every session and the memory file. Irreversible."""
    return await handlers.wipe(session_service, APP_NAME, USER_ID, log=_log)


@app.get("/health")
def health():
    # A Workflow has no .model — the model calls live in its agent nodes — so
    # this reports the shape rather than assuming an LlmAgent.
    return {
        "ok": True,
        "app": APP_NAME,
        "user": USER_ID,
        "agent": root_agent.name,
        "kind": type(root_agent).__name__,
        "model": getattr(root_agent, "model", None),
        "sessions": SESSION_DESC,
        "memory": os.environ.get("MEMORY_DIR", "./memory"),
        "venue": os.environ.get("VENUE_URL", ""),
    }


if __name__ == "__main__":
    # From Chapter 4 on, root_agent is a Workflow rather than an LlmAgent, and a
    # graph has no model of its own — the model calls live in its agent nodes.
    kind = type(root_agent).__name__
    detail = getattr(root_agent, "model", None) or f"{kind} graph"
    # Fail here, not on the first tool call. venue.py has no localhost fallback,
    # so without this the server starts happily, the agent runs, and the first
    # venue call raises somewhere deep in a tool — which reads as "the agent is
    # broken" rather than "this terminal never sourced set_env.sh".
    if not os.environ.get("VENUE_URL"):
        print("[server] ✗ VENUE_URL is not set, so there is no venue to talk to.",
              flush=True)
        print("[server]   In this terminal:  . ./set_env.sh", flush=True)
        print("[server]   No venue yet?      ./deploy-venue.sh", flush=True)
        raise SystemExit(1)

    print(f"[server] agent    {root_agent.name} · {detail}", flush=True)
    print(f"[server] identity app={APP_NAME} user={USER_ID}", flush=True)
    print(f"[server] venue    {os.environ['VENUE_URL']}", flush=True)
    print(f"[server] sessions {SESSION_DESC}", flush=True)
    print(f"[server] memory   {type(memory_service).__name__ if memory_service else 'none'}", flush=True)
    print(f"[server] listening on http://127.0.0.1:{PORT}  (/wake, /trigger/wake, /task)", flush=True)
    print("[server] nothing will happen until something calls it. Ctrl-C to stop.", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
