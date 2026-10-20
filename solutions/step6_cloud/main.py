"""CHAPTER 6 · Run It While You Sleep — one container, two front doors.

This is the only file that differs between what you ran on your laptop and what
runs in Google Cloud, and none of it is about the agent.

    ┌─ Cloud Run: concert-you ─────────────────────────────────────┐
    │                                                              │
    │   /                MonsterTix, for a person                  │
    │   /wake            what that page posts to                   │
    │   /trigger/wake    what Cloud Scheduler reaches, via Pub/Sub │
    │   /task            what the page's banner reads              │
    │                                                              │
    │            one Runner, one session store, one graph          │
    └──────────────────────────────────────────────────────────────┘

`get_fast_api_app` does the heavy half: it discovers every agent package in
AGENTS_DIR, builds the session and artifact services from the same two URIs you
have been passing to `adk web` since Chapter 3, and mounts a Pub/Sub endpoint
per app at /apps/<app>/trigger/pubsub. It returns an ordinary FastAPI, so the
MonsterTix routes bolt straight onto it.

That built-in Pub/Sub endpoint is kept but NOT what the scheduler is wired to.
It mints a fresh session id on every message — right for "fire an agent at
something", wrong for "finish the thing you started". deploy-agent.sh points
the push subscription at /trigger/wake instead, which finds the session that is
waiting in the queue and tells it to check again. A session waiting for a
person is left alone: a timer is not that person.

Why one service and not two: the page and the agent are the same process, so the
browser calls `/wake` on its own origin. No CORS, no second deployment, no
service-to-service authentication, no network hop between them. Deploying them
apart would mean solving all four for no benefit.

Run it locally, exactly as the container will:

    uvicorn main:app --port 8080

Deploy it:

    ./deploy-agent.sh
"""

from __future__ import annotations

import os
import pathlib
import warnings

warnings.filterwarnings("ignore", message=r".*\[EXPERIMENTAL\].*")

from fastapi import Body                                          # noqa: E402
from fastapi.middleware.cors import CORSMiddleware                # noqa: E402
from fastapi.responses import FileResponse                        # noqa: E402
from google.adk.cli.fast_api import get_fast_api_app              # noqa: E402
from google.adk.cli.utils.service_factory import (                # noqa: E402
    create_artifact_service_from_options,
    create_session_service_from_options,
)
from google.adk.runners import Runner                             # noqa: E402

from concert import agent as concert_agent                        # noqa: E402
from monstertix import handlers                                   # noqa: E402

try:
    from concert.memory import memory_service                      # noqa: E402
except ImportError:                                                # pragma: no cover
    memory_service = None

HERE = pathlib.Path(__file__).parent
APP_NAME = handlers.APP_NAME
USER_ID = handlers.USER_ID
root_agent = concert_agent.root_agent
concert_app = getattr(concert_agent, "app", None)

# The same two URIs as `adk web`. On Cloud Run these are a Cloud SQL connection
# string and a gs:// bucket — set by setup-cloud-state.sh, passed by
# deploy-agent.sh. The defaults below are for running this file on your laptop.
#
# Set them. Trigger sessions default to in-memory, which means a 3am run that
# joins a queue has forgotten the ticket by the time anything wakes it.
SESSION_URI = os.environ.get(
    "SESSION_SERVICE_URI", f"sqlite+aiosqlite:///{HERE}/sessions.db"
)
ARTIFACT_URI = os.environ.get("ARTIFACT_SERVICE_URI", f"file://{HERE}/artifacts")

