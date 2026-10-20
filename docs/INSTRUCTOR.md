# Instructor runbook

Everything you need that students do not. [`CODELAB.md`](CODELAB.md) is what
they see; [`DRYRUN.md`](DRYRUN.md) is how you rehearse it;
[`PRE-WORK.md`](PRE-WORK.md) is what they did before they arrived.

---

## The thesis, in one line

Every framework got better at what goes in the prompt. None got better at
being awake.

One task runs through the whole class — me and Sam, two Amsterdam tickets,
weekend only, no upper bowl, "Two tickets, up to $250 each", finished by a
cloud timer. If you only land one thing, land this: **an agent that promises to
check later has not scheduled anything.** Chapters 3 to 6 are what has to be
true before leaving it alone is reasonable.

The four deep dives are required reading inside the chapters, not side pages:
**Memory** (3B, 3C), **Resumption** (4C), **Authority** (5A), **Reliability**
(5B, 5C). Do not let them get skipped by a room that is behind.

---

## Before the day

### Two weeks before

| | |
|---|---|
| **A project with billing, per student or shared** | `setup.sh` enables ten APIs. Without billing it fails, and no message at 9am fixes that |
| **Students can enable APIs** | needs `serviceusage.services.enable`. If not, enable them yourself beforehand |
| **Run the pre-work yourself on a clean clone**, on the project students will use | this is the check that catches things |
| **Publish PRE-WORK.md** with a hard "done by" date | the class has no setup time in it |

Thirty simultaneous Cloud Run deploys share one Cloud Build queue. The
pre-work exists so that never happens in the room.

### The night before

```
[ ] ./verify.sh all green on a clean clone, on the students' project
[ ] Cloud SQL RUNNABLE:  gcloud sql instances describe workshop-sessions --format='value(state)'
[ ] ./use-solution.sh 6 && ./setup-cloud-state.sh && ./deploy-agent.sh
    — run it once yourself. In class your deploy is a redeploy (~2 min) and
    you have a known-good service to fall back on for 6B
[ ] rehearse 4B and 5C at least (see DRYRUN.md) — they are the ones that
    depend on timing
[ ] ./use-solution.sh 1 so you start where they start
[ ] collect the students' ./verify.sh output for anyone still red
```

Recommend to students, not require: `./setup-cloud-state.sh` once Cloud SQL is
RUNNABLE. It takes a minute and turns Chapter 6 into a deploy only.

---

## The plan: 110 + 10

| Clock | Chapter | Section | Minutes | What must have happened before you move on |
|---|---|---|---|---|
| 0:00 | **1 Meet** | 1A The mission | 2 | everyone can point at queue, stock, orders on the panel |
| 0:02 | | 1B Your workspace | 3 | Load step 1 done; one answer from the agent; `two-days-ago` in the dropdown |
| 0:05 | **2 Wake** | 2A Prompt | 5 | proactive prompt swapped, sixty seconds of nothing watched |
| 0:10 | | 2B Caller | 5 | clock fired, server log shows a run nobody typed; no order |
| 0:15 | **3 Remember** | 3A Session DB | 8 | `user:prefs` seen, `temp:seatmap` absent, rows seen in the DB |
| 0:23 | | 3B Memory Service | 8 | `recall` first, Saturday picked, `remember` wrote one line |
| 0:31 | | 3C Services & lifetimes | 9 | the services table read, the compaction sample read |
| 0:40 | **4 Resume** | 4A Pause | 8 | one ticket, parked on `queue:wait`, task card says *queue* |
| 0:48 | | 4B Kill & continue | 9 | killed, restarted, resumed on the same ticket, SKIP THE WAIT, *ready to buy* |
| 0:57 | | 4C What resumed | 8 | node counts read off the events; the rerun question answered |
| 1:05 | **5 Buy** | 5A Authority | 10 | `authorization` in state, confirmed; parked in the queue |
| 1:15 | | 5B Check the world | 10 | section A sold out, order lands in C, one order |
| 1:25 | | 5C Retry once | 10 | venue reset, new session + budget, BREAK, retry, **one** order with `attempts: 2` |
| 1:35 | **6 Cloud** | 6A Move | 4 | deploy started/finished, `/health` shows Cloud SQL + bucket |
| 1:39 | | 6B Cloud wake-up | 8 | cloud task created, SKIP THE WAIT, job run, order appears on the page |
| 1:47 | | 6C Explain & clean up | 3 | chain narrated; `destroy-agent.sh` run or scheduled for after class |
| 1:50 | **Buffer** | | 10 | questions, repairs, anyone still on 5C |

