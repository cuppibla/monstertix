---

id: monstertix
summary: One task, six chapters. An agent that remembers, waits in a queue, survives being killed, buys inside a limit you confirmed, and finishes in the cloud while you sleep. ADK 2 on Google Cloud.
categories: Cloud, AiAndMachineLearning
authors: Workshop
Feedback Link: https://github.com/gca-americas/monstertix


---


# MonsterTix: Long-Running Agents on Google Cloud

## Before you begin (0 min)

### The task

> Get two tickets to The Midnight Signal in Amsterdam, for me and Sam. We can
> only do weekends, and we will not sit in the upper bowl. The agent may stop
> running while it waits in the queue; when it is woken it checks the venue
> again and buys inside the limit I confirmed. In the end, a cloud timer
> finishes it.

That sentence is the whole course. Same two people, same city, same preferences
in every chapter. Each chapter lets the agent finish a little more of it without
anyone at the keyboard, and each one ends with a checkpoint you should be able
to answer from what you saw.

![What you are building](img/overview.png)

<aside class="negative">
<b>⚠️ Ethical disclaimer.</b> Ticket bots are a real problem and real ticketing sites prohibit automation. This workshop runs against a <b>mock venue</b> that you deploy yourself, buying <b>one</b> allotment for <b>yourself</b>, inside limits you set. The band is invented.
</aside>

### The four deep dives

| | The question | Chapter |
|---|---|---|
| **Memory** | Where is a fact kept, for how long, and how does it reach *this* run? | 3 |
| **Resumption** | After the process dies, what exactly comes back? | 4 |
| **Authority** | How is "comfortable around $200" different from "you may spend up to $250 tonight"? | 5 |
| **Reliability** | Stock moved, the response never came, something retried — how many orders? | 5 |

### Setup is done before class

Installing, signing in, enabling APIs, deploying the venue and starting the
Cloud SQL instance all happen in [`PRE-WORK.md`](PRE-WORK.md). If you have not
done it, do it now; it takes half an hour and most of that is waiting.

The class assumes:

- `./verify.sh` is all green
- the **workbench** is open on :4800 (Cloud Shell: Web Preview → port 4800)
- your **venue panel** is open: `$VENUE_URL/panel`

Every section of this document is also a page in the workbench, with the same
ids (1A, 1B, 2A …), the same "Your turn" steps as buttons, and *Watch* checks
that tick when the evidence is there. Read here, act there — or do everything
from terminals; both paths are given.

### How every section works

**The question** → **Your turn** (exact messages, buttons, commands) → **What
you should see** (2–4 concrete observations) → **Key code** (the lines that
matter, quoted from the real files) → **Checkpoint** (a question, and a short
model answer you should read only after you have tried).

Loading a chapter: the workbench's **Load step N** button, or from a terminal
with `adk web` stopped:

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh N
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

`use-solution.sh N` copies chapter N's `concert/` into `agent/` and its
`monstertix/` to the root, resets `memory/userx.md`, rebuilds `sessions.db`
with the `two-days-ago` conversation, and empties `artifacts/`. The venue is
never touched; **RESET THE VENUE** on the panel does that. The two flags on
`adk web` are the same two every chapter uses; Chapter 3 explains them.

Three words the workbench uses, which mean three different things:

| | What it does | What survives |
|---|---|---|
| **Load step N** | new code, new state, venue reset | the memory seed, the `two-days-ago` session |
| **Restart** (or **kill -9** then Restart) | the agent process stops and starts | everything on disk: sessions, memory, artifacts, the venue |
| **Resume current task** | answers the pause the current session is parked on | everything — this continues the same task |

## Chapter 1 · Meet MonsterTix (5 min)

### 1A · The mission

#### The question

What has to be true at the end for this task to count as done?

Most ticket sites put you in a queue. You join, you are #14,203, the line moves
for forty minutes, and when you reach the front you have a short window to pick
seats and pay. The conversation that started the task is long over by then.
That is the shape of a **long-running task**: it takes longer than one chat
turn, against a system you do not control.

Four things must be true at the end, and every later chapter is about one of
them:

1. **The preferences are right** — the Saturday show, not the Tuesday one; never
   section B.
2. **No second queue ticket** — however many times the agent is restarted or
   woken, it holds the place it already has.
3. **The purchase is inside the authorization** — "Two tickets, up to $250
   each", confirmed by a person, for this task.
4. **Exactly one order** — even when the venue's response never arrives and
   something retries.

#### Your turn

👉 On the **venue panel** (left column in the workbench, or `$VENUE_URL/panel`),
find the four things you will be watching all day:

- the **shows** — eight dates. Amsterdam has two: Tuesday 10 Nov (`ms-ams-02`)
  and Saturday 14 Nov (`ms-ams-01`). The weeknight is $10 a seat cheaper and
  listed first.
- the **queue** — tickets and positions. Empty now.
- the **stock** — per show, sections A (lower bowl, $210), B (upper bowl,
  $145), C (general admission, $95)
- the **orders** — zero. The activity feed underneath narrates everything the
  agent and the buttons do.

👉 Press **RESET THE VENUE** once, so you know what "back to the start" looks
like: 8 shows, all seats available, clock at 1×.

![The Midnight Signal, on tour](img/poster.png)

#### What you should see

- Two Amsterdam shows, the Tuesday above the Saturday, the Tuesday cheaper.
- Section B exists at the Saturday show and is the cheapest reserved seat. It
  is the wrong seat for this person, and nothing on the panel says so.
- Orders: 0. Queue: empty.

#### Key code

The venue and the agent are **two separate systems**. The agent reaches the
venue only over HTTP, through a thin client:

```python
# agent/concert/venue.py
VENUE_URL = os.environ.get("VENUE_URL", "").rstrip("/")

def get(path: str, **params) -> dict:
    """GET, returning errors as data rather than raising."""
    with client() as c:
        r = c.get(path, params={k: v for k, v in params.items() if v})
        if r.status_code >= 400:
            return {"error": True, "status": r.status_code, **_detail(r.json())}
        return r.json()
```

Errors come back as data. A tool that raises hands the model a stack trace; a
tool that returns `{"error": …}` hands it something it can explain to a
person — which matters the moment somebody presses RESET THE VENUE mid-run and
every queue ticket vanishes.

#### Checkpoint

**Which of the four end conditions can the venue panel prove on its own, and
which one can it not?**

<aside class="positive">
<b>Model answer.</b> The panel shows the queue (one ticket or two), the order count (one or two), and which show and section an order is for (Saturday, not B). It cannot show whether the purchase was <i>authorized</i> — that lives in the agent's session, not in the venue. Chapter 5 is where you learn to read it there.
</aside>

### 1B · Your workspace

#### The question

Where do you type, where do you look, and what is the difference between
loading a chapter, restarting a service and resuming a task?

#### Your turn

👉 In the workbench, find the three areas:

| Area | What is in it |
|---|---|
| **App** (under each "Your turn") | the app that step uses: the **ADK web UI** (the agent on :8000), the **venue panel**, the **MonsterTix page** (:8090). Its process's switch, **Restart**, **kill -9** and **log** are at the top right of the card |
| **Learning** (the reading) | the question, the steps, the file explorer with NEW / CHANGED markers and highlighted lines, the *Watch* checks |
| **Task card** | the current task read from the session store: session id, *Paused on* (queue / you / —), ticket + show, authorization, last order, and **Resume current task** |

👉 Press **Load step 1**. Read what it printed: it stopped the agent, pressed
RESET THE VENUE, ran `./use-solution.sh 1 --force`, and started the agent again.

👉 Open the **agent's log** (the `log` link on the ADK web UI card). You should
see uvicorn listening on :8000 and no errors.

👉 In the **ADK web UI**, pick `concert` from the app dropdown and type:

```
Two tickets to The Midnight Signal in Amsterdam, for me and Sam.
```

Terminal path:

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh 1
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

#### What you should see

- The event stream shows `⚡ recall`, then `⚡ search_events({"city": "Amsterdam"})`,
  then `⚡ get_seatmap({"event_id": "ms-ams-01"})`, then an answer naming the
  **Saturday** show, **section A at $210**, and why Sam rules out the Tuesday.
- The venue's activity feed narrated each tool call (`calling recall`,
  `search_events returned`…).
- The panel is unchanged: no queue ticket, no order. This agent can plan; it
  cannot wait or buy.

![The agent graph: the tools the model can ask for](img/01-02-tool.png)

#### Key code

The whole agent is the bottom of one file:

```python
# agent/concert/agent.py
root_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,
    tools=[search_events, get_seatmap, recall],
)

# `adk web` looks for `app` before `root_agent`. The plugin narrates every tool
# call to the venue's activity feed, so the room can watch the agent work.
app = App(
    name="concert",
    root_agent=root_agent,
    plugins=[PanelPlugin()],
)
```

A name, a model, an instruction, a list of Python functions. The tools are
plain functions; ADK builds the schema the model sees from the signature and
the docstring:

```python
# agent/concert/tools.py
def search_events(city: str = "", weekday: str = "") -> dict:
    """List tour dates. Call with no arguments to see the whole tour.

    This venue sells one artist and one tour, so there is nothing to search by
    name — never ask the user which artist they mean.
    """
    return venue.get("/events", city=city, weekday=weekday)
```

**The model never runs your code.** `⚡ search_events(...)` is the model
*asking* for the call; ADK ran it and handed the result back.

#### Checkpoint

**You pressed Load step 1, then Restart on the agent, then nothing. Which of
those could have deleted a session you were in the middle of?**

<aside class="positive">
<b>Model answer.</b> Only <b>Load step</b>: it runs <code>use-solution.sh --force</code>, which rebuilds <code>sessions.db</code>. <b>Restart</b> stops and starts the process; everything on disk stays. That distinction is the whole of Chapter 4.
</aside>

## Chapter 2 · Wake the Agent (10 min)

### 2A · A prompt cannot start a run

#### The question

The agent has just promised to check the presale. Why does nothing happen?

One invocation is three things: the **Runner** receives a message, the
**Agent** is given the message plus its instruction and tools, the model asks
for tool calls and the Runner executes them until the model answers. Everything
in that list happens *because a message arrived*. Nothing in it happens on a
schedule.

#### Your turn

👉 **Load step 2** (or `./use-solution.sh 2` and restart `adk web`).

👉 In the **ADK web UI**, one normal turn first, so you have a baseline:

```
Does the Amsterdam Saturday show still have seats?
```

👉 Now the prompt lab. Open `agent/concert/agent.py`. Below `INSTRUCTION`
there is a second one, already written:

