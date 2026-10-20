# Chapter 3 · Remember What Matters

Four places a fact can live, and compaction. Load with `./use-solution.sh 3`.

```
concert/tools.py     + note_companion(name, constraint) → state["user:prefs"]
                     get_seatmap still saves the full map as an artifact and the
                     summary as temp:seatmap (this is the chapter that explains why)
concert/memory.py    + remember(fact) in the tool list (the service itself is unchanged)
concert/agent.py     tools=[search_events, get_seatmap, recall, note_companion, remember]
                     App(... events_compaction_config=EventsCompactionConfig(
                           compaction_interval=3, overlap_size=1,
                           summarizer=LlmEventSummarizer(llm=Gemini(model=MODEL))))
```

| Fact | Where it goes | Lasts |
|---|---|---|
| `temp:seatmap` | nowhere — stripped before the write | this invocation |
| `user:prefs` | `user_states` table | every session of this user |
| `seatmap_<event>.json` | the Artifact Service (`artifacts/`) | until deleted |
| a `remember()` line | `memory/userx.md` | until edited; survives deleting the DB |

## Run it by hand

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh 3
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

New session: *Sam can't do weeknights, by the way.* → *Show me the seat map
for the Amsterdam Saturday show.* → *Actually, hold that — what else is on in
Amsterdam?* Then compare the State tab with `two-days-ago`, and read the file:

```bash
cat memory/userx.md
./show-compaction.sh two-days-ago      # the seeded summary, via adk web's API
```

Tests: `./tests/run.sh tests/step3_remember`.
