One scenario runs through the whole course: two tickets, Amsterdam, me and
Sam, weekends only, never the upper bowl, up to $250 a seat. The messages
below are the only ones a student types. Everything else — the queue wait,
the scheduler's wake-up — is answered by a button or a machine, on purpose.

:::exercise id="messages"
## Where each one goes

| Message | Surface | Box |
|---|---|---|
| *Which Amsterdam shows still have seats for me and Sam?* | ADK web UI (2A) | the chat |
| *Keep an eye on the Amsterdam Saturday show for me and Sam, and tell me the moment anything changes.* | ADK web UI (2A prompt lab) | the chat |
| *Which Amsterdam show would you pick for me and Sam?* | ADK web UI (3B) | the chat |
| *Remember this for next time — we always want aisle seats.* | ADK web UI (3B) | the chat |
| *Get me and Sam two tickets to the Amsterdam show.* | ADK web UI (3A, 4A, 5A, 5C), MonsterTix page (6B) | the chat |
| *Two tickets, up to $250 each.* | ADK web UI (5A, 5C) | the `adk_request_input` event's **Enter your response…** box |
| | MonsterTix page (6B) | the chat — the page routes it to the open question |
| *Yes, that's right.* | same as the line above | same box as the question |
| *Check whether the Amsterdam shows still have seats, and tell me what you find.* | nobody types it: `clock.py`'s default `--message` (2B) | `POST /wake` |
| the queue wait | **Resume current task** · the page's **Resume** · Cloud Scheduler | `{"checked": true}` to `queue:wait` |
:::

:::warn
**Two boxes in the ADK web UI.** When a run is parked on a question, the event
shows its own input box. The chat box at the bottom starts a *new* invocation
— on a `Workflow` root that means the graph runs from the top and asks the
same question again, and on a parked queue wait it means a second task with a
second ticket. Every "it asked me twice" and every "two orders" in this course
traces back to that box.
:::

## Describing it instead of writing it

You would not hand-write most of this code at work; you would describe it.
`docs/CODELAB.md` keeps one prompt per piece under **Reference prompts**, with
the thing an assistant reliably gets wrong under each. The shape to keep when
the tickets are gone:

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
    interrupt ids with a prefix that says who may answer; rerun_on_resume=False
    on anything with a side effect; ResumabilityConfig on the App
  - the limits are agreed with a person for THIS task, read back, confirmed,
    and kept in session state the conversation cannot paraphrase
  - re-read anything time-sensitive in a before_tool_callback right before
    acting, and send an idempotency key on anything that spends
  - sessions in Cloud SQL, memory and artifacts in Cloud Storage
  - one Cloud Run service serving a page and a /trigger route that resumes
    the parked task; Cloud Scheduler → Pub/Sub wakes it

Start with the smallest version that parks and resumes. Add the limits after.
```

:::key
Eight messages, one button. If you typed anything else to make the course
work, something upstream needs fixing, not the message.
:::