☕ If you break, break at **0:40**: storage is understood, nothing is parked yet.

**Start `./deploy-agent.sh` during 5C's checkpoint discussion** (students who
finished 5C run `./use-solution.sh 6 && ./deploy-agent.sh` and read 6A while it
builds). That buys 6B its eight minutes.

### What to cut when late

In this order. Each stands alone.

1. **6C's transfer question** → homework (−2 min).
2. **4C's node counting** → you narrate it from your screen, they read the
   table (−4 min). Keep the checkpoint question.
3. **3A's database look** → show it from your terminal (−3 min).
4. **5C** → demo it yourself rather than everyone doing it (−6 min). Never
   drop it entirely; "no response ≠ no order" is half the Reliability dive.
5. **6B done by you alone** on your night-before service, students watch
   (−5 min). Their own deploy becomes homework with `destroy-agent.sh` attached.

**Do not cut 2A, 4B or 5A.** Without watching the prompt do nothing, nobody
believes the caller is necessary. Without the kill, resumption is a slide.
Without the confirmation, Chapter 5 is "the agent bought a ticket".

---

## What to say at each checkpoint

The codelab has a model answer under every checkpoint. These are the five that
carry the course, with what to listen for.

**Chapter 2 — "The agent promised to check later. Why an external caller?"**
Listen for *invocation*. The promise is text produced inside an invocation that
has ended. Nothing exists between invocations: no process of the agent's, no
timer, no loop. The instruction is read when a message arrives, and says
nothing about who sends one. The clock did not change the agent; it changed
who starts it. If someone says "a better prompt", send them to the Reference
variants and ask them to come back with one that works.

**Chapter 3 — "Session DB and memory file still exist. Why does a new session
not know what 'continue that order' means?"**
Listen for *scope*. Task state — show, plan, ticket, authorization — is plain
session state, one session's row. A new session id starts with empty session
state and never reads another session's events. What crosses sessions is
`user:` state and the memory file, and the file holds only explicit
`remember()` writes, never the transcript. So the new session knows the
person and not the task. Continuing a task means returning to that session,
which is Chapter 4. Point at `sessions.state` vs `user_states` if the room
wants proof.

**Chapter 4 — "Set `queue_up` to `rerun_on_resume=True`. Predict, measure, explain."**
Make them predict first; most of the room will say *two tickets*. Then
measure: **one**. Panel count unchanged, no second *joined* line in the feed,
`queue_ticket` unchanged, the resumed invocation holds `check_front` only. In
ADK 2.11 a node that finished is replayed from its recorded output whatever
its flag says; the flag governs the node that holds the interrupt. Then the
real question: so where does a second ticket come from? Listen for two
sources. (1) Typing in the chat box instead of answering the interrupt — a
**new invocation**, graph from the top, `queue_up` included (the most common
way students get two tickets all day). (2) A crash between the venue accepting
the join and the output being recorded — nothing to replay, node runs again:
**at-least-once**. Neither is fixed by a flag, which is why `queue_up` is
written to be safe to repeat and why `purchase` carries an idempotency key.
The flag goes back to `False` because it documents intent.

