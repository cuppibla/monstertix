# Balanced hands-on MonsterTix lab

The default course uses the illustrated reading and real ADK Web exercises.
Learners type requests, answer the budget questions, inspect Events and State,
and deliberately kill and resume a task. Historical guided-course receipts do
not replace these actions or mark the chapter rail complete.

## Teaching sequence

| Chapter | Main experiment | Keep in the core | Optional |
|---|---|---|---|
| Meet | Explore the venue, prepare, ask in ADK Web | You and Sam need two tickets; queue position means people ahead | Full source |
| Wake | Ask once, start the server, fire one 10-second clock | Agent / Runner / caller; the agent does not wake itself | Instruction variants, a manual server call, a repeating clock |
| Memory | Inspect session A, save one preference, recall it in session B | Session DB, Memory Service, state lifetimes, diagrams and code | SQL, full artifact inspection, read-only compaction |
| Resume | Start a task, kill, restart, move its ticket, resume once | Workflow, completed outputs vs interrupted nodes, live queue | Detailed records, crash gap and read-only LRFT comparison |
| Buy | Answer and confirm a budget; prepare one scenario; resume | Authorization, live guard, commit-then-503, same-key retry | Venue implementation |
| Cloud | Instructor demonstration of an existing cloud task | Architecture, source, exact task and trigger | Independent deployment and cleanup |

Each chapter has a focused experiment with reading sections around it. Sections
are not separate experiments. In particular, Memory reuses session A until the
one switch to B; Resume only needs one resume after the restart; Buy uses one
purchase across all three sections. Code viewers and original diagrams remain
visible. Further implementation reading is collapsed where it interrupts the
main story. Diagnostic checks are available under Troubleshooting.

## Interface

- `/step/:chapter/:part` opens the actual section. Chapter links open its first
  section. `/study/...` remains a compatible route.
- The live venue stays on the left. ADK Web opens in a drawer with that section's
  numbered actions and copy buttons beside the real development UI.
- On narrow screens the instructions stack above ADK instead of disappearing.
- The chapter rail uses chapter numbers, not receipts from earlier runs.
- Chapter loading is explicit: it replaces the solution stage and resets live
  sessions, memory seed and venue. Navigation itself does not load or reset.
- `/step/cloud` is the instructor demonstration. Its links expose the full
  deployment extension.

## Combined purchase preparation

One button sells out A for the task's exact show, arms the mock venue's
commit-then-503 fault, and moves that task's exact queue ticket to the front.
Each completed operation appears below the button. Failure stops the sequence;
it never resumes the agent. The learner presses Resume separately.

The helper checks stage 5, a queue pause, a ticket and show, confirmed
session-scoped authorization, and no existing order before making changes.
Budget answers still come from the learner in ADK Web's interrupt response
boxes. A new chat message is not an interrupt response.

## Validation

Use an isolated copy and distinct ports for destructive rehearsal. Do not aim a
walk or test fixture at a learner's active venue or session database.

```bash
cd web
npm run check
npm run build
node --experimental-strip-types --test tests/purchaseScenario.test.mjs
cd ..
./tests/run.sh
python scripts/walk-hands-on.py \
  --url http://127.0.0.1:59073 --output runs/hands-on-walk.json
```

The real-model walk calls the same stage, ADK, clock, venue and resume APIs as
the UI. It resets its target and verifies all five local chapters. It checks
cross-session recall, a ticket surviving a killed process, refusal to resume a
human question, the stale-plan refusal, two purchase attempts and one order.
Browser rehearsal additionally covers actual ADK entry/response boxes, the
combined scenario button, copy/navigation controls and responsive layout.

The older `walk-guided.py` and receipt service remain for compatibility, but
are not the default learning route. The main lab does not auto-send the
learner's prompts or substitute old evidence for a new experiment.

Cloud deployment requires separate rehearsal with configured resources. A
Scheduler dispatch being accepted is not proof of task completion; inspect the
cloud session, Cloud Run logs and final venue order. This local revision does
not deploy or claim to verify a remote cloud task.
