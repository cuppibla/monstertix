The server from the last section is listening, and nothing happens until
something calls it. In that section the caller was you. Now the caller is a
clock: it sleeps, then makes one HTTP request, and you are not involved. This
is the second half, the triggerer.

## The triggerer: something that knows the time

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
Ten seconds after you set the clock, with your hands off the keyboard:

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
:::

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

:::optional title="A repeating clock, and the scheduler's route" minutes=5 needs="MonsterTix running"
**A repeating clock.** Same file, `--every`. Watch it fire twice and switch it
off beside the button; each fire is a new `wake-` session.

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
