# Writing the workbench's steps

Every page of the workbench comes from this folder. The server re-reads it on
each request, so an edit shows on reload; nothing needs rebuilding.

```
content/
  course.yaml                  title, credit
  steps/
    04-resume/                 NN-slug: NN is the order, slug is the URL
      step.yaml                meta, parts, exercises, checks
      a-pause.md               one part's reading
      b-restart.md
  images/                      served at /content-images/
```

The codelab's own figures in `docs/img/` are served at `/docs-img/`, so a step
uses them without a copy: `:::figure src="/docs-img/06-02-intro.png"`.

## step.yaml

```yaml
title: Pause, Restart, Resume
kicker: Chapter 4            # default "Chapter N"; the appendix says "Reference"
minutes: 25
color: amber            # cyan, purple, blue, amber, green, red, lime, teal
venue: true             # optional: the live venue panel in a left column (chapter 1)
stage: 4                # the solution stage this page's code is: chapters and stages are 1:1
appendix: true          # optional: listed after the chapters as "Reference", not counted as one
summary: One or two sentences under the title.
parts:
  - id: a
    label: Pause                        # the chip in the top bar
    headline: Turn waiting into a pause # the page title for this part
    body: a-pause.md
    exercises:                          # placed in the reading with :::exercise id="code"
      code:
        title: …
        intro: …
        tasks: [ … ]
    expect: [ … ]                       # "What you should see": top of the verify card
    checks: [ … ]                       # the Watch panel at the end of the part
    checksTitle: Watch                  # optional
```

### Chapters, sections, reference

The top bar numbers the steps that are not `appendix: true` as chapters 1…N,
in folder order, and lists an appendix after them as **Reference**. Parts are
the sections (`4a`, `4b`…). The old nine step slugs still resolve: `story`,
`asleep`, `trigger`, `context`, `compaction`, `resumption`, `workflow`,
`human` and `cloud` redirect to the section that teaches the same thing
(`meet/a`, `wake/a`, `wake/b`, `remember/a`, `remember/c`, `resume/a`,
`resume/a`, `buy/a`, `cloud/a`), so keep those slugs for the new folders.
Next/Previous only navigates; a section is never marked done by reading it.

### Tasks

**prepare** loads a stage's code: stops the agent, presses RESET THE VENUE,
runs `./use-solution.sh N --force`, starts the agent again. `N` is the
chapter number.

```yaml
- kind: prepare
  id: prepare
  step: 4
```

