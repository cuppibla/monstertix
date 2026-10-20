You saved one preference and watched a new session recall it. Now separate
that long-term memory from the task itself: a preference can carry forward,
but a new conversation does not inherit the old task's place in line.

## Three services, three jobs

| Service | Holds | In this lab | In the cloud |
|---|---|---|---|
| **Session Service** | conversation events, task state, and resume records | `sessions.db` | Cloud SQL |
| **Memory Service** | selected facts to read in later tasks | `memory/userx.md` | Cloud Storage |
| **Artifact Service** | files, such as the full seat map | `artifacts/` | Cloud Storage |

The Session Service answers **“where did this task stop?”** The Memory Service
answers **“what should a later task know about this person?”** They solve
different problems. `recall()` brings a saved preference into a model call;
saving an event in the Session DB does not automatically write it to memory.

:::figure src="/docs-img/04-02-fivestage.png" caption="Five places a fact can live. The key distinction is whether it belongs to this invocation, this task, or the person across tasks."
:::

| Where it lives | Next message? | Process restart? | New session? |
|---|---|---|---|
| `temp:seatmap` | no | no | no |
| `party_size` — plain session state | yes | yes | **no** |
| `user:prefs` | yes | yes | **yes**, for the same app and user |
| `memory/userx.md` | yes | yes | **yes**, if the new task calls `recall()` |
| a seat-map artifact | yes | yes, with file storage | no; its path includes the session id |

These are the storage choices in this lab. The default in-memory services
would lose their data when the process stops. The file-backed services here
survive a process restart; deleting their files is a different operation.

### Read the code behind one example

:::code path="agent/concert/tools.py" highlight="save_artifact\(|^async def get_seatmap|state\[\x22temp:seatmap\x22\] ="
:::

`get_seatmap` saves the full map as an artifact and returns a short summary to
the model. It also sets `temp:seatmap` for the current invocation. ADK removes
that temporary value before persisting state. In the next chapter, the chosen
show and queue ticket must therefore go into **plain session state**.

:::optional title="Inspect the full seat-map artifact" minutes=2 needs="a session that called get_seatmap"
:::exercise id="run"
:::figure src="/docs-img/04-01-newsession4.png" caption="The Artifacts tab holds the full map under a filename and version. The model received a short summary rather than every seat."
:::
:::
:::

:::key
A new session can know your preferences without knowing which task you were
halfway through. To continue a paused task, return to that task's session.
:::

:::checkpoint
**Both the Session DB and memory file still exist. Why does a new session not know what “continue that order” refers to?**
:::answer
The old task's transcript and state belong to its session id. A new session
starts with a different id and no queue ticket or plan. It can recall general
preferences, but continuing the task means loading the old session. That is
what we will do in chapter 4.
:::
:::

:::optional title="Compaction: a read-only comparison" minutes=4 needs="nothing to run"
Long conversations can become too large to send to the model on every turn.
**Compaction** gives the model a summary of older turns. It changes the
conversation context, not the memory file or task state.

:::figure src="/docs-img/05-02-intro.png" caption="Compaction summarizes session events. Memory remains a separate store."
:::

**Original conversation, shortened for this comparison:**

```
You:   Me, Sam, and maybe Priya want to see The Midnight Signal.
You:   Sam can't do weeknights; he's bailed on every single one.
Agent: Then Amsterdam on Saturday the 14th.
```

**The lab's seeded summary includes:**

```
They looked at the Amsterdam dates and settled on a Saturday show
because Sam cannot do weeknights.
```

Sam's weekend constraint **is preserved**. Some conversational wording and
the tentative mention of Priya are absent. Summaries can retain the facts
that matter, but they are still paraphrases; this example does not claim
that compaction forgot Sam's rule.

:::code path="agent/concert/agent.py" highlight="events_compaction_config=EventsCompactionConfig\(|compaction_interval=|overlap_size=|summarizer=LlmEventSummarizer"
:::

The demo uses `compaction_interval=3` and `overlap_size=1`, so summaries appear
after a short conversation. The summary is stored with the session's events.
`user:prefs`, plain task state, the memory file and artifacts are unchanged.
No extra conversation or command is needed for this comparison.
:::
