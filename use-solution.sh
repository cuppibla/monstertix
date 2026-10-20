#!/usr/bin/env bash
# Load a chapter's finished code into place, and reset the state around it.
#
#     ./use-solution.sh 4          load Chapter 4, from a clean slate
#     ./use-solution.sh 4 --keep   load the code, leave memory and sessions alone
#     ./use-solution.sh 4 --force  reset even if something holds sessions.db open
#     ./use-solution.sh            list what is available
#
# Every chapter ships the same two packages:
#
#     concert/      the agent          → agent/concert/
#     monstertix/   server, page, clock → ./monstertix/
#
# Chapter 6 also ships main.py, Dockerfile and requirements.txt, and those go
# into agent/ together with a copy of monstertix/, because agent/ is the build
# context `./deploy-agent.sh` uploads.
#
# Unless you pass --keep it also puts memory, sessions and artifacts back to
# their starting state. That is what makes a chapter behave the same on the
# fourth rehearsal as it did on the first.
#
# Your venue is never touched — press RESET THE VENUE on the panel for that.
set -euo pipefail
cd "$(dirname "$0")"

PY=./.venv/bin/python
[ -x "$PY" ] || PY=python

# The six chapters, by number. Fixed here rather than globbed, so a stray
# folder in solutions/ can never be loaded by accident.
stage_dir() {
  case "$1" in
    1) echo "solutions/step1_meet" ;;
    2) echo "solutions/step2_wake" ;;
    3) echo "solutions/step3_remember" ;;
    4) echo "solutions/step4_resume" ;;
    5) echo "solutions/step5_buy" ;;
    6) echo "solutions/step6_cloud" ;;
    *) echo "" ;;
  esac
}

stage_title() {
  case "$1" in
    1) echo "Meet MonsterTix" ;;
    2) echo "Wake the Agent" ;;
    3) echo "Remember What Matters" ;;
    4) echo "Pause, Restart, Resume" ;;
    5) echo "Buy Within Agreed Limits" ;;
    6) echo "Run It While You Sleep" ;;
  esac
}

if [ $# -eq 0 ]; then
  echo "Which chapter?"
  for n in 1 2 3 4 5 6; do
    d=$(stage_dir "$n")
    mark=""; [ -d "$d/concert" ] || mark="   (missing: $d/concert)"
    printf "  %s  %-28s %s%s\n" "$n" "$(stage_title "$n")" "$d" "$mark"
  done
  echo ""
  echo "  ./use-solution.sh 4"
  exit 0
fi

STEP="$1"
KEEP=""
FORCE=""
shift
for arg in "$@"; do
  case "$arg" in
    --keep)  KEEP=1 ;;
    --force) FORCE=1 ;;
    *) echo "✗ unknown option $arg  (--keep, --force)"; exit 1 ;;
  esac
done

MATCH=$(stage_dir "$STEP")
if [ -z "$MATCH" ] || [ ! -d "$MATCH" ]; then
  echo "✗ no solution for chapter $STEP"
  echo "  try:  ./use-solution.sh"
  exit 1
fi
if [ ! -d "$MATCH/concert" ] || [ ! -d "$MATCH/monstertix" ]; then
  echo "✗ $MATCH is incomplete — it needs both concert/ and monstertix/"
  exit 1
fi

# Deleting sessions.db while `adk web` holds it open does not error — it leaves
# the running process writing to a file nobody can see, and the next thing that
# looks strange costs an hour. Stop first.
if [ -z "$KEEP" ] && [ -z "$FORCE" ] && lsof -ti:8000 >/dev/null 2>&1; then
  echo "✗ something is running on :8000, and this would delete sessions.db"
  echo "  underneath it. Ctrl-C the agent first, then run this again."
  echo ""
  echo "  or:  ./use-solution.sh $STEP --keep      code only, state untouched"
  echo "       ./use-solution.sh $STEP --force     reset anyway (not the agent"
  echo "                                           on :8000? then this is you)"
  exit 1
fi

# ── the code ───────────────────────────────────────────────────────────────
# The agent.
rm -rf agent/concert
cp -r "$MATCH/concert" agent/concert

