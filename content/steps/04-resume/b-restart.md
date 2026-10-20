The run is parked and the agent process is about to die. Decide first what dies with it: the ticket, the plan, the place in the queue, the paused run, the conversation. Then kill it, bring it back, and continue the same task, not a new one.

:::exercise id="run"
:::

:::task
:::

## Key code: what a dead process takes with it

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

### Three buttons that look alike

| What you press | What it does to the session store |
|---|---|
| **Resume current task** | sends a `function_response` for `queue:wait` (`{"checked": true}`) into the **same session**. The parked invocation continues from `check_front` |
| the chat box | starts a **new invocation** in that session. The graph enters from `START`: `pick_show` again, `queue_up` again, a **second ticket** at the back of a queue of 14,203 |
| **New Session** | a new row; the old task is untouched and still parked |
| **Load chapter / RESET THE VENUE** | rebuilds `sessions.db` or empties the venue's queue; the old task is gone or its ticket is |

The first two are the ones that get confused, and they are indistinguishable until you look at the venue panel and count tickets. The button on this page does what `monstertix/handlers.wake` and chapter 6's scheduler do: look up the newest session with an open interrupt, check that it is a queue wait, and answer that interrupt by id. It never types into the chat.

:::code path="agent/concert/nightly.py" highlight="create_request_input_response\(pending, \{\x22checked\x22: True\}\)|^def pending_interrupt"
:::

### Why the position was lower, and why that is the right answer

The first Resume produced one log line, `[check_front] #… — not yet. Pausing.`, with a smaller number than before you killed anything. `check_front` is `rerun_on_resume=True`, so every wake-up asks the venue again. The venue's clock ran the whole time yours was dead, and the position is the one thing that changed while the process was gone. Re-reading it is not redundant; it is the reason to wake up at all. The second Resume, after SKIP THE WAIT, found `ready: true`, fell through, and `ready_to_buy` ran for the first and only time.

:::warn
**If you saw `[open]` and `[pick_show]` again, you typed in the chat box.** The venue now shows two tickets and the `resumed` check will say *it joined the queue again*. Load chapter 4 again and do 4A and 4B in one session, resuming only with the button.
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
