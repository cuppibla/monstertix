# Chapter tests

One folder per solution, mirroring `solutions/`. Every test answers the same
question: **does this chapter still do what the course says it does?**

Not "does the code import" — that is table stakes. These check that if a student
types what the instructions tell them to type, they see what the instructions
show them.

## Run them

```bash
cd monstertix
./tests/run.sh
```

That is the whole thing. It sources `set_env.sh`, starts a scratch venue on
**:8099** if one is not already there, and runs the fast suite. Takes a few
seconds.

```
62 passed, 7 skipped in 3.4s
```

The skipped ones are the live tests. To run those too:

```bash
./tests/run.sh --live
```

Several minutes, and it spends tokens — every one of them drives the real agent
or the real graph against the real model.

### One chapter at a time

```bash
./tests/run.sh tests/step5_buy
./tests/run.sh --live tests/step5_buy
```

Everything except `--live` is passed straight to `pytest`, so `-k`, `-x` and
`-v` all work. If you pass only flags, `tests/` is added for you:

```bash
./tests/run.sh -k guard -v
./tests/run.sh -x                    # stop at the first failure
./tests/run.sh --live -k "sell_out"
```

### Without the runner

```bash
. ./set_env.sh
VENUE_DB=/tmp/test-venue.db VENUE_PORT=8099 python -m venue &
VENUE_URL=http://127.0.0.1:8099 pytest tests/ -q
```

## Why :8099 and not :8080

So a test run can never touch the venue you are teaching from. The tests press
**RESET THE VENUE** constantly — between individual assertions — and doing that
to a venue somebody is demonstrating against wipes their queue ticket mid-run.
That has happened; it is why the port is different.

Tests that need the venue skip themselves with a readable message if nothing is
listening, rather than failing with a connection error.

## The two kinds

| | What it checks | Cost |
|---|---|---|
| **structural** | the wiring the chapter depends on — `queue_up` really has `rerun_on_resume=False`, compaction names its own model, the guard refuses in the documented order, the purchase retries once with the same key | milliseconds, no model |
| **behavioural** | drives the agent or the graph through the beats the chapter walks through, and checks the venue afterwards | a minute or more each, real tokens |

Behavioural tests carry `@needs_model` and are skipped unless
`WORKSHOP_TEST_LIVE=1` is set. That split is deliberate: the fast suite is meant
to be usable as a pre-flight check before a run-through, so it has to stay fast
enough that you actually run it.

## What each chapter asserts

| Chapter | The claim being held in place |
|---|---|
| 1 meet | three read-only tools (`search_events`, `get_seatmap`, `recall`), no way to buy or wait, `app_name=concert` |
| 2 wake | the `PROACTIVE_INSTRUCTION` block has the exact shape the workbench prompt lab edits; still nothing that buys; the agent has no clock of its own |
| 3 remember | a real `BaseMemoryService`, `recall` is `async`, `get_seatmap` writes `temp:` state and an artifact, `note_companion` writes `user:` state only, compaction is on with its own summariser model |
| 4 resume | root is the graph and the app is resumable; the graph ends at `ready_to_buy`; only `check_front` reruns on resume; `queue:wait` is the interrupt id; a lost ticket ends the run instead of parking it forever; nothing in the package can buy |
| 5 buy | `agree_budget` first with stable `budget:ask` / `budget:confirm` ids; `budget.parse` cases; the guard's refusal order (`no_authorization` → `wrong_seat_count` → `over_authorization` → `stale_plan` → `price_moved`); `purchase` retries once on 5xx with the same key and reports `attempts`; the venue really deduplicates on that key |
| 6 cloud | the `concert/` package is byte-for-byte chapter 5 |

The live tests for chapter 4 prove the run parks with exactly one ticket and
reaches *ready to buy* on the same ticket after SKIP THE WAIT. For chapter 5:
sell out section A during the wait and the order lands in C with two seats; a
budget question nobody answers means no ticket and no order.

## What is deliberately not tested

**Chapter 6's cloud path.** Creating a Cloud SQL instance takes ten minutes and
costs money, so `setup-cloud-state.sh` and `deploy-agent.sh` are verified by
hand. The deployable files (`main.py`, `Dockerfile`, `requirements.txt`,
`monstertix/`) have their own checks outside this folder's chapter tests.

## Adding one

Assert against **behaviour the course promises**, not implementation.
`test_check_front_survives_a_lost_ticket` earns its place because the chapter
claims the run never parks forever. A test that `tools.py` contains five
functions does not.

The helpers are in `harness.py`:

```python
from harness import FakeContext, FakeToolContext, call_node, drive, load_step, needs_model, tool_names

m = load_step("step5_buy")                 # imports that chapter's `concert` package
t = drive(m.root_agent, ["Two tickets in Amsterdam for me and Sam."],
          on_interrupt=lambda msg, tr: None)
assert t.interrupts                        # it parked
assert venue.tickets == 0                  # `venue` is a fixture

from concert import nightly as n
out = call_node(n.check_front, {"ticket": "q_1"}, FakeContext())   # a node, alone
```

`load_step` clears any previously imported `concert` first — every chapter
ships a package with the same name, and without that, chapter 5's test quietly
asserts against chapter 4's code and passes for the wrong reason.

`drive` answers interrupts for you. Pass `on_interrupt=lambda msg, t: ...` to
decide what to reply, or return `None` to leave the run parked and assert on
that. `call_node` runs the plain function behind a `@node` with a fake context,
so a refusal path can be tested without the graph, the venue or a model.
