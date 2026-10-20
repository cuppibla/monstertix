Three things happened in that session and they are easy to mistake for one another: data that was persisted, an input that the resume sent in, and nodes that executed. The venue showed one ticket, so the graph did not start over. But the graph panel counted every edge twice. This section is about telling, from the records alone, what actually ran.

:::exercise id="read"
:::

## Key code: three kinds of record

| Kind | Where | Examples from your session |
|---|---|---|
| **persisted data** | `sessions.state`, `user_states`, `events` | `queue_ticket`, `plan`, `request`; every node's output event; the `adk_request_input` call |
| **resume input** | one `events` row, authored by `user` | the `function_response` for `queue:wait` with `{"checked": true}`, once per Resume |
| **node execution records** | `events` rows with a `node_info.path` like `concert_nightly@1/check_front@1`, plus the checkpoint events a resumable `App` writes | run 1: one for every node up to `check_front`. Run 2 and 3: a new `check_front` record each time, and finally `ready_to_buy` |

The resume input is a user event, but it is not a message. It answers an interrupt by id. That is why `open_the_night` ignored it: `what_they_asked_for` only collects `text` parts, and the answer has none.

### What `App` and `ResumabilityConfig` do

:::code path="agent/concert/agent.py" highlight="^app = App\(|resumability_config=ResumabilityConfig\(is_resumable=True\)"
:::

`adk web` looks for `app` before `root_agent`. `App` is where settings that belong to the whole application go, and `ResumabilityConfig(is_resumable=True)` makes two things true: an interrupt parks the invocation instead of simply ending it, and the workflow writes a checkpoint of node statuses to the event stream as it goes. On the next call into that session with an answer to the open interrupt, the workflow reads those records back and knows which nodes finished, with what output, and which one it stopped in.

ADK's own docstring is worth reading in full:

> *"1. pause an invocation upon a long-running function call. 2. resume an invocation from the last event, if it's paused or failed midway through. Note: ADK resumes in a best-effort manner: 1. Tool call to resume needs to be idempotent because we only guarantee an at-least-once behavior once resumed. 2. Any temporary / in-memory state will be lost upon resumption."*

Point 2 is chapter 3's `temp:` row again: `temp:seatmap` does not survive a pause.

### What `rerun_on_resume` decides, per node

:::code path="agent/concert/nightly.py" highlight="^@node\(rerun_on_resume=True\)|^@node\(rerun_on_resume=False\)|^pick_show = node\(picker, rerun_on_resume=False\)"
:::

When a resume walks the graph it enters every node again from `START`. That is the edge count you saw. At each node it checks the records:

| The node's record says | What happens |
|---|---|
| finished with an output in an earlier run | **fast-forwarded**: the recorded output is re-surfaced and the node's function is not called. `open_the_night`, `pick_show`, `queue_up` |
| stopped on an interrupt that now has an answer, and `rerun_on_resume=True` | **re-executed** from scratch, with the answer available. `check_front` |
| stopped on an interrupt that now has an answer, and `rerun_on_resume=False` | **completed without running**: the answer becomes the node's output |
| no record at all | runs for the first time. `ready_to_buy` |

So `True` on `check_front` is the whole mechanism: every wake-up re-queries `/queue/<ticket>`, because the position is the one thing that changed while the process was gone. Set it to `False` and the second run would hand `{"checked": true}` to `ready_to_buy` as if it were a plan, without ever asking the venue. The `False` on the three nodes before it says what they should do if a resume ever reaches them unfinished; in the normal path they have an output on record, and the record is what protects them.

### What must re-run, and which side effects must not

| Work | On resume | Because |
|---|---|---|
| ask the venue where the ticket is | **re-run** | the answer went stale while nothing was running |
| re-read a seat map before buying (chapter 5) | **re-run** | same reason; the plan was made forty minutes ago |
| choose the show | not again | the choice is recorded, and a second choice could differ |
| `POST /queue/join` | **never again** | a second ticket is a second place at the back of 14,203 people |
| `POST /purchase` (chapter 5) | never again | a second order is money |

