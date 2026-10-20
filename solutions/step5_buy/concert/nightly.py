"""Chapter 5 · Buy Within Agreed Limits — the graph, with a person at the start and a buyer at the end.

Nothing from the last chapter is replaced. It is surrounded:

    START ─► agree_budget ─► open_the_night ─► pick_show ─► queue_up ─► check_front ─► brief ─► buyer_agent
               (function)       (function)      (agent)     (function)   (function)   (function)   (agent)
               asks a PERSON    says what        reads       joins once,  at the front? turns the    reads the
               what they will   tonight is for   memory,     keeps the    no → PAUSE    plan into     seat map
               spend, reads it  and what may     picks the   ticket       yes ↓         a message     again, buys,
               back, stores it  be spent         show                     │                           writes one
               ─ reruns on resume ─              ─ run once ──────────┘   └─ every wake-up re-checks   message

Two kinds of pause, one mechanism. `agree_budget` and `check_front` both
return a `RequestInput`, and the graph parks the same way for both. What
differs is who answers:

    budget:ask, budget:confirm    a person, in the chat. Nothing else may
                                  answer these — a scheduler that fills in a
                                  budget is a scheduler spending your money.

    queue:wait                    anything at all. The panel, the MonsterTix
                                  server, Cloud Scheduler. The answer is just
                                  "look again".

The interrupt ids are stable strings for that reason: whoever wakes the run
can read the prefix and know which kind of wait this is.

What a resume does, per node, is the same as in the last chapter. Nodes that
finished — pick_show, queue_up, and agree_budget once it has stored the
authorization — have an output on record and are replayed from it, whatever
their `rerun_on_resume` says (google/adk/workflow/utils/_replay_interceptor.py,
"Case 4"). The node the resume reaches with its interrupt answered is the one
the flag governs: `rerun_on_resume=True` on agree_budget and check_front makes
that node run again, so it can read the answer or ask the venue again, instead
of having the answer payload handed over as its output. The one gap the
framework cannot close is a crash between a side effect and the node's return —
which is why queue_up reuses a ticket it already holds, and why purchase
carries an idempotency key.

The buyer at the end is the conversational agent, imported from agent.py, with
a guard in front of its purchase tool. It never asks — see the instruction.

Run it by hand:
    python -m concert.nightly

It asks for a budget in the terminal, parks at #14,203, and continues when you
run it again after SKIP THE WAIT.
"""

from __future__ import annotations

import asyncio
import time
import warnings

from google.adk import Event, Runner, Workflow
from google.adk.agents import Agent
from google.adk.agents.context import Context
from google.adk.artifacts import InMemoryArtifactService
from google.adk.events.request_input import RequestInput
from google.adk.sessions import DatabaseSessionService
from google.adk.workflow import START, node
from google.adk.workflow.utils._workflow_hitl_utils import (
    create_request_input_response,
    get_request_input_interrupt_ids,
)
from google.genai import types
from pydantic import BaseModel

from . import budget, memory, venue
from .agent import buyer_agent
from .config import MODEL
from .memory import recall
from .tools import get_seatmap, search_events

warnings.filterwarnings("ignore", message=r".*\[EXPERIMENTAL\].*")

# The interrupt id for the queue wait. Stable on purpose: whoever wakes this
# run — the panel, the MonsterTix server, a scheduler — answers THIS id, and
# can tell from the prefix that it is a queue wait and not a question for a
# person.
QUEUE_WAIT = "queue:wait"

# The two questions for a person. Same mechanism, different prefix — so the
# thing waking the run can refuse to answer these on a person's behalf.
ASK_BUDGET = "budget:ask"
CONFIRM_BUDGET = "budget:confirm"


class Plan(BaseModel):
    """What pick_show decides, and what every node after it works from."""

    event_id: str
    city: str
    section: str
    seats: int
    reason: str


def what_they_asked_for(ctx: Context) -> str:
    """Everything this person typed, joined, in their own words.

    The tempting design is fields — city, party_size, weekends_only — and it
    breaks on the first sentence you did not anticipate. So do not model it.
    Keep the text and let the picker read it.

    Only `text` parts count, which quietly does the right thing: answers to an
    interrupt arrive as function_responses, so they are not echoed back in
    here. What is left is what the person freely said.
    """
    said = []
    for event in (ctx.session.events or []):
        if event.author != "user":
            continue
        for part in (event.content.parts if event.content else []) or []:
            text = (getattr(part, "text", None) or "").strip()
            if text and text not in said:
                said.append(text)
    return "\n".join(said)