```python
PROACTIVE_INSTRUCTION = """
You are a proactive ticket assistant.

Monitor the presale for The Midnight Signal. The moment it opens, check whether
the Amsterdam Saturday show still has seats and tell me — do not wait to be
asked, and do not wait for me to say anything. Act on your own.

Keep checking until you have an answer.
"""
```

Swap it in — the workbench's prompt lab does this for you (**Swap it in and
restart the agent**); by hand, change `instruction=INSTRUCTION` to
`instruction=PROACTIVE_INSTRUCTION` and restart `adk web`.

👉 Tell it the plan, once, in a **new session**:

```
The presale opens at 10:00. Check the Amsterdam Saturday show the moment it does, and tell me.
```

👉 Now take your hands off the keyboard for sixty seconds and watch the
**venue's activity feed** and the agent's **log**. The workbench counts the
seconds for you.

#### What you should see

- The agent agrees, and sounds like it means it. It may even say *"I'll keep an
  eye on it."*
- For the whole minute: **no new invocation**. No new events, no tool calls,
  nothing in the activity feed, nothing in the agent log.
- The service is fine. The agent's log still shows it listening. Nothing is
  broken; nothing was called.

#### Key code

Read the instruction again: *monitor*, *the moment*, *keep checking*. Every one
of those describes something happening **over time**. Now read what an
instruction is:

```python
# agent/concert/agent.py
root_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,           # ← swap to PROACTIVE_INSTRUCTION, then restart
    tools=[search_events, get_seatmap, recall],
)
```

A string, handed to the model as part of a request, **at the moment something
sends a message**. Nothing reads it in between. An instruction cannot invoke
the function it is written inside, whatever it says.

More wordings that fail the same way — *"set a timer for 10:00"*, *"check
every five minutes"*, *"act autonomously without waiting for input"* — are in
the Reference section if you want to try them. They all fail for the same
reason, and the Reference is where that belongs.

#### Checkpoint

**The agent promised to check later. Why does it still need an external caller?**

<aside class="positive">
<b>Model answer.</b> The promise is a sentence in a response, produced during an invocation that has now ended. The model has no process, no timer and no loop between invocations; the instruction is read only when a message arrives. Something outside the agent has to <i>create</i> the next invocation — a person typing, or a caller with a clock. The agent does not change. Who starts it does.
</aside>

### 2B · Give it a caller

#### The question

What is the smallest thing that can start an invocation when nobody is typing?

Two pieces, kept deliberately apart: a **server** that listens, with a Runner
behind it; and a **clock** that knows the time and POSTs to the server. The
server knows about agents and sessions. The clock knows a URL and a number of
seconds, and has never heard of ADK.

```
   clock.py ──POST /wake──► monstertix/server.py ──► Runner.run_async ──► concert agent ──► venue
   (knows the time)         (listens; owns the Runner)                  (unchanged)
```

#### Your turn

👉 Put `instruction=INSTRUCTION` back if you changed it by hand (the workbench's
**Put the original file back** does it), and restart the agent.

👉 Turn on **MonsterTix** (the switch on its card), or in a second terminal:

```bash
cd ~/monstertix && . ./set_env.sh
python -m monstertix.server
```

Read its first lines: the agent it loaded, `identity app=concert user=user`,
the venue, `sessions sqlite+aiosqlite:///…/sessions.db`, and *"nothing will
happen until something calls it."*

👉 Start the **clock** for one fire in ten seconds (the clock card, or a third
terminal):

```bash
python -m monstertix.clock --in 10
```

👉 Hands off. Watch the server log and the venue's activity feed.

#### What you should see

- Clock log, ten seconds later: `firing → POST /wake`, then
  `done. the agent ran and you were not involved.`
- Server log: `[server] woken · session wake-xxxxxxxx`, then
  `called recall`, `called search_events`, `called get_seatmap`, then
  `said   …` with an availability report for the Amsterdam shows.
- Venue activity feed: the same tool calls, narrated. **No queue ticket, no
  order.** The clock's default message is a check, not a purchase.
- In the ADK web UI's session list, a new session `wake-…` appeared. Same
  `sessions.db`, two front doors.

#### Key code

The Runner is what `adk web` has been doing for you — about six lines:

```python
# monstertix/server.py
session_service = create_session_service_from_options(
    base_dir=WORKSHOP / "agent", session_service_uri=SESSION_URI
)
artifact_service = create_artifact_service_from_options(
    base_dir=WORKSHOP / "agent", artifact_service_uri=ARTIFACT_URI
)
_services = dict(
    session_service=session_service,
    artifact_service=artifact_service,
    memory_service=memory_service,
)
if concert_app is not None:
    runner = Runner(app=concert_app, **_services)
```

The endpoint, which hands the message to a shared handler:

```python
# monstertix/server.py
@app.post("/wake")
async def wake(payload: dict = Body(default={})):
    return await handlers.wake(
        runner, session_service, APP_NAME, USER_ID,
        message=handlers.message_from(payload),
        session_id=handlers.session_id_from(payload),
        log=_log,
    )
```

```python
# monstertix/handlers.py
async for event in runner.run_async(
    user_id=user_id, session_id=session_id, new_message=new_message
):
    ...
```

And the caller. Look at its imports: `httpx`, `time`, `argparse`. No ADK:

```python
# monstertix/clock.py
DEFAULT_MESSAGE = (
    "Check whether the Amsterdam shows still have seats, and tell me what you find."
)
...
with httpx.Client(timeout=300) as client:
    time.sleep(args.delay)
    while True:
        log(f"firing → POST {route}")
        response = client.post(f"{TRIGGER_URL}{route}", json=body)
```

That separation is the reason Chapter 6 can delete `clock.py` and put Cloud
Scheduler in its place without touching the other side. The MonsterTix page
on :8090 is the same `/wake` route with a browser in front of it; the FastAPI
details and the repeating `--every` mode are in the Reference.

#### Checkpoint

**You started the clock. Did you invoke the agent?**

<aside class="positive">
<b>Model answer.</b> No. You started a process that knows the time. Ten seconds later <i>it</i> sent a POST, the server's Runner created the invocation, and the agent ran with nobody at a keyboard. The distinction matters because in Chapter 6 the thing that knows the time is Cloud Scheduler, and you are asleep.
</aside>

## Chapter 3 · Remember What Matters (25 min)

This chapter is the **Memory** deep dive. Three sections, one picture: a
**service** is the thing that reads and writes; a **store** is where the bytes
go; and nothing reaches the model unless something in the current run reads it
back.

### 3A · Session DB: where this task lives

#### The question

When you type a message, where does it go, and what else goes with it?

The **Session Service** is the ADK component that reads and writes sessions. The
**session store** behind it is whatever you pointed the URI at — here a SQLite
file, in Chapter 6 Cloud SQL. Every user message, every tool call, every tool
result and every state change becomes a row in it.

#### Your turn

👉 **Load step 3**. What changed since Chapter 2: `tools.py` gains
`note_companion`; `memory.py` gains `remember`; `agent.py` lists both and wraps
the agent in an `App` with compaction switched on (3C).

👉 In the **ADK web UI**, start a **New Session** and say three things, one
after another:

```
Sam can't do weeknights, by the way.
```

```
Show me the seat map for the Amsterdam Saturday show.
```

```
Actually, hold that — what else is on in Amsterdam?
```

The third message matters: it ends the turn that read the seat map.

👉 Open the **Events** stream and the **State** tab (left side of the ADK web
UI). Then open the **session dropdown** and switch to `two-days-ago`. Look at
its Events and its State. Then come back to your own session.

👉 A read-only look at the database itself, from a terminal:

```bash
cd ~/monstertix && .venv/bin/python - <<'EOF'
import sqlite3
db = sqlite3.connect("sessions.db")
print("sessions:", db.execute("select id, app_name, user_id from sessions").fetchall())
print("two-days-ago state:", db.execute("select state from sessions where id='two-days-ago'").fetchone()[0])
print("user_states:", db.execute("select user_id, state from user_states").fetchall())
print("events in two-days-ago:", db.execute("select count(*) from events where session_id='two-days-ago'").fetchone()[0])
EOF
```

#### What you should see

- **Events, your session:** `⚡ note_companion({"name": "Sam", "constraint": …})`
  and its `✓`; `⚡ get_seatmap({"event_id": "ms-ams-01"})` and a `✓` whose
  result is a short summary ending in `"artifact": "seatmap_ms-ams-01.json"`,
  not 2,500 seat rows.
- **State, your session:** `user:prefs` → `{"Sam": "cannot do weeknights"}`.
  **`temp:seatmap` is not there** — not stale, not empty, absent.
- **State, `two-days-ago`:** `target_event_id: ms-ams-01`, `party_size: 2`,
  and the same `user:prefs`. Your new session has the `user:` key and **does
  not have** `target_event_id` or `party_size`.
- **The database:** `sessions` has one row per session (`two-days-ago`,
  yours, the `wake-…` from Chapter 2), each with `app_name=concert`,
  `user_id=user`; the plain keys sit in `sessions.state`; the `user:` key sits
  in a separate `user_states` table, once, keyed by app and user; 13 events for
  `two-days-ago`.

![State tab: user:prefs present, temp:seatmap absent](img/04-01-newsession3.png)

#### Key code

The two flags you pass to `adk web` pick the stores:

```bash
--session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db"
--artifact_service_uri="file://$WORKSHOP/artifacts"
```

Without them ADK keeps sessions in memory and throws them away when the
process stops. `sqlite+aiosqlite://`, not `sqlite://`: ADK drives SQLAlchemy
through its asyncio extension, so the driver must be async.

Where a state key goes is decided by its **prefix**, and ADK assigns the
meaning:

| Key | Stored | Lasts |
|---|---|---|
| `party_size` | with the session (`sessions.state`) | until the session is deleted |
| `user:prefs` | against the user (`user_states`) | every session this user has |
| `app:…` | against the app (`app_states`) | every user |
| `temp:seatmap` | nowhere | this invocation; stripped before the write |

```python
# agent/concert/tools.py
def note_companion(name: str, constraint: str, tool_context: ToolContext) -> dict:
    # `user:` state belongs to the person, not to this conversation. A new
    # session for the same user starts with it already there
    prefs = dict(tool_context.state.get("user:prefs", {}))
    prefs[name] = constraint
    tool_context.state["user:prefs"] = prefs
    return {"companions": prefs}
```

```python
# agent/concert/tools.py — inside get_seatmap
await tool_context.save_artifact(filename, part)           # the 6 KB file → Artifact Service
tool_context.state["temp:seatmap"] = summary               # this invocation only
```

