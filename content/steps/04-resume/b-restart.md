**Can this ticket task survive a program crash?** The task has already paused
and saved its progress. Now deliberately kill the ADK process, start it again,
and resume the same task. Success means the same session and ticket survive,
without choosing the show or joining the queue again.

After **kill -9**, expect the ADK service to show **killed** and stop accepting
messages. The venue page stays open and the ticket keeps moving: it belongs
to the ticket seller, which is a separate service. Then use the remaining
buttons below to start ADK, move the ticket to the front, and resume.

:::exercise id="run"
:::figure src="/docs-img/06-01-resume1.png" example="true" caption="The ticket stays in the venue's queue while the agent task is paused. Killing the ADK process does not remove the ticket."
:::
:::

:::task
:::

## Key code: what a dead process takes with it

:::figure src="/docs-img/06-02-timeline.png" caption="The same ticket, across a process that died: the run parks, the queue keeps draining on the venue's side, the process is killed and restarted, the session is reloaded from sessions.db, and the next check finds the same ticket further up the line."
:::

Here is the prediction, answered.

| | Where it lived | Survived `kill -9`? |
|---|---|---|
| the queue ticket and its position | the venue's database | **yes**: the panel kept counting down |
| `queue_ticket`, `plan`, `request` | session state, `sessions.db` | **yes** |
| the conversation and every node's output | `events` rows, `sessions.db` | **yes** |
| the paused invocation, with `queue:wait` open | an `events` row, because the `App` is resumable | **yes** |
| the Python objects holding all of the above in RAM | the process | **no**, and nothing needed them |

Everything that mattered was already written before the kill, which is the point of chapter 3's `--session_service_uri`. What `ResumabilityConfig` adds is the last row in that table: not just *what was said*, but *where the run had got to*, parked on `check_front` with an interrupt open. Without it the rows are a transcript; with it they are a position to continue from.

:::code path="agent/concert/agent.py" highlight="resumability_config=ResumabilityConfig\(is_resumable=True\)|^root_agent = nightly"
:::

### Resume, a new message, or a new session?

| What you press | What it does to the session store |
|---|---|
| **Resume current task** | sends a `function_response` for `queue:wait` (`{"checked": true}`) into the **same session**. The parked invocation continues from `check_front` |
| the chat box | starts a **new invocation** from `START`; it can choose a plan again. `queue_up` may reuse a still-valid ticket, but this does not continue the paused invocation |
| **New Session** | a new row; the old task is untouched and still parked |
| **Load chapter / RESET THE VENUE** | rebuilds `sessions.db` or empties the venue's queue; the old task is gone or its ticket is |

The first two can look similar in the chat window. Check the interrupt response and node records to distinguish them. The button on this page does what `monstertix/handlers.wake` and chapter 6's scheduler do: look up the newest session with an open interrupt, check that it is a queue wait, and answer that interrupt by id. It never types into the chat.

:::code path="agent/concert/nightly.py" highlight="create_request_input_response\(pending, \{\x22checked\x22: True\}\)|^def pending_interrupt"
:::

### What the resumed node reads now

You moved this ticket to the front before resuming. `check_front` has `rerun_on_resume=True`, so it asks the venue for the current position, finds `ready: true`, and lets `ready_to_buy` run. The earlier show choice and queue ticket come from completed records.

If you resume before moving the ticket to the front, the same node simply reads a lower position and pauses again. That is useful in production, but you do not need an extra resume to prove the lesson here.

:::warn
**If you see a fresh `[open]` and model call for `[pick_show]`, check whether you typed a new chat message.** That starts another invocation. A reused ticket alone does not prove that you resumed the old one. Load chapter 4 again and do 4A and 4B in one session, resuming only with the button.
:::

:::key
Killing the process lost nothing, because the place in line was the venue's and the place in the run was in the database. Resuming means answering the open interrupt in that session, not sending a new message.
:::

:::checkpoint
**The agent was dead for the whole wait. Who moved the queue, and who noticed it was over?**
:::answer
The venue moved the queue: position is a function of join time and the venue clock, computed on request. Nobody noticed on its own. You did, by pressing SKIP THE WAIT and then Resume; `check_front` only learned the answer because something outside the agent woke it and it re-queried. In chapter 6 that something is a scheduler, and nothing in `check_front` changes.
:::
:::
