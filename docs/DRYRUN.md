# Dry run

> **Detailed route.** The default workbench now uses six guided pages. See
> [SIMPLIFIED-LAB.md](SIMPLIFIED-LAB.md) for the short course. These original
> exercises remain available under `/study/...` for deeper study.

Rehearse every section before anyone else sees it. The question is never "does
it install". It is: **does each section produce the evidence the codelab
promises, in front of a live model, without you nudging it?** Every nudge is a
prompt or a sentence that needs fixing.

Keep a note open. Write down anything that surprised you, and how long each
section actually took against the budget in [`INSTRUCTOR.md`](INSTRUCTOR.md).

---

## The rig

Two ways to rehearse. Use the workbench, because that is what students use;
switch to terminals when you want to see what a button did.

**Workbench:** `./workbench.sh` → :4800. Load step N, the switches, kill -9,
Restart, Resume current task. Your deployed venue is on the left.

**Terminals, against a local venue you can restart freely** (`. ./set_env.sh
local` affects one terminal and never edits `.env`):

```bash
cd ~/monstertix && . ./set_env.sh local        # in every terminal
python -m venue                                # A — the venue you can break, :8080
adk web agent --port 8000 --allow_origins "*" \
  --session_service_uri="sqlite+aiosqlite:///$WORKSHOP/sessions.db" \
  --artifact_service_uri="file://$WORKSHOP/artifacts"       # B — the agent
python -m monstertix.server                    # C — MonsterTix, :8090 (chapter 2 on)
python -m monstertix.clock --in 10             # D — the caller, when a section says so
```

Between chapters: Ctrl-C the agent, `./use-solution.sh N`, start it again, and
press RESET THE VENUE. Tests use :8099 with their own database and never touch
this venue: `./tests/run.sh` before you start, `./tests/run.sh --live` once.

### Start from chapter N directly

Every chapter is self-contained: `./use-solution.sh N` (or Load step N) gives
you that chapter's `concert/` + `monstertix/`, the seed memory, the
`two-days-ago` session and an empty `artifacts/`. Then:

| To start at | Do this first | Because |
|---|---|---|
| 2 | nothing | same agent as 1 plus the prompt lab |
| 3 | nothing | the seed session and memory file are what 3 opens |
| 4 | RESET THE VENUE | 4A needs an empty queue to show one ticket |
| 5A/5B | RESET THE VENUE | A must be in stock to sell it out |
| 5C | RESET THE VENUE; a new session with a confirmed budget | the retry needs its own order |
| 6 | `./use-solution.sh 6`, `./setup-cloud-state.sh` (once), `./deploy-agent.sh` | the cloud task is new; nothing local is needed |

### Switching sections and reloading the page

While a task is parked, navigate away from the section and back, and reload
the browser tab:

- [ ] the **task card** still shows the same session id, *Paused on: queue*,
      the same `q_…` ticket
- [ ] after **Restart** on the agent card the ADK web UI frame reopens the
      last session
- [ ] **Next/Previous** only navigates — no section is marked done by reading it;
      the chip in the top bar shows checks passed/total

---

## Chapter 1 · Meet MonsterTix

### 1A

- [ ] panel shows 8 shows; Amsterdam Tuesday `ms-ams-02` above Saturday
      `ms-ams-01`, $10 cheaper per section
- [ ] RESET THE VENUE → 0 orders, empty queue, clock 1×

### 1B

**Load step 1.** Type *Two tickets to The Midnight Signal in Amsterdam, for
me and Sam.*

- [ ] `recall` → `search_events` → `get_seatmap(ms-ams-01)`; answer names
      Saturday, section A, $210, and Sam's weeknights
- [ ] it never asks *which artist*. If it does, the `search_events` docstring
      drifted
- [ ] panel: 0 tickets, 0 orders; activity feed narrated the tool calls
- [ ] `two-days-ago` is in the session dropdown. If not: `seed.session`, user id
      `user`

Time: ___ / 5 min

---

## Chapter 2 · Wake the Agent

### 2A

**Load step 2.** One normal turn, then swap `PROACTIVE_INSTRUCTION` in (prompt
lab or by hand), restart, tell it the plan in a new session, hands off 60 s.

- [ ] it agrees convincingly (if it says *"I'll keep an eye on it"*, note it:
      that line is gold in the room)
- [ ] 60 s: no new events, no activity-feed lines, nothing in the agent log
- [ ] put the original back; restart

### 2B

MonsterTix on; clock `--in 10`; hands off.

- [ ] clock log: `firing → POST /wake` … `done. the agent ran and you were not involved.`
- [ ] server log: `woken · session wake-…`, `called recall`, `called search_events`,
      `said …` — an availability report, **no purchase**
- [ ] panel: 0 tickets, 0 orders; a `wake-…` session now in the ADK dropdown
- [ ] read what it said. Useless at 3am is fine; buying would be a bug

Time: ___ / 10 min

---

## Chapter 3 · Remember What Matters

### 3A

**Load step 3.** New session; the three messages (Sam's weeknights / seat map
for the Saturday show / what else is on).

