Everything so far ran on this machine: `adk web` or the MonsterTix server on
`:8090`, `sessions.db` next to the code, `memory/userx.md`, a folder of
artifacts, and `clock.py` in a terminal. Close the laptop and all five stop.
A task that parks for forty minutes needs a runtime that does not sleep,
storage that outlives any one process, and a clock somebody else runs.

What has to change to get there — and, more to the point, what does not?

:::exercise id="run"
:::figure src="/docs-img/overview.png" caption="Where each piece lands: the Runner and the graph in one Cloud Run service, sessions in Cloud SQL, memory and artifacts in Cloud Storage, the venue on its own Cloud Run service, and Cloud Scheduler as the clock."
:::
## Local and cloud, side by side

| | On your laptop | On Cloud Run |
|---|---|---|
| **Entry point** | `adk web` (`:8000`) or `python -m monstertix.server` (`:8090`) | `agent/main.py` — one FastAPI serving the page, `/wake`, `/trigger/wake`, `/task` |
| **Session Service** | `sqlite+aiosqlite:///…/sessions.db` | **Cloud SQL** (Postgres) — `postgresql+asyncpg://…?host=/cloudsql/…` |
| **Memory Service** | `memory/userx.md` | the same file in a **Cloud Storage** bucket (`MEMORY_DIR=gs://…/memory`) |
| **Artifact Service** | `file://…/artifacts` | `gs://…/artifacts` |
| **The clock** | `python -m monstertix.clock` → `POST /wake` | **Cloud Scheduler** → Pub/Sub topic → push subscription → `POST /trigger/wake` |
| **`concert/`** | chapter 5 | **unchanged** — byte-for-byte chapter 5 |

The diff is a new entrypoint, a container, and configuration. The agent, the
graph, the guard and the idempotency key are the files you finished chapter 5
with.

:::code path="agent/main.py" highlight="^SESSION_URI = os\.environ\.get|^ARTIFACT_URI = os\.environ\.get|session_service_uri=SESSION_URI|artifact_service_uri=ARTIFACT_URI"
:::

`get_fast_api_app` builds the session and artifact services from the same two
URIs you have been passing to `adk web` since chapter 3. On Cloud Run those
URIs are a Postgres connection string and a bucket — set by
`setup-cloud-state.sh` in the setup steps below, passed by `deploy-agent.sh`. The
defaults in the file are for running `main.py` on a laptop.
:::

## Why the files cannot come with you

A Cloud Run container has a writable filesystem, so nothing errors when the
agent writes to it. But that filesystem belongs to **one instance**, and Cloud
Run starts and stops instances as traffic comes and goes. When yours stops,
the disk goes with it. Picture the graph joining a queue at 3am, writing the
ticket to a SQLite file in `/tmp`, and finding the file empty when the
scheduler wakes it. No error, no crash — an agent that has forgotten.

`deploy-agent.sh` now stops if the cloud session database or bucket is missing.
Run the setup commands below before deploying; this chapter requires durable storage.

:::task id="cloud-setup"
:::

:::warn
**Deploying does not migrate the task.** The card above is read from the
local `sessions.db`; it still shows the chapter 5 task you ran on this
machine. The cloud agent has its own session store in Cloud SQL, and it is
empty until you create a task there. That is what the next section does: a
new task, created in the cloud, finished by the scheduler.
:::

## Key code: one container, two front doors

:::code path="agent/main.py" highlight="web=False|trigger_sources=\[\x22pubsub\x22\]|@app\.post\(\x22/trigger/wake\x22\)|allow=\(\x22queue\x22,\)"
:::

`main.py` mounts the MonsterTix routes on the FastAPI that `get_fast_api_app`
returns. No dev UI (`web=False`); the page is the surface a person gets. Two
doors wake the run:

| Route | Who calls it | What it does |
|---|---|---|
| `POST /wake` | the page | answers whatever the session is parked on with your message |
| `POST /trigger/wake` | Pub/Sub, on the scheduler's behalf | `resume_waiting(allow=("queue",))` — finds the newest session parked on a **queue** wait and tells it to check again. A session waiting for a person is reported, not resumed |

`trigger_sources=["pubsub"]` also mounts ADK's own `/apps/concert/trigger/pubsub`.
It is kept and **not** what the scheduler is wired to: it mints a fresh session
id on every message, which is right for "fire an agent at something" and wrong
for "finish the thing you started".

:::code path="agent/Dockerfile" highlight="CMD exec uvicorn main:app"
:::

:::code path="agent/requirements.txt" highlight="^asyncpg|^google-cloud-storage"
:::

Ordinary `python:3.12-slim` and uvicorn. `asyncpg` because ADK drives
SQLAlchemy through its asyncio extension, so a Cloud SQL session store needs
the async driver; `google-cloud-storage` because the memory file and the
artifacts become objects in a bucket.

:::key
Two URIs and one environment variable moved. The agent did not.
:::

:::checkpoint
**The deploy finished and the health check answers. Why is the task card on this page still showing yesterday's local task?**
:::answer
Because a deploy ships code, not state. `agent/` was built into a container
and started with `SESSION_SERVICE_URI` pointing at Cloud SQL — a database
that has never seen your laptop's `sessions.db`. The task card reads the local
file, so it still shows the local task; the cloud service reads Postgres, so
it has no task at all. Moving an in-flight task would mean copying its
session rows, its ticket and its authorization across — nothing in this
chapter does that, on purpose. The cloud task is created in the cloud.
:::
:::
