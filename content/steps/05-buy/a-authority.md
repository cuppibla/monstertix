Chapter 4 ended at the front of the queue with nothing bought. The memory file
says this person is *"comfortable around $200, $250 is the hard ceiling"*. So
the run knows a number. Is that enough to spend their money tonight?

No. A preference is history. Authority is given for one task, by the person,
in words they confirmed. This section puts that conversation at the front of
the graph, before anything is searched or queued — and keeps it in a place
the next session will not inherit.

:::note
**What this chapter teaches.** One purchase, three locks, and all three have
to hold at the same moment:

1. **Permission.** A person agreed a limit for *this* task, in their own words,
   and confirmed it. Memory of what they spent before does not count. (5a)
2. **Guard.** In the instant before money moves, code re-reads the world. A
   plan made forty minutes ago is not trusted; a refusal with a reason is the
   normal outcome, not a bug. (5b)
3. **Once.** If the response is lost and something retries, the retry cannot
   buy twice. The same operation carries the same key. (5c)

| Section | The question it answers |
|---|---|
| 5a · Permission | Who said the agent may spend, and where is that stored? |
| 5b · Guard | What stops it acting on a stale plan? |
| 5c · Once | What stops a retry from buying twice? |

One run covers all three: you agree the limit in 5a, break the world and wake
the run in 5b, and read the retry off the records in 5c.
:::

:::exercise id="run"
:::figure src="/docs-img/09-02-workflow.png" caption="Chapter 4's graph with agree_budget in front: it asks, reads the number back, and stores the ask and the budget before anything is searched or queued. Two RequestInput pauses: one for a person, one for the queue."
:::
:::figure src="/docs-img/09-01-hitl1.png" example="true" caption="The run stops and asks what you will spend, in the event's own response box. Nothing is searched until you answer."
:::
:::figure src="/docs-img/09-01-hitl3.png" example="true" caption="budget in the State tab, in your own words, next to queue_ticket. Plain session state: the next session will not inherit it."
:::
## The graph, one node longer

:::code path="agent/concert/nightly.py" highlight="^nightly = Workflow\(|edges=\[\(START, agree_budget"
:::

It is chapter 4's graph with `agree_budget` in front and a buyer at the end.
Nothing in the middle moved: `pick_show` still reads memory and takes the
Saturday, `queue_up` still joins once, `check_front` still parks.

```
START ─► agree_budget ─► open_the_night ─► pick_show ─► queue_up ─► check_front ─► brief ─► buyer_agent
          asks a PERSON                                                 PAUSE
```

**Two nodes stop and wait, and they are the same mechanism.** `check_front`
waits for the venue's queue and is answered by anything with a clock.
`agree_budget` waits for a person and may only be answered by one. The
difference is in the interrupt id, not in the framework.
:::

:::warn
**Answer in the box on the event, not the chat box.** The chat box starts a new
invocation, which runs the graph from the top and asks you the same question
again. Everything below depends on getting this right.
:::

:::task
:::

## Two kinds of waiting

The task card reads *Paused on: the queue* once the run parks. Earlier, while
the question was open, it read *Paused on: you* and the **Resume current
task** button was disabled. That is the whole distinction, made visible:

| Interrupt id | Who may answer | Answer |
|---|---|---|
| `budget:ask`, `budget:confirm` | a person, in the event’s response box | the sentence they typed, as `{"result": …}` |
| `queue:wait` | anything: the panel, the MonsterTix server, Cloud Scheduler | `{"checked": true}` — "look again" |

The ids are stable strings on purpose. Whoever wakes the run reads the prefix
and knows which kind of wait this is. A scheduler that fills in a budget is a
scheduler spending your money, so the clock never answers a person-wait — in
chapter 6 you will watch it refuse.

## Key code: authority

:::code path="agent/concert/nightly.py" highlight="^def agree_budget|interrupt_id=ASK_BUDGET|interrupt_id=CONFIRM_BUDGET|answers = ctx\.resume_inputs|ctx\.state\[budget\.AUTH_KEY\] = auth"
:::

Three things make `agree_budget` work, and you need all three:

| | |
|---|---|
| `@node(rerun_on_resume=True)` | when this node is paused on a question and its answer arrives, the function runs again to read it. After authorization is stored and the node finishes, later queue resumes reuse its record |
| a **stable** `interrupt_id` | the default is a fresh UUID per run, so there would be nothing to look the answer up by |
| `ctx.resume_inputs[id]` | where the answer lands. **Not** the return value of `RequestInput` — ADK iterates a node rather than sending into it |

Two interrupts, not one, and the second is the point. The first answer is what
somebody said. The second is what they agreed to. Only after the second does
`authorization` go into state with `confirmed: True`.

:::code path="agent/concert/budget.py" highlight="^SESSION STATE, NOT|^AUTH_KEY = "
:::

**Session state, not `user:`.** Open the State tab: the key is `authorization`
with no prefix. A budget is agreed for one booking. Put it under `user:` and it
silently governs every run this person ever makes, and they are never asked
again. So every new session starts with no authorization and has to agree one.
That is the honest trade: a limit that has to be re-agreed, against a limit
that quietly outlives the conversation it came from.

:::note
**There is no default and no unattended path.** If nobody answers, the run
stays parked on `budget:ask` and nothing is bought. `fence.py` refuses any
`purchase` with `no_authorization` when `budget.load()` returns `None`. That is
the correct outcome, not a failure to handle.
:::

:::optional title="Going deeper: what budget.py keeps" minutes=5 needs="nothing — reading only"
:::code path="agent/concert/budget.py" highlight="^def parse\(|^def make\(|^def load\(|^def allows\("
:::

`budget.py` keeps two things side by side:

```
text            "Two tickets, up to $250 each."    the sentence, verbatim
seats           2                                   what the guard compares
per_seat_max    250.0
confirmed       True, and when
```

The sentence is what you show the person back and what the buyer agent reads.
The numbers are what `fence.py` compares a live price against in the instant
before money moves. A model is good at reading a sentence and bad at being the
last line of defence, so the code checks the numbers.
:::

:::key
Memory says what this person has been willing to spend. Authorization says
what they agreed to spend tonight. Only the second is stored for this task,
and only the second is checked before money moves.
:::

:::checkpoint
**Being willing to spend $250 in the past — why is that not authorization to buy now?**
:::answer
The $250 in `memory/userx.md` describes the person: what they were comfortable
with on an earlier booking. It was never said about *this* show, *this* number
of seats, or *tonight*. Authorization is a decision for one task, made by the
person, confirmed in their own words, and stored in session state so it dies
with the conversation it was agreed in. The guard reads `authorization`, never
memory — if the person has not confirmed a limit for this task, the answer is
`no_authorization` and nothing is bought, however much history says they could
afford it.
:::
:::
