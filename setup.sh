#!/usr/bin/env bash
# One-time setup. Works in Cloud Shell, on a laptop, anywhere with Python 3.11+.
set -euo pipefail
cd "$(dirname "$0")"

# --- 1. Python ------------------------------------------------------------
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3,11) else 0)')
if [ "$PY_OK" != "1" ]; then
  echo "✗ Python 3.11+ required (ADK 2 workflows need it). Found: $(python3 --version)"
  exit 1
fi

# --- 2. Dependencies ------------------------------------------------------
# Re-running setup.sh has to work. The codelab tells you to do it after
# `gcloud auth application-default login`, and several errors below say so too.
if command -v uv >/dev/null 2>&1; then
  if [ -d .venv ]; then
    echo "→ venv       reusing .venv"
  else
    echo "→ venv       creating with uv"
    uv venv .venv --python 3.11 >/dev/null 2>&1 || uv venv .venv >/dev/null
  fi
  uv pip install -q --python .venv/bin/python -r requirements.txt
else
  if [ -d .venv ]; then
    echo "→ venv       reusing .venv"
  else
    echo "→ venv       creating with python -m venv (slower)"
    python3 -m venv .venv
    .venv/bin/pip install -q --upgrade pip
  fi
  .venv/bin/pip install -q -r requirements.txt
fi

# --- 3. Config ------------------------------------------------------------
# What YOU set in this shell, captured before .env can overwrite it. Sourcing
# .env below is how the workshop remembers your answers, and it must not be how
# a stale saved value beats a deliberate export you just made.
_SHELL_PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
_SHELL_REGION="${GOOGLE_CLOUD_REGION:-}"
_SHELL_LOCATION="${GOOGLE_CLOUD_LOCATION:-}"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "→ created .env"
fi
[ -f .env ] && set -a && . ./.env && set +a

# The shell wins. An export you typed a minute ago is a clearer statement of
# intent than a line written into .env by a run last week.
[ -n "$_SHELL_PROJECT" ]  && GOOGLE_CLOUD_PROJECT="$_SHELL_PROJECT"
[ -n "$_SHELL_REGION" ]   && GOOGLE_CLOUD_REGION="$_SHELL_REGION"
[ -n "$_SHELL_LOCATION" ] && GOOGLE_CLOUD_LOCATION="$_SHELL_LOCATION"

mkdir -p artifacts memory
# The agent APPENDS to this file every time it calls remember(), so after a few
# runs it fills up with duplicate booking lines. seed/memory/ holds the pristine
# copies, and use-solution.sh restores from them at the start of every chapter.
[ -f memory/userx.md ] || cp seed/memory/default.md memory/userx.md

# --- 4. Google Cloud ------------------------------------------------------
# We use Vertex AI, so auth is Application Default Credentials rather than an
# API key. Everything below is a check with a fix attached, never a silent pass.
set +e

echo ""
if ! command -v gcloud >/dev/null 2>&1; then
  echo "✗ gcloud not found. Install the Google Cloud CLI, or use Cloud Shell"
  echo "  where it is already present:  https://shell.cloud.google.com"
  exit 1
fi

# --- which project? -------------------------------------------------------
# Two kinds of room run this workshop, and they want opposite things.
#
#   Google Skills  hands you a project and a billing account before you type
#                  anything, exported as GOOGLE_CLOUD_PROJECT and
#                  GOOGLE_CLOUD_REGION. Asking a question the platform has
#                  already answered is just a chance to answer it wrong.
#
#   Anywhere else  your laptop, your own account, nothing set up yet. We make a
#                  project — long-running-<10 random chars> — and attach the
#                  newest CDP credit. scripts/billing-enablement.py does both.
#
# Read _SHELL_PROJECT, never the live GOOGLE_CLOUD_PROJECT: .env was sourced
# further up, so the live variable may be something THIS script wrote last week.
# Only the copy captured before that source proves the platform set it.
#
#   PROJECT_ID=x ./setup.sh   use x, skip everything below
#   rm ~/project_id.txt       forget the project an earlier run made
PROJECT_FILE="$HOME/project_id.txt"
PROJECT=""
SOURCE=""

