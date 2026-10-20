"""THE TRIGGERER — something that knows the time. Ctrl-C to stop.

    python -m monstertix.clock --in 10           once, ten seconds from now
    python -m monstertix.clock --every 120       every two minutes, forever
    python -m monstertix.clock --in 10 --trigger  POST /trigger/wake instead:
                                                 resume a run waiting in the
                                                 queue, say nothing new

Look at what this file imports: `httpx`, `time`, `argparse`. No ADK. It has
never heard of an agent, a Runner or a session — it knows a URL and a clock.

That is the whole point of keeping it separate. In Chapter 6 this file is not
deployed and Cloud Scheduler does its job instead, and nothing on the other
side changes. `--trigger` is the local rehearsal of exactly that: the same
route the scheduler reaches, with the same empty body.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

TRIGGER_URL = os.environ.get(
    "TRIGGER_URL", f"http://127.0.0.1:{os.environ.get('TRIGGER_PORT', '8090')}"
).rstrip("/")

# A check, not a purchase. Nothing is bought until Chapter 5, and nothing is
# ever bought without an authorization a person gave in this task.
DEFAULT_MESSAGE = (
    "Check whether the Amsterdam shows still have seats, and tell me what you find."
)


def log(message: str) -> None:
    print(f"[clock] {message}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m monstertix.clock")
    parser.add_argument("--in", dest="delay", type=float, default=60,
                        help="seconds until the first fire (default 60)")
    parser.add_argument("--every", type=float, default=0,
                        help="seconds between fires; 0 = once only")
    parser.add_argument("--message", default=DEFAULT_MESSAGE,
                        help="what to say on POST /wake (ignored with --trigger)")
    parser.add_argument("--trigger", action="store_true",
                        help="POST /trigger/wake — resume a queue wait, like Cloud Scheduler")
    args = parser.parse_args()

    route = "/trigger/wake" if args.trigger else "/wake"
    body = {} if args.trigger else {"message": args.message}

    log(f"target   {TRIGGER_URL}{route}")
    log(f"first fire in {args.delay:g}s"
        + (f", then every {args.every:g}s" if args.every else ", once only"))
    log("go and watch the other terminal — do not touch the keyboard")

    with httpx.Client(timeout=300) as client:
        time.sleep(args.delay)
        while True:
            log(f"firing → POST {route}")
            try:
                response = client.post(f"{TRIGGER_URL}{route}", json=body)
                if response.status_code >= 400:
                    log(f"trigger returned {response.status_code}")
                elif args.trigger and not (response.json() or {}).get("woke"):
                    # The server answered, but found nothing a timer may resume.
                    # That is a result, not a failure — a person's question
                    # stays a person's question at 3am.
                    log(f"nothing resumed: {(response.json() or {}).get('reason')}")
                else:
                    log("done. the agent ran and you were not involved.")
            except httpx.HTTPError:
                log(f"nothing listening at {TRIGGER_URL} — is the server running?")
            except ValueError:
                log("done. the agent ran and you were not involved.")
            if not args.every:
                return
            time.sleep(args.every)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped.")
        sys.exit(0)