# --- node 0: agree the authorization, in the graph, with a real person ----


def _said(answer) -> str:
    """The text of an answer to an interrupt, however it was wrapped.

    The MonsterTix page and the test harness answer with {"result": text};
    `adk web` lets a person type any JSON. Take the obvious keys, else the
    whole thing as a string.
    """
    if isinstance(answer, dict):
        for key in ("result", "text", "message", "answer"):
            if answer.get(key):
                return str(answer[key]).strip()
        return ""
    return str(answer or "").strip()


@node(rerun_on_resume=True)
def agree_budget(node_input, ctx: Context):
    """Stop the run and ask what they will spend. Read it back. Then store it.

    Three things make this work, and you need all three:

      @node(rerun_on_resume=True)
          when the resume reaches this node with an answer, run the node again
          instead of taking the answer as its output. That is how the second
          question gets asked, and how the answer is read and stored.

      a STABLE interrupt_id
          not the random one you get by default. It is the key you look the
          answer up by, so it has to be the same string on the run that asks
          and the run that reads.

      ctx.resume_inputs[interrupt_id]
          where the answer actually arrives. Not the return value of the
          RequestInput — ADK iterates a node rather than sending into it, so
          there is no value coming back that way.

    Two interrupts, not one, and the second is the point. The first answer is
    what somebody said. The second is what they agreed to. Only after the
    second does the authorization go into state with confirmed=True — and the
    guard in fence.py will not let a purchase through without it.

    There is no default and no unattended path. If nobody answers, the run
    stays parked here and nothing is bought. That is the correct outcome.
    """
    answers = ctx.resume_inputs or {}

    # Do this on every run, not just the first. The node reruns on resume, so a
    # correction typed later is picked up here rather than lost.
    ctx.state["request"] = what_they_asked_for(ctx)

    agreed = budget.load(ctx.state)
    if agreed:
        print(f"  [agree_budget] already agreed: {budget.describe(agreed)}")
        return Event(output=agreed)

    said = _said(answers.get(ASK_BUDGET))
    if not said:
        print("  [agree_budget] nothing agreed yet. Asking.")
        return RequestInput(
            interrupt_id=ASK_BUDGET,
            message=(
                "Before I book anything: how many tickets, and the most to pay "
                "for each? For example: \"Two tickets, up to $250 each.\""
            ),
        )

    parsed = budget.parse(said)
    if not parsed:
        # Not a refusal — a request for the shape the guard can check.
        print(f"  [agree_budget] could not read: {said!r}. Asking again.")
        return RequestInput(
            interrupt_id=ASK_BUDGET,
            message=(
                f"I could not read a number of tickets and a per-ticket limit in "
                f"\"{said}\". Say it like: \"Two tickets, up to $250 each.\""
            ),
        )

    reply = _said(answers.get(CONFIRM_BUDGET))
    if not reply:
        print(f"  [agree_budget] reading back: {said}")
        return RequestInput(
            interrupt_id=CONFIRM_BUDGET,
            message=(
                f"So: {parsed['seats']} ticket{'s' if parsed['seats'] != 1 else ''}, "
                f"up to ${parsed['per_seat_max']:g} each. Have I got that right?"
            ),
        )

    if not reply.lower().lstrip().startswith(
        ("yes", "yep", "yeah", "correct", "that's right", "thats right", "confirmed", "right", "ok")
    ):
        # They corrected it rather than agreeing. If the correction parses, it
        # becomes the thing they are agreeing to — they have now said it twice.
        corrected = budget.parse(reply)
        if not corrected:
            print(f"  [agree_budget] not confirmed: {reply!r}. Asking again.")
            return RequestInput(
                interrupt_id=ASK_BUDGET,
                message=(
                    "No problem — say it again, like: \"Two tickets, up to $250 each.\""
                ),
            )
        said, parsed = reply, corrected

    auth = budget.make(said, parsed)
    ctx.state[budget.AUTH_KEY] = auth
    print(f"  [agree_budget] agreed: {budget.describe(auth)}")
    return Event(output=auth)


# --- node 1: say what tonight is for --------------------------------------