app = get_fast_api_app(
    agents_dir=str(HERE),
    web=False,                        # no dev UI in production
    session_service_uri=SESSION_URI,
    artifact_service_uri=ARTIFACT_URI,
    trigger_sources=["pubsub"],       # ← mounts /apps/<app>/trigger/pubsub (unused here)
    allow_origins=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The same services, built from the same URIs, using ADK's own factories.
#
# `get_fast_api_app` does not hand its services back, so this builds a second
# object against the SAME database and bucket. That is fine and not a trick: a
# session service is a client, not a cache — two of them pointed at one Cloud
# SQL instance see identical data. What would NOT be fine is importing
# monstertix/server.py to get one, because that module builds its own from
# ITS defaults, which on a container means SQLite on a filesystem that is
# destroyed when the instance goes away.
session_service = create_session_service_from_options(
    base_dir=HERE, session_service_uri=SESSION_URI
)
artifact_service = create_artifact_service_from_options(
    base_dir=HERE, artifact_service_uri=ARTIFACT_URI
)

_services = dict(
    session_service=session_service,
    artifact_service=artifact_service,
    memory_service=memory_service,
)
# The App carries resumability and compaction; a bare agent does not. Same
# choice server.py makes, for the same reason.
if concert_app is not None:
    runner = Runner(app=concert_app, **_services)
else:
    runner = Runner(agent=root_agent, app_name=APP_NAME, **_services)

MONSTERTIX = pathlib.Path(
    os.environ.get("MONSTERTIX_DIR", HERE / "monstertix")
)


def _log(message: str) -> None:
    print(message, flush=True)


@app.get("/")
def chat_ui():
    """MonsterTix. The surface that survives leaving your laptop."""
    return FileResponse(MONSTERTIX / "index.html")


@app.post("/wake")
async def wake(payload: dict = Body(default={})):
    """What the page posts to. Identical logic to Chapter 2's server."""
    return await handlers.wake(
        runner, session_service, APP_NAME, USER_ID,
        message=handlers.message_from(payload),
        session_id=handlers.session_id_from(payload),
        log=_log,
    )


@app.post("/trigger/wake")
async def scheduled_wake(payload: dict = Body(default={})):
    """What Cloud Scheduler reaches, via Pub/Sub push.

    The body is a Pub/Sub envelope — `{"message": {"data": ...}, "subscription":
    ...}` — and none of it is read. A timer has nothing to say except that time
    has passed. `resume_waiting` finds the newest session parked on a QUEUE
    wait and answers it; a session parked on a person's question is reported,
    not resumed. Returning 200 either way is deliberate: a 5xx would make
    Pub/Sub retry, and retrying "there is nothing to do" is noise.
    """
    return await handlers.resume_waiting(
        runner, session_service, APP_NAME, USER_ID,
        session_id=handlers.session_id_from(payload),
        allow=("queue",),
        log=_log,
    )


@app.get("/task")
async def task(session_id: str | None = None):
    """The current task, from session state. The page's banner reads this."""
    return await handlers.task_summary(session_service, APP_NAME, USER_ID, session_id)


@app.get("/session/{session_id}/messages")
async def session_messages(session_id: str, since: float = 0.0):
    """Everything the agent has said in this session since `since`."""
    return await handlers.session_messages(
        session_service, APP_NAME, USER_ID, session_id, since
    )


@app.post("/session/new")
def new_session():
    return {"session_id": handlers.new_session_id()}


@app.post("/admin/wipe")
async def wipe(payload: dict = Body(default={})):
    """Delete every session and the memory file.

    Public, because the service is deployed --allow-unauthenticated so Pub/Sub
    and a browser can both reach it. Anyone with the URL can empty this agent.
    That is acceptable for a workshop and is not acceptable for anything else —
    in a real deployment this route needs auth, or should not exist.
    """
    return await handlers.wipe(session_service, APP_NAME, USER_ID, log=_log)


# `get_fast_api_app` already answers /health with {"status": "ok"}, and routes
# match in the order they were added — so ours would never be reached. The page
# reads `sessions` and `memory` off this route for the wipe dialog, so replace
# theirs rather than add a second one.
app.router.routes[:] = [
    r for r in app.router.routes if getattr(r, "path", None) != "/health"
]


@app.get("/health")
def health():
    return {
        "ok": True,
        "app": APP_NAME,
        "user": USER_ID,
        "agent": root_agent.name,
        "kind": type(root_agent).__name__,
        "model": getattr(root_agent, "model", None),
        # The password is in this URI. Show the host part only.
        "sessions": SESSION_URI.split("@")[-1] if "@" in SESSION_URI else SESSION_URI,
        "memory": os.environ.get("MEMORY_DIR", "./memory"),
        "venue": os.environ.get("VENUE_URL", ""),
    }
