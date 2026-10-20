"""Chapter 5 · Buy Within Agreed Limits — the graph gets a buyer, and a guard.

The run from the last chapter reached the front of the queue and stopped. Now
the last node buys. Which is when three things need to be true at once:

    AUTHORITY   The person confirmed "two tickets, up to $250 each" for THIS
                task, before the run joined the queue. Not a preference from
                memory — permission, with numbers, for tonight. agree_budget
                in nightly.py asks for it; budget.py keeps it.

    THE WORLD   The seat map behind the plan is forty minutes old. The buyer
                is told to act on the plan anyway — and before_tool_callback=
                refresh_before_purchase (fence.py) checks the live price and
                stock in the instant before money moves. If the plan has gone
                stale the purchase is refused with a reason, and only then does
                the buyer look again. The guard is the check, not the model's
                caution: a model that "remembers to re-read" is a model that
                sometimes forgets, and a guard in code never does.

    ONCE        The order commits, the response never arrives, and something
                retries. purchase carries an Idempotency-Key derived from the
                session and the request, so the retry gets the original order
                back instead of a second one. Press BREAK THE NEXT PURCHASE on
                the panel to watch it.

The buyer below is the conversational agent from the early chapters with a
narrower job and a narrower tool list. It is the LAST node of the graph, and
nobody is there when it runs — so it never asks.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.apps.app import App, EventsCompactionConfig, ResumabilityConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.google_llm import Gemini

from .config import MODEL
from .fence import refresh_before_purchase
from .memory import recall, remember
from .panel import PanelPlugin
from .tools import get_seatmap, purchase

INSTRUCTION = """
You are the last step of a run that started while this person was asleep. The
graph has already agreed a budget with them, chosen the show, joined the queue
and waited. You have been woken because you are at the front of the line.

There is NOBODY THERE. Never ask a question — not about the budget, not about
which section, not to confirm anything. A question here stops the whole run and
nothing is ever bought.

The message you were sent has the plan — which show, which section, how many
seats — and the authorization, in the person's own words: how many seats, and
the most to pay for each. That authorization is the limit. It was given for this
task.

Do this, in this order:

  1. Act on the plan. Call purchase with exactly the planned show, the planned
     section and the planned number of seats. Do NOT read the seat map first:
     the plan was agreed, and a guard in front of purchase re-checks the live
     inventory and the authorization for you in the instant before money
     moves. If the plan still holds, you are done buying.

  2. If — and only if — that purchase comes back refused with a reason
     (stale_plan, over_authorization, price_moved), the world moved while you
     waited. Now read the seat map again with get_seatmap, and call recall() if
     you have not yet seen what this person is like. It holds what past
     bookings taught you — including the sections they refuse to sit in. For
     this person the upper bowl (section B at Ziggo Dome) is never an option,
     however cheap it is.

  3. Pick the best remaining section that has enough seats, is at or under the
     per-seat limit, and that this person would actually sit in. Compare the
     price to the limit before you call purchase again. If there is no such
     section, buy nothing and say so. A refusal with a reason is not a bug, it
     is the answer — read the reason and act on it, never argue with it.

  4. Write ONE short message they will read over breakfast: what you got, what
     it cost, and why that section. Prices are in US dollars. If you bought
     nothing, say plainly what stopped you.

  5. Call remember() with the outcome, in one sentence that will still make
     sense months from now.

Be concrete and brief.
"""

buyer_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,
    # Runs in the instant before any purchase reaches the venue. See fence.py.
    before_tool_callback=refresh_before_purchase,
    tools=[get_seatmap, recall, remember, purchase],
)


# THE ROOT IS THE GRAPH — and the budget conversation happens inside it.
#
# The graph took charge because nobody was typing at 3am. That does not mean
# nobody CAN type: `agree_budget` stops the run and asks a real person a real
# question, using the same interrupt that makes the queue wait free. And
# `buyer_agent` above is the last node.
from .nightly import nightly                              # noqa: E402

root_agent = nightly

app = App(
    name="concert",
    root_agent=nightly,
    plugins=[PanelPlugin()],
    resumability_config=ResumabilityConfig(is_resumable=True),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1,
        # Required once the root is a Workflow. ADK normally borrows the
        # summariser's model from the root agent, and a graph has no model —
        # `No LlmAgent model available for event compaction summarizer.`
        summarizer=LlmEventSummarizer(llm=Gemini(model=MODEL)),
    ),
)
