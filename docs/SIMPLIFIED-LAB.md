# Guided MonsterTix lab

The core is six pages, following one ticket-buying story. A fresh experiment is
created at each chapter boundary; chapters 4 and 5 each preserve their own task
through every pause and resume. The course does not pretend that switching
solution stages carries a task forward.

## Teaching sequence

| Chapter | Learner action | Essential reading | Expand only when needed |
|---|---|---|---|
| Meet | Prepare once; read the model reply | You and Sam need two tickets; a queue position is not seconds | Agent / Runner / Venue; original architecture and source |
| Wake | Ask once; schedule one check | Prompt → no future run; external caller → Runner → invocation | Standalone clock and `/wake` implementation |
| Memory | Read one run; save aisle seats; create session B | Session DB events/state; Memory Service facts; `user:prefs` is separate | Raw records, artifact lifetime, SQL, read-only compaction |
| Resume | Start task; actually kill; restart and resume | A Workflow names the steps; completed outputs are reused; waiting `check_front` runs again | Node records, `rerun_on_resume`, crash gap, read-only LRFT comparison |
| Buy | Answer budget and confirmation; prepare faults; resume | Authority → guard → same-key retry → exactly one order | Full function responses, idempotency derivation, business errors |
| Cloud | Watch an instructor's prepared deployment | External caller reaches a saved cloud task | Independent deploy / task / Scheduler / logs / cleanup |

The buy preparation button performs three visible, sequential operations:
section A sells out for the task's show; the venue arms a commit-then-503
response; only this queue ticket moves to the front. It does not resume the
agent. Failure stops the sequence. A later resume answers `queue:wait` in the
bound session. Budget answers always come from the learner's form, addressed
to the exact pending `budget:*` interrupt.

The third chapter keeps a side-by-side view of actual A/B recall and seat map
responses. The memory diff shows the newly written lines. Raw events and state
are available underneath. No successful memory write is inferred from “noted.”

## What changed in the interface

- Six core pages replace 17 mandatory a/b/c pages. The chapter rail shows earned
  receipts; reading ahead never earns completion.
- One next-action card replaces scattered preparation and instruction lists.
  It shows the expected visible result and any error at that action.
- The live venue, inventory, queue and orders remain. A compact task card adds
  the bound session, invocation count and queue position. Advanced venue
  controls are collapsed to avoid accidental independent scenario changes.
- The existing MonsterTix application remains available. The core uses the
  guided controls; the original application is useful in detailed study.
- The ADK drawer is an inspection tool, bound to the current experiment's exact
  session. It no longer duplicates a second full set of core instructions.
- Historical receipts and archived records remain readable after loading
  another chapter. They are labelled as historical, separate from the live venue.
- Old `/step/:chapter/:part` links open the corresponding single core page.
  The unchanged detailed exercises remain reachable under `/study/:chapter/:part`.

## Evidence and recovery

`workbench/services/learning.py` owns the coordination, not agent decisions.
It uses the existing solution packages and real ADK `/run` calls. Actions carry
an attempt ID, and person answers also carry an interrupt ID. A stale page
cannot answer a different task. Only one operation runs at a time.

`runs/learning.json` stores attempts and earned receipts. Each receipt contains
its session IDs, stage, code fingerprint, timestamp and observed checks. Raw
sessions and memory are saved under `runs/learning-evidence/` before stage
loading clears live data. Receipts survive workbench restarts. “Start a fresh
experiment” explicitly resets live state and retains completed receipts.

The local one-shot timer is intentionally not durable scheduling. A workbench
restart before it fires marks it interrupted and offers a new clock action.
Restarting an agent service reuses its session; it does not answer a person or
start a new purchase. Missing evidence stays missing rather than being filled
with an expected sample value.

A Workflow resume can retain the same ADK invocation ID. The invocation counter
counts distinct recorded IDs, not HTTP requests or graph edges. For the Wake
experiment, a new prompt from the clock does create another invocation.

## Validation

After setup, run the ordinary suite with `./tests/run.sh`. For the frontend:

```bash
cd web
npm run check
npm run build
```

To rehearse the guided route, start a separate local workbench with distinct
`WORKBENCH_PORT`, `AGENT_PORT`, `VENUE_PORT` and `TRIGGER_PORT`. Also set
`VENUE_URL` to that local venue. Do not point a rehearsal at a class in progress.

```bash
uv run --python .venv/bin/python python scripts/walk-guided.py \
  --url http://127.0.0.1:58873
```

The walk resets that workbench's live data, calls the real model for all five
local chapters, checks each receipt, and confirms earlier raw records remain
readable after stage changes. It writes `runs/guided-walk.json` and deliberately
does not dispatch cloud jobs. Fixture budget answers apply only to the simulated
local venue. The learner interface never auto-answers those questions.

Before a class, separately rehearse the instructor's cloud deployment. Configure
`AGENT_SERVICE_URL`, the project/region and optionally `PRESALE_TOPIC` (the
existing job name). Inspect the exact cloud session; confirm its budget on the
cloud page; advance that venue's ticket; dispatch the existing job. Check both
Cloud Run logs and the final order. Scheduler accepting a dispatch is not proof
that the task completed. This example assumes one active cloud task.
