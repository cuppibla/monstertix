#!/usr/bin/env bash
# The workbench: the workshop's steps in the browser, with the venue, the
# agent, MonsterTix and the clock as switches on the left.
#
#     ./workbench.sh            start it in the background, print the link
#     ./workbench.sh stop       stop it, and every process it started
#     ./workbench.sh restart    stop, rebuild the page if needed, start
#     ./workbench.sh fg         run it in this terminal; Ctrl-C stops everything
#
# In Cloud Shell: Web Preview → Change port → 4800.
[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
set -euo pipefail
cd "$(dirname "$0")"

PORT="${WORKBENCH_PORT:-4800}"
PY=./.venv/bin/python
[ -x "$PY" ] || { echo "✗ no .venv yet. Run ./setup.sh first."; exit 1; }
mkdir -p runs

running_pid() {
  # Two checkouts may be open at once. Never stop another checkout's server.
  local candidate directory
  for candidate in $(pgrep -f -- "-m workbench$" 2>/dev/null || true); do
    if [ -d "/proc/$candidate/cwd" ]; then
      directory="$(readlink "/proc/$candidate/cwd" 2>/dev/null || true)"
    elif command -v lsof >/dev/null 2>&1; then
      directory="$(lsof -a -p "$candidate" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
    else
      continue
    fi
    if [ "$directory" = "$(pwd -P)" ]; then
      echo "$candidate"
      return
    fi
  done
}

stop() {
  local pid
  pid="$(running_pid)"
  if [ -z "$pid" ]; then
    echo "→ workbench was not running"
    return 0
  fi
  # SIGINT is Ctrl-C: the workbench stops what it started before it exits.
  kill -INT "$pid" 2>/dev/null || true
  for _ in $(seq 1 40); do
    kill -0 "$pid" 2>/dev/null || { echo "→ workbench stopped"; return 0; }
    sleep 0.25
  done
  kill -KILL "$pid" 2>/dev/null || true
  echo "→ workbench stopped (forced)"
}

build() {
  # The page is built once; it is rebuilt only when its sources are newer.
  if ! command -v npm >/dev/null 2>&1; then
    [ -f web/dist/index.html ] || { echo "✗ npm is not installed and the page is not built"; exit 1; }
    return 0
  fi
  if [ ! -d web/node_modules ]; then
    echo "→ installing the page's packages"
    (cd web && npm ci --no-audit --no-fund --loglevel=error)
  fi
  if [ ! -f web/dist/index.html ] || [ -n "$(find web/src web/index.html web/package.json -newer web/dist/index.html -print -quit)" ]; then
    echo "→ building the page"
    (cd web && npm run build --silent >/dev/null)
  fi
}

start() {
  if [ -n "$(running_pid)" ]; then
    echo "→ workbench is already running"
  else
    if curl -fsS "http://127.0.0.1:$PORT/api/env" >/dev/null 2>&1; then
      echo "✗ port $PORT is already serving another checkout; choose WORKBENCH_PORT"
      exit 1
    fi
    build
    nohup "$PY" -m workbench > runs/workbench.log 2>&1 &
    for _ in $(seq 1 40); do
      curl -fsS "http://127.0.0.1:$PORT/api/env" >/dev/null 2>&1 && break
      sleep 0.25
    done
    curl -fsS "http://127.0.0.1:$PORT/api/env" >/dev/null 2>&1 \
      || { echo "✗ the workbench did not start. runs/workbench.log says:"; tail -20 runs/workbench.log; exit 1; }
    echo "→ workbench started (log: runs/workbench.log)"
  fi
  echo ""
  if [ -n "${CLOUD_SHELL:-}" ]; then
    echo "  Open it: Web Preview (top right) → Change port → $PORT"
  else
    echo "  Open it: http://localhost:$PORT"
  fi
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  fg)      build; exec "$PY" -m workbench ;;
  *)       echo "usage: ./workbench.sh [start|stop|restart|fg]"; exit 1 ;;
esac