if [ -n "${PROJECT_ID:-}" ]; then
  PROJECT="$PROJECT_ID"
  SOURCE="PROJECT_ID on the command line"
elif [ -n "$_SHELL_PROJECT" ]; then
  PROJECT="$_SHELL_PROJECT"
  SOURCE="GOOGLE_CLOUD_PROJECT — set by your lab platform"
elif [ -f "$PROJECT_FILE" ] && [ -s "$PROJECT_FILE" ]; then
  PROJECT=$(tr -d '[:space:]' < "$PROJECT_FILE")
  [ -n "$PROJECT" ] && SOURCE="remembered in $PROJECT_FILE"
elif [ -n "${GOOGLE_CLOUD_PROJECT:-}" ]; then
  PROJECT="$GOOGLE_CLOUD_PROJECT"
  SOURCE="saved in .env by an earlier run"
fi

# Nothing to go on. Offer to make one — but let somebody who already has a
# project say so. Creating a second project they will never look at again is a
# worse outcome than one extra question.
if [ -z "$PROJECT" ] && [ -t 0 ]; then
  echo ""
  echo "  No Google Cloud project found for this workshop."
  echo "  Press Enter and one gets created for you (long-running-… , with a"
  echo "  billing account attached), or type the id of one you already have."
  echo ""
  printf "  Project id [create a new one]: "
  read -r ANSWER
  ANSWER=$(printf '%s' "$ANSWER" | tr -d '[:space:]')
  if [ -n "$ANSWER" ]; then
    PROJECT="$ANSWER"
    SOURCE="you typed it"
  fi
  echo ""
fi

# One call, both jobs: reach the project (or create one), then make sure it can
# be billed. Vertex AI and Cloud Run are both dead without a billing account,
# and its absence otherwise turns up as a baffling 403 somewhere in Chapter 2.
# Human-readable progress goes to stderr and streams straight to the terminal;
# stdout carries one line, PROJECT=<id>, and nothing else.
# A remembered project can be deleted between runs, or belong to an account
# this Cloud Shell is no longer signed in as. When the id came from a file
# rather than from a person, let the bootstrap start over instead of dead-ending
# on ~/project_id.txt, which no student has ever heard of.
case "$SOURCE" in
  remembered*|saved*) RECOVER="--fallback-create" ;;
  *)                  RECOVER="" ;;
esac

if [ -n "$PROJECT" ]; then
  BOOTSTRAP=$(.venv/bin/python scripts/billing-enablement.py --project "$PROJECT" $RECOVER)
else
  BOOTSTRAP=$(.venv/bin/python scripts/billing-enablement.py --create)
fi

PROJECT=$(printf '%s\n' "$BOOTSTRAP" | sed -n 's/^PROJECT=//p' | tail -1)
if [ -z "$PROJECT" ]; then
  echo ""
  echo "✗ No usable project, so setup stops here — every chapter from Chapter 2"
  echo "  onwards deploys into one. The message above says what to fix."
  exit 1
fi

printf '%s\n' "$PROJECT" > "$PROJECT_FILE"
gcloud config set project "$PROJECT" >/dev/null 2>&1
echo "→ project    $PROJECT  (${SOURCE:-created just now} — rm $PROJECT_FILE to start over)"

# Location and region: use whatever is already set, and only fall back if it is
# not. Somebody with GOOGLE_CLOUD_LOCATION exported has told us where they work,
# and asking again or overwriting it would be rude.
#
#   GOOGLE_CLOUD_LOCATION   where the MODEL is served. "global" is right for
#                           Gemini on Vertex and is not a Cloud Run region.
#   GOOGLE_CLOUD_REGION     where SERVICES live: Cloud Run, Cloud SQL, buckets,
#                           Pub/Sub, Scheduler. Everything deployable uses this.
LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"

# Deliberately NOT read from `gcloud config get-value run/region`. That value
# often survives from another project entirely, and silently deploying a
# student's venue to a region they picked months ago for something else is the
# kind of thing nobody notices until the URLs do not match the codelab.
if [ -n "${GOOGLE_CLOUD_REGION:-}" ]; then
  REGION="$GOOGLE_CLOUD_REGION"
  if [ -n "$_SHELL_REGION" ]; then REGION_SRC="from GOOGLE_CLOUD_REGION in your shell"
  else REGION_SRC="from .env"; fi
