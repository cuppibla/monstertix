# Chapter 1 · Meet MonsterTix

The agent that can plan and nothing else. Load with `./use-solution.sh 1`.

```
concert/      agent.py    root_agent = Agent("concert", tools=[search_events, get_seatmap, recall])
                          app = App(name="concert", root_agent, plugins=[PanelPlugin()])
              tools.py    search_events(city, weekday) · get_seatmap(event_id) → artifact + temp:seatmap
              memory.py   MarkdownMemoryService over memory/userx.md; recall() and remember(fact)
                          (recall is in the tool list from chapter 1 so the answers make sense;
                          memory is *taught* in chapter 3)
              venue.py    httpx client; errors returned as data, never raised
              config.py   ADK_MODEL, fail-fast Vertex credential check
              panel.py    PanelPlugin: narrates tool calls to the venue's activity feed
monstertix/   server.py   POST /wake, POST /trigger/wake, GET /task … on :8090 (same in every chapter)
              handlers.py what those routes do; clock.py; index.html
```

Nothing here waits in a queue or spends money.

## Run it by hand

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh 1
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

Open http://localhost:8000, pick `concert`, and type
*Two tickets to The Midnight Signal in Amsterdam, for me and Sam.*
Expect `recall` → `search_events` → `get_seatmap(ms-ams-01)` and an answer
naming the Saturday show, section A, $210.

Tests: `./tests/run.sh tests/step1_meet`.