With `scope: venue` the same card only resets the venue (orders, queue,
inventory). No code is copied, no process is stopped, sessions.db and the
memory file stay, so the task under way keeps its session, ticket and
authorization. The page says so: *Reset the venue (orders, queue, inventory).
Code, sessions and memory stay.* Use it where an experiment needs a clean
venue but the same task (chapter 5's retry).

```yaml
- kind: prepare
  id: prepare
  step: 5
  scope: venue
```

**files** is the file explorer. `stage`/`compare` mark files that step `stage`
adds (NEW) or changes (CHANGED) relative to step `compare`, with a bar beside
each changed line. `highlight` is a regular expression; matching lines are
tinted, and `highlightLabel` says in one sentence what they do. Mark the lines
that carry the idea, not every changed line.

```yaml
- kind: files
  id: files
  open: agent/concert/agent.py        # shown first
  stage: 6
  compare: 5
  only: [agent/concert/]              # default: agent/ and monstertix/
  highlight: 'LongRunningFunctionTool|ResumabilityConfig'
  highlightLabel: '`join_queue` is wrapped in …'
```

**turn** is the numbered list of things the student does. Each item has a
`text` (optional) and at most one action:

| Key | What the item shows |
|---|---|
| `say: "…"` + `in: agent` | a message to type, with a copy button that also brings that app forward |
| `answer: "…"` + `in: agent` | the same, for an `adk_request_input` event box (the page warns it is not the main chat box) |
| `press: SELL THE GOOD SEATS` + `venue: sellout` + `body: {…}` | a venue panel button: the same POST to `/admin/<venue>` |
| `service: agent` + `action: kill` | start, stop, restart or kill a service: `venue`, `agent`, `monstertix`, `clock` |
| `look: venue` | a button that brings `venue`, `agent` or `monstertix` forward |
| `run: ./show-compaction.sh` | runs a command from the repo root and shows its output |
| `clock: {in: 10, every: 0}` | starts `python -m monstertix.clock` with those arguments; `trigger: true` adds `--trigger` (posts to `/trigger/wake`, chapter 6's rehearsal) |
| `resume: task` | the **Resume current task** button: answers the current session's queue wait (see `:::task`) |
| only `text` | an instruction with no button |

The apps an exercise uses are framed right under its card, in tabs: every
`in:` and `look:` app, and the venue panel when there is a `press:`. To name
them yourself, give the exercise `apps: [agent, venue]`. Each app's card has
its process's switch, log, and (for the agent) kill -9 and Restart at its top
right. The venue starts with the workbench and is always on. The clock has no
app; a `clock:` item shows its switch and log beside the button.

Venue buttons (`venue:`): `reset`, `advance-queue` (SKIP THE WAIT), `sellout`
(body `{city, section}`), `hang-once` (BREAK THE NEXT PURCHASE), `clock`
(body `{multiplier}`).

### What you should see

`expect:` on a part is a short list of what the ADK web UI and the venue panel
should show once the student has done the "Your turn". It opens the verify card
at the end of the part, above the checks. Describe the screen in words (event
names, State keys, the panel's banner) rather than adding a screenshot after
the card.

```yaml
expect:
  - "After the restart: `⚡ check_queue` with the same `q_…` ticket, and a lower position."
```

### Checks

A check runs a read-only command and passes when it exits 0. The page shows
the command under "how", so it should be one a student could run.

```yaml
- id: saturday
  label: It queued for the Saturday show
  probe: python3 -m workbench.probe tool join_queue
  contains: ms-ams-01                 # optional: the output must also contain this
  hint: shown while the check has not passed
  expect: fail                        # optional: see below
  note: shown when an `expect: fail` row has happened
```

`expect: fail` marks a failure the step is built to show (chapter 2's agent that
never wakes). Write the probe so it passes when the
failure is observed; the row turns amber with an "expected" tag rather than
green.

Probes may only run `python3 -m workbench.probe …` or a reading `curl`.
`python -m workbench.probe --help` lists the questions it answers: `tool`,
`response`, `state`, `memory`, `artifacts`, `compaction`, `orders`, `queue`,
`tickets`, `killed`, `wake`, `session`, `pending`, `nodes`, `file`, `url`,
`turns`, `prompts`, `setting`, and the task questions `task`,
`authorization`, `guard`, `retry`, `resumed`.
`$VENUE_URL`, `$WORKSHOP`, `$PROJECT` and `$REGION` are filled in.

#### This session only

The course is one task, but a student may start it more than once, and an
old session must never pass a check for a new experiment. Scope a check to
the **current session** (the newest one, by its latest event; the seeded
`two-days-ago` conversation never counts):

| Probe | Looks at |
|---|---|
| `tool NAME --current`, `response NAME --current`, `state KEY --current`, `nodes A B --current`, `pending --current` | the newest session's events only |
| `orders --since-session [--count N] [--section C] [--qty N]` | venue orders created after the newest session's first event |
| `task [--kind queue\|person\|none] [--ready] [--ticket]` | the current task: paused on the queue, on a person (`budget:*`), or not paused; `ready_to_buy`; a `queue_ticket` |
| `authorization [--confirmed]` | the session's `authorization` state (`{text, seats, per_seat_max, confirmed, confirmed_at}`) |
| `guard REASON` | the last `purchase` response in the session carries `"reason": "REASON"` (`no_authorization`, `wrong_seat_count`, `over_authorization`, `stale_plan`, `price_moved`) |
| `retry` | the last `purchase` response has `attempts >= 2`, and the venue has exactly one order since the session started |
| `resumed` | the session has ≥ 2 invocations, one `queue_ticket`, and the venue logged one `joined` since the session started |
| `wake --trigger` | the clock's log shows a `POST /trigger/wake` that was answered (chapter 6's local rehearsal) |

Rows that use any of these show a small *this session only* tag in the Watch
panel, so the student knows an earlier run is not being counted.

```yaml
- id: once
  label: It did not join the queue a second time
  probe: python3 -m workbench.probe resumed
- id: stale
  label: The guard refused the old plan
  probe: python3 -m workbench.probe guard stale_plan
- id: order
  label: One order, in section C, for this task
  probe: python3 -m workbench.probe orders --since-session --count 1 --section C
```

## The reading (.md)

Markdown, plus these blocks:

```
:::section kicker="Look on disk" headline="Where the ticket was"
…a card…
:::

:::key            the one sentence to remember
:::note           a developer's note
:::warn           a caution

:::figure src="/docs-img/06-02-intro.png" caption="…"
:::

:::file path="agent/concert/fence.py" label="Show fence.py"
:::

:::app tab="venue"         an app framed in the reading; tab="agent venue" for two
:::

:::exercise id="run"
Anything written in here is shown inside the "Your turn" card, under its
tasks: the walkthrough of the code its file explorer opens.
:::

:::code path="agent/concert/tools.py" highlight="^def note_companion"
:::

:::columns
one
---
two
:::

:::task                    the current task card (below)
:::

:::optional title="Compaction by hand" minutes=10 needs="a session with 20+ turns"
Collapsed until opened. Markdown and any block in here.
:::

:::checkpoint
**Why does a persisted session not resume a paused run by itself?**
:::answer
Collapsed behind "Reveal". Write the answer here.
:::
:::
```

### The task card

`:::task` (with no `id`) is the **current task**, read from the session store
every three seconds and never remembered by the page: the session (short id,
how many runs, which store), *Paused on: the queue / you / —*, the queue
ticket and show, the authorization as `budget.describe` words it, *ready to
buy*, and the last order. Its **Resume current task** button answers the
session's queue wait (`queue:wait`) with `{"checked": true}` through
`adk web`'s `POST /run`, or MonsterTix's `POST /wake` when adk web is off,
so the run continues in the same session with the same ticket. When the
task is waiting on a person (`budget:ask`, `budget:confirm`) the button is
disabled and says so: a person answers in the chat. The same button goes in
a numbered list as a turn item, `resume: task`.

`:::task id="files"` inside an `:::exercise` is unchanged: it places that
card's task in the reading.

### Optional and checkpoint

`:::optional` is off the main line: a collapsed card with `title`,
`minutes` (how long it takes) and `needs` (what it assumes is in place).
Skipping it costs nothing. `:::checkpoint` is the question that ends a
section; write the question in bold as its first line, and put the answer
inside an `:::answer` block, which is collapsed behind **Reveal** so the
student predicts first. A `title="…"` on `:::checkpoint` replaces the
"Checkpoint" kicker.

### Code

`:::code` shows a project file, never a pasted copy. A page has one file
explorer: the "Your turn" card's own if the page has one, otherwise the first
`:::code`. Every other `:::code` on the page is a button that opens its file
there and scrolls to it; `button="false"` only adds its lines to the
highlights. Explorers with a `stage` read that step's solution folder, so the
code is right before the student loads the step. `highlight` is a regular
expression; write a double quote inside it as `\x22`.

## Translations

English is the source. A translation sits next to it, one file at a time, and
anything not yet translated falls back to English:

```
04-resume/
  step.yaml          English
  step.es.yaml       only the strings that differ in Spanish
  a-pause.md
  a-pause.es.md
course.es.yaml
```

A `step.<lang>.yaml` is merged over the English one: maps key by key, lists
of maps by `id` (by position for `turn` items, which have none). Leave out
`probe`, `run`, `venue`, `open`, `highlight` and other non-prose keys; the
English values are kept. A language appears in the page's language menu as
soon as one file exists for it.

The interface's own words are in `web/src/i18n/en.json`, rebuilt from the code
by `node web/scripts/i18n.mjs`. To translate them, copy it to `es.json`,
translate the values, and register it in `web/src/i18n/index.tsx`.

## Style

Write for the student at the keyboard: what to do, what they will see, why it
matters. End each sentence on the fact; no summarising clause after the point.