else
  _gcloud_run_r=$(gcloud config get-value run/region 2>/dev/null || true)
  _gcloud_comp_r=$(gcloud config get-value compute/region 2>/dev/null || true)
  if [ -n "$_gcloud_run_r" ] && [ "$_gcloud_run_r" != "(unset)" ]; then
    REGION="$_gcloud_run_r"; REGION_SRC="from gcloud run/region"
  elif [ -n "$_gcloud_comp_r" ] && [ "$_gcloud_comp_r" != "(unset)" ]; then
    REGION="$_gcloud_comp_r"; REGION_SRC="from gcloud compute/region"
  else
    REGION="us-central1"; REGION_SRC="default"
  fi
fi
export GOOGLE_CLOUD_LOCATION="$LOCATION" GOOGLE_CLOUD_REGION="$REGION"

echo "→ location   $LOCATION  (where the model is served)"
echo "→ region     $REGION  ($REGION_SRC — everything deployable goes here)"

# If gcloud disagrees, say so rather than quietly picking one.
GCLOUD_REGION=$(gcloud config get-value run/region 2>/dev/null)
case "$GCLOUD_REGION" in
  ""|"(unset)"|"$REGION") ;;
  *) echo "             note: your gcloud run/region is $GCLOUD_REGION, which is NOT"
     echo "             being used. To deploy there:  GOOGLE_CLOUD_REGION=$GCLOUD_REGION ./setup.sh" ;;
esac

# The project id is the one line in .env that differs per student, so write it
# rather than making them edit it by hand.
if grep -q '^GOOGLE_CLOUD_PROJECT=' .env; then
  sed -i.bak "s|^GOOGLE_CLOUD_PROJECT=.*|GOOGLE_CLOUD_PROJECT=$PROJECT|" .env && rm -f .env.bak
else
  printf 'GOOGLE_CLOUD_PROJECT=%s\n' "$PROJECT" >> .env
fi

# GOOGLE_GENAI_USE_VERTEXAI is not decoration: the model check below and every
# ADK process afterwards read it to decide between Vertex AI and the Gemini
# Developer API, and only one of those works with the ADC we just set up.
for pair in "GOOGLE_CLOUD_LOCATION=$LOCATION" "GOOGLE_CLOUD_REGION=$REGION" \
            "GOOGLE_GENAI_USE_VERTEXAI=true" \
            "ADK_MODEL=${ADK_MODEL:-gemini-2.5-flash}"; do
  key="${pair%%=*}"
  if grep -q "^$key=" .env; then
    sed -i.bak "s|^$key=.*|$pair|" .env && rm -f .env.bak
  else
    printf '%s\n' "$pair" >> .env
  fi
done

. ./.env 2>/dev/null
GOOGLE_CLOUD_PROJECT="$PROJECT"

# Application Default Credentials. Rather than telling you to go and run a
# command and come back, just run it — one browser click in Cloud Shell.
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  if [ -t 0 ]; then
    echo "→ auth       no credentials yet, opening the sign-in flow"
    echo ""
    gcloud auth application-default login
    echo ""
  fi
  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "✗ Still no Application Default Credentials. Run this, then ./setup.sh again:"
    echo ""
    echo "      gcloud auth application-default login"
    exit 1
  fi
fi
echo "→ auth       ok"

# Quota project mismatches are the single most common cause of a confusing
# 403 later, so fix it here rather than during Chapter 2.
gcloud auth application-default set-quota-project "$PROJECT" >/dev/null 2>&1 \
  && echo "→ quota      set to $PROJECT"

