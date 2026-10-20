# Chapter 4 · Pause, Restart, Resume

The root becomes a graph, and the wait becomes a pause. Ends at *ready to
buy*; nothing is bought. Load with `./use-solution.sh 4`.

```
concert/nightly.py   NEW. Workflow "concert_nightly":
                       START → open_the_night → pick_show → queue_up → check_front → ready_to_buy
                     open_the_night   function, rerun_on_resume=False  state["request"]
                     pick_show        Agent "pick_show", output_schema=Plan, rerun_on_resume=False
                     queue_up         function, rerun_on_resume=False  POST /queue/join once;
                                      state["queue_ticket"], ["queue_event_id"], ["plan"]
                     check_front      function, rerun_on_resume=True   GET /queue/<ticket>;
                                      not ready → RequestInput(interrupt_id="queue:wait")
                     ready_to_buy     function                         state["ready_to_buy"]=True
concert/agent.py     root_agent = nightly
                     App(... resumability_config=ResumabilityConfig(is_resumable=True), compaction as before)
```

There is no `purchase` tool anywhere in this stage.

## Run it by hand

```bash
cd ~/monstertix && . ./set_env.sh
./use-solution.sh 4
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"
```

New session: *Two tickets to the Amsterdam show for me and Sam.* The run parks
at #14,203. Then `kill -9 $(lsof -ti:8000)`, start `adk web` again, reopen the
session, and answer the `adk_request_input` event in **its** reply box (or
press **Resume current task** in the workbench). Press SKIP THE WAIT on the
panel and resume once more: `[ready] at the front for ms-ams-01. Ready to buy.`

Headless, without `adk web` (uses its own `nightly.db`):

```bash
cd agent && python -m concert.nightly      # parks; SKIP THE WAIT; run again
```

Tests: `./tests/run.sh tests/step4_resume` (`--live` proves one ticket across
the restart).
