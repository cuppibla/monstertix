# MonsterTix — Long-Running Agents on Google Cloud

A hands-on workshop on **long-running agents**, built with
[ADK 2](https://adk.dev) and Google Cloud. The guided course targets **60–75
minutes after setup**, with optional implementation reading and deployment.
That timing is a teaching estimate, not a measured classroom result.

> Get two tickets to The Midnight Signal in Amsterdam, for me and Sam.
> Sam can only do weekends, and we avoid the upper bowl. Save the task,
> wait in the queue, survive a restart, and buy inside the limit I confirm.

**Start in the workbench:** after the [pre-work](docs/PRE-WORK.md), run
`./workbench.sh` and open the printed URL. Each chapter has one page with the
next action, real results, and expandable code and records. The original
[detailed codelab](docs/CODELAB.md) remains available for self-study.

## The six chapters

| # | Core experiment | What proves it | Target time |
|---|---|---|---|
| 1 | Meet the ticket task; check the environment once | Model reply, agent and venue reachable | 3–5 min |
| 2 | Ask once; let a one-shot timer call again | Timer source and another invocation in the same session | 8–10 min |
| 3 | Read one trace; save an aisle preference; ask in one new session | Session A/B events beside the actual memory write and recall | 12–15 min |
| 4 | Queue, kill, restart and resume the same task | Same session and ticket; `ready_to_buy`; zero orders | 12–15 min |
| 5 | Confirm a limit; prepare the combined fault; resume once | `stale_plan`, two HTTP attempts, duplicate suppression, one matching order | 15–18 min |
| 6 | Watch an instructor's existing cloud task resume through Scheduler | Cloud task, trigger logs and matching venue order | 8–10 min |

The short route has **13 learning milestones**: 1 + 2 + 3 + 3 + 3 + one cloud
demonstration. Preparation and the human's two budget answers are real actions,
not extra lessons. Time ranges allow different teaching pacing.

**Session DB and Memory Service remain core material.** The course also keeps
the distinction between completed node records and interrupted nodes, human
authorization, live guards, and idempotency. SQL, Artifact Service details,
compaction and the LongRunningFunctionTool comparison expand in place. LRFT
is read-only comparison; it is not a loadable replacement experiment.

The six core URLs are `/step/meet`, `/step/wake`, `/step/remember`,
`/step/resume`, `/step/buy`, `/step/cloud`. Old `/step/buy/c` bookmarks land on
the corresponding core chapter. Original a/b/c exercises are at `/study/...`.
A new chapter deliberately loads a fresh code stage and resets live sessions,
seeded memory and venue state. The page explains this before preparation;
completed learning receipts and raw evidence survive in `runs/`.

Independent cloud deployment is an **optional 20–30 minute extension**, with
cleanup required if you create resources. The core cloud page does not deploy;
it can inspect an `AGENT_SERVICE_URL` and dispatch an existing Scheduler job.
A cloud task must have its own authorization. Local sessions are not migrated.

See [the guided-course implementation notes](docs/SIMPLIFIED-LAB.md) for the
state contract, boundaries, recovery and instructor walkthrough.

---

## Repo layout

```
setup.sh                 pre-work, one command: venv, project, APIs, .env, seed, Cloud SQL (background), venue
verify.sh                one screen of ticks. run it before you trust anything
workbench.sh             the workbench on :4800: start, stop, restart, fg
use-solution.sh N        load chapter N's code and reset the state around it (1..6)
deploy-venue.sh          your own mock venue on Cloud Run (setup.sh runs it)
setup-cloud-state.sh     Cloud SQL database + user + bucket; writes two URIs into .env
deploy-agent.sh          chapter 6: Cloud Run service, topic, push subscription → /trigger/wake, Scheduler job
destroy-agent.sh         chapter 6 clean-up (--all also drops Cloud SQL + the bucket)
destroy-venue.sh         tear the venue down
set_env.sh               source this in every new terminal
show-compaction.sh       prints the compaction summaries the dev UI does not show

agent/                   where students work. use-solution.sh writes here
  concert/               the agent package (agent.py tools.py memory.py venue.py config.py panel.py,
                         + nightly.py from chapter 4, + budget.py fence.py from chapter 5)
  main.py, Dockerfile,   chapter 6 only: the single-container entrypoint and its
  requirements.txt,      dependencies, plus a copy of monstertix/ so the page
  monstertix/            ships inside the container

monstertix/              the MonsterTix page, its server, and the clock (every chapter)
  server.py              your own Runner behind your own endpoints, on :8090
  handlers.py            what the endpoints DO — shared with agent/main.py
  clock.py               the local stand-in for Cloud Scheduler
  index.html             the page a person actually uses

venue/                   the mock ticket seller. its own Cloud Run service
  app.py                 events, seat maps, queue, purchase, and every panel button
  static/                the control panel, the poster, the theme tune

solutions/               one folder per chapter: step1_meet … step6_cloud
content/                 the workbench's chapters: step.yaml + markdown per section
workbench/               the workbench server: processes, checks, the task card, the proxy
web/                     the workbench page (React). Built by workbench.sh
tests/                   one folder per chapter, mirroring solutions/
seed/                    the two-days-ago session and the starting memory file
docs/
  PRE-WORK.md            what a student does before class
  CODELAB.md             the course, as a codelab
  INSTRUCTOR.md          runbook: minute plan, checkpoint answers, what breaks, clean-up
  DRYRUN.md              rehearsal checklist with the evidence to collect
  build-preview.py       renders CODELAB.md → preview.html
```

### How a chapter is loaded

`./use-solution.sh N` (N = 1…6) copies one solution folder into place:

| In `solutions/stepN_*/` | Goes to | Why |
|---|---|---|
| `concert/` | `agent/concert/` | the agent package; `adk web agent` reads that directory |
| `monstertix/` | `./monstertix/` | the page, server and clock; `python -m monstertix.server` finds them at the root |
| `main.py`, `Dockerfile`, `requirements.txt`, `monstertix/` *(chapter 6 only)* | `agent/` | `agent/` is the build context `deploy-agent.sh` uploads |

**Every chapter ships both `concert/` and `monstertix/`**, so loading any
chapter directly gives a consistent pair. Chapter 6's `concert/` is byte for
byte chapter 5's.

Unless you pass `--keep`, it also resets the state around the code:
`memory/userx.md` back to `seed/memory/default.md`, `sessions.db` rebuilt with
the `two-days-ago` conversation, `artifacts/` emptied. It refuses to delete
`sessions.db` while something holds :8000; `--force` overrides that. The venue
is never touched — press **RESET THE VENUE** on the panel for that.

The workbench's **Load step N** button does the same thing: stop the agent,
RESET THE VENUE, `./use-solution.sh N --force`, start the agent again. Its
*Reset the venue* variant (used in 5C) resets the venue only and keeps code,
sessions and memory, so the task under way keeps its session, ticket and
authorization.

### Three ports, and the workbench

| | |
|---|---|
| **:8000** | `adk web` — the development UI. State, Events, Artifacts, the graph. Not something you ship |
| **:8080** | the venue, when run locally. Deployed, it is `$VENUE_URL`; the panel is at `/panel` |
| **:8090** | `monstertix/server.py` — the page at `/`, `POST /wake`, `POST /trigger/wake`, `GET /task` |
| **:4800** | the workbench: one page per chapter, task controls, live venue and optional ADK drawer |

Tests use **:8099** with their own venue database, so a test run never resets
the venue you are teaching from.

### One identity everywhere

`app_name="concert"`, `user_id="user"` — in `adk web`, the MonsterTix server,
`main.py`, the seed and the workbench. `adk web` hardcodes `userId=user` and
has no user picker, so anything seeded under another id exists and is
invisible. `MEMORY_USER=userx` names the memory **file** (`memory/userx.md`)
and is not a user id.

---

## Setup

Students do this before class — the full walk-through is
[`docs/PRE-WORK.md`](docs/PRE-WORK.md). In short:

```bash
git clone <REPO_URL> ~/monstertix
cd ~/monstertix
./setup.sh          # project, APIs, venv, .env, seed, Cloud SQL in the background, venue, workbench
./verify.sh         # one screen of ticks
./use-solution.sh 1
```

`setup.sh` is safe to re-run: it reuses `.venv`, remembers the project in
`~/project_id.txt`, skips APIs already on, and never creates a second Cloud SQL
instance. Credentials are Vertex AI via Application Default Credentials. **No
API keys anywhere.**

```
GOOGLE_CLOUD_PROJECT=<theirs>
GOOGLE_CLOUD_LOCATION=global        # where the model is served
GOOGLE_CLOUD_REGION=us-central1     # where the services live
GOOGLE_GENAI_USE_VERTEXAI=true
ADK_MODEL=gemini-2.5-flash
```

> ⚠️ `-latest` model aliases are AI-Studio-only and 404 on Vertex. Pin the id.

Requirements: Python **3.11+** (ADK 2's `Workflow` needs it), `google-adk[db]
>= 2.6.2`, `gcloud`, and Node if the workbench page has to be built. Cloud
Shell has all of it.

---

## Laptop → cloud

Chapter 6 shows this as a diff, and the point is how little is in it:

| On a laptop | In the cloud | What changes |
|---|---|---|
| `--session_service_uri=sqlite+aiosqlite:///…/sessions.db` | Cloud SQL (`postgresql+asyncpg://…?host=/cloudsql/…`) | a connection string |
| `--artifact_service_uri=file://…/artifacts` | `gs://<bucket>/artifacts` | a URI |
| `memory/userx.md` | `gs://<bucket>/memory/userx.md` | `MEMORY_DIR` |
| `adk web` / `monstertix/server.py` | one Cloud Run service (`agent/main.py` + `Dockerfile`) | an entrypoint |
| `python -m monstertix.clock --trigger` | Cloud Scheduler → Pub/Sub → `/trigger/wake` | who sends the POST |

```
   the graph, its tools, budget.py, fence.py, the idempotency key:   UNCHANGED
```

`solutions/step6_cloud/concert/` is identical to `solutions/step5_buy/concert/`
(a test holds that in place). Credentials do not appear in the table because
they never change: ADC on the laptop, ADC on Cloud Run.

Deploying does **not** migrate anything. A task parked in your laptop's
`sessions.db` stays there. Chapter 6 creates a new task in the cloud and lets
the scheduler finish that one.

---

## Testing

```bash
./tests/run.sh            # offline, a few seconds
./tests/run.sh --live     # drives the real model; minutes, costs tokens
```

One folder per chapter, mirroring `solutions/`. Tests that need a model are
skipped unless `--live`. The suite includes the original chapter checks and guided-course integrity tests. See
[`tests/README.md`](tests/README.md) for what each chapter asserts.

---

## For instructors

- **[`docs/SIMPLIFIED-LAB.md`](docs/SIMPLIFIED-LAB.md)** — the current guided route and validation commands.
- **[`docs/INSTRUCTOR.md`](docs/INSTRUCTOR.md)** — the original extended 110 + 10 minute plan,
  model answers to every checkpoint, what breaks and how to tell an expected
  outcome from an environment fault, what to cut, the clean-up order.
- **[`docs/DRYRUN.md`](docs/DRYRUN.md)** — rehearse every section locally and
  collect the evidence it promises, including "start from chapter N" paths.

Rehearse at least once on a fresh clone. Most of what goes wrong in a room is
state left over from the last rehearsal, and `use-solution.sh` exists to make
that recoverable in one command.
