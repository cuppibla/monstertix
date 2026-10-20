The venue takes the order, writes it, charges the card — and the response
never arrives. The caller sees a 503. Was the order created? It cannot tell.
"Submitted successfully" and "received a success response" are two different
facts, and a network only promises the second when it promises anything.

So something retries. If the retry is a second purchase, the person wakes up
to two pairs of tickets. This section breaks the response on purpose and
watches the retry come back with the *same* order.

:::exercise id="run"
:::figure src="/docs-img/07-01-solution2.png" caption="The venue charges the order and then the reply fails. The retry carries the same idempotency key, so the venue answers with the order it already has: last_order is set once."
:::
:::figure src="/docs-img/09-01-hitl5.png" caption="One order, exactly as intended: 2× section A · 420, and section A's count down by two. However many times the purchase was retried."
:::
## The reset, and what it keeps

**Reset the venue** above clears orders, queue and inventory, and nothing
else. The chapter 5 code stays in `agent/`, `sessions.db` keeps every session,
and the memory file is untouched. The new session is what makes the
authorization fresh: it is session state, so it has to be agreed again.

:::code path="agent/concert/tools.py" highlight="^def purchase\(|key = hashlib\.sha256\(|headers=\{\x22Idempotency-Key\x22: key\}|while attempts < 2|retrying with the same key|\x22attempts\x22: attempts, \x22idempotency_key\x22: key"
:::
:::

:::task
:::

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
`attempts` and `idempotency_key`, so the Events tab tells you what happened
without reading a log.

## The venue's half

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

**BREAK THE NEXT PURCHASE** arms branch 5: the seats are taken, the row is
written, and *then* the response fails. The retry arrives with the same key,
branch 1 finds the row, and the venue returns it with `duplicate: true`. One
order. The activity feed shows both lines: `COMMITTED, then failed the
response (hang-once)`, then `duplicate suppressed — returned ord_…`.

:::note
**Who else retries.** Here the tool retries. In production the retry may come
from an HTTP client, a Pub/Sub push that did not get its 200, a scheduler, or
the graph being woken again. The key protects against all of them for the
same reason: it names the *operation*, not the attempt.
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
