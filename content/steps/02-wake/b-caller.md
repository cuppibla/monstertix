The agent is loaded and nothing is happening. Nothing in the agent can change
that. So add the thing that was missing: a caller. In this section the caller
is a clock that knows one URL, and the URL belongs to a server you own, with a
Runner behind it. The agent file does not change at all. Hold on to that: it
is the point.

## Two halves, kept apart

:::figure src="/docs-img/03-02-ed.png" caption="The trigger and the triggerer, kept apart"
:::

| | | becomes, in Chapter 6 |
|---|---|---|
| **the trigger** | an endpoint that can run the agent: `monstertix/server.py` | Cloud Run |
| **the triggerer** | something with a clock, that calls it: `monstertix/clock.py` | Cloud Scheduler |

They stay in two files all the way to the cloud. The clock imports `httpx`,
`time` and `argparse`. No ADK. It has never heard of an agent, a Runner or a
session; it knows a URL and a delay.

:::exercise id="fire"
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
things. Ten seconds after you set the clock:

```
[clock]  firing → POST /wake
[server] woken · session wake-3f9a21c0
[server]   called recall
[server]   called search_events
[server]   said   Both Amsterdam shows still have seats. For you and Sam the
                  Saturday 14 Nov show at Ziggo Dome fits …
[clock]  done. the agent ran and you were not involved.
```

That is the answer to the last section. Something outside the agent called
it, and that something was a `sleep` and one HTTP request.
:::

## Key code

Three files take part, and you have already read the first one. The agent's
instruction and tools are unchanged from the last section; nothing here
mentions a clock:

:::code path="agent/concert/agent.py" highlight="^    instruction=INSTRUCTION,|^    tools=\["
:::

**The Runner.** `server.py` builds the same services `adk web` builds, from the
same URIs, and hands them to a `Runner` together with the agent. Every flag
you pass to `adk web` has a matching argument here; this is the part of `adk
web` that was doing the work all along.

:::code path="monstertix/server.py" highlight="^_services = dict\(|^    session_service=session_service,|^    artifact_service=artifact_service,|runner = Runner\("
:::

**`/wake`.** One route. It takes a message out of the body and passes it, with
the Runner, to `handlers.wake`:

:::code path="monstertix/server.py" highlight="^@app\.post\(\x22/wake\x22\)|^async def wake\(payload|return await handlers\.wake\("
:::

`handlers.wake` is the run itself: find or create the session, wrap the
message as user content, and loop over `runner.run_async`, logging each tool
call and each sentence as the events come out. A caller gets sentences back and
never needs to know what an agent is.

:::code path="monstertix/handlers.py" highlight="^async def wake\(|session_id = session_id or f\x22wake-|new_message = types\.Content\(role=\x22user\x22, parts=\[types\.Part\(text=message\)\]\)|async for event in runner\.run_async\(|log\(f\x22\[server\]   called \{call\.name\}\x22\)"
:::

**The clock.** Sleep, then one POST. The body is a sentence that asks for a
check, and nothing in this chapter can buy: the agent has no purchase tool,
and nothing is ever bought without an authorization a person gives in the
task.

:::code path="monstertix/clock.py" highlight="^DEFAULT_MESSAGE = \(|time\.sleep\(args\.delay\)|response = client\.post\(f\x22\{TRIGGER_URL\}\{route\}\x22|if not args\.every:"
:::

The session id was `wake-` and eight hex digits: every fire is a fresh session
with no memory of the last one. The agent still knew about Sam and the upper
bowl, because `recall()` reads the memory file, which is not the session.
Chapter 3 takes those two stores apart.

:::key
A server that listens is the trigger. A clock that calls it is the triggerer.
The agent sits behind both and never learns which one woke it.
:::

:::note
**This is not an alarm clock yet.** The workbench started both halves, and
they stop when it does. In Chapter 6 `clock.py` is not deployed; Cloud
Scheduler does its job, `server.py` becomes `main.py` on top of
`get_fast_api_app(...)`, and the same routes run in one Cloud Run container
with the page. Nothing on the agent side changes, which is why the two halves
are separate files.
:::

:::optional title="The page, the FastAPI details, and a repeating clock" minutes=8 needs="MonsterTix running"
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
Chapter 6; `clock.py --trigger` rehearses it locally.

**A repeating clock.** Same file, `--every`. Watch it fire twice and switch it
off beside the button; each fire is a new `wake-` session.

:::exercise id="repeat"
:::
:::

:::checkpoint
**The agent already promised to check later. Why does it still need an
external caller?**
:::answer
Because the promise was text in a model response, and a response is the end
of an invocation, not the start of one. After the Runner returns there is no
model, no loop and no timer anywhere in the agent: the process is a web server
waiting for the next HTTP request. "Later" needs something that exists at that
later time and knows the URL: a clock, a scheduler, a person. The agent can
say what should happen when it is called; it cannot be the thing that calls.
:::
:::