- [ ] `note_companion` and `get_seatmap` in the events; the seat-map result is
      a summary with `"artifact": "seatmap_ms-ams-01.json"`
- [ ] State: `user:prefs = {"Sam": "cannot do weeknights"}`; **no**
      `temp:seatmap`
- [ ] `two-days-ago` State: `target_event_id`, `party_size`, `user:prefs`;
      your session lacks the first two
- [ ] the python snippet prints sessions with `app_name=concert user_id=user`,
      the plain keys in `sessions.state`, the `user:` key in `user_states`,
      13 events

### 3B

New session; *Two tickets to The Midnight Signal in Amsterdam, for me and
Sam.* Then *Remember that Sam always wants an aisle seat.*

- [ ] `recall` is the **first** call and its result contains *"Sam bails on
      weeknights"*
- [ ] picks `ms-ams-01` Saturday; steers off section B unprompted
- [ ] `remember` called; `tail memory/userx.md` shows the new line under
      Preferences, and none of the chat
- [ ] the Watch check `memory --contains` passes

### 3C

- [ ] Artifacts tab shows `seatmap_ms-ams-01.json`; `find artifacts -name
      'seatmap_*'` finds it under `apps/concert/users/user/sessions/<id>/…`
- [ ] `two-days-ago` events start with a summary block
- [ ] read the compaction sample aloud against the clock: it must fit in 2–3
      minutes

Time: ___ / 25 min

---

## Chapter 4 · Pause, Restart, Resume

### 4A

**Load step 4.** RESET THE VENUE. New session; *Two tickets to the Amsterdam
show for me and Sam.*

- [ ] log: `[open]`, `[queue_up] ms-ams-01 section A — ticket q_… at #14,203`,
      `[check_front] #14,203 — not yet. Pausing.`
- [ ] picker chose **ms-ams-01**, section **A**, `seats: 2` (read the Plan JSON)
- [ ] events end on `adk_request_input` *"Still in the queue at #14,203…"*
- [ ] State: `request`, `queue_ticket`, `queue_event_id`, `plan`
- [ ] panel: **one** ticket; task card: *Paused on: queue*

### 4B — the evidence of the course

Write down the ticket id: `q_________`

- [ ] **kill -9** → card says *killed*; the panel's position keeps falling
- [ ] **Restart** → State still shows the same `queue_ticket`
- [ ] **Resume current task** → `[check_front] #1x,xxx — not yet. Pausing.`
      and **no** `[open]`, **no** `[queue_up]`
- [ ] panel: still **one** ticket, same id — *ticket unchanged after
      kill/restart, no second join_queue*
- [ ] **SKIP THE WAIT** (clock at 1×), Resume within ~2 min →
      `[check_front] at the front`, `[ready] … Ready to buy.`
- [ ] final message says *Ready to buy. Nothing is bought in this chapter.*;
      State `ready_to_buy: true`; panel **0 orders**
- [ ] Watch: `resumed` passes (≥2 invocations, one `join_queue`, one ticket)

Rehearse the timing: if you dawdle after SKIP THE WAIT the hold expires and
`check_front` reports *ticket gone*. Know what that looks like so you can name
it in the room.

### 4C

- [ ] across the invocations: `open_the_night`/`pick_show`/`queue_up` once,
      `check_front` three times; one `POST /queue/join` in the activity feed
- [ ] **the checkpoint experiment, once:** edit `nightly.py`, set `queue_up`
      to `rerun_on_resume=True`, Restart, new session, park, Resume →
      **still one ticket**: panel count unchanged, no second *joined …* in the
      feed, State `queue_ticket` unchanged, the resumed invocation holds
      `check_front` only. Finished nodes replay from recorded output. Put it
      back.
- [ ] **the real second-ticket source, once:** with a run parked, type
      anything in the **chat box** (not the reply box) → `[open]`,
      `[queue_up]` again, **two** tickets on the panel. This is what students
      will do by accident; know what it looks like

Time: ___ / 25 min

---

## Chapter 5 · Buy Within Agreed Limits

### 5A

**Load step 5.** RESET THE VENUE. New session; the three messages (*Two
tickets to the Amsterdam show for me and Sam.* / *Two tickets, up to $250
each.* / *Yes.*) — the last two in the `adk_request_input` reply box.

- [ ] `budget:ask` first, before any tool call; task card *Paused on: you*,
      Resume disabled with *waiting for you*
- [ ] `budget:confirm` reads back *2 tickets, up to $250 each*
- [ ] after *Yes*: `[agree_budget] agreed`, `[open] … Authorization: 2 seats,
      up to $250 each`, `[queue_up]`, `[check_front] … Pausing.`
- [ ] State `authorization = {text, seats: 2, per_seat_max: 250.0, confirmed: true, confirmed_at}`
- [ ] **no-authorization path:** in a *separate* new session, start the task
      and do not answer. Then `python -m monstertix.clock --in 5 --trigger`
      (server on). Server log: *not resuming …: waiting for a person to
      answer*. Panel: no ticket, **no order** — *no order without
      authorization; the timer does not answer for a person*
- [ ] try a wrong-shaped answer once (*whatever it costs*) → it asks again with
      the example shape