# Everything the workshop actually touches. Enabling an API that is already on
# is a no-op, but each call still costs a round trip — so we diff first and
# enable only what is missing, in one batched call.
REQUIRED_APIS=(
  aiplatform.googleapis.com        # Vertex AI — the models, every chapter
  run.googleapis.com               # Cloud Run — the venue (pre-work), and the agent in Chapter 6
  cloudbuild.googleapis.com        # builds the container for `run deploy --source`
  artifactregistry.googleapis.com  # where Cloud Build puts the image
  storage.googleapis.com           # Cloud Build's source staging bucket
  pubsub.googleapis.com            # Chapter 6 — the trigger topic
  cloudscheduler.googleapis.com    # Chapter 6 — the 3am cron
  cloudtrace.googleapis.com        # Chapter 6 — seeing what happened overnight (optional)
  logging.googleapis.com           # Chapter 6 — logs from a run nobody watched
  sqladmin.googleapis.com          # Chapter 6 — Cloud SQL, where sessions live in the cloud
)

ENABLED=$(gcloud services list --enabled --project "$PROJECT" --format='value(config.name)' 2>/dev/null || true)
MISSING=()
for api in "${REQUIRED_APIS[@]}"; do
  grep -qx "$api" <<<"$ENABLED" || MISSING+=("$api")
done

if [ ${#MISSING[@]} -eq 0 ]; then
  echo "→ apis       all ${#REQUIRED_APIS[@]} already enabled"
else
  echo "→ apis       enabling ${#MISSING[@]} of ${#REQUIRED_APIS[@]} (this can take a minute)"
  for api in "${MISSING[@]}"; do echo "               $api"; done
  if gcloud services enable "${MISSING[@]}" --project "$PROJECT" 2>/tmp/svc-enable.err; then
    echo "→ apis       enabled"
  else
    echo ""
    echo "✗ Could not enable APIs on $PROJECT."
    echo "  $(head -2 /tmp/svc-enable.err | tr '\n' ' ')"
    echo ""
    echo "  If you do not own this project, ask someone who does to run:"
    echo ""
    echo "      gcloud services enable ${MISSING[*]} \\"
    echo "        --project $PROJECT"
    echo ""
    echo "  If it says billing is not enabled, the project needs a billing"
    echo "  account attached before Vertex AI or Cloud Run will work."
    exit 1
  fi
fi

# Ask the model one question, so a bad .env shows up here rather than in the
# middle of Chapter 2. Reporting only — see the else branch below: this never
# stops setup, because a 404 on the model id is not a reason to skip building
# the venue and the seeded session.
#
# The client is built with NO arguments on purpose. .env is what `adk web` and
# every deploy script read, so .env is what this has to test. A check that
# passes because we hand-built a correct client here, while .env says something
# else entirely, is worse than no check: it sends a student into Chapter 2
# believing the rig works.
MODEL="${ADK_MODEL:-gemini-2.5-flash}"
export ADK_MODEL="$MODEL"
export GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION GOOGLE_GENAI_USE_VERTEXAI

CHECK=$(.venv/bin/python - <<'PY' 2>&1
import logging, os, time, warnings

# The SDK writes an unsolicited paragraph about automatic function calling to
# the log on every generate_content. With 2>&1 that lands in the middle of our
# answer, so silence it — and note the __MODELCHECK__ marker below, which is
# what makes the shell immune to anything else that decides to print.
logging.disable(logging.WARNING)
warnings.filterwarnings("ignore")


def attempt():
    from google import genai
    # Checked BEFORE constructing the client. Without this the SDK raises its
    # own "No API key was provided ... ai.google.dev" at construction time,
    # which sends a student off to mint an AI Studio key for a workshop that
    # authenticates with ADC and never wants one.
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() not in ("true", "1"):
        raise RuntimeError(
            "GOOGLE_GENAI_USE_VERTEXAI is not true in .env, so this would call "
            "the Gemini Developer API and ask for an API key. Set it to true."
        )
    # Reads GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT and
    # GOOGLE_CLOUD_LOCATION out of the environment, exactly as ADK will.
    c = genai.Client()
    if not c.vertexai:
        # An API key in the environment can still win. Catch it here rather
        # than letting the quota land somewhere nobody expects.
        raise RuntimeError(
            "resolved to the Gemini Developer API despite the .env setting — "
            "is GOOGLE_API_KEY or GEMINI_API_KEY set in your shell?"
        )
    c.models.generate_content(model=os.environ["ADK_MODEL"], contents="hi")


# A project created ninety seconds ago says 403 PERMISSION_DENIED on
# aiplatform.endpoints.predict for a while after the API is switched on. It is
# a propagation delay wearing a permissions error's clothes, and it clears on
# its own, so give it a couple of minutes before believing it.
SETTLING = ("permission_denied", "403", "has not been used in project",
            "is disabled", "service_disabled", "unavailable", "503")

last = ""
for i in range(4):
    try:
        attempt()
        print(f"__MODELCHECK__ OK {os.environ.get('GOOGLE_CLOUD_PROJECT', '?')} "
              f"{os.environ.get('GOOGLE_CLOUD_LOCATION', '?')}")
        break
    except Exception as exc:
        last = f"{type(exc).__name__}: {str(exc)[:200]}"
        if i < 3 and any(s in last.lower() for s in SETTLING):
            print(f"   (Vertex AI not ready yet on this project, retrying in 20s)")
            time.sleep(20)
            continue
        print(f"__MODELCHECK__ FAIL {last}")
        break
PY
)
set -e

# Pick our marker line out of whatever else decided to print. The old test read
# the first two characters of the whole capture, which an SDK log line at the
# top silently turned into a failure report on a working rig.
RESULT=$(printf '%s\n' "$CHECK" | sed -n 's/^__MODELCHECK__ //p' | tail -1)

case "$RESULT" in
  "OK "*)
    # "OK <project> <location>" — the values the client actually resolved out of
    # .env. Printing them is the point: it is how a stale .env becomes visible.
    read -r _ CHK_PROJECT CHK_LOCATION <<<"$RESULT"
    echo "→ model      $MODEL responds  (Vertex AI · $CHK_PROJECT · $CHK_LOCATION)"
    ;;
  *)
    # NOT fatal. A model that will not answer is worth knowing about now, but
    # it is not worth stopping setup over: the venue, the seeded session and
    # Cloud SQL are all still worth having, and Chapter 2 is the first chapter that
    # actually needs the model. There is time to fix this.
    echo "→ model      $MODEL did not answer — setup continues anyway"
    echo ""
    echo "  ${RESULT:-${CHECK}}"
    echo ""
    case "$RESULT" in
      *403*|*PERMISSION_DENIED*|*permission*)
        echo "  On a project this new, that is usually Vertex AI still switching"
        echo "  on rather than anything you did. It clears by itself. Carry on —"
        echo "  and if Chapter 2 still cannot reach the model, run ./setup.sh again."
        ;;
      *404*|*NOT_FOUND*|*not?found*)
        echo "  '-latest' aliases are AI Studio only and do not exist on Vertex."
        echo "  Set a pinned id in .env, e.g. ADK_MODEL=gemini-2.5-flash"
        echo "  List what this project actually has:"
        echo ""
        echo "      set -a; . ./.env; set +a"
        echo "      .venv/bin/python -c \"from google import genai; \\"
        echo "        [print(m.name) for m in genai.Client().models.list()]\""
        ;;
    esac
    ;;
