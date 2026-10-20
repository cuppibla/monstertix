"""Chapter 4 · Pause, Restart, Resume — the wait becomes a pause.

The task has four parts, and they are not all the same kind of work:

    START ─► open_the_night ─► pick_show ─► queue_up ─► check_front ─► ready_to_buy
               (function)       (agent)     (function)   (function)     (function)
               says what        reads       joins once,   at the front?  says so, and
               tonight is for   memory,     keeps the     no → PAUSE     stops. Nothing
                                picks the   ticket        yes ↓          is bought here.
                                show                      │
               ─ run once ──────────────────────────┘     └─ every wake-up re-checks

One node is an agent, because choosing a show is judgement: which night Sam
can make, which section this person refuses to sit in. The rest are functions,
because joining a queue and asking "am I at the front yet" are rules, and a
rule should not be a coin flip at 3am.

WHAT HAPPENS WHEN IT IS NOT AT THE FRONT

`check_front` returns a `RequestInput`. That is ADK's interrupt: the graph stops
where it stands and the invocation is written to the session store. Nothing
loops, nothing sleeps, nothing holds a connection open. The process can die.

Waking it up does not start over. What actually happens, per node:

    open_the_night, pick_show, queue_up
        finished, with an output on record. ADK replays them from that record
        and never calls them again — whatever their `rerun_on_resume` says.
        So the agent does not pick a second show and you do not take a second
        ticket. (google/adk/workflow/utils/_replay_interceptor.py, "Case 4".)

    check_front   @node(rerun_on_resume=True)
        the node the resume reaches, with its interrupt answered. The flag
        decides what happens here: True runs the node again, so it asks the
        venue where you are now; False would hand it the answer payload as its
        output and move on without looking. Asking again is the whole point.

So the run ends in exactly one place: at the front of the queue, ready to buy.
It might take several wake-ups to get there, and it costs nothing in between.
The buying is the next chapter.

One gap remains, and it is not the framework's to close. A node's output is
recorded when the node returns. If the process dies between the venue POST and
that return, the POST happened and the record did not, and the next run calls
the node again. That window is why `queue_up` reuses a ticket it already
holds, and why a purchase carries an idempotency key.

Run it by hand:
    python -m concert.nightly

It will stop at #14,203. Press SKIP THE WAIT on the panel and run it again.
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

from . import memory, venue
from .config import MODEL
from .memory import recall
from .tools import get_seatmap, search_events

warnings.filterwarnings("ignore", message=r".*\[EXPERIMENTAL\].*")

# The interrupt id for the queue wait. Stable on purpose: whoever wakes this
# run — the panel, the MonsterTix server, a scheduler — answers THIS id, and
# can tell from the prefix that it is a queue wait and not a question for a
# person.
QUEUE_WAIT = "queue:wait"


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


# --- node 1: say what tonight is for --------------------------------------


@node(rerun_on_resume=False)
def open_the_night(node_input, ctx: Context) -> Event:
    """Give the picker something to answer.

    An agent node responds to its input, and first in the graph with no user
    message there is nothing to respond to — so this says the sentence a person
    would have said. What they typed is kept in state["request"], so every
    later node and every wake-up can read the same words.
    """
    asked = str(ctx.state.get("request") or "").strip() or what_they_asked_for(ctx)
    ctx.state["request"] = asked
    print("  [open]        Nobody is awake. Choosing the show.")
    if asked:
        print(f"  [open]        they asked for: {asked[:70]}")
    return Event(output=(
        "Choose the show and section for this person, and buy nothing.\n\n"
        "What they asked for, in their own words:\n\n"
        f"    {asked or '(nothing said this time. Use what recall() tells you.)'}"
        "\n\nApply everything recall() tells you about who comes with them, "
        "which days work, and which sections they will not sit in. If nothing "
        "on the tour fits, choose nothing and say so."
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

The message you were sent says what they asked for, in their words. The city
and the days are in there, and so is who is coming. Two people means two
seats: put 2 in `seats`, and the section must have that many available right
now. A person who can only do weekends has ruled out every weekday show, even
when a cheaper seat exists on a Tuesday.

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


# --- node 5: at the front. Say so, and stop. ------------------------------


@node(rerun_on_resume=False)
def ready_to_buy(node_input, ctx: Context) -> Event:
    """The end of this chapter: the run reached the front of the queue.

    Nothing is bought. The point of this chapter is that a run which was
    killed, restarted and woken is still the SAME run — same ticket, same
    plan, same place in the line. Buying is the next chapter's job, and it
    plugs in exactly here.
    """
    if node_input.get("lost"):
        print("  [ready]       the queue place was lost. Nothing to do.")
        return Event(output=(
            "The queue place expired before we reached the front — the venue "
            "only holds a ticket for so long. Start a new run to try again."
        ))
    if node_input.get("no_show"):
        return Event(output=f"No show was chosen: {node_input.get('reason', '')}")

    ctx.state["ready_to_buy"] = True
    ctx.state["ready_at"] = time.strftime("%H:%M:%S")
    print(f"  [ready]       at the front for {node_input.get('event_id')}. Ready to buy.")
    return Event(output=(
        f"At the front of the queue for {node_input.get('event_id')} in "
        f"{node_input.get('city')}: {node_input.get('seats')} seats in section "
        f"{node_input.get('section')}. Ready to buy. Nothing is bought in this chapter."
    ))


nightly = Workflow(
    name="concert_nightly",
    description="The unattended presale run: choose, queue, wait, reach the front.",
    edges=[(START, open_the_night, pick_show, queue_up, check_front, ready_to_buy)],
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
        print("  Press SKIP THE WAIT on the panel, then run this again:")
        print("      python -m concert.nightly\n")
    else:
        print("=== done ===")


if __name__ == "__main__":
    asyncio.run(main())
