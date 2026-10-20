# Chapter 2 · Wake the Agent

Same agent as chapter 1, plus the prompt lab. Load with `./use-solution.sh 2`.

```
concert/agent.py     adds PROACTIVE_INSTRUCTION. Swap it into root_agent, restart, and
                     watch nothing happen: an instruction cannot create an invocation.
monstertix/          unchanged in content, but this is the chapter that uses it:
  server.py          a Runner behind POST /wake — what adk web was doing for you
  clock.py           httpx + time + argparse, no ADK. POSTs to /wake after --in seconds.
                     DEFAULT_MESSAGE is an availability check; nothing is bought.
  handlers.py        wake(): runs the agent once and returns what it said
```

## Run it by hand

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh 2
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

**2A** — edit `agent/concert/agent.py`: `instruction=PROACTIVE_INSTRUCTION`,
restart `adk web`, tell it the plan, wait a minute. No new invocation. Put
`INSTRUCTION` back.

**2B** — two more terminals (each after `. ./set_env.sh`):

```bash
python -m monstertix.server          # :8090, logs every wake
python -m monstertix.clock --in 10   # fires once, ten seconds from now
```

Expect the server log to show `woken · session wake-…`, `called recall`,
`called search_events`, and a sentence about seat availability. No ticket, no
order on the venue panel.

Tests: `./tests/run.sh tests/step2_wake`.
