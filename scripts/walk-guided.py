#!/usr/bin/env python3
"""Walk the local core through the same endpoints as the page.

This resets the named LOCAL workbench's live experiment and calls the real
model. It never deploys or runs the cloud demo. Use an isolated workbench.
"""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--url", required=True, help="isolated local workbench origin")
parser.add_argument("--output", default="runs/guided-walk.json")
args = parser.parse_args()
assert urllib.parse.urlsplit(args.url).hostname in ("localhost", "127.0.0.1", "::1"), "local workbench only"
base = args.url.rstrip("/")
report = {"started_at": time.time(), "chapters": {}, "cloud": "not run; requires instructor deployment"}


def request(path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()) from exc


def save():
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))


def act(slug, action, state, **extra):
    print(f"{slug}: {action}", flush=True)
    return request(f"/api/learning/{slug}/{action}", {
        "attempt_id": (state.get("attempt") or {}).get("id"), **extra})


try:
    for slug in ("meet", "wake", "remember", "resume", "buy"):
        state = act(slug, "prepare", {}, fresh=True)
        for previous in report["chapters"]:
            assert request(f"/api/learning/{previous}").get("receipt"), f"lost receipt: {previous}"
            assert any(request(f"/api/learning/{previous}/records")["sessions"]), f"lost records: {previous}"
        if slug != "meet":
            assert state["next"] == "request", state
            state = act(slug, "request", state)
        if slug == "wake":
            state = act(slug, "clock", state)
            deadline = time.time() + 180
            while not state.get("receipt") and time.time() < deadline:
                time.sleep(2)
                state = request("/api/learning/wake")
                timer = state["attempt"]["marks"].get("timer", {})
                if timer.get("state") in ("failed", "interrupted", "blocked"):
                    raise AssertionError(state)
        elif slug == "remember":
            state = act(slug, "remember", state)
            state = act(slug, "new-session", state)
        elif slug == "resume":
            original = state["task"]["session_id"]
            ticket = state["task"]["queue_ticket"]
            state = act(slug, "kill", state)
            assert state["next"] == "restart"
            state = act(slug, "restart", state)
            state = act(slug, "resume", state)
            assert state["task"]["session_id"] == original
            assert state["task"]["queue_ticket"] == ticket
            assert state["venue"]["orders"] == 0
        elif slug == "buy":
            # Test fixture answers in the simulated venue, never real spending.
            for answer in ("Two tickets, up to $250 each.", "Yes, I confirm two tickets at up to $250 per ticket."):
                assert state["next"] == "answer", state
                state = act(slug, "answer", state, text=answer, interrupt_id=state["task"]["pending"]["id"])
            state = act(slug, "scenario", state)
            assert state["venue"]["orders"] == 0
            state = act(slug, "resume", state)
        assert state.get("receipt"), {"slug": slug, "state": state}
        report["chapters"][slug] = state["receipt"]
        save()
        print(f"{slug}: complete; {len(state['receipt']['checks'])} observed results", flush=True)
    report["finished_at"] = time.time()
    print("All five local chapters passed. Cloud demonstration was not run.", flush=True)
except Exception as exc:
    report["error"] = str(exc)
    raise
finally:
    save()
