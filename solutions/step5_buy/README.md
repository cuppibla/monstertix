# Chapter 5 · Buy Within Agreed Limits

The graph from chapter 4 with a person at the start and a buyer at the end.
Load with `./use-solution.sh 5`.

```
concert/nightly.py   START → agree_budget → open_the_night → pick_show → queue_up
                           → check_front → brief → buyer_agent
                     agree_budget   rerun_on_resume=True; interrupts "budget:ask" then
                                    "budget:confirm"; stores state["authorization"] only
                                    after the person confirms. No default, no unattended path.
                     brief          plain function: plan + authorization text + "act on the plan:
                                    call purchase now, without reading the seat map first; only if
                                    the guard refuses, read it again" → the buyer's message
concert/budget.py    NEW. AUTH_KEY="authorization"; parse("Two tickets, up to $250 each.")
                     → {seats: 2, per_seat_max: 250.0}; load / make / describe / allows
concert/fence.py     NEW. refresh_before_purchase — before_tool_callback for `purchase` only.
                     Refusals, in order: no_authorization → wrong_seat_count →
                     over_authorization → stale_plan → price_moved. Returning a dict
                     short-circuits the tool; the venue is never called.
concert/tools.py     + purchase(event_id, section, seats): Idempotency-Key =
                     sha256(session:event:section:seats)[:24]; retries once on 5xx with
                     the same key; returns attempts + idempotency_key; sets state["last_order"]
concert/agent.py     buyer_agent = Agent("concert", before_tool_callback=refresh_before_purchase,
                                         tools=[get_seatmap, recall, remember, purchase])
                     root_agent = nightly (the graph), App as in chapter 4
```

## Run it by hand

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh 5
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

New session: *Two tickets to the Amsterdam show for me and Sam.* → in the
`adk_request_input` reply box: *Two tickets, up to $250 each.* → *Yes.* It
queues and parks.

- **5B:** SELL THE GOOD SEATS, SKIP THE WAIT, resume → `purchase(A)` refused
  with `stale_plan`, then `get_seatmap` → `recall` → one order in section C.
- **5C:** RESET THE VENUE, new session, confirm the budget again, BREAK THE
  NEXT PURCHASE, SKIP THE WAIT, resume → `attempts: 2`, `duplicate: true`,
  one order.

Headless: `cd agent && python -m concert.nightly` asks for the budget in the
terminal.

Tests: `./tests/run.sh tests/step5_buy` (`--live` covers the sell-out and the
unanswered budget).
