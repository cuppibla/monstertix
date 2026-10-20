The agent is loaded and nothing is happening. Nothing *inside* the agent can
change that. The missing piece is outside it, and it has two halves. This
section builds the first half. The next section builds the second. The agent
file does not change in either one. Hold on to that: it is the point.

## The two halves

:::figure src="/docs-img/03-02-ed.png" caption="Left: the trigger, a server that listens. Right: the triggerers, anything that calls it."
:::

| | plain words | the file | becomes, in Chapter 6 |
|---|---|---|---|
| **the trigger** | the server that listens. It can run the agent, and it waits to be called | `monstertix/server.py` | Cloud Run |
| **the triggerer** | the thing that calls it. Here, a clock | `monstertix/clock.py` | Cloud Scheduler |

The two words look alike, so read them as a pair: the trigger is the doorbell,
the triggerer is whoever presses it. The one ending in *-er* does the pressing,
like *caller*. In the figure, the house with the bell is the trigger; the
people running at it, the cron job, the click on the website, are triggerers.

This section is the house. The next one is the clock.

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

`adk web` has a Runner of its own. This section is where you build one
yourself, and that is the entire difference between a development UI and
something you can deploy.

## The trigger: your own web server

`monstertix/server.py` is a small FastAPI server. At startup it builds one
Runner, from the same URIs `adk web` uses, so the two see the same sessions:

:::code path="monstertix/server.py" highlight="^_services = dict\(|^    session_service=session_service,|^    artifact_service=artifact_service,|runner = Runner\("
:::

Then it opens one door, `POST /wake`. A message comes in the body, and the
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

:::optional title="Call it manually before using the clock" minutes=2 needs="MonsterTix running"
:::exercise id="manual"
:::

The MonsterTix page is a chat window that posts to `/wake`;
when you press send, the log shows the Runner at work:

```
[server] woken · session 5c1e…
[server]   called recall
[server]   called search_events
[server]   said   For you and Sam I'd pick the Saturday 14 Nov show at Ziggo
                  Dome …
```

Same agent, same tools; now your server owns the Runner. The next section uses a clock as the caller.
:::
:::

:::key
The trigger is a server that listens, with a Runner behind it. It can run the
agent, and it does nothing until something calls it. The next section sends that request from a clock.
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
**MonsterTix is running and the agent is loaded. Will it check the Amsterdam
show on its own now?**
:::answer
No. A server that listens is only half of it. Nothing happens on `/wake`
until something sends a request there. The optional manual call uses the page; otherwise no call has arrived yet. The agent cannot send that request to itself: once
the Runner returns, no code of its own is running. The missing half is the
next section.
:::
:::