**Chapter 5A — "$250 in history ≠ authorization now."**
Listen for *scope* again, and *who*. The file describes the person: no seat
count, no task, no confirmation, no time. The authorization is an instruction
for this task, read back, confirmed, with numbers code can compare, stored in
this session. `budget.load` returns `None` without `confirmed: true`; the guard
refuses with `no_authorization`. And nothing automatic may supply one: a
`budget:` interrupt is only ever answered by a person. If someone asks "why not
a default budget for 3am", the answer is that a default nobody remembers
choosing is not a limit.

**Chapter 5C — "No response ≠ no order."**
Listen for *commit before response*. The venue writes the order and then
answers; a failure after the write is indistinguishable from one before it. So
the caller learns nothing from silence, and the fix is not to find out but to
make the retry safe: the same `Idempotency-Key`, derived from session + event +
section + seats, lets the venue return the original order with
`duplicate: true`. `attempts: 2`, one order id, one row. If someone proposes
"check the orders list before retrying", point out the same network that lost
the response can lose the check.

Also worth saying out loud, once:

- **On ticket bots.** Say it before they think it: a mock venue each student
  deploys, one allotment, limits they set, an invented band.
- **On `[EXPERIMENTAL]` warnings.** `EventsCompactionConfig` and
  `ResumabilityConfig` are pre-GA. The warnings are expected; the APIs may move.
- **On "ChatGPT already does this."** It does, and it is asleep at 10am. A chat
  session is a save file; this is a server that kept running.
- **On cost.** Everything scales to zero except Cloud SQL and the bucket.
  `./destroy-agent.sh --all` at the end, and say it twice.

---

## What breaks, and what to do

The most useful skill in the room is telling an **expected outcome of the
experiment** from an **environment fault**. First table: things that look like
failures and are the lesson. Second table: actual faults.

### Expected outcomes that look like failures