esac

# --- 5. The pre-loaded session ------------------------------------------
# Chapter 3 opens a session that has already been alive for two days. Without
# this there is nothing to open. Safe to re-run: it rebuilds only the
# 'two-days-ago' session and leaves the student's own work alone.
if .venv/bin/python -m seed.session >/tmp/seed.log 2>&1; then
  echo "→ seed       session 'two-days-ago' ready (13 events, 2 days old)"
else
  echo "→ seed       FAILED — Chapter 3 has nothing to open"
  tail -4 /tmp/seed.log | sed 's/^/               /'
  echo "               retry with:  python -m seed.session"
fi

# ── Cloud SQL, started now and collected in Chapter 6 ───────────────────
#
# Creating a Postgres instance takes eight to twelve minutes, which is most of
# a chapter. Nobody should sit and watch it, so it starts here, in the
# background, during the pre-work — and Chapter 6 picks up
# whatever finished.
#
# db-f1-micro is the smallest thing Cloud SQL sells. It is the wrong size for
# anything real and exactly right for one student's sessions table.
SQL_INSTANCE="${SQL_INSTANCE:-workshop-sessions}"
if gcloud sql instances describe "$SQL_INSTANCE" --project "$PROJECT" >/dev/null 2>&1; then
  echo "→ cloudsql   $SQL_INSTANCE already exists"