### 5B

Continue the 5A task.

- [ ] **SELL THE GOOD SEATS** → A = 0 on both Amsterdam shows; State `plan`
      still says A
- [ ] **SKIP THE WAIT**, **Resume current task**
- [ ] buyer calls `purchase(ms-ams-01, A, 2)` **first** → `✓ purchase` is
      `{"error": true, "reason": "stale_plan", "actually_available": 0, …}`;
      no purchase line in the venue feed for it
- [ ] then `get_seatmap` (A `available: 0`) → `recall` → `purchase(ms-ams-01, C, 2)`
      → `remember`
- [ ] **one order: `ms-ams-01`, section C, 2 × $95** — *section C after
      sell-out*, never B
- [ ] Watch: `guard stale_plan` passes
- [ ] the breakfast message names the section, the price in dollars, and why;
      `remember` wrote one line
- [ ] Watch: `orders --since-session --section C --qty 2` passes

If it takes B: note it. The instruction forbids B explicitly; if it happens
more than once in five rehearsals the prompt needs tightening, not the guard.

### 5C — its own experiment

- [ ] **Reset the venue** (scope *venue*): orders 0, A back in stock; the 5B
      session is still in the dropdown with its order
- [ ] New session, confirm the budget again (3 messages), park
- [ ] **BREAK THE NEXT PURCHASE**, **SKIP THE WAIT**, **Resume current task**
- [ ] agent log: `[purchase] venue answered 503 — retrying with the same key`
- [ ] venue feed: `ord_… COMMITTED, then failed the response (hang-once)`, then
      `duplicate suppressed — returned ord_…`
- [ ] `✓ purchase`: `attempts: 2`, `duplicate: true`, the **same** `id`
- [ ] panel: **exactly one order** — *one order after retry*
- [ ] Watch: `retry` passes

Time: ___ / 30 min

---

## Chapter 6 · Run It While You Sleep

### 6A

```bash
./use-solution.sh 6
./setup-cloud-state.sh        # once; needs Cloud SQL RUNNABLE
./deploy-agent.sh             # 3–4 min
```

- [ ] `diff -r solutions/step5_buy/concert solutions/step6_cloud/concert` is empty
- [ ] deploy prints `→ state Cloud SQL + gs://…`, `→ push → …/trigger/wake`
      (**not** `/apps/concert/trigger/pubsub`), `→ schedule 0 3 * * *`
- [ ] `curl $AGENT_SERVICE_URL/health` → `"kind": "Workflow"`, sessions host
      `…host=/cloudsql/…`, memory `gs://…/memory`
- [ ] the page loads at the service URL

### 6B

On the cloud page: **New session**, the three messages, banner *waiting in the
queue*. **SKIP THE WAIT**. Then:

```bash
gcloud scheduler jobs run presale-<you> --location=$GOOGLE_CLOUD_REGION
```

- [ ] within seconds the page shows the buyer's message; banner *done · order ord_…*
- [ ] `gcloud run services logs read concert-<you> --region=… --limit=50`:
      `answering queue interrupt queue:wait`, `woken · session web-…`,
      `[check_front] at the front`, `called purchase`
- [ ] `curl $AGENT_SERVICE_URL/task`: `pending: null`, `last_order: ord_…`,
      the authorization you confirmed — *the scheduler job resumed the cloud
      task*, the `web-…` one, not anything local
- [ ] panel: one new order, inside $250
- [ ] **negative path:** new session on the page, start the task, do not answer
      the budget, run the job → logs *waiting for a person to answer*, no order
- [ ] local rehearsal of the same route works: MonsterTix on,
      `python -m monstertix.clock --in 5 --trigger` against a locally parked
      queue wait

### 6C

```bash
./destroy-agent.sh
./destroy-agent.sh --all
./destroy-venue.sh          # only if you are done rehearsing
```

- [ ] output lists removed / already gone / kept, in the order schedule →
      subscription → topic → service (→ Cloud SQL → bucket)
- [ ] `gcloud scheduler jobs list`, `pubsub topics list`, `run services list`,
      `sql instances list`, `storage ls` — none of yours left
- [ ] `.env` no longer has `AGENT_SERVICE_URL` (nor the cloud URIs after `--all`)
- [ ] the service URL returns 404; the local `sessions.db` / `memory/` /
      `artifacts/` are intact — *the clean-up leaves the page, the script output
      and `.env` agreeing about what stopped*

Time: ___ / 15 min

---

## After the run

1. **Which sections needed a nudge?** Anywhere you said "no, read the seat map
   first" is a prompt to fix, not a student mistake to warn about.
2. **Which beat failed to reproduce?** The ones that can silently not happen:
   the picker choosing B, the buyer reading the seat map before its first
   `purchase` (so the refusal is never seen), the hold
   expiring before you resumed in 4B/5B.
3. **Where were you over time?** Write the real minutes next to the budget and
   decide the cuts before the day, not during it.

Nothing to put back. `. ./set_env.sh local` only affected the terminals you
typed it in, and `.env` still points at Cloud Run. `./use-solution.sh 1` to
start where the students will.
