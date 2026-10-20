#!/usr/bin/env bash
# Confirm the rig is ready, in one screen of ticks.
#
# Everything here is a thing that fails LATER and confusingly if it is wrong now.
# The asyncio SQLite drivers are the sharp one: without them nothing complains
# until the first session write, which is Chapter 3, in front of the room.
#
# Cloud SQL is deliberately NOT checked. setup.sh starts it in the background and
# it takes eight to twelve minutes. Nothing before Chapter 6 touches it, so a
# "still creating" here would be noise.
#
#     ./verify.sh
#     ./verify.sh --no-model    skip the live model call (offline, or in a hurry)

set -uo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
FAILED=0
MODEL_CHECK=1
[ "${1:-}" = "--no-model" ] && MODEL_CHECK=""

pass() { printf "  \033[32m✓\033[0m %-34s %s\n" "$1" "${2:-}"; }
warn() { printf "  \033[33m~\033[0m %-34s %s\n" "$1" "${2:-}"; }
fail() { printf "  \033[31m✗\033[0m %-34s %s\n" "$1" "${2:-}"; FAILED=1; }

check() {          # check <label> <command...>   — quiet unless it breaks
  local label="$1"; shift
  local out
  if out=$("$@" 2>&1); then
    pass "$label" "$(echo "$out" | tail -1)"
  else
    fail "$label" "$(echo "$out" | tail -1 | cut -c1-60)"
  fi
}

echo ""
echo "  Checking the rig"
echo ""

# --- the toolchain --------------------------------------------------------
if [ ! -x "$PY" ]; then
  fail "virtualenv" ".venv missing — run ./setup.sh"
  echo ""; exit 1
fi
pass "virtualenv" ".venv"
check "adk installed"        .venv/bin/adk --version

# --- the ADK 2 APIs the workshop is built on ------------------------------
check "adk 2 apis"           "$PY" -c \
  "from google.adk.apps.app import App, ResumabilityConfig; print('App + ResumabilityConfig')"
check "workflow graphs"      "$PY" -c \
  "from google.adk.workflow import Workflow, START, node; print('Workflow + node')"

# --- session storage, the one that fails late -----------------------------
check "async sqlite drivers" "$PY" -c \
  "import sqlalchemy, aiosqlite, greenlet; print('sqlalchemy + aiosqlite + greenlet')"

# --- credentials ----------------------------------------------------------
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
fi
if [ -n "${GOOGLE_CLOUD_PROJECT:-}" ]; then
  pass "project" "$GOOGLE_CLOUD_PROJECT"
else
  fail "project" "GOOGLE_CLOUD_PROJECT not in .env — run ./setup.sh"
fi
if [ "${GOOGLE_GENAI_USE_VERTEXAI:-}" = "true" ]; then
  pass "vertex ai" "no API keys anywhere"
else
  fail "vertex ai" "GOOGLE_GENAI_USE_VERTEXAI should be true"
fi
if command -v gcloud >/dev/null 2>&1; then
  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    pass "credentials (ADC)" "$(gcloud config get-value account 2>/dev/null)"
  else
    fail "credentials (ADC)" "gcloud auth application-default login"
  fi
else
  fail "credentials (ADC)" "gcloud not installed"
fi

# --- the model, one short call --------------------------------------------
# Reads .env exactly as ADK will. A pass here means Chapter 2's first run will
# reach the model; a fail here is far cheaper than the same fail in the room.
if [ -n "$MODEL_CHECK" ] && [ -n "${GOOGLE_CLOUD_PROJECT:-}" ]; then
  export GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}" \
         GOOGLE_GENAI_USE_VERTEXAI="${GOOGLE_GENAI_USE_VERTEXAI:-true}"
  MODEL="${ADK_MODEL:-gemini-2.5-flash}"
  OUT=$(timeout 60 "$PY" - "$MODEL" <<'PYCHK' 2>&1
import logging, sys, warnings
logging.disable(logging.WARNING); warnings.filterwarnings("ignore")
from google import genai
c = genai.Client()
if not c.vertexai:
    raise SystemExit("resolved to the Developer API — is GOOGLE_API_KEY set?")
r = c.models.generate_content(model=sys.argv[1], contents="Say OK.")
print("answered:", (r.text or "").strip()[:24])
PYCHK
  )
  if [ $? -eq 0 ]; then
    pass "model call" "$MODEL · $(echo "$OUT" | tail -1)"
  else
    fail "model call" "$MODEL — $(echo "$OUT" | tail -1 | cut -c1-70)"
  fi
