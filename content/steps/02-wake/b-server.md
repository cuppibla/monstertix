In 2a, you sent a question and the agent checked the Amsterdam tickets once.
To check again later, something must send another request.

**The Server receives that request and runs the agent.** Clicking **Start
MonsterTix** starts a Python web service. It loads the agent and prepares a
Runner, then waits. Starting the server alone does not check any tickets.

**First, send a question yourself.** Use the MonsterTix chat on the left
and watch its reply. **In 2c, the Clock will send the same question** after
a ten-second delay. You keep the same agent
and instruction throughout.

## Where the left-hand page fits

The left-hand **MonsterTix** tab is a chat page served by this server.
Sending a message there calls the server's `/wake` endpoint. This is your
next action: send the question in the exercise below and wait for its reply.
The **Venue panel** is the simulated ticket seller: it shows seat availability
and the activity caused by tool calls.

| Part | Its job in this experiment |
|---|---|
| MonsterTix chat page | Lets you send a question manually |
| Server · `server.py` | Receives the question; its Runner runs the agent and returns the answer |
| Clock · `clock.py` | Waits, then sends the preset question automatically |

## A receiver and a caller

:::figure src="/docs-img/03-02-ed.png" caption="Left: the trigger, a server that listens. Right: the triggerers, anything that calls it."
:::

The diagram calls the receiving server the **trigger**, and the things that
send it requests **triggerers**. For this lab, keep the concrete pair in mind:
**Server receives; Clock sends.** In Chapter 6 these jobs move to Cloud Run
and Cloud Scheduler.

## What a Runner does

In the last section you learned that an `Agent` is a description: a name, a
model, an instruction, a list of tools. It does not run anything. The thing
that runs it is the **Runner**, and until now it was hidden inside `adk web`.
Here is what it does, every time a message arrives:

:::figure src="/docs-img/03-01-flow.png" caption="What a Runner does around your agent, from one message in to one answer out."
:::

1. A message comes in over HTTP.
2. The Runner finds or creates the session.
3. It stores the message in that session.
4. It hands the model the conversation so far, and the model starts the work.
5. Each time the model asks for a tool, the Runner runs the function and feeds
   the result back. Repeat until the model stops asking.
6. The Runner returns the answer and writes every step to storage.

`adk web` already has a Runner. The prepared server code below creates one
for the MonsterTix app, so a caller can reach the agent without opening ADK Web.

## The trigger: your own web server

`monstertix/server.py` is a small FastAPI server. At startup it builds one
Runner, from the same URIs `adk web` uses, so the two see the same sessions:

:::code path="monstertix/server.py" highlight="^_services = dict\(|^    session_service=session_service,|^    artifact_service=artifact_service,|runner = Runner\("
:::

The `POST /wake` endpoint receives a message in the request body, and the
route hands it to the Runner:

:::code path="monstertix/server.py" highlight="^@app\.post\(\x22/wake\x22\)|^async def wake\(payload|return await handlers\.wake\("
:::

`handlers.wake` is the run itself: find or create the session, wrap the
message as user content, loop over `runner.run_async`, and log each tool call
and each sentence as the events come out. Whoever called `/wake` gets
sentences back and never needs to know what an agent is.

:::code path="monstertix/handlers.py" highlight="^async def wake\(|new_message = types\.Content\(role=\x22user\x22, parts=\[types\.Part\(text=message\)\]\)|async for event in runner\.run_async\(|log\(f\x22\[server\]   called \{call\.name\}\x22\)"
:::

:::exercise id="start"
What MonsterTix prints when it starts:

```
[server] agent    concert · gemini-2.5-flash
[server] identity app=concert user=user
[server] venue    http://127.0.0.1:8080
[server] sessions sqlite+aiosqlite:///…/sessions.db
[server] memory   MarkdownMemoryService
[server] listening on http://127.0.0.1:8090  (/wake, /trigger/wake, /task)
[server] nothing will happen until something calls it. Ctrl-C to stop.
```

Read that last line. The server is running and the agent is loaded, and
nothing is happening. Being callable and being called are two different
things.

The MonsterTix page is a chat window that posts to `/wake`;
when you press send, the log shows the Runner at work:

```
[server] woken · session 5c1e…
[server]   called recall
[server]   called search_events
[server]   said   For you and Sam I'd pick the Saturday 14 Nov show at Ziggo
                  Dome …
```

Same agent, same tools; now your server owns the Runner. You sent this
request through the chat page. In 2c, the Clock sends the same question.
:::

:::key
The Server receives a question and uses its Runner to run the agent.
Starting it only makes it ready. Sending a chat message starts a run.
The Clock in the next section will send the same question automatically.
:::

:::optional title="The page, and the other routes" minutes=5 needs="MonsterTix running"
**The page.** `adk web` is a development UI and not something you ship. So the
same server serves a page: a chat window that posts to `/wake` and renders
what comes back. It knows nothing about ADK and would work unchanged against
any endpoint that answers the same way.

| On the page | What it is underneath |
|---|---|
| the conversation | `POST /wake`, one message at a time |
| the banner at the top | `GET /task`: *waiting in the queue*, *waiting for you*, *running*, or *done* |
| **New session** | a fresh session id. Nothing is deleted |
| **Resume** | answers a queue wait, from Chapter 4 on |
| **Wipe everything** | deletes every session and the memory file. It asks first, and says where that state lives |

:::code path="monstertix/server.py" highlight="^@app\.get\(\x22/\x22\)|return FileResponse\(STATIC / \x22index\.html\x22\)|^@app\.get\(\x22/health\x22\)|^@app\.post\(\x22/trigger/wake\x22\)"
:::

**The other routes.** `/health` reports which agent and which session store
the server is holding, and the workbench reads it. `/trigger/wake` is the
route a scheduler reaches: no body, resumes a run that is waiting in the
queue, and leaves a run that is waiting for a person alone. You use it in
Chapter 6.
:::

:::checkpoint
**You sent a question and got an answer. Will the Server check the Amsterdam
shows again on its own now?**
:::answer
No. A server that listens is only half of it. Nothing happens on `/wake`
until something sends another request there. Your chat message started one
run; it did not schedule the next one. The agent cannot send that request to itself: once
the Runner returns, no code of its own is running. The missing half is the
next section.
:::
:::