# The server, the page and the clock, at the root where
# `python -m monstertix.server` finds them.
rm -rf monstertix
cp -r "$MATCH/monstertix" monstertix

# The deployable surface. Only Chapter 6 has one; anything an earlier load left
# in agent/ is removed, so `adk web agent` sees exactly one app.
rm -f agent/main.py agent/server.py agent/Dockerfile agent/requirements.txt
rm -rf agent/monstertix
DEPLOYABLE=""
if [ -f "$MATCH/main.py" ]; then
  for f in main.py Dockerfile requirements.txt; do
    cp "$MATCH/$f" "agent/$f"
    DEPLOYABLE="$DEPLOYABLE $f"
  done
  cp -r "$MATCH/monstertix" agent/monstertix
  DEPLOYABLE="$DEPLOYABLE monstertix/"
fi

find agent monstertix -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

# `adk web` treats EVERY directory under agent/ as an app and errors on any that
# is not one — which empties the dropdown. A stray ./memory or ./artifacts left
# by running something from inside agent/ is enough to do it.
for d in agent/*/; do
  case "$(basename "$d")" in
    concert|monstertix) ;;
    *) rm -rf "$d"; echo "→ tidied  removed stray agent/$(basename "$d")/" ;;
  esac
done

LOADED="concert/ + monstertix/"
[ -n "$DEPLOYABLE" ] && LOADED="$LOADED + agent/{$(echo "$DEPLOYABLE" | sed 's/^ //; s/ /, /g')}"
echo "→ loaded  Chapter $STEP · $(stage_title "$STEP")  ($LOADED)"

# ── the state around it ────────────────────────────────────────────────────
if [ -z "$KEEP" ]; then
  # Memory. A chapter can have its own starting file; otherwise everyone gets
  # the same one. See seed/memory/README.md.
  SEED=seed/memory/step"$STEP".md
  [ -f "$SEED" ] || SEED=seed/memory/default.md
  mkdir -p memory
  cp "$SEED" memory/userx.md
  echo "→ memory  $SEED → memory/userx.md"

  # Sessions. Rebuilt rather than emptied, because Chapter 3 opens a
  # conversation that has to already exist and be two days old.
  rm -f sessions.db
  if "$PY" -m seed.session >/dev/null 2>&1; then
    echo "→ session sessions.db rebuilt, with 'two-days-ago' back in it"
  else
    echo "⚠ session sessions.db deleted, but reseeding failed."
    echo "          run '$PY -m seed.session' and read the error."
  fi

  # Artifacts. The seat maps a previous run saved are not this run's.
  rm -rf artifacts
  mkdir -p artifacts
  echo "→ files   artifacts/ emptied"
else
  echo "→ state   left alone (--keep)"
fi

# `adk web` defaults to --reload (uvicorn restarts the server on file changes)
# but --reload_agents=false. Whether a running server picks up new agent code is
# therefore not something to rely on. Restarting takes two seconds and removes
# the question, which is worth more than being right about it.
if lsof -ti:8000 >/dev/null 2>&1; then
  echo ""
  echo "⚠ adk web is running on :8000. Restart it so you know it is running"
  echo "  the code you just loaded, and check the tool list in the left panel."
fi
if lsof -ti:8090 >/dev/null 2>&1; then
  echo "⚠ MonsterTix is running on :8090. Restart it too — it imports the agent."
fi

echo ""
echo "  Now go and read what changed:"
for f in agent/concert/*.py; do
  case "$(basename "$f")" in
    venue.py|config.py|__init__.py) ;;
    *) printf "      %-34s %s\n" "$f" \
         "$(grep -m1 -oE '^"""[^"]*' "$f" | sed 's/^"""//' | cut -c1-52)" ;;
  esac
done
echo ""
case "$STEP" in
  6) echo "  Then:  ./setup-cloud-state.sh && ./deploy-agent.sh" ;;
  *) echo "  Then start adk web in terminal 1, and press RESET THE VENUE on the panel."
     echo "      python -m monstertix.server        # the page, on http://127.0.0.1:8090"
     echo "      python -m monstertix.clock --in 10 # the caller, in a third terminal" ;;
esac