Two things to keep apart, because the next chapter depends on it:

- **A new session is not a deleted session.** `two-days-ago` is still there
  with its state. Your new session simply does not *share* its plain keys.
- **Persisting a session is not the same as resuming it.** The rows make
  resumption *possible*. The mechanism that continues a paused run is Chapter 4.

#### Checkpoint

**Your new session and `two-days-ago` both show `user:prefs`. Why does only
one of them show `target_event_id`?**

<aside class="positive">
<b>Model answer.</b> <code>user:prefs</code> is user-scoped: one row in <code>user_states</code> for <code>(concert, user)</code>, visible from every session of that user. <code>target_event_id</code> has no prefix, so it is session state, written into that one session's row. A new session starts with empty session state by design — the show, the party size, and later the queue ticket and the authorization belong to one task, not to the person.
</aside>

### 3B · Memory Service: bring the past into this task

#### The question

"Sam can't do weeknights" was said two days ago, in another session, and
nothing in this session mentions it. How does it get into this run?

ADK's answer is an interface, `BaseMemoryService`, with two methods:

```python
async def add_session_to_memory(session)                  # take a conversation in
async def search_memory(*, app_name, user_id, query)      # hand memories back
```

ADK ships three implementations (`InMemoryMemoryService`,
`VertexAiRagMemoryService`, `VertexAiMemoryBankService`). None fits a workshop:
the first forgets on restart and cannot be seeded, the other two need cloud
resources that take minutes to create. So this course implements the interface
itself, over a Markdown file — because you can open it, read it, and edit it.

#### Your turn

👉 Open the memory file:

```bash
cat ~/monstertix/memory/userx.md
```

Four lines matter:

```
- Sam bails on weeknights. Every weeknight show we booked, Sam cancelled.
- Hates the upper bowl at Ziggo Dome — "couldn't see a thing" from section B.
- Comfortable spend is around $200 per ticket. $250 is the hard ceiling.
- Always books two seats, always together.
```

👉 In the ADK web UI, **New Session**, and ask without mentioning days or
sections:

```
Two tickets to The Midnight Signal in Amsterdam, for me and Sam.
```

👉 Click the `✓ recall` row and read what came back. Then click the answer.

👉 Now tell it something worth keeping, and watch which tool it reaches for:

```
Remember that Sam always wants an aisle seat.
```

```bash
tail -5 ~/monstertix/memory/userx.md
```

#### What you should see

- `⚡ recall()` is the **first** tool call, before `search_events`. Its `✓`
  contains the whole file as text, including *"Sam bails on weeknights"*.
- The answer picks **`ms-ams-01`, Saturday 14 Nov**, and says why it skipped
  the Tuesday. It steers away from section B without being told to.
- `⚡ remember({"fact": "Sam always wants an aisle seat…"})`, and the line is
  now in `memory/userx.md` under *Preferences*. Your earlier chat turns are
  **not** in the file.

#### Key code

The implementation is small, and it returns ADK's own types — which is what
makes it swappable for Memory Bank later:

```python
# agent/concert/memory.py
class MarkdownMemoryService(BaseMemoryService):

    async def add_session_to_memory(self, session: Session) -> None:
        """Ingest a whole conversation. We deliberately do not."""
        return None

    async def search_memory(self, *, app_name, user_id, query) -> SearchMemoryResponse:
        path = self._path(user_id)                      # memory/userx.md
        if not path.exists():
            return SearchMemoryResponse(memories=[])
        return SearchMemoryResponse(memories=[
            MemoryEntry(content=types.Content(
                role="user", parts=[types.Part(text=path.read_text())]))])
```

The two tools are thin wrappers over one shared instance:

```python
# agent/concert/memory.py
MEMORY_DIR = pathlib.Path(os.environ.get("MEMORY_DIR", "./memory"))
MEMORY_USER = os.environ.get("MEMORY_USER", "userx")
memory_service = MarkdownMemoryService(MEMORY_DIR)

async def recall() -> dict:
    response = await memory_service.search_memory(
        app_name="concert", user_id=MEMORY_USER, query=""
    )
    ...

def remember(fact: str) -> dict:
    path = memory_service._path(MEMORY_USER, for_writing=True)
    ...
    lines.insert(lines.index("## Preferences") + 1, f"- {fact.strip()}")
```

The read path: `recall()` → `search_memory` → file → text in the tool result →
**only now** in the model's context. The write path: `remember(fact)` → one
line appended. **The current conversation is never written to the file on its
own.** `add_session_to_memory` is a deliberate no-op; dumping raw turns into
the file would destroy the one thing that makes it useful, which is that a
person can read it.

**How the service is wired, and why it differs by surface.** In production a
memory service is handed to the Runner and ADK calls it for you. The
MonsterTix server does exactly that:

```python
# monstertix/server.py
_services = dict(session_service=…, artifact_service=…, memory_service=memory_service)
```

`adk web` cannot take an object — it builds services from URIs at startup,
before it imports your code — so in the dev UI `recall` and `remember` call the
service directly. The service is the real thing; only the wiring is a
workaround. `MEMORY_USER=userx` names the **file**. The ADK user is `user`
everywhere; keep the two apart.

#### Checkpoint

**Trace "Sam only does weekends" from disk to the model, in order.**

<aside class="positive">
<b>Model answer.</b> <code>memory/userx.md</code> (written by <code>remember()</code> after a past booking) → <code>recall()</code> is called because the instruction says to call it first → <code>MarkdownMemoryService.search_memory</code> reads the file into a <code>MemoryEntry</code> → the text is the tool result → the tool result is appended to this session's events and sent to the model → the model rules out the Tuesday. Remove the <code>recall</code> call and the file still exists and nothing changes in the answer.
</aside>

### 3C · Services, lifetimes, and summaries

#### The question

Which facts cross sessions, which belong to this task only, which must be
re-fetched — and what does compaction change?

#### Your turn

👉 Open the **Artifacts** tab in your current session. Click
`seatmap_ms-ams-01.json`. Then on disk:

```bash
find ~/monstertix/artifacts -name 'seatmap_*' | head -3
```

👉 Compare your current session's **State** tab with `two-days-ago` once more,
side by side with the table below.

👉 Read the compaction sample below. It is a **prepared sample**, taken from
`seed/session.py`, so that everyone reads the same one — you are not required
to trigger compaction live. (If you want to: Reference → *Trigger compaction
live*.)

#### What you should see

- The artifact is a real file:
  `artifacts/apps/concert/users/user/sessions/<session>/artifacts/seatmap_ms-ams-01.json/versions/0/…`.
  It never appeared in the prompt; the model only ever saw the summary.
- Your session has `user:prefs` and nothing else; `two-days-ago` has
  `user:prefs` plus its own plain keys; neither has `temp:seatmap`.
- The `two-days-ago` event stream begins with a summary block where its first
  four turns used to be.

![Compacted turns at the top of two-days-ago](img/04-02-oldsession2.png)

#### Key code

Three services, one table:

| Service | Job | This course, local | Chapter 6, cloud | How it is wired here |
|---|---|---|---|---|
| **Session Service** | events, state, and what a resume needs | `sessions.db` (SQLite) | Cloud SQL | `--session_service_uri` on `adk web`; the same URI in `server.py` and `main.py` |
| **Memory Service** | long-term facts for later tasks | `memory/userx.md` | `gs://bucket/memory/userx.md` | handed to the Runner in `server.py`/`main.py`; called from `recall`/`remember` under `adk web` |
| **Artifact Service** | files such as seat maps | `artifacts/` | `gs://bucket/artifacts` | `--artifact_service_uri` on `adk web`; the same URI in `server.py` and `main.py` |

Lifetimes, for one fact in each place:

| Where | Survives the next message? | Survives a restart? | Survives a new session? | Survives deleting the DB? |
|---|---|---|---|---|
| `temp:seatmap` | **no** | no | no | no |
| `party_size` (session state) | yes | yes | **no** | no |
| `user:prefs` | yes | yes | yes | no |
| `memory/userx.md` | yes | yes | yes | **yes** |
| an artifact | yes | yes | depends on the service | depends on the service |

Comparing across sessions only works when the **app and user identity are the
same** — `concert` / `user` on every surface here. Seed a session under another
user id and it exists, answers over the API, and is invisible in the dropdown.

**Compaction — required, read-only (2–3 minutes).** `agent.py` now wraps the
agent in an `App` with:

```python
# agent/concert/agent.py
events_compaction_config=EventsCompactionConfig(
    compaction_interval=3,
    overlap_size=1,
    summarizer=LlmEventSummarizer(llm=Gemini(model=MODEL)),
),
```

After every three user-initiated invocations, ADK replaces older events with
an LLM-written summary — one more event row, with the text under
`actions.compaction`, which is why the dev UI shows a block rather than a
message. The sample, from the seeded session:

**Raw conversation** (four turns, two days ago):

```
you     We're thinking about seeing The Midnight Signal. Me, Sam, and maybe Priya.
agent   They've got eight dates. Amsterdam on the 14th and 10th, New York, Tokyo,
        Mexico City, Auckland. Amsterdam is closest to you — shall I look at those two?
you     Yes. Sam can't do weeknights though, he's bailed on every single one.
agent   Noted — I'll rule out anything midweek. That kills the 10th, which is a
        Tuesday. So Amsterdam on Saturday the 14th.
```

**What compaction wrote** (the model now reads this instead):

```
The user is planning to see The Midnight Signal with friends. They looked at
the Amsterdam dates and settled on a Saturday show because Sam cannot do
weeknights. Pricing was discussed: lower bowl $210, upper $145, GA $95.
```

**State and memory, untouched by it:**

```
user:prefs          {"Sam": "cannot do weeknights"}      ← verbatim, user_states
target_event_id     ms-ams-01                            ← verbatim, session state
memory/userx.md     "Sam bails on weeknights. Every weeknight show we booked, Sam cancelled."
```

Read the three together. The summary kept the gist and dropped the texture —
*"he's bailed on every single one"*, *"that kills the 10th"*. This one happened
to keep Sam; a longer, chattier conversation may not. **A summary rewrites the
transcript. It does not rewrite state, and it does not touch the memory
file.** That is why `note_companion` and `remember()` exist as deliberate
writes: anything load-bearing goes somewhere a summariser cannot paraphrase.
Parameters, the SQL to read a summary, and triggering one live are in the
Reference.

#### Checkpoint

**The session DB and the memory file are both still there. Why does a new
session not know what "continue that order" refers to?**

