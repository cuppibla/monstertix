The run is parked. It holds a plan — section A, two seats — built from a seat
map it read before the wait, and that snapshot is in `temp:seatmap`. Forty
minutes in a real queue is long enough for section A to sell out. Nothing
would be missing from the agent's context when it wakes; the wrong thing would
be present. Who notices?

The buyer is told to act on the plan without reading the seat map first. That
is deliberate: the thing that catches a stale plan is a guard in code, not the
model's caution. This section makes the plan stale on cue and watches the
guard refuse.

:::exercise id="run"
:::figure src="/docs-img/07-01-bug1.png" caption="SELL THE GOOD SEATS on the venue panel: section A goes to zero while the run is parked. The agent's saved seat map is now a lie, and nothing told it."
:::
:::figure src="/docs-img/07-01-bug2.png" caption="Without a guard: the purchase is attempted on the stale plan and the venue refuses it. The agent only finds out by failing."
:::
:::figure src="/docs-img/07-01-solution1.png" caption="With a refresh before purchase: the seat map is read again first, section A is gone, and what is actually there is offered instead."
:::
## What the model holds

`get_seatmap` wrote two things when the picker called it: the full seat map as
an artifact, and a summary in `temp:seatmap` with `captured_at`. `temp:` state
lives for one invocation, but the plan built from it went into `state["plan"]`
and travels along the graph's edges. So when the buyer wakes it is handed
*"2 seats in section A"* with no idea the world moved.

:::code path="agent/concert/tools.py" highlight="tool_context\.state\[\x22temp:seatmap\x22\] = summary|\x22captured_at\x22: seatmap\[\x22captured_at\x22\]"
:::
:::

:::task
:::

## Key code: the guard

:::code path="agent/concert/fence.py" highlight="^def refresh_before_purchase|if tool\.name != \x22purchase\x22|live = venue\.get\(f\x22/events/\{event_id\}/seatmap\x22\)|\x22reason\x22: \x22stale_plan\x22|\x22believed_available\x22|\x22actually_available\x22"
:::

`refresh_before_purchase` is the buyer's `before_tool_callback`. It runs in the
instant before every tool call and does nothing unless the tool is `purchase`.
Then, in a fixed order:

| Check | `reason` |
|---|---|
| nobody confirmed a budget for this task | `no_authorization` |
| the agent asked for a different number of seats | `wrong_seat_count` |
| the **live** price is above the per-seat limit | `over_authorization` |
| fewer seats left than the plan needs | `stale_plan` |
| the price changed since the agent last looked | `price_moved` |

**Returning a dict from a `before_tool_callback` short-circuits the tool.** The
agent gets the dict back as if `purchase` had returned it, and the venue is
never called. Returning `None` lets the call through — and the guard leaves
`temp:guard = "passed"` and `temp:verified_price` behind when it does.

:::code path="agent/concert/agent.py" highlight="before_tool_callback=refresh_before_purchase|If — and only if — that purchase comes back refused"
:::

The buyer's instruction says: try the plan, and only if it comes back refused
with a reason, read the seat map again, call `recall()` for who this person is,
and pick again. That is why you see `purchase(A)` → refusal → `get_seatmap` →
`purchase(C)` in Events. A refusal with a reason is the answer, not a bug.

:::note
**Why not tell the model to be careful?** On the nights the model happened to
re-read, you would never see the refusal, and on the nights it forgot you would
have no protection at all. Telling it to try the plan makes the guard do the
same work every night, and makes that work visible.
:::

:::warn
**The venue still checks.** The guard reads the seat map and the order lands a
moment later; something can sell between the two. The venue's `/purchase`
re-checks availability when the order arrives and answers `409 sold_out` if the
seats are gone. The guard does not replace that — it keeps the agent from
making a request it should already know will fail, and from making one it was
never allowed to make.
:::

:::optional title="What happens without the guard" minutes=3 needs="nothing — reading only"
Take `before_tool_callback` off the buyer and run the same experiment. The
agent calls `purchase(A, 2)`, the request reaches the venue, and the venue
answers:

```
409  {"error": "sold_out", "section": "A", "available": 0, "requested": 2,
      "message": "those seats are gone — re-fetch the seatmap before buying"}
```

The outcome is the same on a good night: the model reads the message, re-reads
the seat map, buys C. What you lose is the authority check. Without the guard
nothing in code compares the live price with `per_seat_max`, so a model that
misreads *"$250"* as *"$2,500"* is stopped by nobody. The venue checks stock.
Only the guard checks permission.

:::file path="venue/app.py" label="Show venue/app.py — the /purchase route"
:::
:::

:::key
The guard re-reads the world in the instant before money moves and refuses
with a reason. The model acts on the reason. The venue checks once more when
the order lands.
:::

:::checkpoint
**The buyer was told "act on the plan". Why is `purchase(A)` being refused the correct outcome, and not a failed run?**
:::answer
The plan was right when it was made and wrong by the time it was acted on;
only the guard can know that, because only the guard reads the live seat map
at the moment of purchase. A refusal with `stale_plan` is information the
model did not have: it carries what the agent believed (400 seats) and what is
true (0). The buyer reads that, re-reads the seat map, applies memory (never
the upper bowl) and the authorization (at or under $250), and buys the one
section that fits. One order, two seats, section C — bought from the world as
it is, not as it was before the wait.
:::
:::