### Why idempotency still matters

Finished nodes are skipped, so where would a duplicate come from? From the gap the docstring calls *at-least-once*. `queue_up` posts to the venue and then its output event is written. Kill the process between those two steps and the record shows a node with no output; the next resume runs it again, and the venue now has two tickets for one task. The window is small and it is real, and no setting closes it. The only fix is on the other side: make the side effect safe to repeat. `queue_up` is not (the venue hands out a fresh ticket per request), which is tolerable for a queue place and not for a purchase; chapter 5's `purchase` sends an `Idempotency-Key` derived from the session, the show, the section and the seat count, so the retry of the *same* purchase returns the *same* order.

### The alternative: let the agent own the queue

Everything above is a `Workflow` owning the wait. ADK has a second way to pause, built for a tool rather than a node: `LongRunningFunctionTool`. Wrap `join_queue` in it and the tool may return a ticket *without the call being finished*; the invocation parks on that open call, and resumes when something answers it. Read-only comparison:

| | Workflow + `RequestInput` (this chapter) | `LongRunningFunctionTool` |
|---|---|---|
| who decides to join the queue | a function node, always, once | the model, when it chooses to call the tool |
| where the pause is | `check_front`, with a named interrupt `queue:wait` | the open `join_queue` call |
| what a wake-up re-runs | `check_front` | the model's next turn, which must decide to call `check_queue` |
| how a waker knows it is a queue wait | the interrupt id's prefix | by inspecting which tool call is open |

Both park an invocation in the same session store and both depend on `ResumabilityConfig`. The difference is who owns the rule. In this course the queue is a rule, so a node owns it. The full experiment with the tool version is in the Reference chapter, [`/step/reference/a`](/step/reference/a).

:::key
Resuming re-enters the graph and re-executes only what has no finished record: the interrupted node if it asks to rerun, and everything after it. Re-query the world there; never repeat the side effects before it, and make the ones you cannot avoid repeating safe to repeat.
:::

:::checkpoint
**Set `queue_up` to `rerun_on_resume=True`. What happens on the next resume, and how would you prove it from the venue and from the execution records?**
:::answer
Predict the second ticket, then check, because the proof is cheap: the venue panel's ticket count (`python3 -m workbench.probe tickets --count 1` or `--count 2`), the `joined ms-ams-01 at #…` lines in the venue's Activity feed, the `[queue_up]` lines in the agent log, and whether `queue_ticket` in state changed between run 1 and run 2.

What you will find, in this ADK version, is one ticket, one `joined`, one `[queue_up]` line, and an unchanged `queue_ticket`. `rerun_on_resume` says what a node does when a resume reaches it with its interrupt answered; `queue_up` was never interrupted, it finished with an output on record, and a finished record is fast-forwarded regardless of the flag. The flag on `check_front` is the one doing the work.

A second ticket comes from two other places, and both show up in the same evidence: a message typed in the chat box (a new invocation, `[open]` and `[pick_show]` run again, `queue_ticket` changes, two tickets at the venue), or the process dying after `POST /queue/join` and before `queue_up`'s output was written (one invocation, two `joined` lines, the record shows `queue_up` with no output before the second run). That second case is why idempotency matters even though finished nodes are skipped.
:::
:::

:::optional title="Run the LongRunningFunctionTool version" minutes=12 needs="the Reference chapter's step loaded; a fresh venue"
The Reference chapter carries the agent-owned version of the queue: `join_queue` wrapped in `LongRunningFunctionTool`, `check_queue` as an ordinary tool, and the same `ResumabilityConfig`. Load it from [`/step/reference/a`](/step/reference/a), then in a new session ask for the two Amsterdam tickets, kill and restart the agent, and ask *Where am I in line?* in the chat. Compare with this chapter: the same ticket survives, but the re-check is now the model's decision, and typing in the chat is the resume rather than the mistake. Then ask yourself which of the two you would trust to run unattended at 3am.
:::