<aside class="positive">
<b>Model answer.</b> "That order" is task state — the show, the plan, the queue ticket, the authorization — and task state is plain session state, written into one session's row. A new session has a new id and starts with empty session state; it does not read other sessions' events. What does cross over is <code>user:</code> state and whatever <code>remember()</code> chose to write to the file — preferences, not the task. And the file contains only explicit writes, never the transcript. So the new session knows who Sam is and what this person likes, and has no idea which task was under way. Continuing a task means going back to <i>that</i> session, which is Chapter 4.
</aside>

## Chapter 4 · Pause, Restart, Resume (25 min)

This chapter is the **Resumption** deep dive. It ends at *ready to buy*: the
run reaches the front of the queue on the same ticket it started with, after
its process has been killed. Nothing is bought until Chapter 5.

### 4A · Turn waiting into a pause

#### The question

The queue takes forty minutes. What should the agent be doing during them?

Nothing. Not sleeping, not polling — *not running*. The task becomes a graph
whose waiting step **stops the run** and writes where it stopped into the
session store. From Chapter 4 on, `root_agent` is that graph.

```
START ─► open_the_night ─► pick_show ─► queue_up ─► check_front ─► ready_to_buy
           (function)       (agent)     (function)   (function)     (function)
           says what        reads       joins once,  at the front?  says so, and
           tonight is for   memory,     keeps the    no → PAUSE     stops. Nothing
                            picks the   ticket       yes ↓          is bought here.
                            show
```

One node is an agent, because choosing a show is judgement. The rest are
functions, because joining a queue and asking "am I at the front" are rules,
and a rule should not be a coin flip at 3am.

#### Your turn

👉 **Load step 4**. New: `nightly.py` (the graph). `agent.py` now exports the
graph as `root_agent` and turns on `resumability_config`.

👉 In the **ADK web UI**, **New Session**, and start the task:

```
Two tickets to the Amsterdam show for me and Sam.
```

👉 Watch the agent's **log** and the **venue panel**. Then open the **State**
tab and the **task card**.

#### What you should see

- Agent log, four lines, then silence:
  ```
  [open]        Nobody is awake. Choosing the show.
  [queue_up]    ms-ams-01 section A — ticket q_xxxxxxxx at #14,203
  [check_front] #14,203 — not yet. Pausing.
  ```
  (`pick_show` shows in the event stream as `recall`, `search_events`,
  `get_seatmap` calls and a JSON `Plan`.)
- The event stream ends on an **`adk_request_input`** event: *"Still in the
  queue at #14,203. Wake me again and I will check."* The invocation is over.
  Nothing is running.
- **State:** `request` (your sentence), `queue_ticket: q_…`,
  `queue_event_id: ms-ams-01`, `plan: {event_id, city, section: "A", seats: 2, reason}`.
- **Venue panel:** one queue ticket, moving down from #14,203 at 1×. **Task
  card:** *Paused on: queue*, the ticket, the show.

#### Key code

The graph, with its one agent node:

```python
# agent/concert/nightly.py
picker = Agent(
    name="pick_show",
    model=MODEL,
    tools=[recall, search_events, get_seatmap],
    output_schema=Plan,
    instruction="""Choose one show and one section for this person. Buy nothing.

THERE IS NOBODY THERE. The person is asleep. You cannot ask a question …""",
)
pick_show = node(picker, rerun_on_resume=False)

nightly = Workflow(
    name="concert_nightly",
    description="The unattended presale run: choose, queue, wait, reach the front.",
    edges=[(START, open_the_night, pick_show, queue_up, check_front, ready_to_buy)],
)
```

Joining the queue, as a function node that writes the ticket to state:

```python
# agent/concert/nightly.py
@node(rerun_on_resume=False)
def queue_up(node_input, ctx: Context) -> Event:
    plan = Plan(**node_input)
    ticket = venue.post("/queue/join", {"event_id": plan.event_id})
    ctx.state["queue_ticket"] = ticket["ticket"]
    ctx.state["queue_event_id"] = plan.event_id
    ctx.state["plan"] = plan.model_dump()
    return Event(output={**plan.model_dump(), "ticket": ticket["ticket"]})
```

And the pause — a `RequestInput` instead of a loop:

```python
# agent/concert/nightly.py
QUEUE_WAIT = "queue:wait"

@node(rerun_on_resume=True)
def check_front(node_input, ctx: Context):
    ticket = node_input.get("ticket") or ctx.state.get("queue_ticket") or ""
    status = venue.get(f"/queue/{ticket}")
    if status.get("error"):
        return Event(output={**node_input, "ticket": "", "lost": True})
    if not status.get("ready"):
        return RequestInput(
            interrupt_id=QUEUE_WAIT,
            message=f"Still in the queue at #{status.get('position', 0):,}. "
                    "Wake me again and I will check.",
        )
    return Event(output=node_input)
```

`RequestInput` is ADK's interrupt. The graph stops where it stands, the
invocation is written to the session store, and the process is free to die.
The interrupt id is a **stable string** with a prefix (`queue:`), so whoever
wakes the run can tell a queue wait from a question for a person (Chapter 5).

#### Checkpoint

**There is a queue ticket, a pending interrupt, and the invocation has ended.
What is the agent's process doing right now?**

<aside class="positive">
<b>Model answer.</b> Nothing related to this task. <code>adk web</code> is idle, listening. No coroutine is sleeping, no connection is open to the venue. The only record that a task is half-done is in <code>sessions.db</code>: the events up to the <code>adk_request_input</code>, and the state keys. That is why killing the process next is safe to try.
</aside>

### 4B · Kill it, then continue

#### The question

If the process dies now, what is lost?

Write your prediction down before you press anything. Three candidates: the
queue ticket, the place in the queue, the plan.

#### Your turn

👉 On the **agent's card**, press **kill -9**. (Terminal:
`kill -9 $(lsof -ti:8000)`.) The card shows **killed**.

👉 Look at the **venue panel**. Wait ten seconds. Look again.

👉 Press **Restart** on the agent's card (terminal: start `adk web` again with
the same two flags). The ADK web UI reopens; pick your session from the
dropdown if it did not come back on its own. Check the **State** tab.

👉 Press **Resume current task** on the task card. (In the ADK web UI you can
instead type anything — `check` — into the `adk_request_input` event's own
reply box, **not** the chat box at the bottom. The chat box starts a new
invocation, which replays the graph from the top and takes a second ticket.)

👉 Read the log. Then press **SKIP THE WAIT** on the venue panel, leave the
clock at 1×, and press **Resume current task** again within a couple of
minutes — the venue holds a place at the front for about as long as it takes
1,000 more people to be served.

#### What you should see

- While the agent was dead, the **queue kept moving**: the ticket's position
  on the panel went down. The venue did not notice.
- After the restart, **State** still has `queue_ticket` — the same `q_…`.
- First resume: `[check_front] #13,xxx — not yet. Pausing.` **No `[open]`,
  no `[queue_up]`.** The panel still shows **one** ticket.
- After SKIP THE WAIT, second resume:
  ```
  [check_front] at the front
  [ready]       at the front for ms-ams-01. Ready to buy.
  ```
  The run's final message: *"At the front of the queue for ms-ams-01 in
  Amsterdam: 2 seats in section A. Ready to buy. Nothing is bought in this
  chapter."* State: `ready_to_buy: true`. Panel: one ticket, zero orders.

#### Key code

The setting that makes the pause survive a dead process:

```python
# agent/concert/agent.py
app = App(
    name="concert",
    root_agent=nightly,
    plugins=[PanelPlugin()],
    # Without this, a RequestInput still stops the run — but there is nothing
    # to come back to. With it, the parked invocation is in the session store
    # and the next call picks it up where it stopped.
    resumability_config=ResumabilityConfig(is_resumable=True),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1,
        summarizer=LlmEventSummarizer(llm=Gemini(model=MODEL)),
    ),
)
```

And how a parked run is woken — by **answering its interrupt**, not by sending
a message. This is what **Resume current task** posts to `adk web`'s `/run`,
and what MonsterTix's `/wake` builds when it finds a pending `queue:` wait:

```python
# monstertix/handlers.py — inside wake()
pending = _pending_in(session)
if pending:
    interrupt_id, kind, _ = pending
    answer = {"checked": True} if kind == "queue" else {"result": message}
    new_message = types.Content(
        role="user",
        parts=[create_request_input_response(interrupt_id, answer)],
    )
```

Resuming needs two things found, not assumed: the **right session** (the one
with the pending interrupt) and the **right pause** (its interrupt id). Both
come from the session store, which is why a process that has never seen this
task before can continue it.

#### Checkpoint

**The ticket survived. The place in the queue survived. The plan survived.
What did *not* survive, and why did that not matter?**

