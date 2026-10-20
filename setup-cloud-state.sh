#!/usr/bin/env bash
# Chapter 6 · Run It While You Sleep — give the agent somewhere durable to keep
# things.
#
#     ./setup-cloud-state.sh        once; safe to run again
#
# Everything the agent remembers has been on your laptop until now:
#
#     sessions.db          a SQLite file next to the code
#     memory/*.md          a markdown file you can open in an editor
#     artifacts/           seat maps written to a folder
#
# All three are perfect for learning and all three are wrong in the cloud, for
# the same reason: a Cloud Run container has a writable filesystem that is
# destroyed when the instance goes away, which happens whenever traffic stops.
# Write a session to /tmp at 3am and it is gone by morning — no error, no
# warning, just an agent that has forgotten it was ever in a queue.
#
# So this script makes three things that outlive a container:
#
#     1. a database on the Cloud SQL instance setup.sh started for you
#     2. a user for the agent to connect as
#     3. a Cloud Storage bucket for memory and artifacts
#
# and prints the two URIs that replace the two file paths. Nothing is migrated:
# a task that is parked in your laptop's sessions.db stays there. Chapter 6
# starts a NEW task in the cloud and lets the scheduler finish that one.
set -euo pipefail
cd "$(dirname "$0")"

_shell_region="${GOOGLE_CLOUD_REGION:-}"
[ -f .env ] && set -a && . ./.env && set +a
[ -n "$_shell_region" ] && export GOOGLE_CLOUD_REGION="$_shell_region"

PROJECT="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT — run ./setup.sh}"
REGION="${AGENT_REGION:-${GOOGLE_CLOUD_REGION:-us-central1}}"
SQL_INSTANCE="${SQL_INSTANCE:-workshop-sessions}"
DB_NAME="${SQL_DB:-adk}"
DB_USER="${SQL_USER:-adk}"

