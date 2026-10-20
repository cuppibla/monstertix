# Before class: the pre-work

Everything here happens before the workshop starts. Budget **30–40 minutes**,
most of it waiting for Google Cloud. Class begins at Chapter 1 with the rig
already working, and there is no time in the 110 minutes to repair a setup.

Do it the day before, not the morning of. If something fails you want a night
to ask about it.

---

## What you need

- A Google Cloud project **with billing enabled**, where your account can enable
  APIs and deploy to Cloud Run. If your lab platform hands you one, it is
  already exported as `GOOGLE_CLOUD_PROJECT`.
- Python **3.11 or newer**, `git`, and the `gcloud` CLI.
- **Cloud Shell has all of that.** It is the recommended place to run the
  workshop; see the Cloud Shell notes at the end.

---

## 1. Clone and run setup

```bash
cd ~
git clone <REPO_URL> monstertix
cd ~/monstertix
./setup.sh
```

If it has no project to go on it asks once:

```
  No Google Cloud project found for this workshop.
  Press Enter and one gets created for you (long-running-… , with a
  billing account attached), or type the id of one you already have.
```

Then it does the following, in order, and prints a line per step:

| Step | What it does | How long |
|---|---|---|
| **venv** | creates `.venv` (with `uv` if present) and installs `requirements.txt` | 1 min |
| **.env** | copies `.env.example` to `.env`; your answers are remembered there | — |
| **project** | picks the project (`PROJECT_ID=…`, your platform's export, `~/project_id.txt`, or `.env`), validates it | seconds |
| **auth** | `gcloud auth application-default login` only if you have no credentials | a browser round-trip |
| **quota** | sets the project as the ADC quota project | seconds |
| **apis** | enables the ten the course uses: `aiplatform`, `run`, `cloudbuild`, `artifactregistry`, `storage`, `pubsub`, `cloudscheduler`, `cloudtrace`, `logging`, `sqladmin` — only the missing ones | 1 min |
| **model** | one real call to Gemini, so a bad project or model id fails here and not in class | seconds |
| **seed** | builds the `two-days-ago` session (13 events) that Chapter 3 opens | seconds |
| **cloudsql** | starts a Postgres instance `workshop-sessions` **in the background** | 8–12 min, unattended |
| **venue** | deploys your own mock ticket seller to Cloud Run with `./deploy-venue.sh` | 1–2 min |
| **workbench** | builds the page if needed and starts it on :4800 | 1–3 min the first time |

The last lines tell you where your venue is:

```
✓ setup complete.

  your venue:  https://venue-you-xxxx.us-central1.run.app/panel
               keep this tab open all day. It is where you press the buttons,
               and where you check whether the agent actually did what it said.

  check it:    ./verify.sh
```

**Every step is safe to re-run.** `setup.sh` reuses `.venv`, remembers the
project, skips APIs that are already on, redeploys the venue over itself, and
will not create a second Cloud SQL instance. When in doubt, run it again.

### Why some of it is pre-work

- **Cloud SQL takes eight to twelve minutes to build.** Nothing before Chapter 6
  needs it, so `setup.sh` starts it now and walks away. The log is
  `~/.cloudsql-create.log`.
- **Enabling APIs propagates slowly.** The first Cloud Run deploy after enabling
  `run` and `cloudbuild` can fail with *"API has not been used in project…"*.
  `setup.sh` retries once after 30 s; if the venue still did not deploy, wait a
  minute and run `./deploy-venue.sh`.
- **A brand-new project can say `403 PERMISSION_DENIED` from Vertex AI** for a
  few minutes. `setup.sh` says so and continues. Run `./verify.sh` again later.
- **Thirty people deploying at 9am share one Cloud Build queue.** Done the night
  before, nobody waits on anybody.

---

## 2. Verify

```bash
cd ~/monstertix
./verify.sh
```

One screen of ticks. All of these should be green:

```
  Checking the rig

  ✓ virtualenv                         .venv
  ✓ adk installed                      adk, version 2.x
  ✓ adk 2 apis                         App + ResumabilityConfig
  ✓ workflow graphs                    Workflow + node
  ✓ async sqlite drivers               sqlalchemy + aiosqlite + greenlet
  ✓ project                            your-project-id
  ✓ vertex ai                          no API keys anywhere
  ✓ credentials (ADC)                  you@example.com
  ✓ model call                         gemini-2.5-flash · answered: OK
  ✓ seeded session                     two-days-ago · 13 events
  ✓ memory file                        ./memory/userx.md · N lines of memory
  ✓ solutions                          6 chapters, each with concert/ + monstertix/
  ✓ agent/concert                      loaded — ./use-solution.sh to change chapter
  ✓ region                             us-central1  (services)
  ✓ venue                              https://venue-you-xxxx.us-central1.run.app
  ✓ workbench page                     web/dist/index.html built

  Ready. Cloud SQL is still building in the background and nothing
  before Chapter 6 needs it.
```

Each ✗ row prints the command that fixes it. The usual ones:

| Row | Fix |
|---|---|
| `credentials (ADC)` | `gcloud auth application-default login`, then `./setup.sh` again |
| `model call` | a new project still switching Vertex AI on — wait a few minutes. Or a `-latest` model id in `.env`; set `ADK_MODEL=gemini-2.5-flash` |
| `seeded session` | `.venv/bin/python -m seed.session` |
| `agent/concert` | `./use-solution.sh 1` (see the next step) |
| `venue` | `./deploy-venue.sh`, and give Cloud Run a minute to start it from cold |
| `workbench page` | `./workbench.sh` builds it; it needs `npm`. Without Node the terminal path still works |

### Load Chapter 1

```bash
./use-solution.sh 1
```

This puts Chapter 1's `concert/` into `agent/` and `monstertix/` at the root,
and resets memory, sessions and artifacts to their starting state. You will run
it (or press **Load step N** in the workbench) at the start of every chapter.

---

## 3. Open the workbench

`setup.sh` started it. If not, or after a `git pull`:

```bash
./workbench.sh            # start in the background (log: runs/workbench.log)
./workbench.sh restart    # after a pull: rebuilds the page if it changed
./workbench.sh stop       # stop it, and everything it started
./workbench.sh fg         # in this terminal; Ctrl-C stops everything
```

Open **http://localhost:4800** — in Cloud Shell, **Web Preview → Change port →
4800**. You should see Chapter 1 and, on the left, your live venue panel. Press
**Load step 1** once so you have seen what it does: it stops the agent, presses
RESET THE VENUE, runs `./use-solution.sh 1 --force`, and starts the agent again.

> **4800 is not in Web Preview's quick list.** The menu offers 8080 and a few
> others; pick **Change port** and type `4800` yourself. Choosing the default
> 8080 opens a tab with nothing behind it (the venue is on Cloud Run, not on
> 8080 of your Cloud Shell).

> **`Unable to forward your request to a backend` / `Couldn't connect to a
> server on port 4800`?** The workbench was not up yet when the tab opened —
> Web Preview only forwards to a port something is already listening on.
> `./workbench.sh` prints its link only once the port answers; if it has, just
> reload the tab. From a terminal, `curl -s localhost:4800/api/env` answers
> with your project and venue when it is ready.

Three things to look at, so they are not new on the day:

| Where | What it is |
|---|---|
| **the section** | the reading, a file explorer that marks what this chapter changed, the numbered "Your turn", and *Watch* checks that tick on their own |
| **under each "Your turn"** | the app that card uses — the ADK web UI, the venue panel, the MonsterTix page — framed through the workbench so one port is enough. The process's switch, **Restart**, **kill -9** and its log are at the card's top right |
| **the task card** | a read-only summary of the current task: session, what it is paused on, queue ticket, authorization, last order, and a **Resume current task** button |

---

## 4. The terminal path (optional, but know it exists)

Everything in the workbench can be done from terminals. Every new terminal
starts with:

```bash
cd ~/monstertix
. ./set_env.sh
```

which activates the venv, loads `.env`, and exports `$WORKSHOP`, `$VENUE_URL`,
`MEMORY_DIR` and `MEMORY_USER`. It prints what it set. Then:

```bash
# terminal 1 — the ADK web UI, with the two storage flags every chapter uses
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"

# terminal 2 — the MonsterTix server (chapter 2 onwards)
python -m monstertix.server

# terminal 3 — the clock (chapter 2 and chapter 6's rehearsal)
python -m monstertix.clock --in 10
```

Stop `adk web` (Ctrl-C) before `./use-solution.sh N`; it refuses to delete
`sessions.db` under a running process unless you pass `--force`.

---

## 5. The night before: a checklist

```
[ ] ./verify.sh is all green
[ ] the venue panel opens: $VENUE_URL/panel shows 8 shows, all seats available
[ ] the workbench opens on :4800 and Load step 1 completes
[ ] in the ADK web UI (the agent card in 1B) the dropdown shows `concert`
    and the session list includes `two-days-ago`
[ ] Cloud SQL finished:
        gcloud sql instances describe workshop-sessions --format='value(state)'
    prints RUNNABLE. If it is still PENDING_CREATE, leave it; check again later
[ ] recommended: run ./setup-cloud-state.sh once RUNNABLE. It creates the
    database, the user and the bucket and writes two URIs into .env, so
    Chapter 6 is a deploy and not a provisioning step. Safe to re-run
[ ] you know which terminal/tab is which: workbench :4800, venue panel, and a
    terminal in ~/monstertix with . ./set_env.sh sourced
```

If you want to see the whole thing end to end before class, [`CODELAB.md`](CODELAB.md)
is the course; nothing in it needs an instructor present.

---

## Cloud Shell notes

- **Web Preview** is how you reach ports: top-right → *Change port* → 4800 for
  the workbench. The workbench proxies the ADK web UI, the venue panel and the
  MonsterTix page, so 4800 is the only port you need to preview. Nothing in
  the course asks you to preview 8000, 8080 or 8090 directly.
- **It idles out after about an hour** and the VM can restart. `~/monstertix`
  is in your home directory and survives, and so does `sessions.db`. Run
  `./workbench.sh` again (it is `nohup`'d, so closing the terminal tab alone
  does not stop it). A parked task is still parked — Chapter 4 is exactly
  about this.
- **`adk: command not found`** means a new tab without the venv:
  `. ./set_env.sh`.
- **Disk.** The venv and the workbench's `node_modules` need about 300 MB.
  Cloud Shell's 5 GB is plenty unless other labs already filled it;
  `./verify.sh` has a `disk` row, and Cloud Shell itself warns at 95 %.
  `du -sh ~/* | sort -h` finds what to remove.
- **Billing.** Cloud Run scales to zero, so an idle venue costs nothing. The
  Cloud SQL instance (`db-f1-micro`) and the bucket keep billing until Chapter
  6's `./destroy-agent.sh --all`. If you set up and then cannot attend, run
  `./destroy-agent.sh --all && ./destroy-venue.sh`.

---

## If you are stuck

```bash
./setup.sh            # safe to re-run: fixes auth, APIs, .env, seed, venue
./verify.sh           # says which row is wrong and what fixes it
./deploy-venue.sh     # redeploy the venue on its own
./workbench.sh restart
```

Bring the output of `./verify.sh` to class if anything is still red. The
instructor runbook has a repair for every row.
