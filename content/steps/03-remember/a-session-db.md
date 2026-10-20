Two days ago somebody talked to this agent about Amsterdam, Sam, and the upper bowl, then closed the laptop. The process that held that conversation is long gone, and the ADK web UI still lists it. So where is it? What exactly got written, by whom, and what does a brand-new session start with? This section is you finding the answer on disk rather than taking it on trust.

## What this chapter adds

:::figure src="/docs-img/04-02-impl.png" caption="Storage architecture: note_companion writes user:prefs; get_seatmap saves an artifact and a temporary summary; recall and remember use memory. The purchase tool shown here is added later, in chapter 5."
:::

| File | What changed |
|---|---|
| `tools.py` | `note_companion` is new: it writes a fact into `user:prefs`. `get_seatmap` used to return the whole seat map; now it saves the full map to a file and keeps a one-line summary in `temp:seatmap` |
| `memory.py` | new. Our own memory store, a Markdown file, with `recall` and `remember` over it |
| `agent.py` | three more tools in the list, and the instruction tells the agent to use them |

Three writers, and each lands in a different store. The agent is started with
two flags it did not have before, and they are what make any of it persist:

| Flag | What it is |
|---|---|
| `--session_service_uri` | where every message, tool call and state change is written, as rows. A SQLite file here |
| `--artifact_service_uri` | where files the agent saves go. A folder here |

Without them ADK keeps everything in memory and throws it away when the
process stops.

:::exercise id="run"
After your one message, three things went into storage, in three different
places:

| | What was stored | Which tool did it | Where it went |
|---|---|---|---|
| 1 | the full seat map, 6 KB | `get_seatmap`, via `save_artifact` | the artifact service: a file under `artifacts/` |
| 2 | a one-line seat map summary | `get_seatmap`, into `temp:seatmap` | **nowhere**: stripped before the state is saved |
| 3 | Sam cannot do weeknights | `note_companion`, two days ago | `user:prefs`, in session state, visible from every session of this user |

The **State** tab is where you check the second and the third. `user:prefs`
is there before you type anything; `temp:seatmap` is not there even though
`get_seatmap` wrote it a moment ago:

:::figure src="/docs-img/04-01-newsession3.png" caption="The State tab of a fresh session: user:prefs is there, temp:seatmap is not. Your keys will differ a little from this earlier build; the shape is the same."
:::

For comparison, this screenshot shows `two-days-ago`, a different session row. Its task-specific keys stay with that row; you do not need to switch sessions to continue:

:::figure src="/docs-img/04-02-oldsession1.png" caption="The session list: your new session and two-days-ago, side by side. Both are rows in the same sessions.db."
:::

:::figure src="/docs-img/04-02-oldsession2.png" caption="two-days-ago: target_event_id and party_size are plain keys, this session only. user:prefs is the same one your new session sees."
:::
:::

## Key code: the service writes, the database keeps

Two words get used as if they were one thing. They are not.

| | What it is | In this workshop |
|---|---|---|
| **Session Service** | the ADK object that reads and writes sessions: `create_session`, `append_event`, `get_session` | `DatabaseSessionService`, built by `adk web` from a URI |
| **Session DB** | the storage behind it | `sessions.db`, one SQLite file at the repo root |

The agent's switch starts it like this:

```bash
adk web agent --port 8000 \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

Without the first flag, ADK keeps sessions in memory and throws them away when the process stops. With it, the service writes every event into SQLite as it happens, and SQLite does not care whether the process that wrote it is still alive. That is the whole reason `two-days-ago` is still in the dropdown: a file outlived a process.

:::figure src="/content-images/adk-storage.svg" caption="adk web, its two flags, and where each one writes: sessions.db with its four tables, and the artifacts/ folder, filed by app, user and session."
:::

### How a conversation becomes rows

Here are the relevant tables. You can inspect them with the optional query below:

```
sessions      app_name · user_id · id · state · create_time · update_time
events        id · app_name · user_id · session_id · invocation_id · timestamp · event_data
user_states   app_name · user_id · state · update_time
```

**Every event is one row in `events`.** Your message is a row. `⚡ recall` is a row whose `event_data` holds a `function_call`. `✓ recall` is a row holding the `function_response`, with the memory text inside it. The final answer is a row with `text`. One message, three tools, one reply: eight rows, and the Events tab is a rendering of exactly those rows. Who said it, which tool, what came back: all JSON inside `event_data`.

**State rides along in the same rows.** When `note_companion` writes `tool_context.state["user:prefs"] = …`, the event it belongs to carries that change in `actions.state_delta`. The service applies the delta and also keeps the result where it is quick to read:

| A key called | The service stores it in | Who sees it |
|---|---|---|
| `party_size` | `sessions.state`, on that one row | that session only |
| `user:prefs` | `user_states`, keyed by app + user | every session of this user |
| `app:tour_id` | `app_states`, keyed by app | every user of the app |
| `temp:seatmap` | nowhere | this invocation, then gone |

ADK assigns the meaning of the prefixes. You do not declare them anywhere;
the first part of the key name decides where the value goes and how long it
lasts.

That last row is the one you saw with your own eyes: `get_seatmap` set `temp:seatmap` a second before the State tab was drawn, and the tab did not show it. ADK strips `temp:` keys before persisting. `temp:` is a scratchpad for one run, not a place to keep anything.

:::code path="agent/concert/tools.py" highlight="state\[\x22temp:seatmap\x22\] =|state\[\x22user:prefs\x22\] ="
:::

### A new session is not a deleted session

**New Session** inserts a new row in `sessions`. It does not touch `two-days-ago`. Both rows share `app_name="concert"` and `user_id="user"`, which is why both see the same `user_states` row and why your new session knew about Sam before you typed anything. What it did not inherit is `target_event_id` and `party_size`: those sit in the other session's `state` column, and no part of ADK copies them across.

Reset is the other thing. Loading a chapter deletes `sessions.db` and rebuilds it. That is why `two-days-ago` is always exactly two days old: `use-solution.sh` runs `seed/session.py`, which writes those twelve turns with back-dated timestamps, the `user:prefs` entry, the two session-scoped keys, and one genuine compaction record. It is a planted past, and it is planted in the same tables the agent writes to.

:::note
**Saving is not resuming.** The rows are the raw material for picking a task up after the process dies, and they are only the raw material. Nothing in this chapter resumes anything; what it takes to continue a *paused run* from these rows is chapter 4.
:::

:::checkpoint
**You press New Session and ask: "How many of us are going?" What does the agent know, and from where?**
:::answer
It knows Sam cannot do weeknights, because `user:prefs` is read from `user_states` for app `concert` and user `user`, and every session of that user sees it. It does not know the party size. `party_size: 2` is in the `state` column of the `two-days-ago` row only, and a new session is a new row. It will either ask, or call `recall` and find "always books two seats" in the memory file, which is the next section.
:::
:::

:::optional title="Inspect the rows with SQL" minutes=3 needs="your session from this chapter"
:::exercise id="sql"
:::
:::
