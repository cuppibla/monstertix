#!/usr/bin/env bash
# Chapter 6 · Run It While You Sleep — put your agent on Cloud Run, and give it
# an alarm clock.
#
#     ./use-solution.sh 6        first: puts main.py, Dockerfile, requirements.txt
#                                and monstertix/ into agent/
#     ./setup-cloud-state.sh     then: Cloud SQL database + bucket (once)
#     ./deploy-agent.sh          this
#
# Five things, in order:
#   1. deploy agent/ to Cloud Run
#   2. a topic for Cloud Scheduler to publish to
#   3. a service account Pub/Sub can push as
#   4. a push subscription: topic → your agent's /trigger/wake
#   5. a Scheduler job that publishes on a cron
#
# Each student gets their own service, named after them, exactly like the venue.
# Re-running is safe: every step creates-or-updates.
set -euo pipefail
cd "$(dirname "$0")"

_shell_region="${GOOGLE_CLOUD_REGION:-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$_shell_region" ] && export GOOGLE_CLOUD_REGION="$_shell_region"

PROJECT="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT — run ./setup.sh}"
REGION="${AGENT_REGION:-${GOOGLE_CLOUD_REGION:-us-central1}}"

WHO=$(gcloud config get-value account 2>/dev/null | cut -d@ -f1 \
      | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/-*$//' | cut -c1-24)
SERVICE="${AGENT_SERVICE:-concert-${WHO:-student}}"
TOPIC="${PRESALE_TOPIC:-presale-${WHO:-student}}"
SA="concert-trigger"
CRON="${PRESALE_CRON:-0 3 * * *}"

# agent/ has to be the Chapter 6 layout: the concert package plus the
# container's entrypoint plus a copy of the page. use-solution.sh 6 puts all of
# it there; anything else is an earlier chapter's agent/, which has no main.py.
for f in agent/main.py agent/Dockerfile agent/requirements.txt agent/monstertix/index.html agent/concert/agent.py; do
  if [ ! -f "$f" ]; then
    echo "✗ $f is missing. Load Chapter 6 first:"
    echo ""
    echo "      ./use-solution.sh 6"
    echo ""
    exit 1
  fi
done
case "${VENUE_URL:-}" in
  ""|*127.0.0.1*|*localhost*)
    echo "✗ VENUE_URL is '${VENUE_URL:-}'. A Cloud Run agent cannot reach a venue on"
    echo "  your laptop. Deploy one (./deploy-venue.sh writes the URL into .env)."
    exit 1 ;;
esac

# Durable state, or an honest warning. A Cloud Run container's filesystem is
# destroyed when the instance goes away, so sqlite in /tmp is a session store
# that forgets — silently, overnight, exactly when nobody is watching.
if [ -n "${CLOUD_SESSION_SERVICE_URI:-}" ]; then
  SESSION_URI="$CLOUD_SESSION_SERVICE_URI"
  ARTIFACT_URI="${CLOUD_ARTIFACT_SERVICE_URI:?run ./setup-cloud-state.sh}"
  SQL_FLAG=(--add-cloudsql-instances "${SQL_CONNECTION_NAME:?run ./setup-cloud-state.sh}")
  echo "→ state    Cloud SQL + $ARTIFACT_URI"
else
  SESSION_URI="sqlite+aiosqlite:////tmp/sessions.db"
  ARTIFACT_URI="gs://none"
  SQL_FLAG=()
  echo "⚠ state    sqlite in /tmp — this DIES with the container."
  echo "           Run ./setup-cloud-state.sh first for a real database."
fi

echo "→ project  $PROJECT"
echo "→ region   $REGION"
echo "→ service  $SERVICE"
echo "→ topic    $TOPIC"
echo ""

# 1. The agent. Cloud Run or GKE only — Agent Runtime does not accept scheduled
#    or event-driven triggers, which is the whole point of this chapter.
#
#    SESSION_SERVICE_URI matters more than it looks. Without it sessions live
#    in the container, so a 3am run that joins a queue has forgotten its ticket
#    by the time anything wakes it.
#
#    The GOOGLE_* vars are not optional either. Credentials come free on Cloud
#    Run — the service account is the identity — but the genai client still has
#    to be told which project and location to call Vertex in, and config.py
#    exits at import if they are missing. A container that exits at import looks
#    like "failed to listen on PORT", which is a long way from the real cause.
#
#    ^|^ is gcloud's alternative delimiter. The default is a comma, which the
#    session URI would survive — but `@` would NOT, because the URI contains one
#    between the password and the host. Splitting on it silently truncates the
#    URI to `postgresql+asyncpg://user:password` and the container dies at
#    startup with an unrelated-looking int() error.
#
#    `gcloud run deploy --source`, not `adk deploy cloud_run`: adk deploy
#    generates its own entrypoint, which serves the agent and nothing else — no
#    MonsterTix, no /wake, no /trigger/wake. It has no flag for supplying your
#    own. So this builds agent/ with its own Dockerfile, which is the same
#    command the venue has used since the pre-work.
#
#    Nothing in here says "unattended". A run that stops on a person's question
#    stays stopped until that person answers; the scheduler only resumes queue
#    waits. That is deliberate — see handlers.resume_waiting.
echo "→ deploying (3-4 minutes)"
gcloud run deploy "$SERVICE" \
  --source agent \
  --project "$PROJECT" --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "^|^SESSION_SERVICE_URI=$SESSION_URI|ARTIFACT_SERVICE_URI=$ARTIFACT_URI|VENUE_URL=$VENUE_URL|MEMORY_USER=${MEMORY_USER:-userx}|GOOGLE_CLOUD_PROJECT=$PROJECT|GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global}|GOOGLE_GENAI_USE_VERTEXAI=true|ADK_MODEL=${ADK_MODEL:-gemini-2.5-flash}" \
  "${SQL_FLAG[@]}" \
  --quiet