<aside class="positive">
<b>Model answer.</b> Anything in the process: the <code>temp:</code> state (<code>temp:seatmap</code> from <code>pick_show</code>'s look at the seat map), in-memory objects, open connections. ADK's own docstring says it: <i>"Any temporary / in-memory state will be lost upon resumption."</i> It did not matter because <code>check_front</code> re-asks the venue on every wake-up rather than trusting anything it remembered. Chapter 5 is where a stale snapshot <i>would</i> matter — and the same rule saves it.
</aside>

### 4C · Read what actually resumed

#### The question

"Resume" sounds like the run picked up where it left off. Which nodes ran
again, which did not, and which side effects must never happen twice?

#### Your turn

👉 In the ADK web UI, open your session's **Events** and the **graph** view
(the second icon on the far-left edge). Count how many times each node appears
across the three invocations (start, resume, resume after SKIP THE WAIT).

👉 Compare three things side by side:

| | Where to look | What you are checking |
|---|---|---|
| **what was persisted** | State tab; `sessions.db` | `queue_ticket`, `plan`, the pending interrupt id |
| **what was sent to resume** | the user event after each pause | a `function_response` named `adk_request_input` with id `queue:wait` — not text |
| **which nodes executed** | the log; the events of each invocation | `check_front` three times; `open_the_night`, `pick_show`, `queue_up` once |

#### What you should see

- Invocation 1: `open_the_night`, `pick_show` (with its tool calls),
  `queue_up`, `check_front` → interrupt.
- Invocation 2: `check_front` only → interrupt. Invocation 3: `check_front`,
  `ready_to_buy`.
- Exactly one `POST /queue/join` in the venue's activity feed for this task,
  and one ticket.

#### Key code

What a resume re-executes is decided by the runtime, and the flag is
narrower than its name suggests:

```python
# agent/concert/nightly.py
@node(rerun_on_resume=False)          # open_the_night, pick_show, queue_up
@node(rerun_on_resume=True)           # check_front — the node holding the interrupt
```

In ADK 2.11 a node that **finished** in an earlier invocation is **replayed
from its recorded output** on resume, whichever way its flag is set. The
recorded `Plan` and the recorded ticket are fed down the edge again; no model
call, no `POST /queue/join`. The flag matters for the node that **holds the
interrupt**: with `rerun_on_resume=True`, `check_front` runs its body again
(and asks the venue again); with `False` it would only be handed the answer it
parked on. So the three events you counted — one join, three checks — come
from "finished nodes replay, the interrupted node reruns", not from the three
`False`s.

That changes where the risk of a second ticket actually lives:

| Question | Answer |
|---|---|
| Why does persisting the session not, by itself, resume the paused run? | Rows record *where* it stopped. Something must send a `function_response` for that interrupt id into that session; `ResumabilityConfig` is what lets the Runner continue the recorded invocation instead of starting a new one. |
| Why re-query the queue position on resume? | It is the one thing that changed while the process was gone. A stored position is a fact about the past. |
| Which work must re-run, and which side effects must not repeat? | Re-run: reads of the world (`check_front`). Never repeat: the join (`queue_up`), and in Chapter 5 the purchase. |
| Finished nodes are replayed from their outputs. Why still idempotency? | Replay relies on the output having been **recorded**. A crash between the venue accepting the join and the event landing in the store leaves no output to replay, and the node runs again — an at-least-once window the policy cannot see. And a message typed into the chat box is a **new invocation**, which runs the graph from the top. Idempotent joins and the purchase key cover both. |

**A short comparison: `LongRunningFunctionTool`.** ADK also lets a *tool*
return immediately with a handle and park the run until something sends the
result back. It fits a single slow call inside a chat; the graph fits a task
with several steps where the policy per step matters. This course uses the
graph on the main line. The tool-based alternative is written up in the
Reference.

#### Checkpoint

**Set `queue_up` to `rerun_on_resume=True`. Predict what the next resume
does, then measure it from the venue and the events. Where does a second
ticket really come from?**

<aside class="positive">
<b>Model answer.</b> <i>Prediction:</i> a second <code>POST /queue/join</code>, a new ticket at #14,203, two tickets on the panel. <i>Measurement:</i> one ticket. The panel's count stays at one, the activity feed shows no second <i>joined ms-ams-01</i>, State's <code>queue_ticket</code> is unchanged, and the resumed invocation contains <code>check_front</code> only — because a finished node is replayed from its recorded output regardless of the flag. The flag only governs the node that holds the interrupt. <i>So where does a second ticket come from?</i> Two real sources: (1) typing into the chat box instead of answering the interrupt — that is a <b>new invocation</b>, and the graph runs from the top, <code>queue_up</code> included; (2) a crash between the venue accepting the join and the node's output being recorded — nothing to replay, so the node runs again (<b>at-least-once</b>). Neither is fixed by a flag. That is why <code>queue_up</code> is written to be safe to repeat and why <code>purchase</code> carries an idempotency key in Chapter 5. Put the flag back to <code>False</code>; it documents intent even where the runtime would replay anyway.
</aside>

## Chapter 5 · Buy Within Agreed Limits (30 min)

This chapter holds the **Authority** deep dive (5A) and the **Reliability**
deep dive (5B, 5C). The graph from Chapter 4 is not replaced; it is
surrounded: a person at the start, a buyer at the end.

```
START ─► agree_budget ─► open_the_night ─► pick_show ─► queue_up ─► check_front ─► brief ─► buyer_agent
           (function)       (function)      (agent)     (function)   (function)   (function)   (agent)
           asks a PERSON,   says what        reads       joins once   at the front? plan →       reads the seat
           reads it back,   may be spent     memory,                  no → PAUSE    message      map again, buys
           stores it                         picks                                               once, one message
```

5A and 5B run as one continuous task. 5C is a separate, clearly marked
experiment with its own start.

### 5A · Agree before acting

#### The question

The memory file says *"$250 is the hard ceiling."* Is that permission to spend
$250 tonight?

No. It is a **preference** — a fact about the person, read from history.
**Authority** is given for one task, by the person, in words they confirmed,
and it has a scope: how many seats, how much each, when it was confirmed. The
graph asks for it before it does anything else, and the code checks it in the
instant before money moves.

#### Your turn

👉 **Load step 5**. New: `budget.py` (parse, store, check an authorization),
`fence.py` (the guard in front of `purchase`), `purchase` in `tools.py`,
`agree_budget` and `brief` in `nightly.py`, `buyer_agent` in `agent.py`.

👉 In the **ADK web UI**, **New Session**:

```
Two tickets to the Amsterdam show for me and Sam.
```

The run stops on an `adk_request_input`: *"Before I book anything: how many
tickets, and the most to pay for each? For example: "Two tickets, up to $250
each.""*

👉 Answer **in that event's reply box**, not the chat box:

```
Two tickets, up to $250 each.
```

It reads it back: *"So: 2 tickets, up to $250 each. Have I got that right?"*

👉 Same box:

```
Yes.
```

👉 Open the **State** tab and the **task card**.

#### What you should see

- Two interrupts before anything else ran: ids `budget:ask` and
  `budget:confirm`. No `recall`, no `search_events` until after your *Yes*.
- Log after the confirmation:
  ```
  [agree_budget] agreed: 2 seats, up to $250 each (confirmed 09:41)
  [open]        Nobody is awake. Authorization: 2 seats, up to $250 each (confirmed 09:41)
  [queue_up]    ms-ams-01 section A — ticket q_xxxxxxxx at #14,203
  [check_front] #14,203 — not yet. Pausing.
  ```
- **State:** `authorization` →
  `{"text": "Two tickets, up to $250 each.", "seats": 2, "per_seat_max": 250.0, "confirmed": true, "confirmed_at": "09:41"}`.
  No prefix: session state, for this task only.
- **Task card:** *Paused on: queue*, authorization *2 seats, up to $250 each*.
  Before your *Yes* it said *Paused on: you*, and **Resume current task** was
  disabled with the reason *waiting for you — answer in the chat*.

#### Key code

Two kinds of pause, one mechanism, different prefixes:

```python
# agent/concert/nightly.py
ASK_BUDGET = "budget:ask"
CONFIRM_BUDGET = "budget:confirm"

@node(rerun_on_resume=True)
def agree_budget(node_input, ctx: Context):
    answers = ctx.resume_inputs or {}
    ctx.state["request"] = what_they_asked_for(ctx)

    agreed = budget.load(ctx.state)
    if agreed:
        return Event(output=agreed)

    said = _said(answers.get(ASK_BUDGET))
    if not said:
        return RequestInput(interrupt_id=ASK_BUDGET, message="Before I book anything: …")

    parsed = budget.parse(said)
    if not parsed:
        return RequestInput(interrupt_id=ASK_BUDGET, message=f"I could not read … \"{said}\" …")

    reply = _said(answers.get(CONFIRM_BUDGET))
    if not reply:
        return RequestInput(interrupt_id=CONFIRM_BUDGET,
                            message=f"So: {parsed['seats']} tickets, up to ${parsed['per_seat_max']:g} each. Have I got that right?")
    ...
    auth = budget.make(said, parsed)
    ctx.state[budget.AUTH_KEY] = auth
    return Event(output=auth)
```

Three things make a question-to-a-person work, and all three are needed:
`rerun_on_resume=True` (so the node runs again when woken instead of being
skipped), a **stable** `interrupt_id` (so the answer can be looked up), and
`ctx.resume_inputs[interrupt_id]` (where the answer arrives — not the return
value of `RequestInput`).

What is stored, and why both halves:

```python
# agent/concert/budget.py
AUTH_KEY = "authorization"            # session state key

def make(text: str, parsed: dict) -> dict:
    return {
        "text": text.strip(),                       # what they said, verbatim
        "seats": int(parsed["seats"]),              # what the guard compares
        "per_seat_max": float(parsed["per_seat_max"]),
        "confirmed": True,
        "confirmed_at": time.strftime("%H:%M"),
    }

def allows(auth, seats, price) -> tuple[bool, str]:
    if not auth:                                   return False, "no_authorization"
    if int(seats) != int(auth["seats"]):           return False, "wrong_seat_count"
    if float(price) > float(auth["per_seat_max"]): return False, "over_authorization"
    return True, ""
```

The sentence is what the buyer reads and what you are shown back. The numbers
are what code compares against a live price. **Session state, not `user:`** —
a budget is agreed for one booking. Under `user:` it would silently govern
every run this person ever makes.

**Waiting for a person vs waiting for the queue.** Both park the run the same
way. The difference is who may answer. `handlers.resume_waiting` — what the
clock, the scheduler and the Resume button call — only answers `queue:`
waits:

```python
# monstertix/handlers.py
def kind_of(interrupt_id: str) -> str:
    if interrupt_id.startswith("queue:"):  return "queue"
    if interrupt_id.startswith("budget:"): return "person"
    return "other"
```

There is no default budget and no unattended path. If nobody answers, the run
stays parked and nothing is bought.

#### Checkpoint

**The memory file has said "$250 is the hard ceiling" for months. Why is that
not an authorization to buy tonight?**

<aside class="positive">
<b>Model answer.</b> It is a description of the person, written after a past booking, with no scope: not how many seats, not for which task, not confirmed for tonight. An authorization is an instruction, given for this task, read back and confirmed, with numbers the guard can check, stored in <i>this</i> session. <code>budget.load</code> returns <code>None</code> unless <code>confirmed</code> is true; the guard then refuses with <code>no_authorization</code>, whatever the file says. And a timer cannot supply one: <code>budget:</code> interrupts are never answered by anything but a person.
</aside>

### 5B · Check the world again

#### The question

The plan says section A. The seat map that plan was built from is forty
minutes old. What happens when section A sold out while the agent was asleep?

#### Your turn

Continue the task from 5A; it is parked in the queue.

👉 On the **venue panel**, press **SELL THE GOOD SEATS**. Section A goes to
zero for every Amsterdam show. The plan in state still says `"section": "A"`.

👉 Press **SKIP THE WAIT**. Then **Resume current task** (within a couple of
minutes, clock at 1×).

👉 Read the buyer's message, the log, and the **venue panel**.

#### What you should see

- Log: `[check_front] at the front`, then the buyer's tool calls **in this
  order**: `purchase(ms-ams-01, A, 2)` — the plan, exactly as agreed — then
  `get_seatmap`, then `recall`, then `purchase(ms-ams-01, C, 2)`, then
  `remember`.
- The first `✓ purchase` is a **refusal, not an order**:
  `{"error": true, "reason": "stale_plan", "believed_available": …, "actually_available": 0, …}`.
  The venue's activity feed shows no purchase attempt for it; the guard
  short-circuited the call before it left the agent.
- The `✓ get_seatmap` result shows section A with `"available": 0`.
- **One order on the panel: `ms-ams-01`, section C, 2 seats, $95 each.** Not
  B, although B is $145 and under the limit — the memory file rules it out.
- The buyer's message says what it got, what it cost, and why C.

#### Key code

The handover tells the buyer to **act on the plan**, not to check first:

```python
# agent/concert/nightly.py — brief()
f"Act on the plan: call purchase for {plan.seats} seats in section "
f"{plan.section} of {plan.event_id} now, without reading the seat map "
"first. The guard in front of purchase re-checks live inventory and the "
"authorization for you. Only if it refuses — the seat map is forty "
"minutes old and the world may have moved — read the seat map again and "
"pick the best remaining section that fits the authorization and what "
"you know about this person, or buy nothing."
```

```python
# agent/concert/agent.py — buyer INSTRUCTION
  1. Act on the plan. Call purchase with exactly the planned show, the planned
     section and the planned number of seats. Do NOT read the seat map first:
     the plan was agreed, and a guard in front of purchase re-checks the live
     inventory and the authorization for you in the instant before money
     moves. If the plan still holds, you are done buying.

  2. If — and only if — that purchase comes back refused with a reason
     (stale_plan, over_authorization, price_moved), the world moved while you
     waited. Now read the seat map again with get_seatmap, and call recall() …
```

That is deliberate. Telling the model "be careful, re-read first" would hide
the guard: on the nights the model re-read you would never see the refusal,
and on the nights it forgot you would have no protection. So the stale plan is
tried, the guard refuses it with a reason, and only then does the model go
looking.

The guard runs in the instant before `purchase` reaches the venue, whatever
the model decided. Returning a dict short-circuits the tool:

```python
# agent/concert/fence.py
def refresh_before_purchase(tool, args, tool_context) -> dict | None:
    if tool.name != "purchase":
        return None
    auth = budget.load(tool_context.state)
    if auth is None:
        return {"error": True, "reason": "no_authorization", ...}
    if int(seats) != int(auth["seats"]):
        return {"error": True, "reason": "wrong_seat_count", ...}

    live = venue.get(f"/events/{event_id}/seatmap")          # now, not then
    current = next((s for s in live["sections"] if s["section"] == section), None)
    ok, why = budget.allows(auth, seats, current["price"])
    if not ok:
        return {"error": True, "reason": why, ...}             # over_authorization
    if current["available"] < seats:
        return {"error": True, "reason": "stale_plan", ...}
    if believed and believed["price"] != current["price"]:
        return {"error": True, "reason": "price_moved", ...}

    tool_context.state["temp:verified_price"] = current["price"]
    tool_context.state["temp:guard"] = "passed"
    return None
```

```python
# agent/concert/agent.py
buyer_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,
    before_tool_callback=refresh_before_purchase,
    tools=[get_seatmap, recall, remember, purchase],
)
```

Order of checks, and the `reason` each refusal carries: `no_authorization` →
`wrong_seat_count` → `over_authorization` → `stale_plan` → `price_moved`.
The venue checks stock again when the order lands (`409 sold_out`); the guard
does not replace that. It stops the agent making a request it should already
know will fail, and one it was never allowed to make.

#### Checkpoint

**Nothing was missing from the agent's context when it woke up. What was
wrong with it?**

<aside class="positive">
<b>Model answer.</b> The wrong thing was <i>present</i>: a plan built from a seat map taken before the wait. Context is a snapshot; the world moved. The fix is not a bigger context and not "ask the model to be careful" — it is code that re-reads the live inventory in the instant before acting and refuses with a reason the model cannot skip. The model's job is to act on the refusal, which it did.
</aside>

### 5C · Retry without buying twice

#### The question

The venue took the order. The response never arrived. Was the order created?

You cannot tell. "Submitted successfully" and "received a success response" are
different events, and a network can separate them. So the question is not how
to find out; it is how to make retrying safe.

#### Your turn

This is a separate experiment with its own start. Four things are reset, and
one is not:

👉 Press **Reset the venue** (the 5C card's button, scope *venue only*; or
RESET THE VENUE on the panel). Orders, queue and inventory go back to the
start. **Code, sessions and memory stay.**

👉 **New Session** in the ADK web UI, and confirm an authorization for this
experiment exactly as in 5A:

```
Two tickets to the Amsterdam show for me and Sam.
```
```
Two tickets, up to $250 each.
```
```
Yes.
```

The run queues and parks.

👉 On the venue panel press **BREAK THE NEXT PURCHASE**. The next order will be
committed, and then the response will fail with a 503.

👉 Press **SKIP THE WAIT**, then **Resume current task**.

👉 Read the `✓ purchase` result, the agent log, and the venue panel.

#### What you should see

- Agent log: `[purchase]    venue answered 503 — retrying with the same key`.
- Venue activity feed, in order: `ord_xxxx COMMITTED, then failed the response
  (hang-once)`, then `duplicate suppressed — returned ord_xxxx`.
- The `✓ purchase` result has `"attempts": 2`, an `"idempotency_key"`, the
  same `"id": "ord_xxxx"` the venue committed first, and `"duplicate": true`.
- **Venue panel: exactly one order.**

#### Key code

```python
# agent/concert/tools.py
def purchase(event_id: str, section: str, seats: int, tool_context: ToolContext) -> dict:
    # Derived from the session and the request, so a retry of the SAME purchase
    # produces the SAME key. A random uuid here would be a key in name only.
    key = hashlib.sha256(
        f"{tool_context.session.id}:{event_id}:{section}:{seats}".encode()
    ).hexdigest()[:24]
    ...
    # One retry, same key, only on a server-side failure. A 409 (sold out,
    # still in the queue) is an answer, not a failure.
    attempts = 0
    while attempts < 2:
        attempts += 1
        result = venue.post("/purchase", payload, headers={"Idempotency-Key": key})
        if not (result.get("error") and int(result.get("status") or 0) >= 500):
            break
    result = {**result, "attempts": attempts, "idempotency_key": key}
    if not result.get("error"):
        tool_context.state["last_order"] = result.get("id")
    return result
```

On the venue's side the first thing `/purchase` does is look the key up:

```python
# venue/app.py
if idem_key:
    seen = row("SELECT * FROM orders WHERE idem_key=?", (idem_key,))
    if seen:
        return {**seen, "duplicate": True}
```

The retry is not cleverer; it is **the same operation, identified the same
way**, so the venue can recognise it. That is the difference between retry
logic and idempotency.

#### Checkpoint

**The caller got no response. Why can it not conclude that no order was
created — and what makes the retry safe anyway?**

<aside class="positive">
<b>Model answer.</b> The venue commits the order <i>before</i> it writes the response; a failure after the commit looks identical, from outside, to a failure before it. So "no response" carries no information about the order. The retry is safe because it sends the same <code>Idempotency-Key</code>, derived from session + event + section + seats; the venue finds the original order under that key and returns it with <code>duplicate: true</code> instead of selling the seats again. Two attempts, one order id, one row on the panel.
</aside>

## Chapter 6 · Run It While You Sleep (15 min)

The same task, in the cloud: a new task is created on the deployed service,
parks in the queue, and Cloud Scheduler wakes it. **Deploying migrates
nothing.** The task you parked in your laptop's `sessions.db` stays there;
the cloud gets its own.

### 6A · Move the runtime and the storage

#### The question

What has to change about the agent to run it somewhere your laptop is not?

Nothing about the agent. What changes is where it runs, where it keeps things,
and who sends the POST.

| On your laptop | In the cloud | What changes |
|---|---|---|
| `adk web` / `monstertix/server.py` | one Cloud Run service: `agent/main.py` + `Dockerfile` | the entrypoint |
| `sqlite+aiosqlite:///…/sessions.db` | Cloud SQL, `postgresql+asyncpg://…?host=/cloudsql/…` | `SESSION_SERVICE_URI` |
| `file://…/artifacts` | `gs://<bucket>/artifacts` | `ARTIFACT_SERVICE_URI` |
| `memory/userx.md` | `gs://<bucket>/memory/userx.md` | `MEMORY_DIR` |
| `python -m monstertix.clock --trigger` | Cloud Scheduler → Pub/Sub → `/trigger/wake` | who sends the POST |

A Cloud Run container has a writable filesystem that is destroyed when the
instance goes away. Write a session to `/tmp` at 3am and it is gone by
morning — no error, just an agent that has forgotten it was in a queue.

#### Your turn

👉 **Load step 6** (`./use-solution.sh 6`). It copies the same `concert/` as
Chapter 5 and adds `main.py`, `Dockerfile`, `requirements.txt` and a copy of
`monstertix/` to `agent/`, which is the build context.

👉 If you did not run it in the pre-work, create the durable state (Cloud SQL
must be `RUNNABLE`; `setup.sh` started it hours ago):

```bash
cd ~/monstertix && . ./set_env.sh
./setup-cloud-state.sh
```

👉 Deploy. Three to four minutes; start it and read the diff while it runs:

```bash
./deploy-agent.sh
```

```bash
diff -r solutions/step5_buy/concert solutions/step6_cloud/concert && echo "concert/ unchanged"
```

👉 When it finishes, check what the service thinks its storage is:

```bash
. ./set_env.sh            # picks up AGENT_SERVICE_URL from .env
curl -s $AGENT_SERVICE_URL/health
```

#### What you should see

- `deploy-agent.sh` prints five things, in order:
  ```
  → state    Cloud SQL + gs://<project>-agent-<you>/artifacts
  → agent    https://concert-<you>-xxxx.<region>.run.app
  → topic    presale-<you> created
  → iam      concert-trigger@<project>.iam.gserviceaccount.com may invoke concert-<you>
  → push     → https://concert-<you>-xxxx.<region>.run.app/trigger/wake
  → schedule 0 3 * * *
  ```
- The `diff` prints nothing: the agent package is identical.
- `/health` reports `"kind": "Workflow"`, `"sessions": "/adk?host=/cloudsql/…"`
  (host part only; the password is not shown) and `"memory": "gs://…/memory"`.

#### Key code

```python
# agent/main.py
app = get_fast_api_app(
    agents_dir=str(HERE),
    web=False,                        # no dev UI in production
    session_service_uri=SESSION_URI,
    artifact_service_uri=ARTIFACT_URI,
    trigger_sources=["pubsub"],       # ← mounts /apps/<app>/trigger/pubsub (unused here)
    allow_origins=["*"],
)
```

`get_fast_api_app` builds the session and artifact services from the same two
URIs you have passed to `adk web` since Chapter 3, and returns an ordinary
FastAPI. The MonsterTix routes — `/`, `/wake`, `/trigger/wake`, `/task` — are
bolted onto it from the same `handlers.py` the laptop server used. One
container, two front doors: a page for a person, a route for a timer.

```bash
# deploy-agent.sh — the two URIs and the socket
--set-env-vars "^|^SESSION_SERVICE_URI=$SESSION_URI|ARTIFACT_SERVICE_URI=$ARTIFACT_URI|VENUE_URL=$VENUE_URL|…"
--add-cloudsql-instances "$SQL_CONNECTION_NAME"
```

`postgresql+asyncpg://`, not `postgresql://`: same async-driver rule as
`aiosqlite`, and it fails the same way — at the first write, at 3am.

#### Checkpoint

**Why is ADK's built-in `/apps/concert/trigger/pubsub` mounted but not wired to
the scheduler?**

<aside class="positive">
<b>Model answer.</b> It mints a fresh <code>session_id</code> (and a user id derived from the subscription) on every message. That is right for "fire an agent at something" and wrong for "finish the thing you started": a fresh session has no queue ticket, no authorization and no plan, so it would start a second task — and ask a budget question nobody is there to answer. <code>/trigger/wake</code> finds the session that is already parked on a <code>queue:</code> wait and answers that.
</aside>

### 6B · Resume it from the cloud

#### The question

At 3am, what finds the right task, and how does it know it is allowed to
continue it?

```
Cloud Scheduler ──publish──► Pub/Sub topic ──push──► POST /trigger/wake
                                                          │
                                           handlers.resume_waiting(allow=("queue",))
                                                          │
                              newest session with a pending interrupt ──► kind?
                                        queue:wait → answer {"checked": true} → check_front → brief → buyer
                                        budget:*   → leave it. report "waiting for a person"
```

#### Your turn

👉 Open the service URL in a **new tab** — the MonsterTix page, on the
internet, with nothing of your laptop involved. Press **New session**, then
create the same task:

```
Two tickets to the Amsterdam show for me and Sam.
```
```
Two tickets, up to $250 each.
```
```
Yes.
```

The banner reads **waiting in the queue**.

👉 On the **venue panel**, press **SKIP THE WAIT** (clock at 1×).

👉 Be 3am. Fire the scheduler job now instead of waiting:

```bash
gcloud scheduler jobs list --location=$GOOGLE_CLOUD_REGION          # find presale-<you>
gcloud scheduler jobs run presale-<you> --location=$GOOGLE_CLOUD_REGION
```

👉 Do not touch the page. Within a few seconds the agent's message appears on
its own. Then read the evidence:

```bash
gcloud run services logs read concert-<you> --region=$GOOGLE_CLOUD_REGION --limit=50
curl -s $AGENT_SERVICE_URL/task
```

#### What you should see

- Cloud Run logs, in order: `[server] answering queue interrupt queue:wait`,
  `[server] woken · session web-xxxxxxxx`, `[check_front] at the front`,
  `called get_seatmap`, `called purchase`, `said …`.
- `/task` shows `"pending": null`, `"authorization": {… "confirmed": true}`,
  and a `"last_order": "ord_…"`. The page banner reads **done · order ord_…**.
- **Venue panel: one new order**, `ms-ams-01`, 2 seats, inside $250.
- The session that was resumed is the `web-…` one you just created. Your
  laptop's sessions are not in Cloud SQL and were never candidates.

If you fire the job while the page is still asking for a budget, the logs say
`not resuming web-…: waiting for a person to answer` and nothing is bought.
That is the correct outcome, not a failure.

#### Key code

```python
# monstertix/handlers.py
async def resume_waiting(runner, session_service, app_name, user_id, *,
                         session_id=None, allow=("queue",), ...):
    for sid in candidates:                       # newest first
        pending = _pending_in(session)
        if not pending:
            continue
        interrupt_id, kind, _ = pending
        if kind not in allow:
            return {"woke": None, "kind": kind, "session_id": sid,
                    "reason": "waiting for a person to answer"}
        result = await wake(runner, session_service, app_name, user_id,
                            message=message, session_id=sid, log=log)
        return {"woke": sid, "kind": kind, "reason": "resumed", **result}
    return {"woke": None, "kind": None, "reason": "nothing is waiting"}
```

```bash
# deploy-agent.sh — the push subscription and the alarm clock
gcloud pubsub subscriptions create "$TOPIC-push" --topic="$TOPIC" \
  --push-endpoint="$URL/trigger/wake" --push-auth-service-account="$SA_EMAIL"
gcloud scheduler jobs create pubsub "$TOPIC" --schedule="0 3 * * *" \
  --time-zone="Etc/UTC" --topic="$TOPIC" --message-body='{"kind":"check_the_queue"}'
```

The message body is not read. A timer has nothing to say except that time has
passed. Pub/Sub in the middle holds the message if the service is restarting,
retries delivery, and lets a second subscriber join later without touching the
scheduler.

You can rehearse this exact route locally, against `monstertix/server.py`:
`python -m monstertix.clock --in 10 --trigger` posts an empty body to
`/trigger/wake`.

#### Checkpoint

**Two sessions are parked: yesterday's, on `budget:ask`, and today's, on
`queue:wait`. The scheduler fires. What happens to each?**

<aside class="positive">
<b>Model answer.</b> <code>resume_waiting</code> walks sessions newest first and stops at the first one with a pending interrupt. If today's is newer it is resumed and yesterday's is untouched. If yesterday's were newer, the handler would find its <code>budget:</code> wait, refuse (<code>kind</code> not in <code>allow</code>), log <i>waiting for a person to answer</i>, and return without looking further — today's queue wait would wait for the next fire. Either way no timer ever answers a budget question.
</aside>

### 6C · Explain it, then clean up

#### The question

Can you narrate the whole chain — trigger, storage, resume, purchase — and
then take it apart in the right order?

#### Your turn

👉 Say the chain out loud, from the scheduler to the order, naming where each
fact lived. Then try the transfer question below.

👉 Stop the alarm clock first, then the rest. From a terminal:

```bash
cd ~/monstertix && . ./set_env.sh
./destroy-agent.sh            # schedule → subscription → topic → Cloud Run service
./destroy-agent.sh --all      # …and the Cloud SQL instance and the bucket (they keep billing)
./destroy-venue.sh            # the venue, when you are done with the workshop
```

👉 Confirm nothing is left:

```bash
gcloud scheduler jobs list --location=$GOOGLE_CLOUD_REGION
gcloud pubsub topics list
gcloud run services list --region=$GOOGLE_CLOUD_REGION
gcloud sql instances list
gcloud storage ls
curl -s -o /dev/null -w '%{http_code}\n' $AGENT_SERVICE_URL/health     # 404 once the service is gone
```

#### What you should see

- `destroy-agent.sh` prints what it removed, what was already gone, and what
  it kept (`Cloud SQL`, `bucket`) until `--all`. It also drops
  `AGENT_SERVICE_URL` (and, with `--all`, the cloud URIs) from `.env`.
- The lists are empty of `presale-<you>`, `concert-<you>`,
  `workshop-sessions` and `<project>-agent-<you>`.
- The service URL stops answering. Your laptop state — `sessions.db`,
  `memory/`, `artifacts/` — is untouched; `use-solution.sh` resets it.

#### Key code

The order is the point:

```bash
# destroy-agent.sh
# 1. Scheduler first, so nothing fires at a half-deleted stack.
# 2. The push subscription, then the topic it hangs off.
# 3. The service.
# 4. The durable state, which is the part that keeps billing.  (--all)
```

#### Checkpoint

**Transfer.** A supplier's part is out of stock. You want an agent that checks
the supplier every fifteen minutes and, when the part is back, buys up to 40
units at no more than $12 each — once. Map it onto what you built: which node
is an agent, which are functions, which pause may a timer answer, what lives in
session state versus memory, and what is the idempotency key?

<aside class="positive">
<b>Model answer.</b> One agent node at most — choosing between equivalent SKUs or suppliers, if that is judgement; everything else is functions. The "agree the limit" node asks a person for <i>40 units, up to $12 each</i> and parks on a <code>budget:</code>-style id a timer may not answer; the "check stock" node reruns on every resume and parks on a <code>queue:</code>-style id a timer may answer. Session state: the authorization, the supplier job id, the plan, the last order. Memory: preferred suppliers, past outcomes. The purchase runs once — a finished node is replayed from its recorded output — but is still written to be safe to repeat, behind a guard that re-reads price and stock, with an <code>Idempotency-Key</code> derived from session + part + quantity, so a retry after a lost response returns the original order.
</aside>

## Reference & optional

Nothing here is required. Each item says how long it takes and what it needs.

### Optional experiments

**Prompt variants that fail (5 min · Chapter 2 loaded).** Swap each into
`root_agent` in turn, restart, tell it the plan, and wait a minute:

- *"Set a timer for 10:00 and check the Amsterdam show then."*
- *"Check every five minutes whether the presale has opened."*
- *"Act autonomously. Do not wait for user input."*

Same result each time: no invocation. The wording is not the variable.

**The repeating clock (2 min · Chapter 2).** `python -m monstertix.clock
--every 120` fires `/wake` every two minutes; `--trigger` makes it post to
`/trigger/wake` instead, which is Chapter 6's route. Watch
`monstertix/server.py`'s log fill up with runs you did not start.

**The MonsterTix page's internals (10 min · reading).** `monstertix/index.html`
polls `GET /task` for the banner (*running / waiting in the queue / waiting for
you / done · order*) and `GET /session/{id}/messages?since=` for anything the
agent said while the page was not the caller — which is how a scheduled run's
message reaches the browser. It knows nothing about ADK.

**Trigger compaction live (10 min · Chapter 3 loaded).** `compaction_interval=3`
counts user-initiated invocations. Hold a chatty conversation — mention Sam's
weeknights early, then talk about other cities and friends for four or five
turns — then:

```bash
./show-compaction.sh                 # the newest session
./show-compaction.sh two-days-ago    # the seeded one
```

Read the summary and look for what it dropped. Then ask it to *"Book us
something"* and see whether it still avoids the Tuesday. If it does not, that is
the lesson landing, not a bug — and the fix was `note_companion` writing
`user:prefs`, which the summariser cannot touch. `overlap_size=1` makes each
summary start one turn earlier than it strictly needs to, so a question and its
answer are not split across two summaries:

![Two summaries, overlapping by one turn](img/05-02-compaction.png)

**Where a summary is kept (5 min · a session with a compaction).** One more
`events` row, with no `content`; the text is under `actions.compaction`:

```bash
.venv/bin/python - <<'EOF'
import sqlite3, json
db = sqlite3.connect("sessions.db")
for (data,) in db.execute("select event_data from events where event_data like '%compaction%'"):
    c = json.loads(data)["actions"]["compaction"]
    print(c["start_timestamp"], "→", c["end_timestamp"])
    print(c["compacted_content"]["parts"][0]["text"], "\n")
EOF
```

**Artifacts beyond one file (5 min · Chapter 3).** `tool_context.load_artifact`
reads one back; versions accumulate under
`artifacts/apps/concert/users/user/sessions/<session>/artifacts/<name>/versions/`.
`memory://` (the default when no flag is given), `file://` and `gs://` are the
three URI schemes `--artifact_service_uri` accepts.

**The `LongRunningFunctionTool` alternative (15 min · reading, optional
coding).** Instead of a graph, make the queue join a `LongRunningFunctionTool`
inside the chat agent: the tool returns immediately with the ticket, the run
parks, and a poller that finds tickets at the front POSTs the stored wake
payload back. It needs `ResumabilityConfig` on the `App` just the same. It is
a good fit for one slow call in a conversation; it has no per-step
recorded-output replay per step, so the "join once, check many times" rule
lives in your poller instead of the graph. The course keeps the graph on the main line
because the policy per node is the thing being taught.

**Conditional budgets (reading · Chapter 5).** *"$100 for the cheap seats,
$250 for the good ones, more on a Saturday"* is one decision with three numbers
and two conditions. `budget.parse` deliberately refuses it and asks for the
shape the guard can check. A real implementation stores the sentence and
evaluates each condition **at purchase time** against the live seat map, not
at the time it was agreed. Worth building; not something every student should
have to parse in a thirty-minute chapter.

**Cloud Trace (5 min · Chapter 6 deployed).** `deploy-agent.sh` does not pass
`--trace_to_cloud`. Add it to the `gcloud run deploy` command and redeploy, and
a run appears in the Console's Trace page with the queue wait as a gap in the
middle. Ingestion lags by minutes; a trace from last night is more useful on a
projector than one from thirty seconds ago.

**Deep SQL (5 min · Chapter 6 deployed).** Your cloud task as rows:

```bash
gcloud sql connect workshop-sessions --user=adk --database=adk   # password printed by setup-cloud-state.sh
```
```sql
select id, app_name, user_id, update_time from sessions order by update_time desc;
select count(*) from events;
```
```bash
gcloud storage cat gs://<project>-agent-<you>/memory/userx.md | head
```

### Reference prompts

You would not hand-write most of this at work; you would describe it. One
prompt per piece, and under each the thing an assistant reliably gets wrong.

**The agent (Chapter 1).**
> Write a Google ADK 2 agent package `concert`: `agent.py` with `root_agent = Agent(name, model, instruction, tools)` and an `App` wrapping it; `tools.py` with plain functions `search_events(city="", weekday="")` and `get_seatmap(event_id, tool_context)`, each with an `Args:` docstring for every argument; `venue.py` as a thin httpx client that returns errors as `{"error": True, …}` and never raises; `config.py` reading `ADK_MODEL` and failing at import if Vertex credentials are missing.

*Gets wrong:* docstrings are the tool schema. Read every generated one as if
you were the model.

**The caller (Chapter 2).**
> Two files, kept separate. `server.py`: a FastAPI app whose `POST /wake` runs an ADK agent once with `Runner.run_async` and returns what it said, building its session and artifact services from the same URIs `adk web` takes. `clock.py`: a CLI that POSTs to that endpoint after `--in` seconds and optionally every `--every` seconds. It must not import ADK.

*Gets wrong:* asked for one file, you get one file, with the clock and the
Runner tangled. Naming the separation is what lets Cloud Scheduler replace the
clock later.

**Memory (Chapter 3).**
> Implement `BaseMemoryService` over a Markdown file per user: `search_memory` returns the whole file as one `MemoryEntry` in a `SearchMemoryResponse`; `add_session_to_memory` is a deliberate no-op. Reads must not create the directory. Add `recall()` (async) and `remember(fact)` tools over it, keyed by a fixed `MEMORY_USER`. Add `note_companion(name, constraint)` writing to `state["user:prefs"]`, and make `get_seatmap` save the full map with `tool_context.save_artifact` and return a summary, stashing it under `temp:seatmap`.

*Gets wrong:* `asyncio.run()` inside a sync tool (always raises inside ADK);
returning dicts instead of ADK's types; `state["prefs"]` when you meant
`state["user:prefs"]`.

**Compaction (Chapter 3).**
> Wrap the agent in an `App` with `EventsCompactionConfig(compaction_interval=3, overlap_size=1, summarizer=LlmEventSummarizer(llm=Gemini(model=MODEL)))`.

*Gets wrong:* omitting `overlap_size` (no default), and omitting the
summariser's model — which works until the root becomes a `Workflow`, which
has no model to borrow.

**The graph (Chapter 4).**
> Rewrite the task as an ADK 2 `Workflow`: a function node that writes the request to state, an agent node with `output_schema` that picks the show, a function node that joins the queue exactly once (`rerun_on_resume=False`, ticket into state), a function node that checks the queue (`rerun_on_resume=True`) and returns `RequestInput(interrupt_id="queue:wait", …)` when not at the front, and a final node that records ready-to-buy. Put `ResumabilityConfig(is_resumable=True)` on the `App`. No sleep loops.

*Gets wrong:* `--session_service_uri=sqlite:///…` (needs `sqlite+aiosqlite://`,
`aiosqlite` and `greenlet`); a polling loop *inside* the agent; a random
interrupt id.

**Authority (Chapter 5).**
> Add a first node that asks a person how many tickets and the most per ticket, reads it back, waits for confirmation, and stores `{text, seats, per_seat_max, confirmed, confirmed_at}` in **session** state. Three things together: `rerun_on_resume=True`, stable interrupt ids `budget:ask` / `budget:confirm`, and reading answers from `ctx.resume_inputs`. No default budget and no unattended path.

*Gets wrong:* a `while not approved` loop that never parks; storing under
`user:` so it outlives the task; treating a correction as a refusal.

**The guard and the key (Chapter 5).**
> Add a `before_tool_callback` for `purchase` only: refuse with a `reason` code if there is no confirmed authorization, the seat count differs, the live price exceeds the per-seat limit, fewer seats are available than requested, or the price moved since the last seat map. Separately, send an `Idempotency-Key` derived from session id + event + section + seats, and retry exactly once on a 5xx with the same key.

*Gets wrong:* "retry safety" becomes backoff and circuit breakers. Say
"idempotency key" explicitly.

**The cloud (Chapter 6).**
> Expose the app with `get_fast_api_app(agents_dir=…, web=False, session_service_uri=<Cloud SQL asyncpg URI>, artifact_service_uri=gs://…, trigger_sources=["pubsub"])` and bolt the same `/wake`, `/trigger/wake`, `/task` routes onto it. Deploy with `gcloud run deploy --source` and `--add-cloudsql-instances`. Create a topic, a push subscription to `/trigger/wake` (not the built-in Pub/Sub route), and a Scheduler job.

*Gets wrong:* offering Agent Engine (no scheduled or event-driven triggers
there); leaving the session service unset so trigger sessions are in-memory;
wiring the subscription to `/apps/<app>/trigger/pubsub`.

**Building your own.** Keep the shape, drop the tickets:

```
I want to build a long-running agent with Google ADK 2 on Google Cloud.

The job:      [what it does]
The waiting:  [what it waits for, and how long]
The limits:   [what it must never do unattended]
The wake-up:  [what tells it to check again]

Build it in this shape:
  - a Workflow graph: functions for steps that must be identical every time,
    agent nodes only where judgement is needed
  - the wait is a node returning RequestInput, not a sleep loop; stable
    interrupt ids with a prefix that says who may answer; rerun_on_resume=True
    only on the node that holds the interrupt; every side effect idempotent
    anyway (replay covers recorded outputs, not the at-least-once window);
    ResumabilityConfig on the App
  - the limits are agreed with a person for THIS task, read back, confirmed,
    and kept in session state the conversation cannot paraphrase
  - re-read anything time-sensitive in a before_tool_callback right before
    acting, and send an idempotency key on anything that spends
  - sessions in Cloud SQL, memory and artifacts in Cloud Storage
  - one Cloud Run service serving a page and a /trigger route that resumes
    the parked task; Cloud Scheduler → Pub/Sub wakes it

Start with the smallest version that parks and resumes. Add the limits after.
```

### If you got stuck

```bash
./use-solution.sh N            # any chapter: code + reset memory, sessions, artifacts
./use-solution.sh N --keep     # code only
```

| Symptom | Fix |
|---|---|
| `adk: command not found` | `. ./set_env.sh` in that tab |
| `address already in use` | `lsof -ti:8000 \| xargs kill -9` (or :8090) |
| `VENUE_URL is not set` | `. ./set_env.sh`; no venue yet → `./deploy-venue.sh` |
| Model 404 | a `-latest` alias in `.env`. `ADK_MODEL=gemini-2.5-flash` |
| `two-days-ago` missing from the dropdown | `.venv/bin/python -m seed.session`; it must be under user `user` |
| Dropdown empty / app will not load | `ls agent/` must show `concert/` (and `monstertix/` in chapter 6) and nothing else. `./use-solution.sh N --force` tidies it |
| A second queue ticket appeared | you answered in the chat box instead of the `adk_request_input` reply box (or Resume current task). The chat box starts a new run |
| Resume says *nothing is paused* | the run finished, or the ticket expired at the front (hold ≈ 1,000 people's worth of queue time). Start a new session |
| Queue never reaches the front | press **SKIP THE WAIT**; at 1× it takes forty minutes |
| `Job.state must be ENABLED` | `gcloud scheduler jobs resume presale-<you> --location=$GOOGLE_CLOUD_REGION` |
| Scheduler fired, nothing bought | logs say *waiting for a person to answer*: the cloud task is still on its budget question. Answer it on the page |
| `[EXPERIMENTAL]` warnings | expected; `EventsCompactionConfig` and `ResumabilityConfig` are pre-GA |
| Memory file full of duplicate booking lines | `remember()` appends every run. `./use-solution.sh N` resets it |
| Cloud Shell timed out | `./workbench.sh`; `sessions.db` survived, and so did your parked task |