elif [ -z "$MODEL_CHECK" ]; then
  warn "model call" "skipped (--no-model)"
fi

# --- the seeded conversation Chapter 3 opens ------------------------------
if [ -f sessions.db ]; then
  EVENTS=$("$PY" - <<'PYSEED' 2>/dev/null
import sqlite3
db = sqlite3.connect("sessions.db")
try:
    print(db.execute("select count(*) from events where session_id='two-days-ago'").fetchone()[0])
except sqlite3.Error:
    print(0)
PYSEED
  )
  if [ "${EVENTS:-0}" -gt 0 ]; then
    pass "seeded session" "two-days-ago · $EVENTS events"
  else
    fail "seeded session" "not in sessions.db — run: $PY -m seed.session"
  fi
else
  fail "seeded session" "no sessions.db — run: $PY -m seed.session"
fi

# --- the memory file ------------------------------------------------------
MEMFILE="${MEMORY_DIR:-./memory}/${MEMORY_USER:-userx}.md"
if [ -f "$MEMFILE" ]; then
  pass "memory file" "$MEMFILE · $(grep -c '^- ' "$MEMFILE") lines of memory"
else
  fail "memory file" "$MEMFILE missing — cp seed/memory/default.md $MEMFILE"
fi

# --- the six chapters -----------------------------------------------------
MISSING=""
for d in step1_meet step2_wake step3_remember step4_resume step5_buy step6_cloud; do
  [ -d "solutions/$d/concert" ] && [ -d "solutions/$d/monstertix" ] || MISSING="$MISSING $d"
done
if [ -z "$MISSING" ]; then
  pass "solutions" "6 chapters, each with concert/ + monstertix/"
else
  fail "solutions" "incomplete:$MISSING"
fi
if [ -f agent/concert/agent.py ]; then
  pass "agent/concert" "loaded — ./use-solution.sh to change chapter"
else
  fail "agent/concert" "empty — run ./use-solution.sh 1"
fi

# --- the venue ------------------------------------------------------------
pass "region" "${GOOGLE_CLOUD_REGION:-us-central1}  (services)"

if [ -n "${VENUE_URL:-}" ]; then
  if curl -sf --max-time 20 "$VENUE_URL/health" >/dev/null 2>&1; then
    pass "venue" "$VENUE_URL"
  else
    fail "venue" "$VENUE_URL not answering /health — ./deploy-venue.sh"
  fi
else
  fail "venue" "not deployed yet — run ./deploy-venue.sh"
fi

# --- the workbench --------------------------------------------------------
if [ -f web/dist/index.html ]; then
  pass "workbench page" "web/dist/index.html built"
elif command -v npm >/dev/null 2>&1; then
  warn "workbench page" "not built yet; npm found — ./workbench.sh builds it"
else
  fail "workbench page" "web/dist missing and no npm — install Node, or use the terminal path"
fi

# Is it answering? In Cloud Shell this is the only port you preview: the
# ADK web UI, the venue panel and MonsterTix are all reached through it.
WB_PORT="${WORKBENCH_PORT:-4800}"
if curl -sf --max-time 5 "http://127.0.0.1:$WB_PORT/api/env" >/dev/null 2>&1; then
  if [ -n "${CLOUD_SHELL:-}" ]; then
    pass "workbench" "on :$WB_PORT — Web Preview → Change port → $WB_PORT"
  else
    pass "workbench" "http://localhost:$WB_PORT"
  fi
else
  warn "workbench" "not running — ./workbench.sh starts it"
fi

# --- room to work ----------------------------------------------------------
# Cloud Shell's home disk is 5 GB and shared with every other lab you have
# cloned there. The venv and node_modules need about 300 MB; a build that
# runs out of space fails with an error that does not say so.
FREE_MB=$(df -Pm "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')
if [ -n "${FREE_MB:-}" ]; then
  if [ "$FREE_MB" -lt 150 ]; then
    fail "disk" "${FREE_MB} MB free in $HOME — not enough for a build; clear space"
  elif [ "$FREE_MB" -lt 500 ]; then
    warn "disk" "${FREE_MB} MB free in $HOME — enough, but close"
  else
    pass "disk" "${FREE_MB} MB free in $HOME"
  fi
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "  Ready. Cloud SQL is still building in the background and nothing"
  echo "  before Chapter 6 needs it."
  echo ""
  exit 0
fi
echo "  Fix the ✗ rows above, then run ./verify.sh again."
echo ""
exit 1