# memory/userx.md becomes gs://<bucket>/memory/userx.md. Same file, same
# format; MarkdownMemoryService reads either.
if [ -n "${STATE_BUCKET:-}" ]; then
  gcloud run services update "$SERVICE" \
    --project "$PROJECT" --region "$REGION" \
    --update-env-vars MEMORY_DIR="$STATE_BUCKET/memory" --quiet >/dev/null
  echo "→ env      state URIs, VENUE_URL, MEMORY_DIR=$STATE_BUCKET/memory"
else
  echo "→ env      state URIs, VENUE_URL  (memory stays in the container — no bucket)"
fi

URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" \
        --region "$REGION" --format='value(status.url)')
[ -n "$URL" ] || { echo "✗ deployed, but could not read the service URL"; exit 1; }
echo "→ agent    $URL"

# 2. The topic Scheduler publishes to.
gcloud pubsub topics create "$TOPIC" --project "$PROJECT" 2>/dev/null \
  && echo "→ topic    $TOPIC created" || echo "→ topic    $TOPIC exists"

# 3. A service account Pub/Sub can push as, allowed to invoke the agent.
gcloud iam service-accounts create "$SA" --project "$PROJECT" \
  --display-name="Concert presale trigger" 2>/dev/null || true
SA_EMAIL="$SA@$PROJECT.iam.gserviceaccount.com"

gcloud run services add-iam-policy-binding "$SERVICE" \
  --project "$PROJECT" --region "$REGION" \
  --member="serviceAccount:$SA_EMAIL" --role=roles/run.invoker --quiet >/dev/null
echo "→ iam      $SA_EMAIL may invoke $SERVICE"

# 4. topic → /trigger/wake.
#
#    NOT /apps/concert/trigger/pubsub. ADK's built-in trigger mints a fresh
#    session id and a user id derived from the subscription name, so every fire
#    starts a conversation from nothing — no queue ticket, no authorization, no
#    memory of what it was doing. It would start a second task instead of
#    finishing the first.
#
#    /trigger/wake finds the newest session parked on a QUEUE wait and tells it
#    to check again. A session waiting for a person is reported, not resumed.
ENDPOINT="$URL/trigger/wake"
if gcloud pubsub subscriptions create "$TOPIC-push" --project "$PROJECT" \
     --topic="$TOPIC" \
     --push-endpoint="$ENDPOINT" \
     --push-auth-service-account="$SA_EMAIL" 2>/dev/null; then
  echo "→ push     → $ENDPOINT"
else
  # It already exists — so UPDATE it. `create` failing quietly used to leave an
  # old push endpoint in place for ever, which meant a redeploy that changed the
  # route looked like it worked and silently kept delivering to the old one.
  gcloud pubsub subscriptions update "$TOPIC-push" --project "$PROJECT" \
    --push-endpoint="$ENDPOINT" \
    --push-auth-service-account="$SA_EMAIL" >/dev/null 2>&1 \
    && echo "→ push     → $ENDPOINT  (updated)" \
    || echo "→ push     ✗ could not update $TOPIC-push"
fi

# 5. The alarm clock. This is clock.py from Chapter 2, run by Google instead of
#    by your terminal: it has retries, a timezone, and it does not stop when
#    you close your laptop. The message body is not read by anything — the
#    route it reaches only needs to know that time has passed.
if gcloud scheduler jobs describe "$TOPIC" --project "$PROJECT" --location="$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update pubsub "$TOPIC" --project "$PROJECT" \
    --location="$REGION" --schedule="$CRON" --time-zone="Etc/UTC" \
    --topic="$TOPIC" --message-body='{"kind":"check_the_queue"}' >/dev/null 2>&1 \
    && echo "→ schedule $CRON  (updated)" || echo "→ schedule job exists"
else
  gcloud scheduler jobs create pubsub "$TOPIC" --project "$PROJECT" \
    --location="$REGION" --schedule="$CRON" --time-zone="Etc/UTC" \
    --topic="$TOPIC" --message-body='{"kind":"check_the_queue"}' >/dev/null \
    && echo "→ schedule $CRON"
fi

# Remember the URL, so the workbench and verify.sh can find the cloud page.
if grep -q '^AGENT_SERVICE_URL=' .env 2>/dev/null; then
  sed -i.bak "s|^AGENT_SERVICE_URL=.*|AGENT_SERVICE_URL=$URL|" .env && rm -f .env.bak
else
  printf 'AGENT_SERVICE_URL=%s\n' "$URL" >> .env
fi

echo ""
echo "✓ deployed."
echo ""
echo "  the front door — the page, not the dev UI:"
echo "      $URL"
echo ""
echo "  start a task there (two tickets, Amsterdam, confirm the authorization),"
echo "  press SKIP THE WAIT on the venue panel, then fire the scheduler now"
echo "  instead of waiting for 3am:"
echo "      gcloud scheduler jobs run $TOPIC --location=$REGION --project=$PROJECT"
echo ""
echo "  then read what it did:"
echo "      gcloud run services logs read $SERVICE --region=$REGION --project=$PROJECT --limit=50"
echo "      curl -s $URL/task"
echo ""
echo "  and clean up when you are done:"
echo "      ./destroy-agent.sh          service, schedule, topic, subscription"
echo "      ./destroy-agent.sh --all    …and Cloud SQL and the bucket"