WHO=$(gcloud config get-value account 2>/dev/null | cut -d@ -f1 \
      | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/-*$//' | cut -c1-24)
BUCKET="${STATE_BUCKET:-gs://${PROJECT}-agent-${WHO:-student}}"

echo "→ project   $PROJECT"
echo "→ instance  $SQL_INSTANCE"
echo "→ bucket    $BUCKET"
echo ""

# --- 1. Is the instance ready? -------------------------------------------
#
# setup.sh started this during the pre-work precisely so nobody
# has to wait for it here. If it is still building, say so plainly rather than
# failing with a Cloud SQL error nobody can read.
STATE=$(gcloud sql instances describe "$SQL_INSTANCE" --project "$PROJECT" \
        --format='value(state)' 2>/dev/null || true)

if [ -z "$STATE" ]; then
  echo "→ instance  creating $SQL_INSTANCE (~10 min); wait for this command to finish"
  gcloud sql instances create "$SQL_INSTANCE" --project "$PROJECT" \
    --database-version=POSTGRES_15 --edition=ENTERPRISE --tier=db-f1-micro \
    --region="$REGION" --storage-size=10 --storage-type=HDD --no-backup --quiet
  STATE=$(gcloud sql instances describe "$SQL_INSTANCE" --project "$PROJECT" --format='value(state)')
fi

if [ "$STATE" != "RUNNABLE" ]; then
  echo "→ instance  still $STATE — Cloud SQL takes 8-12 minutes to build."
  echo "            Watch it with:"
  echo ""
  echo "      gcloud sql operations list --instance=$SQL_INSTANCE --project=$PROJECT --limit=1"
  echo ""
  echo "            Then run this script again."
  exit 1
fi
echo "→ instance  RUNNABLE"

# --- 2. A database and a user --------------------------------------------
if gcloud sql databases describe "$DB_NAME" --instance="$SQL_INSTANCE" --project "$PROJECT" >/dev/null 2>&1; then
  echo "→ database  $DB_NAME exists"
else
  gcloud sql databases create "$DB_NAME" --instance="$SQL_INSTANCE" --project "$PROJECT" --quiet
  echo "→ database  $DB_NAME created"
fi

# Fixed for this workshop; saved in .env rather than printed in the app. This is a workshop
# password for a throwaway instance that is deleted at the end of the day.
#
# It is NOT a pattern to copy. In anything real this lives in Secret Manager
# and the service reads it from there, never from a file in the repo.
#
#   SQL_PASSWORD=something-else ./setup-cloud-state.sh   to override
DB_PASS="${SQL_PASSWORD:-1234qwer}"
if gcloud sql users describe "$DB_USER" --instance="$SQL_INSTANCE" \
     --project "$PROJECT" >/dev/null 2>&1; then
  gcloud sql users set-password "$DB_USER" --instance="$SQL_INSTANCE" \
    --project "$PROJECT" --password="$DB_PASS" --quiet
  echo "→ user      $DB_USER password reset"
else
  gcloud sql users create "$DB_USER" --instance="$SQL_INSTANCE" \
    --project "$PROJECT" --password="$DB_PASS" --quiet
  echo "→ user      $DB_USER created"
fi

CONN=$(gcloud sql instances describe "$SQL_INSTANCE" --project "$PROJECT" \
       --format='value(connectionName)')
[ -n "$CONN" ] || { echo "✗ Could not read the Cloud SQL connection name"; exit 1; }

# --- 3. A bucket for memory and artifacts --------------------------------
#
# memory/userx.md and artifacts/ are files. In the cloud they become
# objects, and ADK takes a gs:// URI wherever it took a file:// one.
if gcloud storage buckets describe "$BUCKET" --project "$PROJECT" >/dev/null 2>&1; then
  echo "→ bucket    exists"
else
  gcloud storage buckets create "$BUCKET" --project "$PROJECT" \
    --location="$REGION" --uniform-bucket-level-access --quiet
  echo "→ bucket    created"
fi

# Seed it with the memory file, so the deployed agent knows who it is buying for.
if [ -f memory/userx.md ]; then
  gcloud storage cp memory/userx.md "$BUCKET/memory/userx.md" --quiet
  echo "→ memory    memory/userx.md → $BUCKET/memory/"
fi

# Cloud Run's runtime identity needs database, model and bucket access.
NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
RUNTIME_SA="${AGENT_RUNTIME_SERVICE_ACCOUNT:-${NUMBER}-compute@developer.gserviceaccount.com}"
for role in roles/cloudsql.client roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$RUNTIME_SA" \
    --role="$role" --condition=None --quiet >/dev/null
done
gcloud storage buckets add-iam-policy-binding "$BUCKET" \
  --member="serviceAccount:$RUNTIME_SA" --role=roles/storage.objectUser --quiet >/dev/null
echo "→ access    runtime can reach Cloud SQL, Vertex AI and the state bucket"

# --- 4. The two URIs that replace the two file paths ----------------------
#
# Cloud Run reaches Cloud SQL over a unix socket at /cloudsql/<connection name>,
# which is why the host looks like a path. The deploy adds the socket with
# --add-cloudsql-instances; without that flag this URI cannot connect.
# URI-escape credentials so a custom password containing @ or & stays valid.
SESSION_URI=$(DB_USER="$DB_USER" DB_PASS="$DB_PASS" DB_NAME="$DB_NAME" CONN="$CONN" python3 - <<'URI'
import os
from urllib.parse import quote
v = lambda k: quote(os.environ[k], safe="")
print(f"postgresql+asyncpg://{v('DB_USER')}:{v('DB_PASS')}@/{v('DB_NAME')}?host=/cloudsql/{os.environ['CONN']}")
URI
)
ARTIFACT_URI="${BUCKET}/artifacts"

python3 - "$SESSION_URI" "$ARTIFACT_URI" "$BUCKET" "$CONN" <<'PY'
import pathlib, shlex, sys
session_uri, artifact_uri, bucket, conn = sys.argv[1:5]
env = pathlib.Path(".env")
lines = env.read_text().splitlines() if env.exists() else []
wanted = {
    "CLOUD_SESSION_SERVICE_URI": session_uri,
    "CLOUD_ARTIFACT_SERVICE_URI": artifact_uri,
    "STATE_BUCKET": bucket,
    "SQL_CONNECTION_NAME": conn,
}
out, seen = [], set()
for line in lines:
    key = line.split("=", 1)[0]
    if key in wanted:
        out.append(f"{key}={shlex.quote(wanted[key])}"); seen.add(key)
    else:
        out.append(line)
for key, value in wanted.items():
    if key not in seen:
        out.append(f"{key}={shlex.quote(value)}")
env.write_text("\n".join(out) + "\n")
PY

echo ""
echo "✓ durable state ready. Written to .env:"
echo ""
echo "   sessions   Cloud SQL   $DB_NAME on $SQL_INSTANCE"
echo "              connect:  gcloud sql connect $SQL_INSTANCE --user=$DB_USER --database=$DB_NAME"
echo "              credentials are saved in .env (not printed in the lab log)"
echo "   memory     $BUCKET/memory/"
echo "   artifacts  $ARTIFACT_URI"
echo ""
echo "   ./deploy-agent.sh picks these up. Nothing in agent/concert changes."
echo "   Not migrated: whatever is in your local sessions.db stays local."
