The queue is 14,203 people long and drains in forty minutes. The obvious way
to wait is a loop that keeps a process alive to achieve nothing, dies with the
laptop, and cannot be picked up again. This chapter replaces the wait with a
pause.

:::note
**What this chapter teaches.** One thing: a forty-minute wait does not need a
living process. Three sentences, one per section:

1. The run **stops itself** and writes down where it stopped and which ticket
   it holds. That is what `ResumabilityConfig` records. (4a)
2. So the process can **die**. Kill it: nothing is lost, because everything
   that mattered was already on disk, and the place in line is the venue's.
   (4b)
3. Later, something **wakes it**: you, a clock, chapter 6's scheduler. It
   continues from where it stopped: finished steps are not repeated, and the
   only thing it does again is ask the venue whether it is at the front. (4c)

| Section | The question it answers |
|---|---|
| 4a · Stop | How does a run stop without a process waiting? |
| 4b · Kill | What dies with the process? |
| 4c · Resume | When it is woken, what runs again, and what must never run again? |

You press nothing to pause. One message starts the task, and the task stops
itself when `check_front` finds that the ticket is not yet at the front.
The workflow code requests this pause; the model does not decide when to pause.
The current agent run ends, while the ADK server may remain running.
**This page ends at the pause.** Go to **4b · Kill** for the buttons that kill,
restart, advance the queue, and resume the task.
:::

:::exercise id="run"
:::figure src="/docs-img/08-01-flow1.png" example="true" caption="What the Events list looks like when the run parks: pick_show finishes with a plan, queue_up puts the ticket in state, then adk_request_input, and nothing after it. The run is waiting for a signal, not running."
:::
:::

:::task
:::

## Key code: the run stops itself at `check_front`

:::figure src="/docs-img/06-02-aync.png" caption="join_queue returns as soon as the ticket is issued, and the work is not done: your turn comes forty minutes later. A plain tool call cannot represent that gap; the pause can."
:::

:::code path="agent/concert/nightly.py" highlight="^def check_front|^\s+return RequestInput\(|interrupt_id=QUEUE_WAIT|^QUEUE_WAIT = "
:::

`check_front` asks the venue `GET /queue/<ticket>`. If `ready` is false it returns `RequestInput(interrupt_id="queue:wait", message="Still in the queue at #N. Wake me again and I will check.")`. That is ADK's **interrupt**: the graph stops where it stands, the invocation is written to the session store with that interrupt open, and the run ends. Nothing loops, nothing sleeps, nothing holds a connection. The `adk_request_input` event you found is that interrupt, rendered.

The interrupt id is a constant on purpose. Whoever wakes this run later, the task card, the MonsterTix server, a scheduler in chapter 6, answers `queue:wait` and can tell from the prefix that it is a queue wait and not a question for a person.

### Why the agent is now a graph

The agent is no longer one `Agent` with tools; it is a `Workflow`, five
nodes in a row, and the agent from chapter 3 is one of them. The reason is
the pause. A pause has to happen at a known place, with a known name, so that
whoever wakes the run later knows what they are answering. `check_front` is
that place. In a chat agent the model decides what to call next; in a graph
the edges decide, and "join the queue once, then check the front" is a rule,
not a judgement. Read the graph once; you do not need to edit it.

:::figure src="/docs-img/08-02-workflow.png" caption="Functions for rules, an agent for judgement"
:::

```
START ─► open_the_night ─► pick_show ─► queue_up ─► check_front ─► ready_to_buy
           (function)       (agent)     (function)   (function)     (function)
```

Look at the four pieces of work and ask of each: is there a judgement in it?

| Node | Shape | Why |
|---|---|---|
| `open_the_night` | function | says what tonight is for, in the words the person typed. An agent node cannot be first: with no message there is nothing to respond to |
| `pick_show` | **agent** | which night Sam can make, which section this person refuses. That is judgement, and it calls `recall`, `search_events`, `get_seatmap` and returns a validated `Plan` |
| `queue_up` | function | join the queue exactly once. A rule, and a rule should not be a coin flip at 3am |
| `check_front` | function | "am I at the front" has one right answer, and the venue has it |
| `ready_to_buy` | function | say so, set `ready_to_buy`, stop. Buying is chapter 5 |

:::code path="agent/concert/nightly.py" highlight="^nightly = Workflow\(|edges=\[\(START|^pick_show = node\(picker|^picker = Agent\(|output_schema=Plan"
:::

`root_agent = nightly` in `agent.py`, so this graph is what `adk web` runs. The agent you talked to in chapter 3 is not gone; the judgement it did is now one node, with a schema on its output so the function after it gets a `Plan` rather than prose.

### Where the ticket went

:::code path="agent/concert/nightly.py" highlight="^def queue_up|venue\.post\(\x22/queue/join\x22|ctx\.state\[\x22queue_ticket\x22\] =|ctx\.state\[\x22plan\x22\] ="
:::

`queue_up` posts to `/queue/join` once and puts the ticket in two places: the node's **output**, so `check_front` gets it along the edge, and **session state**, `queue_ticket`, `queue_event_id`, `plan`, so anything looking at the session from outside can say what this run is doing without reading the graph. The task card above is reading exactly those keys, plus the open interrupt. Both are rows in `sessions.db`, which is where chapter 3 ends and this chapter starts.

:::key
The run is not waiting. It has stopped, and the fact that it stopped at `check_front` with ticket `q_…` is on disk.
:::

:::checkpoint
**The workflow has paused. What holds your place in the queue if the agent process stops?**
:::answer
The venue is. The ticket is a row in the venue's own database and its position is computed from the time you joined and the venue clock, with or without an agent. What the agent holds is the ticket id, written into session state and into `queue_up`'s recorded output. Lose the process and you lose nothing, because neither the place nor the id was in the process.
:::
:::
