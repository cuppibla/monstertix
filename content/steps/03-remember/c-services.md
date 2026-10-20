You now have three stores and five lifetimes in play, and the next two chapters add a queue ticket, a plan and an authorization on top. Before any of that, put the whole picture in one place: which service holds what, how long each thing lasts, what a new session carries over, and what a summary does to a conversation when it gets long.

:::exercise id="run"
The **Artifacts** tab is the third store. The seat map `get_seatmap` saved is
listed there by name, with a version number, and the same bytes are in the
explorer under `artifacts/`:

:::figure src="/docs-img/04-01-newsession4.png" caption="The Artifacts tab: seatmap_ms-ams-01.json, version 0. The file never entered the prompt; the model got a one-line summary and a filename."
:::
:::

## Key code: three services, one table

| Service | Main job | Storage in this workshop | In chapter 6 |
|---|---|---|---|
| **Session Service** | events, state, and the records a paused run needs to continue | SQLite, `sessions.db` | Cloud SQL |
| **Memory Service** | long-term information for later tasks to read | Markdown, `memory/userx.md` | Cloud Storage |
| **Artifact Service** | file contents, like the seat map | local files, `artifacts/` | Cloud Storage |

Each is an interface with a storage behind it, and moving to the cloud changes the URI, not the code that calls it. `save_artifact` in `get_seatmap` writes through whichever artifact service `adk web` was started with:

:::code path="agent/concert/tools.py" highlight="save_artifact\(|^async def get_seatmap"
:::

| URI | Where the bytes go |
|---|---|
| `memory://` | RAM. Gone when the process stops. The default if you pass no flag |
| `file://…` | a folder on disk. What you are using now |
| `gs://bucket` | Cloud Storage. What the deployed agent uses |

The seat map is 6 KB. Returned from the tool, it would be re-sent to the model on every later turn of the session. Saved as an artifact, the prompt pays one filename, and the agent can `load_artifact` the detail back on the rare occasion it needs it. The file you found under `artifacts/apps/concert/users/user/sessions/<session>/…` is the service doing that: app, user and session are in the path, which is why the Artifacts tab of a new session is empty.

### Every fact has a shelf life

:::figure src="/docs-img/04-02-fivestage.png" caption="Five places a fact can live, and how long each lasts"
:::

| Where it lives | Survives the next message? | Survives a restart? | Survives a new session? | Survives deleting `sessions.db`? |
|---|---|---|---|---|
| `temp:seatmap` | **no** | no | no | no |
| `party_size` (plain session state) | yes | yes | **no** | no |
| `user:prefs` | yes | yes | yes | no |
| `memory/userx.md` | yes | yes | yes | **yes** |
| an artifact | yes | yes | no: the path includes the session id, though the file stays on disk | yes, with `file://` |

ADK assigns the meaning of the prefixes. You do not declare them anywhere; the first part of the key name decides where the value goes and how long it lasts. An *invocation* is one request-response cycle, including every tool call inside it. When it ends, ADK writes the new state and strips every `temp:` key on the way out.

**Read that table as being about the containers, not what is in them.** `memory/userx.md` survives everything and only ever holds what `remember()` chose to put there. Nothing writes your current conversation into it.

:::warn
**You will meet `temp:` again in chapter 4.** ADK's own `ResumabilityConfig` docstring says: *"Any temporary / in-memory state will be lost upon resumption."* Your agent is about to join a queue, stop running for forty minutes, and be woken up. `temp:` will not survive that; `user:` state, plain session state and the memory file will.
:::

### This session versus a new one

You did the comparison. Here is what it will look like once chapters 4 and 5 have added their keys:

| | Carries into a new session? | Why |
|---|---|---|
| `user:prefs` | **yes** | stored against the user |
| the memory file | **yes** | not part of any session |
| the transcript and its summaries | no | `events` rows of one session |
| `queue_ticket`, `plan` (chapter 4) | no | plain session state: this task's place in line |
| `authorization` (chapter 5) | no | plain session state, on purpose: a new task gets a new authorization |

One condition on the **yes** rows: the identity has to match. `user:prefs` is keyed by app `concert` and user `user`, and the memory file is picked by `MEMORY_USER`. `adk web`, the MonsterTix server, the seed and the workbench all use the same pair. Seed under a different user id and the row exists, is queryable, and is invisible from the dropdown.

:::warn
**Both stores surviving is not the same as the agent remembering what you were just doing.** `user:prefs` and the memory file cross into a new session, and neither says which show you were in the middle of booking. That lived in the transcript and in session state, and both stayed behind. Chapter 4 is built on exactly that gap.
:::

## Compaction: a read-only sample

:::figure src="/docs-img/05-02-intro.png" caption="Compaction works on the session's events. Memory is a separate store"
:::

Long sessions get summarized. `App(events_compaction_config=EventsCompactionConfig(compaction_interval=3, overlap_size=1, …))` tells ADK: after every three user-initiated invocations, replace the older events the model is shown with a summary written by another model call, starting one turn earlier than strictly needed so no question is cut from its answer. Three is tuned so it fires in a workshop; production values are much larger.

