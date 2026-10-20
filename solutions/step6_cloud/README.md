# Chapter 6 · Run It While You Sleep

Chapter 5's `concert/` package, byte for byte, plus the files that make it a
Cloud Run service. Load with `./use-solution.sh 6`.

```
concert/            identical to solutions/step5_buy/concert (a test holds this)
main.py             one container, two front doors: the MonsterTix page and /wake for a
                    person, /trigger/wake for the scheduler, /task for the banner.
                    get_fast_api_app(web=False, session_service_uri, artifact_service_uri,
                    trigger_sources=["pubsub"]) plus the same handlers as server.py
Dockerfile          python:3.12-slim + uvicorn; nothing ADK-specific
requirements.txt    adds asyncpg (Cloud SQL) and google-cloud-storage (the bucket)
monstertix/         the same page, handlers and clock — the page ships inside the container
```

`./use-solution.sh 6` copies `main.py`, `Dockerfile`, `requirements.txt` and a
copy of `monstertix/` into `agent/`, which is the build context
`./deploy-agent.sh` uploads. Only where things run and where they are kept
changes:

```
sessions    sessions.db  →  Cloud SQL     SESSION_SERVICE_URI = postgresql+asyncpg://…?host=/cloudsql/…
artifacts   artifacts/   →  gs://bucket   ARTIFACT_SERVICE_URI
memory      memory/      →  gs://bucket   MEMORY_DIR
the clock   clock.py     →  Cloud Scheduler → Pub/Sub push → /trigger/wake
```

The push subscription points at `/trigger/wake`, not ADK's built-in
`/apps/concert/trigger/pubsub`: the built-in route mints a fresh session per
message, which would start a second task instead of finishing the parked one.
`handlers.resume_waiting(allow=("queue",))` resumes a `queue:` wait and leaves
a `budget:` wait for the person.

## Run it by hand

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh 6
./setup-cloud-state.sh        # once: database, user, bucket → two URIs in .env
./deploy-agent.sh             # service, topic, service account, push subscription, scheduler job
```

Then open the printed URL, create the task on the page (two tickets, confirm
*Two tickets, up to $250 each.*), press SKIP THE WAIT on the venue panel, and:

```bash
gcloud scheduler jobs run presale-<you> --location=$GOOGLE_CLOUD_REGION
gcloud run services logs read concert-<you> --region=$GOOGLE_CLOUD_REGION --limit=50
curl -s $AGENT_SERVICE_URL/task
```

Locally, the same container entrypoint: `cd agent && uvicorn main:app --port 8080`
(it falls back to a local `sessions.db` and `artifacts/` next to `main.py`).
The same route, rehearsed against `monstertix/server.py`:
`python -m monstertix.clock --in 10 --trigger`.

Clean up: `./destroy-agent.sh` (schedule → subscription → topic → service),
`--all` for Cloud SQL and the bucket too.

Tests: `./tests/run.sh tests/step6_cloud` checks the package is chapter 5's
and still loads as the graph. The deployable files and the cloud path are
verified by hand (`DRYRUN.md`, chapter 6).
