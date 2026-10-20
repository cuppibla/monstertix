You asked for two tickets for you and Sam. The venue saves that order,
but sends back an error: **503**. The agent's purchase tool tries again.
Will you end up with four tickets?

**This section teaches safe retries.** An error response does not prove
that nothing was bought. Sending the **same purchase key** again lets the
venue find and return the order it already saved. The result should be
**two requests, one order, two seats**.

The live card below tells you whether your purchase has finished and reads
the evidence directly from your session. You do not need to hunt through
ADK's JSON before knowing what happened.

:::exercise id="run"
:::figure src="/docs-img/07-01-solution2.png" caption="The venue charges the order and then the reply fails. The retry carries the same idempotency key, so the venue answers with the order it already has: last_order is set once."
:::
:::

:::task
:::

<div id="purchase-key-code" style="scroll-margin-top: 160px"></div>

## Key code: one key, one order

:::code path="agent/concert/tools.py" highlight="key = hashlib\.sha256\(|f\x22\{tool_context\.session\.id\}:\{event_id\}:\{section\}:\{seats\}\x22"
:::

The `Idempotency-Key` is derived, not random:

```
sha256(f"{session.id}:{event_id}:{section}:{seats}")[:24]
```

Same session, same show, same section, same count → same key. A retry of the
same purchase therefore carries the same key, and the venue can recognise it.
A random UUID here would be a key in name only: every attempt would look new.

:::code path="agent/concert/tools.py" highlight="while attempts < 2|int\(result\.get\(\x22status\x22\) or 0\) >= 500|retrying with the same key"
:::

The tool retries **once**, itself, and only on a server-side failure. A 409
(sold out, still in the queue) is an answer, not a failure; retrying it would
ask the same question twice. The response the model finally sees carries
`attempts` and `idempotency_key`. The live card above extracts these exact
fields; ADK Events keeps the full response for you to inspect.

:::optional title="Going deeper: the venue’s half of idempotency" minutes=8 needs="chapter 5 loaded"
:::file path="venue/app.py" label="Show venue/app.py — /purchase and /admin/hang-once"
:::

Two branches in the venue's `/purchase` make this work:

```
1. Seen this exact purchase before? Hand back the original order.
   if idem_key:
       seen = row("SELECT * FROM orders WHERE idem_key=?", (idem_key,))
       if seen:
           return {**seen, "duplicate": True}

5. If HANG ONCE is armed, the order is already committed and the
   caller is about to be told it failed.
   raise HTTPException(503, {"error": "upstream_timeout", "message": "try again"})
```

The scenario’s commit-then-503 fault arms branch 5: the seats are taken, the row is
written, and *then* the response fails. The retry arrives with the same key,
branch 1 finds the row, and the venue returns it with `duplicate: true`. One
order. The activity feed shows both lines: `COMMITTED, then failed the
response (hang-once)`, then `duplicate suppressed — returned ord_…`.

There is no second experiment here: compare these two branches with the same order id in your live activity feed.
:::

:::key
A missing response tells you nothing about whether the order exists. Retry
with the same operation identity, and let the venue answer the question you
cannot.
:::

:::checkpoint
**The caller got no response. Why can't it conclude the order was not created?**
:::answer
Because the failure can happen on either side of the commit. A request can be
lost before it arrives, the server can fail before writing, or — as here — the
server can write the order and then fail to answer. From the caller's side all
three look identical: a timeout or a 5xx. Deciding "it was not created" and
buying again is right in two cases and doubles the order in the third. The
only safe move is to retry with the same idempotency key and let the venue
say which case it was: a new order, or the original one back with
`duplicate: true`.
:::
:::
