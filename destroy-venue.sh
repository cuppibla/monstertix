#!/usr/bin/env bash
# Delete the venue ./deploy-venue.sh created. It scales to zero, so an idle one
# costs nothing — but leaving services lying around in a shared project is rude.
#
#     ./destroy-venue.sh
#
# Safe to run twice. The agent's Cloud Run service, schedule, database and
# bucket are separate: ./destroy-agent.sh [--all].
set -euo pipefail
cd "$(dirname "$0")"

_shell_region="${GOOGLE_CLOUD_REGION:-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$_shell_region" ] && export GOOGLE_CLOUD_REGION="$_shell_region"

PROJECT="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
REGION="${VENUE_REGION:-${GOOGLE_CLOUD_REGION:-us-central1}}"

WHO=$(gcloud config get-value account 2>/dev/null | cut -d@ -f1 \
      | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/-*$//' | cut -c1-30)
SERVICE="${VENUE_SERVICE:-venue-${WHO:-student}}"

if gcloud run services delete "$SERVICE" --region="$REGION" --project "$PROJECT" \
     --quiet >/dev/null 2>&1; then
  echo "→ removed  venue service $SERVICE"
else
  echo "→ absent   venue service $SERVICE (already gone)"
fi

# .env still names it. Blank the line rather than deleting it, so set_env.sh
# keeps refusing to invent a localhost default.
if [ -f .env ] && grep -q '^VENUE_URL=' .env; then
  sed -i.bak "s|^VENUE_URL=.*|VENUE_URL=|" .env && rm -f .env.bak
  echo "→ .env     VENUE_URL cleared"
fi

echo ""
echo "✓ venue removed."
echo ""
echo "  still there:"
if [ -n "${AGENT_SERVICE_URL:-}" ]; then
  echo "      the agent on Cloud Run  $AGENT_SERVICE_URL   → ./destroy-agent.sh"
else
  echo "      the agent on Cloud Run, if you deployed one   → ./destroy-agent.sh"
fi
echo "      Cloud SQL + bucket, if you made them            → ./destroy-agent.sh --all"
echo "      a local venue:  python -m venue  still works, with  . ./set_env.sh local"
