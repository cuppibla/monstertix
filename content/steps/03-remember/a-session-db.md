Two days ago somebody talked to this agent about Amsterdam, Sam, and the upper bowl, then closed the laptop. The process that held that conversation is long gone, and the ADK web UI still lists it. So where is it? What exactly got written, by whom, and what does a brand-new session start with? This section is you finding the answer on disk rather than taking it on trust.

:::exercise id="run"
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

### How a conversation becomes rows

Look at your query's output again. Five tables, and two do the work:

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
| `temp:seatmap` | nowhere | this invocation, then gone |

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
