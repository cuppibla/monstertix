One task ran end to end with nobody at the keyboard: a limit agreed by a
person, a show chosen from memory, a queue joined once, a pause that survived
the process going away, a purchase checked against the live world and the
agreed numbers, and a retry that could not buy twice. Before taking the stack
down, put the whole chain in one place.

## The chain, end to end

```
PERSON        Get me and Sam two tickets…  →  "Two tickets, up to $250 each."  →  Yes
                  │                                   │
GRAPH         agree_budget ─► open_the_night ─► pick_show ─► queue_up ─► check_front ─► brief ─► buyer_agent
                  │  state["authorization"]     recall()      POST /queue/join   RequestInput        purchase
                  │  (session, not user:)       search_events  once              queue:wait          + guard + key
STORAGE       Session Service: events, state, the pending interrupt       Cloud SQL (was sessions.db)
              Memory Service:  memory/userx.md                            bucket   (was a file)
              Artifact Service: seatmap_ms-ams-01.json                     bucket   (was a folder)
CLOCK         Cloud Scheduler ─► Pub/Sub ─► /trigger/wake ─► resume_waiting(allow=("queue",))
              answers queue:wait only; budget:* is left for the person
VENUE         queue ticket · live seat map · /purchase with Idempotency-Key · one order
```

| Question | Answered by | Where you saw it |
|---|---|---|
| Who starts a run? | a caller: the page, the clock, the scheduler — never the prompt | 2B, 6B |
| What survives a restart? | the Session Service: events, state, the parked interrupt | 3A, 4B |
| What may a timer answer? | `queue:wait`; never `budget:*` | 5A, 6B |
| Is this plan still true? | the guard, re-reading the seat map before `purchase` | 5B |
| Did the order go through? | the venue, given the same `Idempotency-Key` | 5C |
| Where does the limit come from? | the person, for this task, confirmed — not memory | 5A |

:::section kicker="Transfer" headline="Restock purchasing"
A warehouse agent reorders stock. Suppliers quote on a portal that queues
requests for hours; prices move daily; the buyer has a spend limit per order
agreed each quarter; purchase orders must never be duplicated.

Map it before reading on: what is `agree_budget`? What is the queue wait? What
does the guard re-read, and what is the idempotency key made of?

:::optional title="One mapping" minutes=2 needs="nothing"
The quarterly limit is `authorization` — agreed by a person, stored with the
task that spends it, never inferred from last quarter. The portal's queue is
`check_front`: a `RequestInput` with a stable id, woken by a schedule. The
guard re-reads the supplier's **current** quote and stock in the instant
before `place_order`, and refuses with `price_moved` or `stale_plan`. The key
is `sha256(f"{session.id}:{sku}:{supplier}:{qty}")` — the same operation gives
the same key, and the portal returns the original PO on a retry. What changes
is every noun; what stays is the four places the agent can go wrong.
:::
:::

:::exercise id="destroy"
## In this order

| Step | What goes | Why this position |
|---|---|---|
| 1 | Scheduler job | so nothing fires at a half-deleted stack — an enabled job runs at 03:00 UTC every night against your venue |
| 2 | push subscription, then the topic | the subscription hangs off the topic |
| 3 | the agent's Cloud Run service | `concert-<you>` |
| 4 | the venue's Cloud Run service | `venue-<you>`, by `./destroy-venue.sh` |
| 5 | Cloud SQL instance | `--all` only: it holds the sessions and keeps billing |
| 6 | the bucket | `--all` only: memory and artifacts, also billing |

Everything that is already gone is reported as `→ absent`; both scripts are
safe to run twice.
:::

## What the page says afterwards

After `./destroy-agent.sh`: `AGENT_SERVICE_URL` is dropped from `.env`, so
the **6A** and **6B** checks that read it fail with *not set in .env yet*.
That is the resource being gone, not a fault. The venue, Cloud SQL and the
bucket are still there, and the script lists them under *still there*.

After `./destroy-venue.sh`: `VENUE_URL` in `.env` is blank. The venue panel
on every page of this workbench has nothing to answer, and every check that
reads the venue — orders, tickets, `url $VENUE_URL/health` — fails. To keep
working locally, start a venue on `:8080` with `python -m venue` and
`. ./set_env.sh local`; the workbench runs one itself when `VENUE_URL` is
empty.

After `./destroy-agent.sh --all`: the cloud URIs leave `.env` too, so a later
`./deploy-agent.sh` would warn *sqlite in /tmp* until `./setup-cloud-state.sh`
is run again.

Your laptop state — `sessions.db`, `memory/`, `artifacts/` — is untouched by
any of this. `./use-solution.sh N` resets it.

:::optional title="Cloud Trace: one wake-up as a trace" minutes=5 needs="the stack still deployed; Cloud Trace API enabled on the project"
Open **Cloud Trace** in the console for your project and filter on the
`concert-<you>` service around the minute the scheduler fired. One trace
covers `POST /trigger/wake`: the session read from Cloud SQL, the queue check
against the venue, the guard's seat-map read, the `purchase` call, and the
session write. The spans put numbers on what chapter 5 showed as log lines —
and make the point that the whole resume is one request, with Pub/Sub's
acknowledgement deadline as its budget.
:::

:::optional title="The session, as rows in Postgres" minutes=5 needs="the Cloud SQL instance still there; the Cloud SQL Auth proxy or Cloud Shell"
`gcloud sql connect` is interactive, so run it in a terminal, not here:

:::terminal
gcloud sql connect workshop-sessions --user=adk --database=adk
:::

```sql
select id, app_name, user_id, update_time from sessions order by update_time desc limit 5;
select count(*) from events where session_id = '<the newest id>';
select state from sessions where id = '<the newest id>';
```

`state` is the JSON you read in the State tab: `authorization`,
`queue_ticket`, `plan`, `last_order`. The pending interrupt is in the events,
as a `function_call` named `adk_request_input` with no matching response until
the scheduler answered it. The password is the fixed one
`setup-cloud-state.sh` printed.
:::

:::key
The schedule goes first, the data goes last, and only by choice. A task that
runs while you sleep is also a bill that runs while you sleep.
:::

:::checkpoint
**You deleted the agent's Cloud Run service but not the Scheduler job. What happens at 03:00 UTC, and what does Pub/Sub do about it?**
:::answer
The job still publishes to the topic. The push subscription tries to deliver
to `https://concert-<you>…/trigger/wake`, gets an error because the service
is gone, and Pub/Sub retries with backoff for as long as its retention allows
— up to seven days by default — logging a delivery failure each time. Nothing
is bought, because nothing is listening, but the project accumulates failed
deliveries and a job that fires every night. That is why `destroy-agent.sh`
deletes the schedule first, then the subscription and topic, and only then the
service: tear down from the caller inward, so no caller is left talking to a
hole.
:::
:::