else
  nohup gcloud sql instances create "$SQL_INSTANCE" \
    --project "$PROJECT" --database-version=POSTGRES_15 \
    --tier=db-f1-micro --region="$REGION" \
    --storage-size=10 --storage-type=HDD --no-backup --quiet \
    >"$HOME/.cloudsql-create.log" 2>&1 &
  echo "→ cloudsql   creating $SQL_INSTANCE in the background (~10 min)"
  echo "             log: ~/.cloudsql-create.log — Chapter 6 needs it, nothing before does"
fi


# ── The venue, deployed now so the workshop starts with a world ──────────
#
# Every student gets their own. A shared one would mean the moment somebody
# presses SELL THE GOOD SEATS, everyone else's agent starts failing for no
# visible reason. `gcloud run deploy` is idempotent, so re-running setup
# redeploys over the top rather than erroring.
# Enabling run/cloudbuild a few seconds ago does not mean they are usable
# yet — enablement propagates, and the first deploy after it can fail with
# "API has not been used in project ... before or it is disabled". So try
# twice, with a pause, before believing it.
echo "→ venue      deploying to Cloud Run (1-2 min)..."
if ! ./deploy-venue.sh >/tmp/venue-deploy.log 2>&1; then
  if grep -qiE "has not been used in project|is disabled|SERVICE_DISABLED|PERMISSION_DENIED" /tmp/venue-deploy.log; then
    echo "→ venue      APIs still switching on, waiting 30s and retrying"
    sleep 30
    ./deploy-venue.sh >/tmp/venue-deploy.log 2>&1 || true
  fi
fi
if grep -q "venue deployed" /tmp/venue-deploy.log; then
  # gcloud bolds the URL, so a greedy [^ ]* match swallows the trailing ANSI
  # reset and prints as a stray [m. Matching only URL-safe characters stops at
  # the escape byte instead, with no sed and no locale trouble.
  VENUE_URL=$(grep -m1 -ao 'https://venue-[A-Za-z0-9._~:/?#@!$&()*+,;=%-]*' \
              /tmp/venue-deploy.log)
  echo "→ venue      deployed  $VENUE_URL"
else
  echo ""
  echo "  ✗✗✗ THE VENUE DID NOT DEPLOY ✗✗✗"
  echo ""
  echo "  Nothing else in this workshop works without it: the agent has no"
  echo "  world to buy from, and no panel to check its story against."
  echo ""
  tail -12 /tmp/venue-deploy.log | sed 's/^/      /'
  echo ""
  echo "  Full log:  /tmp/venue-deploy.log"
  echo "  Retry:     ./deploy-venue.sh"
  echo ""
fi

echo ""
if ! grep -q "venue deployed" /tmp/venue-deploy.log; then
  echo "✗ The venue did not deploy, so setup stops here. Fix the error above,"
  echo "  then run ./deploy-venue.sh (or ./setup.sh again)."
  exit 1
fi
echo "✓ setup complete."
echo ""
echo "  your venue:  $VENUE_URL/panel"
echo "               keep this tab open all day. It is where you press the buttons,"
echo "               and where you check whether the agent actually did what it said."
echo ""
echo "  check it:    ./verify.sh"
echo "  chapter 6:   Cloud SQL is still building in the background (~/.cloudsql-create.log);"
echo "               ./setup-cloud-state.sh collects it, and nothing before Chapter 6 needs it."
echo ""

# The workbench: every chapter in the browser, with the venue, the agent,
# MonsterTix and the clock as switches. A failure here does not fail setup;
# the codelab's terminal commands work without it. workbench.sh waits until
# the port answers before it prints the link, so a tab opened on that link
# never lands on "Unable to forward your request to a backend".
if ./workbench.sh start; then
  :
else
  echo "  ⚠ the workbench did not start. The codelab works without it."
  echo "    Try again with:  ./workbench.sh"
fi
