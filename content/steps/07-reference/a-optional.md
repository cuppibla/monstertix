None of this is required. Each block says how long it takes and what it
assumes is in place. The chapter checks do not depend on any of it.

:::optional title="Prompt variants: how many wordings does it take?" minutes=5 needs="chapter 2 loaded; the ADK web UI running"
Chapter 2 swapped `INSTRUCTION` for `PROACTIVE_INSTRUCTION` once and showed
that no wording starts a run. Keep going: write two or three more variants in
`agent/concert/agent.py` — *"check every minute"*, *"as soon as the presale
opens"*, *"do not wait for me"* — restart the agent after each, and watch the
agent's log for a new invocation that nobody asked for.

```python
# agent/concert/agent.py, chapter 2
root_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,           # ← swap to PROACTIVE_INSTRUCTION, then restart
    tools=[search_events, get_seatmap, recall],
)
```

What you are looking for is the thing that never appears. An instruction is
read when a run happens; it cannot cause one. The point is cheaper to make
with one variant and more convincing with four.
:::

:::optional title="Compaction, triggered live" minutes=10 needs="chapter 3 loaded (an LlmAgent root); a session with three or more turns"
Chapter 3 showed a prepared sample. To watch it happen: in the ADK web UI, on
the chapter 3 code, have a conversation of four or five turns about the tour
— ask for the Amsterdam shows, the seat map, a price, who is coming. The
`App` is configured with `compaction_interval=3, overlap_size=1`, so a
summary is written after the third turn and again every three.

:::exercise id="compaction"
:::

Then the same records, as rows. Compaction lives in an event's
`actions.compaction`, not in its content — which is why the dev UI has nothing
to draw for it:

:::terminal
sqlite3 sessions.db "select session_id, json_extract(event_data, '$.actions.compaction.compacted_content.parts[0].text') from events where json_extract(event_data, '$.actions.compaction') is not null;"
:::

Compare what the summary says with the State tab: `user:prefs` is still exact
after compaction; the sentence that produced it may be gone from the
transcript. That is the difference between a fact kept in state and a fact
left loose in the conversation.

:::code path="agent/concert/agent.py" highlight="events_compaction_config=EventsCompactionConfig|compaction_interval=3|overlap_size=1|summarizer=LlmEventSummarizer"
:::
:::

:::optional title="The LongRunningFunctionTool alternative" minutes=10 needs="nothing — reading only; chapter 4 for context"
ADK has a second way to park a run: a **tool** that returns immediately with a
handle and leaves the invocation waiting until something sends the result
back. Make `join_queue` a `LongRunningFunctionTool` inside the chat agent: it
returns the ticket at once, the run parks on the tool call, and a poller that
notices the ticket reach the front POSTs the stored `function_response` into
the session. `ResumabilityConfig(is_resumable=True)` on the `App` is needed
just the same.

| | `Workflow` (the main line) | `LongRunningFunctionTool` |
|---|---|---|
| Fits | a task with several steps, where the policy per step matters | one slow call inside a conversation |
| Who decides what reruns | `rerun_on_resume` on each node | nobody — the "join once, check many times" rule moves into your poller |
| Where the wait lives | a node returning `RequestInput` with a stable id | the tool call itself; the id is the call's |
| Who may answer | the id's prefix says | whoever holds the function-call id |

The course keeps the graph on the main line because the policy per node is
the thing being taught. If your task is one chat with one slow step, the tool
is less machinery.
:::

:::optional title="Conditional budgets" minutes=5 needs="nothing — a discussion; chapter 5 for context"
*"About $100 for the cheap seats, $250 if they're the good ones, more on a
Saturday."* One decision, three numbers, two conditions. `budget.parse`
refuses it on purpose and asks for the shape the guard can check:

:::code path="agent/concert/budget.py" highlight="Conditional budgets|^def parse\("
:::

A real implementation keeps the sentence verbatim — that part the course
already does — and evaluates each condition **at purchase time** against the
live seat map, not at the time it was agreed: which tier is this section,
which weekday is this show, so which number applies. Two things to get right
if you build it. The evaluation must be code, not the model, for the same
reason `allows()` is code. And the read-back must confirm the *interpretation*
(*"so: up to $100 for sections B and C, up to $250 for A, and on a Saturday
…?"*), because a sentence with conditions is where a person and a parser most
often disagree.
:::

:::optional title="Cloud Trace: one wake-up as a trace" minutes=5 needs="chapter 6 deployed; the Cloud Trace API enabled on the project"
`get_fast_api_app` takes `trace_to_cloud=True`. Add it in `agent/main.py`,
run `./deploy-agent.sh` again, fire the scheduler as in 6B, and open the
**Trace** page in the console for `concert-<you>`. One trace covers
`POST /trigger/wake`: the session read from Cloud SQL, the queue check against
the venue, the guard's seat-map read, `purchase`, the session write. Ingestion
lags by minutes; a trace from a run a while ago reads better on a projector
than one from thirty seconds ago.

:::code path="agent/main.py" highlight="^app = get_fast_api_app\(|trigger_sources=\[\x22pubsub\x22\]"
:::
:::

:::optional title="Deeper database queries" minutes=5 needs="chapter 6 deployed, or the local sessions.db for the SQLite versions"
Locally, with `sqlite3`:

:::terminal
sqlite3 sessions.db "select id, update_time, substr(state, 1, 120) from sessions order by update_time desc limit 5;"
sqlite3 sessions.db "select json_extract(state, '$.authorization') from sessions order by update_time desc limit 1;"
sqlite3 sessions.db "select count(*) from events where json_extract(event_data, '$.content.parts[0].function_call.name') = 'adk_request_input';"
:::

In the cloud, the same tables in Postgres. `gcloud sql connect` is
interactive, so run it in a terminal:

:::terminal
gcloud sql connect workshop-sessions --user=adk --database=adk
:::

```sql
select id, update_time from sessions order by update_time desc limit 5;
select state->'authorization' from sessions order by update_time desc limit 1;
select count(*) from events where session_id = '<id>';
```

And the memory file, as an object:

:::terminal
gcloud storage cat "$STATE_BUCKET/memory/userx.md" | head -20
:::

The pending interrupt is not a column. It is the last `adk_request_input`
function call in `events` with no matching `function_response` after it —
which is exactly what `handlers.pending_interrupt` computes.
:::
