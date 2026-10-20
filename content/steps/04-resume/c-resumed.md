You have two seats planned and one queue ticket. In 4b you killed the
process, restarted it, and pressed Resume. The result said **Ready to buy**.
Here is how the code made that happen. This page is a read-through of that
finished run; there is nothing new to submit.

<div id="resume-code" style="scroll-margin-top: 160px"></div>

## 1 · This is the workflow you just ran

In `agent/concert/nightly.py`, these edges define the order:

```python
nightly = Workflow(
    name="concert_nightly",
    description="The unattended presale run: choose, queue, wait, reach the front.",
    edges=[(START, open_the_night, pick_show, queue_up, check_front, ready_to_buy)],
)
```

`pick_show` chooses the show and seats. `queue_up` gets a ticket.
`check_front` checks that ticket's position. Only when that check succeeds
can the workflow reach `ready_to_buy`. The graph decides this order.

In `agent/concert/agent.py`, the app runs this workflow and enables resuming:

```python
app = App(
    name="concert",
    root_agent=nightly,
    # Other app settings omitted here.
    resumability_config=ResumabilityConfig(is_resumable=True),
)
```

The Session Service writes its progress to `sessions.db`. The process may
stop; the saved ticket, plan and pause record remain there.

## 2 · This return is where the workflow pauses

These are the relevant lines from `check_front`. The full file below also
handles a missing ticket and writes logs; those branches are omitted here.

```python
QUEUE_WAIT = "queue:wait"

@node(rerun_on_resume=True)
def check_front(node_input, ctx: Context):
    ticket = node_input.get("ticket") or ctx.state.get("queue_ticket") or ""
    status = venue.get(f"/queue/{ticket}")

    if not status.get("ready"):
        return RequestInput(
            interrupt_id=QUEUE_WAIT,
            message=f"Still in the queue at #{status.get('position', 0):,}. "
                    "Wake me again and I will check.",
        )
    return Event(output=node_input)
```

Read it in order: **ask the venue → not at the front → return RequestInput**.
`RequestInput` is a named pause. Here its name is `queue:wait`.
ADK saves it, and the current execution stops. It appears in Events as
`⚡ adk_request_input`. There is no sleeping loop inside this function.

## 3 · Resume answers that saved pause

When you clicked **Resume current task**, the workbench sent a request to
ADK's `POST /run`, using the **same session ID**. This is the relevant payload
from `workbench/services/task.py`; app and user identifiers are omitted:

```json
{
  "session_id": "<the same session>",
  "new_message": {
    "role": "user",
    "parts": [{
      "function_response": {
        "id": "queue:wait",
        "name": "adk_request_input",
        "response": {"checked": true}
      }
    }]
  }
}
```

**The button submitted this for you.** That is the later
`✓ adk_request_input` event you now see. It is why the old input box may
already have disappeared: the request has been answered.

Despite its name, `checked: true` means **“wake up and check again”** in this
lab. It contains no queue position and proves nothing about seat availability.
It is not a new “buy tickets” chat message, and it does not start a new session.

## 4 · Why `rerun_on_resume=True` matters here

ADK has received the answer to the pause. What should it do next?
**`True` tells ADK to call `check_front` again, from the beginning of that
function, with its previous input.** It does not continue on the line after
`return RequestInput`, and it does not run every earlier node again.

The important line executes again:

```python
status = venue.get(f"/queue/{ticket}")
```

That asks the venue for the **current** position of the **same** ticket.
The resume signal did not contain that information; the venue does.

| When the signal arrives | What the fresh queue check finds | What happens |
|---|---|---|
| The ticket is still in line | `ready: false` | Return `RequestInput` again; stay paused |
| You already pressed SKIP THE WAIT | `ready: true` | Return the saved plan and ticket; run `ready_to_buy` |

You did the second case in 4b. That is why you saw **Ready to buy** and
**concert_nightly completed!**. There is no purchase node in this chapter,
so no order is placed.

`pick_show` and `queue_up` had already finished and saved their outputs.
ADK reuses those outputs. It does not need another model decision or another
queue ticket. You may see their saved outputs appear again in Events as the
path is reconstructed; that does not mean their functions executed again.

:::key
A resume signal asks the task to continue. `rerun_on_resume=True` makes the
paused queue-check function verify the real queue again before moving on.
The saved outputs preserve the work that was already completed.
:::

:::exercise id="read"
:::

:::checkpoint
**A Clock sends the resume signal too early. Will the workflow claim you are at the front?**
:::answer
No. `check_front` runs again and asks the venue. If `ready` is false, it
returns `RequestInput` again. The signal wakes the task; the queue check
decides whether it may continue. `queue_up` keeps its completed output, so
this does not join the queue again.
:::
:::

:::optional title="What would False do at this pause?" minutes=2 needs="reading only"
For a node paused on an interrupt that has now been answered,
`rerun_on_resume=False` lets ADK use the answer as that node's output,
without calling its function again. In this example the output would be
`{"checked": true}` — not the plan and ticket, and not a fresh queue result.
The following node expects that plan and ticket. This would break our flow
and skip the check it relies on.

False is useful when the answer really is the finished result the next node
needs. Here the answer is only a request to check, so we use True.

This flag is separate from reusing completed work: an earlier node with an
output already on record is replayed from that record either way.
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