@node(rerun_on_resume=False)
def open_the_night(node_input, ctx: Context) -> Event:
    """Give the picker something to answer, and tell it what may be spent.

    Two jobs. An agent node responds to its input, and with no user message
    addressed to it there is nothing to respond to — so this says the sentence
    a person would have said.

    The other job is the authorization. agree_budget put it in state after the
    person confirmed it. That is the join between the two halves of this
    chapter: the limit is agreed by a person while they are awake, and spent by
    a graph while they are not.
    """
    asked = str(ctx.state.get("request") or "").strip() or what_they_asked_for(ctx)
    ctx.state["request"] = asked
    auth = budget.load(ctx.state)
    print(f"  [open]        Nobody is awake. Authorization: {budget.describe(auth)}")
    if asked:
        print(f"  [open]        they asked for: {asked[:70]}")
    return Event(output=(
        "Choose the show and section for this person, and buy nothing yet.\n\n"
        "What they asked for, in their own words:\n\n"
        f"    {asked or '(nothing said this time. Use what recall() tells you.)'}"
        "\n\nThe authorization they confirmed for this task:\n\n"
        f"    {auth['text'] if auth else 'none'}  ({budget.describe(auth)})\n\n"
        "Put that many seats in `seats`, and never choose a section priced "
        "above the per-seat limit. Apply everything recall() tells you about "
        "who comes with them, which days work, and which sections they will "
        "not sit in. If nothing on the tour fits, choose nothing and say so."
    ))


# --- node 2: choose a show. Judgement, so an agent. -----------------------

picker = Agent(
    name="pick_show",
    model=MODEL,
    tools=[recall, search_events, get_seatmap],
    output_schema=Plan,
    instruction="""
Choose one show and one section for this person. Buy nothing.

THERE IS NOBODY THERE. The person is asleep. You cannot ask a question, because
nothing will answer it and the run will simply stop. Never end your turn with a
question. Work through the tools until you have a plan, then return the plan.

Call recall() first. It holds what previous bookings taught you about this
person — who they go with, which days work, which sections they will not sit
in. Those preferences are the whole basis for the choice.

Then search_events. Then get_seatmap for the show you settled on — do not ask
whether to look at it, just look.

The message you were sent says what they asked for, in their words, and the
authorization they confirmed: how many seats, and the most to pay for each.
Put that number of seats in `seats`, and the section must have that many
available right now. A section priced above the per-seat limit is not an
option, however well it fits. A person who can only do weekends has ruled out
every weekday show, even when a cheaper seat exists on a Tuesday.

Return the plan. Put the reason in one sentence, in terms of what you know
about this person — not "section A is the best seats".
""",
)

# Runs once. After it has returned a Plan, every resume replays that Plan from
# the record instead of asking the model again — the flag is not what prevents
# a second pick; the recorded output is. `rerun_on_resume=False` matters only
# if a resume ever reaches THIS node with an interrupt answered, and this node
# never interrupts.
pick_show = node(picker, rerun_on_resume=False)


# --- node 3: get in line. A rule, so a function. --------------------------


@node(rerun_on_resume=False)
def queue_up(node_input, ctx: Context) -> Event:
    """Take a queue ticket. Exactly once, however many times this is woken.

    A second ticket would put you at the back of the line again, forty minutes
    behind where you already were. On an ordinary wake-up this node is safe
    without any help: it finished, its output is on record, and ADK replays
    the record rather than running it. `rerun_on_resume=False` is not what
    protects you here.

    What is NOT covered is a crash between the POST below and this function
    returning — the venue has issued a ticket and nothing was recorded, so the
    next run arrives here again. The guard at the top is for that: if a ticket
    is already in state and the venue still knows it, reuse it. Side effects
    that can be repeated have to be made safe to repeat; the framework
    guarantees at-least-once, not exactly-once.

    The ticket goes two places, and both matter:

      the node output    so check_front can use it. This is how a graph moves
                         data — along an edge.

      session state      queue_ticket, queue_event_id and plan, so anything
                         looking at the session from outside — the MonsterTix
                         page, the workbench — can say what this run is doing
                         without reading the graph.
    """
    plan = Plan(**node_input)
    if not plan.event_id or plan.event_id.lower() in ("none", "null", "no_show", "n/a"):
        print(f"  [queue_up]    no show chosen: {plan.reason}")
        return Event(output={**plan.model_dump(), "ticket": "", "no_show": True})

    # Already holding a ticket for this show? Then a previous attempt got as
    # far as the venue and no further. Keep the place; do not take another.
    held = ctx.state.get("queue_ticket")
    if held and ctx.state.get("queue_event_id") == plan.event_id:
        status = venue.get(f"/queue/{held}")
        if not status.get("error"):
            print(f"  [queue_up]    already holding {held} at #{status.get('position', 0):,} — reusing it")
            ctx.state["plan"] = plan.model_dump()
            return Event(output={**plan.model_dump(), "ticket": held})

    ticket = venue.post("/queue/join", {"event_id": plan.event_id})
    if "ticket" not in ticket:
        raise RuntimeError(
            f"Failed to join queue for event {plan.event_id!r}: {ticket}. "
            "Make sure the venue is running, and press RESET THE VENUE on the panel."
        )
    ctx.state["queue_ticket"] = ticket["ticket"]
    ctx.state["queue_event_id"] = plan.event_id
    ctx.state["plan"] = plan.model_dump()
    # The seat map the plan was chosen from. `temp:seatmap` is gone the moment
    # this invocation pauses, so keep a copy under a plain key: it is what the
    # agent will *believe* when it wakes up, and the guard in front of purchase
    # compares it with the live one.
    if ctx.state.get("temp:seatmap"):
        ctx.state["planned_seatmap"] = ctx.state["temp:seatmap"]
    print(f"  [queue_up]    {plan.event_id} section {plan.section} — "
          f"ticket {ticket['ticket']} at #{ticket['position']:,}")
    return Event(output={**plan.model_dump(), "ticket": ticket["ticket"]})


