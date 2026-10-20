The cloud agent has an empty session store. Nobody has asked it for anything,
nobody has agreed a limit with it, and it is not standing in any queue. So
start there: the same two-person Amsterdam task, created on the page the
container serves. Then let the one thing that is new — a clock Google runs —
finish it.

The question this section answers is not "does it work". It is: when a timer
fires at 3am, how does it find the right task, and how does it know that this
pause is one a timer may end?

:::exercise id="run"
## The chain

:::figure src="/docs-img/10-02-flow.png" caption="Scheduler publishes, Pub/Sub pushes, the agent wakes"
:::

```
Cloud Scheduler ─► Pub/Sub topic ─► push subscription ─► POST /trigger/wake
   (cron)           (holds and          (authenticated         │
                     retries)            as a service account) ▼
                                                     resume_waiting(allow=("queue",))
                                                       newest session with a pending interrupt
                                                       queue:wait  → answer {"checked": true}
                                                       budget:*    → leave it, report why
```

`clock.py` from chapter 2 was sleep-then-POST, and it died with your terminal.
Cloud Scheduler is the same idea run by Google: a cron with retries and a
timezone that keeps working when your laptop is shut. Pub/Sub in the middle
holds the message if the service is restarting, retries delivery itself, and
lets a second subscriber care about presales tomorrow without touching the
schedule.
:::

## Key code: find the right task, and the right kind of wait

:::code path="agent/monstertix/handlers.py" highlight="^async def resume_waiting|candidates = \[s\.id for s in await _newest_first|if kind not in allow:|waiting for a person to answer|return \{\x22woke\x22: sid, \x22kind\x22: kind, \x22reason\x22: \x22resumed\x22"
:::

A timer has nothing to say except that time has passed, so the Pub/Sub
envelope is not read. `resume_waiting` walks the sessions newest first, finds
the first one parked on an interrupt, and looks at the id's prefix:

| Pending interrupt | `kind` | What the trigger does |
|---|---|---|
| `queue:wait` | `queue` | answers it with `{"checked": true}` — the run re-checks the queue and continues |
| `budget:ask`, `budget:confirm` | `person` | **leaves it alone** and returns `{"woke": null, "reason": "waiting for a person to answer"}` |
| nothing pending | — | `{"woke": null, "reason": "nothing is waiting"}` |

:::code path="agent/monstertix/handlers.py" highlight="^def kind_of|interrupt_id\.startswith\(\x22queue:\x22\)|interrupt_id\.startswith\(\x22budget:\x22\)"
:::

This is why the interrupt ids in `nightly.py` are stable strings with a
prefix. A scheduler that answered `budget:ask` would be a scheduler spending
your money; the prefix lets `/trigger/wake` refuse without knowing anything
else about the graph. It returns 200 either way, because a 5xx would make
Pub/Sub retry, and retrying "there is nothing to do" is noise.

:::note
**Why not ADK's built-in trigger route?** `/apps/concert/trigger/pubsub`
exists on this service too. Read its source and you find
`session_id = str(uuid.uuid4())` and a user id derived from the subscription
name: a brand-new session, a different user. It would start a second task
with no ticket and no authorization instead of finishing the first.
`deploy-agent.sh` points the push subscription at `/trigger/wake` instead.
:::

:::warn
**The page and the clock answer the same wait.** On the MonsterTix page a
message while the run is parked goes to `/wake`, which answers whatever is
pending — including `queue:wait`. That is why the exercise says to type
nothing after the confirmation: let the scheduler be the thing that wakes it,
so what you see in the log is the scheduler's work.
:::

:::key
The trigger does not start a run. It finds the session that is already
waiting, checks that a machine is allowed to end that wait, and answers it.
Nobody typed; the task finished.
:::

:::checkpoint
**The scheduler fired while the cloud task was still asking "how many tickets?". What happens, and why is that the right behaviour?**
:::answer
`resume_waiting` finds the session, sees the pending interrupt is
`budget:ask`, classifies it as `person`, and returns
`{"woke": null, "kind": "person", "reason": "waiting for a person to answer"}`
with a 200. The run stays parked, nothing is bought, and the Cloud Run log
says `not resuming …: waiting for a person to answer`. That is right because
the thing being waited for is authorization, and a timer cannot give it:
there is no default budget, no unattended path, and no number from memory
that counts as permission. The next fire after the person answers finds
`queue:wait` instead, and that one it may end.
:::
:::
