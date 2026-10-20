You killed the process and resumed the task once. It kept the same ticket and
reached **ready to buy**, with no order. The next question is what actually
ran again: did the agent choose the show again, or continue the saved plan?

:::exercise id="read"
:::

## The Session DB also holds the place to continue

:::figure src="/docs-img/06-02-intro.png" caption="Resumability keeps the paused task in the session store. In our Workflow, the interrupted node is check_front; completed nodes already have outputs on record."
:::

:::code path="agent/concert/agent.py" highlight="^app = App\(|resumability_config=ResumabilityConfig\(is_resumable=True\)"
:::

`ResumabilityConfig(is_resumable=True)` lets ADK save and use the records
needed to continue a paused invocation. The external caller sends an answer
to `queue:wait` in the same session. That answer means **“check again”**;
it does not itself mean the ticket is at the front.

### Completed nodes and interrupted nodes are different

:::code path="agent/concert/nightly.py" highlight="^@node\(rerun_on_resume=True\)|^@node\(rerun_on_resume=False\)|^pick_show = node\(picker, rerun_on_resume=False\)"
:::

The graph can traverse the earlier nodes again while rebuilding the path.
Traversal is not proof that their functions ran. ADK checks their records:

| Record | What ADK does | Our example |
|---|---|---|
| Finished, with an output | Reuses that output without calling the node again | `pick_show`, `queue_up` |
| Paused on an answered interrupt; `rerun_on_resume=True` | Calls the node again with the answer available | `check_front` re-reads the queue |
| Paused on an answered interrupt; `rerun_on_resume=False` | Uses the answer as the output without calling the node | Not the behavior we want for the queue check |
| No completed execution yet | Runs the node | `ready_to_buy` after the queue clears |

**The recorded output protects completed work.** The flag on `check_front`
controls the interrupted work. With `True`, it asks the venue where this
ticket is now. Without that check, `{"checked": true}` could be mistaken for
having completed the wait.

:::key
Keep completed decisions. Re-check facts that may have changed. A resume is
another request to continue the saved task, and can keep the same invocation id.
:::

:::checkpoint
**If a clock wakes the task while it is still waiting, will it join the queue again?**
:::answer
No. `queue_up` already returned a ticket, so ADK reuses that output.
`check_front` runs again, finds the ticket is not ready, and pauses again.
Once it reaches the front, the same check lets `ready_to_buy` run. One ticket
can therefore survive many wake-ups without keeping the process running.
:::
:::

:::optional title="Deep dive: records, crash gaps, and LRFT" minutes=8 needs="reading only"
### What to look for in the records

- **Task data:** `queue_ticket` and `plan` in session state.
- **Resume input:** a `function_response` answering `queue:wait` by id.
- **Execution records:** completed outputs for earlier nodes, then fresh work
  at `check_front` and `ready_to_buy`.

Changing `queue_up` to `rerun_on_resume=True` would not re-run an already
completed node: its recorded output still wins. The flag matters when a
resume reaches a node with its interrupt answered.

### The gap a checkpoint cannot remove

Suppose a process dies after the venue issues a ticket but before the node's
output is safely recorded. Re-executing that unfinished work can repeat the
external request. Our `queue_up` reuses a valid ticket when it can find one
in state, but this cannot protect a ticket that was never saved.

That is why checkpoints alone do not guarantee exactly one external side
effect. The next chapter makes purchase retries safe with an
`Idempotency-Key`: the same purchase attempt returns the same order.

### Read-only comparison: LongRunningFunctionTool

`LongRunningFunctionTool` is another pattern for work whose result arrives
later. The model calls a tool; an external completion is associated with that
tool call. This lab uses a Workflow and named `RequestInput` instead.

| | Workflow + RequestInput | LongRunningFunctionTool |
|---|---|---|
| Who chooses the sequence? | Graph edges | The model chooses tool calls |
| What does the caller answer? | A named interrupt such as `queue:wait` | The outstanding tool call |
| Where is our “check the queue again” rule? | In `check_front` | It would need to be designed into the tool/completion flow |

Use this to compare ownership of the wait. There is no complete alternative
experiment to load here; the hands-on lab stays with the Workflow you just ran.
:::
