Most ticketing sites put buyers in a queue, both to prevent server crashes and
to manage high demand. You start your purchase and find yourself behind 14,000
people. The queue moves for forty minutes. When your turn finally comes, you
have a short window to pick seats and pay. If you miss that window, your place
in line is given away.

Many real-world tasks follow this pattern: a task that takes far longer than a
single conversation, running against an external system you do not control.
Waiting for a supplier to restock, waiting for a claim approval, waiting in a
queue.

A standard agent lives inside a single chat turn, which lasts seconds and is
purely reactive. It cannot wait forty minutes, and it cannot act when nobody is
typing. The agent you build here can: it goes dormant during the wait, keeps
its context across a process restart, and resumes when something outside it
says it is time.

## The task

The whole course is one sentence, and you will not change it:

:::key
**Get me and Sam two tickets to the Amsterdam show.** We can only go on a
weekend, and we do not sit in the upper bowl. Buy inside the limit I confirm.
:::

The person asking has booked with this agent before, and the agent remembers:
Sam bails on weeknights, and the upper bowl at Ziggo Dome was "couldn't see a
thing". The tour has two Amsterdam dates. Tuesday 10 Nov is ten dollars
cheaper. Saturday 14 Nov is the right one.

:::figure src="/docs-img/poster.png" caption="The Midnight Signal, on tour"
:::

## What makes this a long-running task

The queue is the hard part. Joining is one HTTP call, and then nothing useful
happens for forty minutes. A process that sits and polls for forty minutes
wastes memory, burns money, and dies the moment your laptop sleeps. So the
agent has to stop, and something has to start it again later, in the same task,
without a person at the keyboard.

By the end of Chapter 6 the same task runs end to end on Cloud Run with a
timer waking it. Four things have to be true when it finishes:

| Goal | Where you check it |
|---|---|
| **The right preferences.** Saturday, not Tuesday; never section B. | the plan in the agent's state, and the order on the venue panel |
| **No re-queue after a restart.** Kill the process; the same ticket continues. | **The queue** on the venue panel: one ticket, same number |
| **Buy within the authorization.** Two tickets, up to the limit you confirm in that task. | the authorization in session state, and the order's price |
| **Exactly one order.** Even when the venue's reply fails and the call is retried. | **Tickets bought** on the venue panel: 1 |

## Two systems, not one

The panel on the left is **the venue**: a mock ticket seller with its own
database, its own queue, its own clock. It is a separate service from the
agent. The agent reaches it only over HTTP, through four routes: list events,
read a seat map, join the queue, buy. The venue cannot see the agent's prompt,
its session, or its memory. The agent cannot see what you press on the panel.

That separation is the point of the exercise. When the venue sells out section
A while the agent is dormant, the agent's saved seat map is wrong and nothing
tells it so. When a purchase reply is lost, the venue has an order and the agent
does not know. Every chapter after this one is about handling the gap between
the two.

:::exercise id="look"
:::

:::warn
**Ticket bots are a real problem, and real ticketing sites prohibit
automation.** This workshop runs against a **mock venue** that is yours alone,
buying **one** allotment for **yourself**, inside limits you set. Do not point
this code at a real seller.
:::

## The pieces

| Piece | What it is | Where |
|---|---|---|
| the venue | a FastAPI service with SQLite: shows, sections, a draining queue, orders, the panel | `venue/`, running on :8080 |
| the agent | `concert`: an ADK agent with three tools, read by `adk web` on :8000 | `agent/concert/` |
| MonsterTix | your own server with a Runner, a `/wake` route and a chat page, from Chapter 2 | `monstertix/`, on :8090 |
| the workbench | this page: it loads chapters, starts and stops services, and runs the checks | :4800 |

The agent's hands are in `agent/concert/tools.py`. Two tools so far, both
read-only. Nothing waits and nothing buys; the agent earns those one chapter at
a time.

:::code path="agent/concert/tools.py" highlight="^def search_events\(|^async def get_seatmap\(|return venue\.get\(\x22/events\x22"
:::

`venue.py` is the only place the agent touches the venue: an `httpx` client
and a base URL from `VENUE_URL`. There is no fallback to localhost on purpose.
An agent that silently talks to the wrong venue is worse than one that stops.

:::code path="agent/concert/venue.py" highlight="^VENUE_URL = os\.environ\.get|^def get\(|^def post\("
:::

:::checkpoint
**Two of the four goals can be checked on the venue panel alone. Which two,
and why can the other two not be read from the venue?**
:::answer
*No re-queue* and *exactly one order* are facts about the venue: one ticket in
**The queue**, one row under **Tickets bought**. *The right preferences* and
*within the authorization* are facts about the agent's side: which show it
chose and why, and what the person confirmed in this task. The venue only sees
the result (an order for `ms-ams-01`, section A, $210) and has no idea whether
that matched a preference or a limit. You will read those from the agent's
session state, in the ADK web UI's **State** tab.
:::
:::