| What they see | What it is | What to say |
|---|---|---|
| 2A: *"I'll keep an eye on it!"* and then nothing | the lesson | "It said it would. What is running right now?" |
| 3B/5B: the agent takes section B | the model ignoring the memory file | not a bug in the code: the honest cost of leaving the choice to a model. Ask it why. In 5B the guard still only checks price and stock; B is under $250. The buyer instruction forbids B, and usually holds |
| 5B: the buyer reads the seat map before its first `purchase` | the model not following step 1 of its instruction | the order still lands in C, but the room misses the refusal. Point at the instruction and the `brief` text; note it for the prompt |
| 4B: after SKIP THE WAIT, Resume says *nothing is paused* or `[check_front] ticket gone` | the front-of-queue hold expired (≈1,000 people's worth of queue time; at 1× about three minutes, at 60× seconds) | a real venue does this. New session, and keep the clock at 1× when you press SKIP THE WAIT |
| 5A: the run asks the budget question again after a wrong-shaped answer | `budget.parse` refusing *"whatever it costs"* | the agent is asking for the shape the guard can check. Say it the example way |
| 5B: the first `✓ purchase` is `"reason": "stale_plan"` | the guard refusing the old plan — by design, every time | that is the experiment, not an error: the buyer is told to try the plan first. Watch it re-read and pick C |
| 5C: `[purchase] venue answered 503 — retrying` | the experiment | this is the moment. Count the orders |
| 6B: logs say *not resuming web-…: waiting for a person to answer* | the scheduler fired while the cloud task was on `budget:ask` | correct behaviour. Answer the question on the page, fire again |
| 6B: `nothing is waiting` | the task already finished, or SKIP THE WAIT was not pressed and the run re-parked | check `/task`; press SKIP THE WAIT; fire again |
| Chapter 4+: *Resume current task* is disabled with *waiting for you* | the run is on a person's question | answer it in the ADK web UI's `adk_request_input` box |

### Environment faults

| Symptom | Cause | Recovery |
|---|---|---|
| A second queue ticket on the panel | they typed in the chat box instead of the `adk_request_input` reply box; a new invocation replayed the graph | RESET THE VENUE, New Session, start again. Use **Resume current task** from now on |
| `two-days-ago` missing from the dropdown | seeded under a different user id, or `sessions.db` replaced | `.venv/bin/python -m seed.session`. The id must be `user` |
| Dropdown empty / app will not load | a stray folder under `agent/` (e.g. `memory/` from running something inside it) | `ls agent/`; `./use-solution.sh N --force` tidies it |
| `address already in use` | something on :8000 / :8090 | `lsof -ti:8000 \| xargs kill -9` |
| `VENUE_URL is not set` | terminal without `set_env.sh` | `. ./set_env.sh` |
| `asyncio.run() cannot be called from a running event loop` | a student's own tool called something async without being `async def` | make the tool `async def` and `await` |
| Compaction error *No LlmAgent model available for event compaction summarizer* | a student removed the `summarizer=` line while the root is a Workflow | put it back; a graph has no model to borrow |
| Model 404 | `-latest` alias | `ADK_MODEL=gemini-2.5-flash` in `.env` |
| 403 from Vertex on a fresh project | APIs still propagating | wait a few minutes; `./verify.sh` |
| `setup-cloud-state.sh`: instance still `PENDING_CREATE` | Cloud SQL not finished | it takes 8–12 minutes; this is why it is pre-work. Pair them with a neighbour for 6B |
| `deploy-agent.sh`: `agent/main.py is missing` | Chapter 6 not loaded | `./use-solution.sh 6` |
| `deploy-agent.sh` warns *sqlite in /tmp — this DIES with the container* | `.env` has no `CLOUD_SESSION_SERVICE_URI` | `./setup-cloud-state.sh` first, then redeploy |
| Container fails to start on Cloud Run | `GOOGLE_CLOUD_PROJECT` missing in the env (config.py exits at import), or a `@` in the URI split on a comma | `deploy-agent.sh` already passes both and uses the `^\|^` delimiter; if they edited it, diff against the repo |
| `Job.state must be ENABLED` | a paused scheduler job | `gcloud scheduler jobs resume presale-<you> --location=$GOOGLE_CLOUD_REGION` |
| Cloud Shell idled out | ~1 hour | `./workbench.sh`. `sessions.db` survived — Chapter 4 for free; say so instead of apologising |
| Everything is strange | leftover state | RESET THE VENUE, then `./use-solution.sh N` (Load step N) |

### Repairs in one line

```bash
./use-solution.sh N                 # a student's agent is wrecked: code + state back to chapter N
# RESET THE VENUE on the panel      # their venue is in a strange state
rm sessions.db && .venv/bin/python -m seed.session     # their session history is confusing them
./setup.sh                          # nothing works and you have four minutes: safe to re-run
```

The `solutions/` folders map one-to-one onto chapter numbers. Anyone who falls
behind loads the next chapter and rejoins.

---

## Three surfaces, one agent

| | Where | What it is |
|---|---|---|
| `adk web` | Chapters 1–5 | the dev UI: State, Events, Artifacts, the graph. Answers interrupts in the event's reply box |
| `monstertix/server.py` | Chapter 2, and the Resume button's fallback | your own Runner behind `/wake` and `/trigger/wake`, on :8090 |
| `agent/main.py` on Cloud Run | Chapter 6 | `get_fast_api_app` plus the same handlers, in one container |

All three use `app_name="concert"`, `user_id="user"`, and (locally) the same
`sessions.db`. That is why a task started in one is visible from the others.

---

## Clean-up

### Order

```
1. Scheduler job          gcloud scheduler jobs delete presale-<you>
2. Push subscription      gcloud pubsub subscriptions delete presale-<you>-push
3. Topic                  gcloud pubsub topics delete presale-<you>
4. Cloud Run service      gcloud run services delete concert-<you>
5. Cloud SQL instance     gcloud sql instances delete workshop-sessions        (--all)
6. Bucket                 gcloud storage rm -r gs://<project>-agent-<you>      (--all)
7. The venue              ./destroy-venue.sh
```

`./destroy-agent.sh` does 1–4; `--all` adds 5–6; the venue is separate. The
schedule goes first so nothing fires at a half-deleted stack. Safe to run twice:
everything already gone is reported as *absent*.

### Confirm

```bash
gcloud scheduler jobs list --location=$GOOGLE_CLOUD_REGION      # no presale-<you>
gcloud pubsub topics list                                        # no presale-<you>
gcloud run services list --region=$GOOGLE_CLOUD_REGION           # no concert-<you> (and no venue-<you> after destroy-venue)
gcloud sql instances list                                        # no workshop-sessions
gcloud storage ls                                                # no <project>-agent-<you>
grep -c 'AGENT_SERVICE_URL\|CLOUD_SESSION_SERVICE_URI' .env       # 0
```

The service URL answers 404 once the service is gone; the local `sessions.db`,
`memory/` and `artifacts/` are untouched and `use-solution.sh` resets them.

Cloud SQL (`db-f1-micro`) and the bucket are the two things that keep billing
with nothing running. Say so at 1:47 and again at 2:00. Students who want to
keep experimenting keep them; everyone else runs `--all`.

---

## Why it is built the way it is

Each decision below has a wrong answer that looks reasonable.

**Why one continuous task.** Earlier versions changed city and party size per
step; students spent the first minutes of every step re-understanding a
scenario instead of the mechanism. Two people, Amsterdam, weekend, no upper
bowl, in every chapter, means the only thing that changes is what the agent can
do.

**Why the concert booker.** It is the scenario where the agent must act *while
the human is unavailable*, which is what forces the agreed-authorization
pattern. An expense approver has no consequential action; a trip booker is too
common.

**Why each student deploys their own venue.** A shared one means the moment
somebody presses **SELL THE GOOD SEATS**, everyone else's agent fails for no
visible reason. Half the course is deliberately breaking things.

**Why the weeknight show is cheaper and listed first.** It is the trap the
memory lesson rests on. Price alone or order alone picks the Tuesday. Only the
memory file stands between the agent and that mistake. A student whose agent
books a Tuesday is seeing the lesson, not a bug.

**Why the Workflow, not `LongRunningFunctionTool`, on the main line.** The
graph records each node's output, replays finished nodes on resume and reruns
the interrupted one — and reading that off the events *is* the Resumption
deep dive. The tool-based path is in the Reference.

**Why Chapter 4 stops at ready to buy.** Mixing "did the same ticket survive"
with "was the purchase authorized" in one chapter meant neither question got a
clean answer. Now 4B's evidence is a ticket and 5A's is an authorization.

**Why the authorization is session state and not `user:`.** Under `user:` it
silently governs every future run and the person is never asked again. A
limit that has to be re-agreed is the honest trade.

**Why no default budget for the unattended path.** A scheduler that fills in a
budget is a scheduler spending your money. A run parked on `budget:ask` at 3am
stays parked, and that is correct.

**Why the scheduler reaches `/trigger/wake` and not ADK's Pub/Sub route.** The
built-in route mints a fresh session per message. Right for "fire an agent at
something", wrong for "finish the thing you started".

**Why Cloud Run, not Agent Engine.** Agent Engine cannot receive scheduled or
event-driven triggers. Not a preference.

**Why Vertex and ADC, not an API key.** The credential model is identical on a
laptop and on Cloud Run, so the Chapter 6 diff has nothing to say about auth.

**Why SQLite locally.** A session as rows you can `select` from. Cloud SQL
through a proxy never feels that direct, and the Chapter 6 diff is the point.

**Why deploying does not migrate the local task.** It could, and it would
teach the wrong thing: that state follows the code. State follows the store.
Chapter 6 creates a new task in the cloud store and the scheduler finishes that
one.