# --- node 4: the wait, as an interrupt rather than a sleep ----------------


@node(rerun_on_resume=True)
def check_front(node_input, ctx: Context):
    """Are we at the front yet? If not, stop the run and wait to be woken.

    Returning a `RequestInput` suspends the whole graph. Compare that with the
    obvious version:

        while not ready:          # never do this
            time.sleep(1)

    The loop keeps a process alive for forty minutes to achieve nothing, dies
    with the terminal, and cannot be resumed. The interrupt costs nothing, lives
    in the session store, and survives the machine going away.

    `rerun_on_resume=True` is what makes this node run again when the resume
    arrives with its interrupt answered. Without it ADK would take the answer
    payload — "checked: true" — as the node's output and carry on to the next
    node without ever asking the venue. With it, every wake-up asks again, and
    the answer is the one thing that changed while the process was gone.
    """
    if node_input.get("no_show"):
        return Event(output=node_input)

    ticket = node_input.get("ticket") or ctx.state.get("queue_ticket") or ""
    status = venue.get(f"/queue/{ticket}")

    # The ticket can cease to exist. A place at the front is only held for so
    # long, and the venue gives it away — or somebody pressed RESET THE VENUE.
    # Either way the thing you were waiting for is gone, not merely late.
    # Without this the run parks forever on a `ready` that will never come,
    # which looks exactly like patience.
    if status.get("error"):
        print(f"  [check_front] ticket gone: {status.get('message', 'unknown')}")
        return Event(output={**node_input, "ticket": "", "lost": True})

    if not status.get("ready"):
        print(f"  [check_front] #{status.get('position', 0):,} — not yet. Pausing.")
        return RequestInput(
            interrupt_id=QUEUE_WAIT,
            message=f"Still in the queue at #{status.get('position', 0):,}. "
                    "Wake me again and I will check.",
        )
    print("  [check_front] at the front")
    return Event(output=node_input)


# --- node 5: at the front. Turn the plan into the sentence you would have typed.


