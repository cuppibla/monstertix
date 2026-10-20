In 2b, you sent a question from the left-hand MonsterTix chat and saw a reply.
**Now the Clock waits ten seconds and sends the same question for you:**

> Check whether the Amsterdam shows still have seats, and tell me what you find.

You do not type this into a chat box. Clicking **Fire once, 10s from now**
runs the Clock, which sends the message to the Server's `/wake` endpoint.
The Server's Runner then runs the agent, the agent asks its tools to check
the tickets, and the Server returns the answer to the Clock.

```text
Click Fire once → Clock waits 10 seconds → sends the preset question
               → Server runs the agent → tools check tickets → answer
```

**This is a scheduled request, not just a connection to the Server.**
The ten seconds are the delay before sending; the agent needs additional
time to finish its answer. Watch **Clock sent** and **Agent replied** below
the button: these show the actual request and response. The Clock uses a
separate `wake-…` session, so the left chat keeps your manual conversation.
To inspect the tool calls, open **MonsterTix → log**.

## The Clock code: wait, then send

`monstertix/clock.py` imports `httpx`, `time` and `argparse`. No ADK. It has
never heard of an agent, a Runner or a session. It knows a URL and a delay:

:::code path="monstertix/clock.py" highlight="^DEFAULT_MESSAGE = \(|time\.sleep\(args\.delay\)|response = client\.post\(f\x22\{TRIGGER_URL\}\{route\}\x22|if not args\.every:"
:::

Sleep, then one POST, then maybe sleep again. That is the whole file. Every
scheduler you have ever used does the same thing, plus retries, time zones,
and a promise to survive a restart.

The message it sends asks for a check, and nothing in this chapter can buy:
the agent has no purchase tool, and nothing is ever bought without an
authorization a person gives in the task.

:::exercise id="fire"
After the delay, the Clock sends its request. The Server runs the agent,
then the Clock reports completion. These lines come from the two logs:

```
[clock]  firing → POST /wake
[server] woken · session wake-3f9a21c0
[server]   called recall
[server]   called search_events
[server]   said   Both Amsterdam shows still have seats. For you and Sam the
                  Saturday 14 Nov show at Ziggo Dome fits …
[clock]  done. the agent ran and you were not involved.
```

That is the answer to section 2a. Something outside the agent called it, and
that something was a `sleep` and one HTTP request. The agent file did not
change. The server did not change. Only the caller did.

The session id was `wake-` and eight hex digits: every fire is a fresh session
with no memory of the last one. The agent still knew about Sam and the upper
bowl, because `recall()` reads the memory file, which is not the session.
Chapter 3 takes those two stores apart.

The one-shot Clock exits after the response. **Check complete** means it
finished normally. The Server stays running, ready for another request.
:::

:::key
In 2b, you sent the question through the chat page. In 2c, the Clock sent
the same question after a delay. Both called `/wake` on the same Server,
which ran the same agent. Only the caller changed.
:::

:::note
**This is not an alarm clock yet.** The workbench started both halves, and
they stop when it does. In Chapter 6 `clock.py` is not deployed; Cloud
Scheduler does its job, `server.py` becomes `main.py` on top of
`get_fast_api_app(...)`, and the same routes run in one Cloud Run container
with the page. Nothing on the agent side changes, which is why the two halves
are separate files.
:::

:::optional title="A repeating clock, and the scheduler's route" minutes=5 needs="MonsterTix running"
**A repeating clock.** Same file, `--every`. Watch it fire twice and press
**Stop clock**; each fire is a new `wake-` session.

:::exercise id="repeat"
:::

**The scheduler's route.** `clock.py --trigger` posts to `/trigger/wake`
instead of `/wake`: no message, just *look again*. It resumes a run that is
waiting in the queue and leaves everything else alone. That is the route Cloud
Scheduler reaches in Chapter 6; there is nothing waiting yet, so it does
nothing here.
:::

:::checkpoint
**The agent already promised, in 2a, to check later. Why does it still need an
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