:::code path="agent/concert/agent.py" highlight="^app = App\(|events_compaction_config=EventsCompactionConfig\(|compaction_interval=|overlap_size=|summarizer=LlmEventSummarizer"
:::

:::figure src="/docs-img/05-02-compaction.png" caption="compaction_interval=3, overlap_size=1: summary B starts one turn before summary A ended, so a question and its answer are never split across two summaries. The summaries are rows in the session store."
:::

:::figure src="/docs-img/04-02-oldsession2.png" caption="two-days-ago in the Events list: row #5, marked N, is where a summary stands in for the turns before it. That row is the compaction record."
:::

Here is what it does, on the `two-days-ago` session, labelled. **Sample 1 · the raw turns** (the first four events, as written):

```
you      We're thinking about seeing The Midnight Signal. Me, Sam, and maybe Priya.
agent    They've got eight dates. Amsterdam on the 14th and 10th, New York, Tokyo,
         Mexico City, Auckland. Amsterdam is closest to you — shall I look at those two?
you      Yes. Sam can't do weeknights though, he's bailed on every single one.
agent    Noted — I'll rule out anything midweek. That kills the 10th, which is a
         Tuesday. So Amsterdam on Saturday the 14th.
```

**Sample 2 · the summary** (one more `events` row, with the text under `actions.compaction.compacted_content` instead of `content`; this is what the model is handed in place of the four turns above):

```
The user is planning to see The Midnight Signal with friends. They looked at the
Amsterdam dates and settled on a Saturday show because Sam cannot do weeknights.
Pricing was discussed: lower bowl $210, upper $145, GA $95.
```

**Sample 3 · the persisted state**, before and after that summary was written:

```
user:prefs        {"Sam": "cannot do weeknights"}     unchanged
target_event_id   ms-ams-01                           unchanged
party_size        2                                   unchanged
memory/userx.md   (the file)                          unchanged
```

So: **what compaction changes** is the transcript the model reads. Four turns became a paraphrase that kept the decision and the prices and dropped the wording, Priya, and "bailed on every single one". **What it does not change** is anything outside the transcript: session state, `user:` state, the memory file and the artifacts are untouched, because compaction never looks at them. That is the whole case for `note_companion` and `remember`: a fact in state or in the file is read back exactly as written; a fact left loose in the conversation is eventually read as a summary somebody else wrote, with no error and no log line when it drifts.

:::key
Put a fact where its lifetime matches how long you need it. Anything you cannot afford to have paraphrased goes somewhere other than the conversation.
:::

:::checkpoint
**The session DB and the memory file are both still there. Why does a new session still not know what "continue that order" refers to?**
:::answer
Because the two things that cross sessions are the two that do not hold it. `user:prefs` says Sam cannot do weeknights; the memory file says past bookings and preferences. "That order" was a show, a party size, and a place in a conversation, and all three lived in the old session: as `events` rows (the transcript and its summary) and as plain session state (`target_event_id`, `party_size`, later `queue_ticket` and `plan`). A new session is a new row in `sessions` with none of them. The stores survived; the task is addressed by session id, and the new session has a different one. Continuing a task means going back to *that* session, which is what chapter 4 does.
:::
:::

:::optional title="Trigger a compaction yourself" minutes=8 needs="chapter 3 loaded, the ADK web UI"
`compaction_interval=3` counts user-initiated invocations. In a new session, have four or five short turns ("hello", "what's on in Amsterdam?", "Sam is coming and he can't do weeknights", "what would two good seats cost?"), then read the summaries ADK wrote:

```bash
./show-compaction.sh            # the session you used most recently
./show-compaction.sh two-days-ago
```

`python3 -m workbench.probe compaction` prints the latest summary too. Compare it with what you actually typed, and then check `user:prefs` in the State tab: unchanged.

**The parameters.** `compaction_interval` is how many invocations between summaries; `overlap_size` is how many turns each summary re-covers from the previous window, so a question and its answer are not split across two summaries. ADK has no default for either; set both. `token_threshold` is the production alternative to a fixed interval. The summarizer is named explicitly (`LlmEventSummarizer(llm=Gemini(model=MODEL))`) because chapter 4 makes the root a `Workflow`, which has no model to borrow.

**Where it sits in SQLite.** A compaction record is an ordinary `events` row with no `content`; the summary is under `actions.compaction`:

```
events row
└── event_data  (JSON)
    ├── id, author, timestamp, invocation_id      ← like every other event
    ├── content                                    ← ABSENT on this one
    └── actions
        └── compaction
            ├── start_timestamp                    ← the window it replaced
            ├── end_timestamp
            └── compacted_content.parts[0].text    ← the summary itself
```

```bash
.venv/bin/python -c "import sqlite3, json; db = sqlite3.connect('file:sessions.db?mode=ro', uri=True); [print(r[0]) for r in db.execute(\"select json_extract(event_data, '$.actions.compaction.compacted_content.parts[0].text') from events where event_data like '%compaction%'\")]"
```

The dev UI draws each event from its `content`, so a compaction row shows as a summary block rather than a message; the database is where the text actually is.
:::