def brief(node_input, ctx: Context) -> Event:
    """Hand the buyer what it needs: the plan, the authorization, and an order.

    A node hands its output to the next node, and when the next node is an
    agent that output arrives as the message it wakes up to. This is where "go
    ahead and buy them" comes from when nobody is awake to say it.

    The order is "buy the plan", not "check first". That is deliberate. The
    seat map behind the plan is forty minutes old and may well be wrong — but
    the thing that catches that is the guard in fence.py, which re-reads the
    live inventory in the instant before every purchase and refuses with a
    reason if the plan has gone stale. Telling the model to be careful would
    hide the guard: on the nights the model happened to re-read, you would
    never see the refusal, and on the nights it forgot you would have no
    protection at all. So the plan is tried, the guard does its job, and the
    model only goes looking when it is told the world moved.

    It also leaves the same mark chapter 4's last node did — state["ready_to_buy"]
    and state["ready_at"] — so the task card can say "ready to buy" before the
    buyer has said anything.

    A plain function, not a decorated node: it has no side effects beyond that
    mark, and the mark is the same every time, so a repeat is harmless.
    """
    auth = budget.load(ctx.state)
    if node_input.get("lost"):
        return Event(output=(
            "The queue place expired before anything could be bought — the venue "
            "only holds the front of the line for so long. Tell me that in one or "
            "two sentences, as a message I will read over breakfast. Buy nothing."
        ))

    if node_input.get("no_show") or str(node_input.get("event_id", "")).lower() in ("none", "null", "no_show", "n/a"):
        reason = node_input.get("reason", "No show on the tour fits.")
        return Event(output=(
            f"No show could be booked. Reason: {reason}\n\n"
            "Tell me that in one or two sentences, as a message I will read over "
            "breakfast. Buy nothing."
        ))

    plan = Plan(**{k: v for k, v in node_input.items()
                   if k not in ("ticket", "lost", "no_show")})
    ctx.state["ready_to_buy"] = True
    ctx.state["ready_at"] = time.strftime("%H:%M:%S")
    return Event(output=(
        f"You are at the front of the queue for {plan.event_id} in {plan.city}. "
        f"The plan, agreed before the wait: {plan.seats} seats in section "
        f"{plan.section}, chosen because: {plan.reason}\n\n"
        "The authorization this person confirmed for this task, in their words:\n\n"
        f"    {auth['text'] if auth else 'NONE — nobody confirmed a budget. Buy nothing.'}"
        f"\n    ({budget.describe(auth)})\n\n"
        f"Act on the plan: call purchase for {plan.seats} seats in section "
        f"{plan.section} of {plan.event_id} now, without reading the seat map "
        "first. The guard in front of purchase re-checks live inventory and the "
        "authorization for you. Only if it refuses — the seat map is forty "
        "minutes old and the world may have moved — read the seat map again and "
        "pick the best remaining section that fits the authorization and what "
        "you know about this person, or buy nothing. Then write me one short "
        "message I will read over breakfast saying what you got and what it "
        "cost. Prices are in US dollars."
    ))


# The last node is `buyer_agent` itself: the agent from agent.py, imported and
# not rebuilt. Its tools, its before_tool_callback, its idempotency key — all
# of it comes along, because there is only one of it.

nightly = Workflow(
    name="concert_nightly",
    description="The presale run: agree the limit, choose, queue, wait, buy within it.",
    edges=[(START, agree_budget, open_the_night, pick_show, queue_up,
            check_front, brief, buyer_agent)],
)


# --- running it from a terminal -------------------------------------------


def pending_interrupt(session) -> str | None:
    """The interrupt id this session is parked on, if any."""
    for event in reversed(session.events or []):
        ids = get_request_input_interrupt_ids(event)
        if ids:
            return ids[0]
    return None


async def main() -> None:
    """Run the graph once and stop wherever it gets to.

    There is deliberately no loop here. If the queue is not ready this exits
    with the run parked in `nightly.db`, and nothing is running until something
    outside calls it again. That something is you, for now. Later it is a
    server, and later still Cloud Scheduler — and nothing in here changes.
    """
    session_service = DatabaseSessionService(db_url="sqlite+aiosqlite:///nightly.db")
    ids = dict(app_name="concert", user_id="user", session_id="tonight")
    if not await session_service.get_session(**ids):
        await session_service.create_session(**ids)
    runner = Runner(
        node=nightly,
        app_name="concert",
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
        memory_service=memory.memory_service,
    )

    # A parked run is resumed by answering its interrupt, not by sending a new
    # message — a plain message starts a fresh invocation and replays the graph.
    session = await session_service.get_session(**ids)
    pending = pending_interrupt(session)

    message = None
    if pending and pending.startswith("queue:"):
        print("=== waking a run that was parked in the queue ===")
        message = types.Content(
            role="user",
            parts=[create_request_input_response(pending, {"checked": True})],
        )
    elif pending:
        answer = input(f"  [{pending}] the run is waiting for you. Your answer: ").strip()
        message = types.Content(
            role="user",
            parts=[create_request_input_response(pending, {"result": answer})],
        )
    else:
        print("=== presale run — nobody is awake ===")

    parked = False
    async for event in runner.run_async(new_message=message, **{
        k: v for k, v in ids.items() if k != "app_name"
    }):
        if get_request_input_interrupt_ids(event):
            parked = True
        for part in (event.content.parts if getattr(event, "content", None) else []) or []:
            if getattr(part, "function_call", None) and part.function_call.name != "adk_request_input":
                print(f"  [agent]       calls {part.function_call.name}")
            elif getattr(part, "text", None) and part.text.strip():
                print(f"\n📱 {part.text.strip()}\n")

    if parked:
        print("\n  Parked. Nothing is running.")
        print("  If it is waiting in the queue: press SKIP THE WAIT on the panel.")
        print("  If it is waiting for you: it will ask when you run this again.")
        print("      python -m concert.nightly\n")
    else:
        print("=== done ===")


if __name__ == "__main__":
    asyncio.run(main())
