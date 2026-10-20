Everything in this course happens in three places, and they are in the same
place on every page. The column on the **left** is the world: the ticket
seller and, from Chapter 2, your own MonsterTix page. The reading you are in
now is the learning area. The **ADK web UI** button at the top right opens the
development window, in a drawer over the reading. Before the agent does
anything, make sure you know which of them you are looking at, and which
button changes what.

## The world, on the left

Two tabs, and both are the real thing, not a picture of it:

| Tab | What it is | Port |
|---|---|---|
| **Venue panel** | the ticket seller: shows, seats, the queue, orders, and a feed of what the agent is doing to it. Always on | :8080 |
| **MonsterTix** | your own server and page, the surface a person would actually use. Off until Chapter 2; its switch and log are on the tab | :8090 |

‹ folds the column away; › brings it back. A "Your turn" button that says
*Show Venue panel* or *Copy · go to MonsterTix* switches to that tab for you.

## The ADK web UI, in a drawer

Chat, **Events**, **State**, the agent graph: the development window into a
run. You would never ship it, and it is not part of the world, so it is not on
the left. **ADK web UI** at the top right opens it over the reading; Esc or ×
closes it, and the conversation is still there when you open it again. At the
top of the drawer: the process **switch**, **log**, **Restart** and
**kill -9**. The word next to the switch is the process state: *running*,
*stopped*, *killed*; the dot on the button shows the same thing on every page.

## Four buttons that are not the same thing

You will press all four of these before the day ends. They are easy to mix up,
and mixing them up destroys an experiment.

| Button | What it does | What survives |
|---|---|---|
| **Load step N** (the bar in a "Your turn" card) | stops the agent, presses RESET THE VENUE, copies chapter N's code into `agent/` and `monstertix/`, starts the agent | sessions.db, the memory file, artifacts |
| **Restart** (ADK web UI drawer) | stops and starts the `adk web` process. Nothing on disk changes | everything: sessions, state, tickets, the venue |
| **Resume current task** (Chapter 4 on) | answers a paused run's queue wait, in the same session, with the same ticket. Starts nothing new | the task continues where it stopped |
| **RESET THE VENUE** (venue panel) | the venue forgets orders, tickets and inventory changes. 8 shows, all seats, clock at 1× | the agent side: sessions, state, memory |

A **new session** in the ADK web UI is a fifth thing: a fresh conversation
with empty session state. It does not delete the old one. Chapter 3 is about
what that means.

:::note
Loading a step is deliberate about what it keeps. It never deletes
`sessions.db` or `memory/userx.md`, so a task you started in one chapter is
still there in the next. When you do want a clean slate on the agent side,
MonsterTix's **Wipe everything** (Chapter 2) is the button that does it, and it
asks first.
:::

## Code viewer and Watch

Every section has one **code viewer**. It shows the project's files, not a
pasted copy: **NEW** and **CHANGED** badges mark what this chapter added
relative to the one before, and tinted lines are the ones that carry the idea.
A "Key code" button in the reading opens its file in that viewer and scrolls
to the lines. The viewer reads this chapter's solution folder until you load
the step, so the code is right even before you press Load.

**Watch**, at the end of every section, runs read-only checks: the session
store, the memory file, the venue's public state, the service logs. Each row
shows the command under **how**. Rows marked *this session only* count only
the newest session, so an earlier run of the same experiment cannot pass a
check for you. An amber row tagged *expected* is a failure the section was
built to show.

Next and Previous only turn pages. Nothing is marked done by reading it; the
chip in the top bar counts checks passed.

:::exercise id="check"
:::

:::note
If a check stays red, read its **hint** first: it says whether the result is
the experiment's own outcome or an environment fault, and what to press.
The full install, with every failure mode, is in `docs/PRE-WORK.md`.
:::

## Key code

The code viewer above opened `agent/concert/agent.py`. The agent is the bottom
of the file:

:::code path="agent/concert/agent.py" highlight="^root_agent = Agent\(|^    (name|model|instruction|tools)="
:::

A name, a model, an instruction, and a list of three Python functions. That is
all an `Agent` is. `adk web` found it because the file is called `agent.py`
and the variable is called `root_agent`; the `App` under it is how the agent
narrates its tool calls to the venue's activity feed. You read the rest of it
in Chapter 2, when you need it.

:::checkpoint
**You press Restart in the ADK web UI drawer, then RESET THE VENUE. Which of these
are gone: the chat you had in the ADK web UI, a queue ticket the agent held,
an order on the panel, the memory file?**
:::answer
Only the venue side is gone: the queue ticket and the order. Restart stops and
starts a process; `sessions.db` is a file on disk and the chat is still in it
(the ADK web UI reopens the last session after a restart). RESET THE VENUE
touches the venue's own database and nothing else, so the memory file and the
session are untouched. The ticket is the interesting case: the agent's session
still *remembers* a ticket number that the venue no longer has. Chapter 4
builds the mechanism that handles exactly that.
:::
:::
