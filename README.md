# MonsterTix — Long-Running Agents on Google Cloud

A two-hour hands-on workshop on **long-running agents**, built with
[ADK 2](https://adk.dev) and Google Cloud.

One task runs through the whole course:

> Get two tickets to The Midnight Signal in Amsterdam, for me and Sam. We can
> only do weekends, and we will not sit in the upper bowl. The agent may stop
> running while it waits in the queue; when it is woken it checks the venue
> again and buys inside the limit I confirmed — "Two tickets, up to $250 each."
> In the end, a cloud timer finishes it.

Same two people, same city, same preferences in every chapter. What changes is
how much of the task the agent can finish without anyone at the keyboard.

**Students read [`docs/CODELAB.md`](docs/CODELAB.md)** and work in the
workbench. Everything below is for whoever runs or maintains the workshop.

---

## The four deep dives

Every framework got better at what goes in the prompt. None got better at being
awake. A chat assistant lives inside one turn; this task takes forty minutes
against a system you do not control. The course teaches four things a
long-running agent needs, and each one is a required reading inside the chapter
that exercises it:

| Deep dive | The question it answers | Where |
|---|---|---|
| **Memory** | Where is a fact kept, for how long, and how does it get into *this* run? | 3B, 3C |
| **Resumption** | After the process dies, what exactly comes back? | 4C |
| **Authority** | How is "they are comfortable around $200" different from "you may spend up to $250 tonight"? | 5A |
| **Reliability** | Inventory moved, the response never came, the retry fired — how many orders are there? | 5B, 5C |

Chapters 1 and 2 set the scene and prove that a prompt cannot start a run.
Chapter 6 moves the same agent to Cloud Run and lets Cloud Scheduler wake it.

---

## The six chapters

110 minutes of class, plus a 10-minute buffer. Installation, sign-in and the
slow resource creation happen **before class** — see
[`docs/PRE-WORK.md`](docs/PRE-WORK.md).

| # | Chapter | Sections | Students can… | Minutes |
|---|---|---|---|---|
| 1 | Meet MonsterTix | 1A The mission · 1B Your workspace | say what the task is, and where to watch the queue, the stock and the orders | 5 |
| 2 | Wake the Agent | 2A Prompt · 2B Caller | say who starts an invocation, and why no wording can | 10 |
| 3 | Remember What Matters | 3A Session DB · 3B Memory Service · 3C Services & lifetimes | trace a fact from storage into the current run; read a compaction summary | 25 |
| 4 | Pause, Restart, Resume | 4A Pause · 4B Kill & continue · 4C What resumed | kill the process mid-queue and prove the same ticket continues to *ready to buy* | 25 |
| 5 | Buy Within Agreed Limits | 5A Authority · 5B Check the world again · 5C Retry once | confirm an authorization, survive a sell-out, retry a failed response and still hold one order | 30 |
| 6 | Run It While You Sleep | 6A Move · 6B Cloud wake-up · 6C Explain & clean up | deploy, create a cloud task, let Scheduler resume it, tear it down | 15 |
| | Buffer | questions, repairs, catching up | | 10 |

Every section has the same shape: **the question → your turn → what you should
see → key code → checkpoint**. Optional material (prompt variants, triggering
compaction live, the `LongRunningFunctionTool` alternative, conditional budgets,
Cloud Trace, deep SQL) sits in a final *Reference & optional* section with time
and prerequisite labels, and never blocks the main line.

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
| **:4800** | the workbench: every section as a page, the processes as switches, the current task card |

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
skipped unless `--live`. Currently **62 passing, 7 skipped** offline. See
[`tests/README.md`](tests/README.md) for what each chapter asserts.

---

## For instructors

- **[`docs/INSTRUCTOR.md`](docs/INSTRUCTOR.md)** — the 110 + 10 minute plan,
  model answers to every checkpoint, what breaks and how to tell an expected
  outcome from an environment fault, what to cut, the clean-up order.
- **[`docs/DRYRUN.md`](docs/DRYRUN.md)** — rehearse every section locally and
  collect the evidence it promises, including "start from chapter N" paths.

Rehearse at least once on a fresh clone. Most of what goes wrong in a room is
state left over from the last rehearsal, and `use-solution.sh` exists to make
that recoverable in one command.
