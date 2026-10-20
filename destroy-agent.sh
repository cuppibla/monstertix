#!/usr/bin/env bash
# Chapter 6 · clean-up. Remove everything ./deploy-agent.sh created, in the
# order that never leaves a timer firing at a half-deleted stack.
#
#     ./destroy-agent.sh          schedule, subscription, topic, service
#     ./destroy-agent.sh --all    …and the Cloud SQL instance and the bucket
#
# The venue is separate — ./destroy-venue.sh. Safe to run twice: everything
# that is already gone is reported as such.
set -euo pipefail
cd "$(dirname "$0")"

_shell_region="${GOOGLE_CLOUD_REGION:-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$_shell_region" ] && export GOOGLE_CLOUD_REGION="$_shell_region"

PROJECT="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
REGION="${AGENT_REGION:-${GOOGLE_CLOUD_REGION:-us-central1}}"

WHO=$(gcloud config get-value account 2>/dev/null | cut -d@ -f1 \
      | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/-*$//' | cut -c1-24)
SERVICE="${AGENT_SERVICE:-concert-${WHO:-student}}"
TOPIC="${PRESALE_TOPIC:-presale-${WHO:-student}}"
SQL_INSTANCE="${SQL_INSTANCE:-workshop-sessions}"
BUCKET="${STATE_BUCKET:-}"
ALL=""
[ "${1:-}" = "--all" ] && ALL=1

REMOVED=()
ABSENT=()
KEPT=()

gone()  { REMOVED+=("$1"); echo "→ removed  $1"; }
none()  { ABSENT+=("$1");  echo "→ absent   $1"; }

echo "→ project  $PROJECT   region $REGION"
echo ""

# 1. Scheduler first, so nothing fires at a half-deleted stack.
if gcloud scheduler jobs delete "$TOPIC" --location="$REGION" --project "$PROJECT" --quiet >/dev/null 2>&1; then
  gone "schedule      $TOPIC"
else none "schedule      $TOPIC"; fi

# 2. The push subscription, then the topic it hangs off.
if gcloud pubsub subscriptions delete "$TOPIC-push" --project "$PROJECT" --quiet >/dev/null 2>&1; then
  gone "subscription  $TOPIC-push"
else none "subscription  $TOPIC-push"; fi
if gcloud pubsub topics delete "$TOPIC" --project "$PROJECT" --quiet >/dev/null 2>&1; then
  gone "topic         $TOPIC"
else none "topic         $TOPIC"; fi

# 3. The service.
if gcloud run services delete "$SERVICE" --region="$REGION" --project "$PROJECT" --quiet >/dev/null 2>&1; then
  gone "service       $SERVICE"
else none "service       $SERVICE"; fi

# 4. The durable state, which is the part that keeps billing. A db-f1-micro
#    instance is a few dollars a month and a bucket is pennies, but neither
#    stops on its own — deleting the Cloud Run service does not touch either.
if [ -n "$ALL" ]; then
  if gcloud sql instances delete "$SQL_INSTANCE" --project "$PROJECT" --quiet >/dev/null 2>&1; then
    gone "Cloud SQL     $SQL_INSTANCE"
  else none "Cloud SQL     $SQL_INSTANCE"; fi
  if [ -n "$BUCKET" ]; then
    if gcloud storage rm -r "$BUCKET" --project "$PROJECT" --quiet >/dev/null 2>&1; then
      gone "bucket        $BUCKET"
    else none "bucket        $BUCKET"; fi
  else
    none "bucket        (STATE_BUCKET not set in .env)"
  fi
  # The URIs in .env now point at nothing. Drop them so the next deploy does
  # not try to attach a database that is gone.
  if [ -f .env ]; then
    sed -i.bak '/^CLOUD_SESSION_SERVICE_URI=/d;/^CLOUD_ARTIFACT_SERVICE_URI=/d;/^STATE_BUCKET=/d;/^SQL_CONNECTION_NAME=/d' .env \
      && rm -f .env.bak
    echo "→ .env     cloud state URIs removed"
  fi
else
  KEPT+=("Cloud SQL     $SQL_INSTANCE" "bucket        ${BUCKET:-<not set>}")
fi
if [ -f .env ] && grep -q '^AGENT_SERVICE_URL=' .env; then
  sed -i.bak '/^AGENT_SERVICE_URL=/d' .env && rm -f .env.bak
fi

echo ""
echo "✓ Chapter 6 infrastructure removed."
echo ""
echo "  removed now   ${#REMOVED[@]}"
for r in "${REMOVED[@]+"${REMOVED[@]}"}"; do echo "      $r"; done
if [ ${#ABSENT[@]} -gt 0 ]; then
  echo "  already gone  ${#ABSENT[@]}"
  for r in "${ABSENT[@]}"; do echo "      $r"; done
fi
if [ ${#KEPT[@]} -gt 0 ]; then
  echo ""
  echo "  still there, because they hold your data and they keep billing:"
  for r in "${KEPT[@]}"; do echo "      $r"; done
  echo ""
  echo "  Delete those too with:  ./destroy-agent.sh --all"
fi
echo ""
echo "  still there on purpose:"
echo "      the venue          ./destroy-venue.sh removes it"
echo "      your laptop state  sessions.db, memory/, artifacts/ — ./use-solution.sh N resets them"
