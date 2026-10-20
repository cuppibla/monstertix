"""Chapter 3 · Remember What Matters — four places a fact can live.

Same agent, and now it writes to four different places. Go and find each one:

    State tab      user:prefs           survives every session for this user
                   temp:seatmap         survives nothing past this invocation
    Artifacts tab  seatmap_*.json       a file, never enters the prompt
    memory/*.md    past bookings        not in this session at all

Then there is the transcript itself. App(events_compaction_config=...) turns on
what every runtime now does: once enough turns have gone by, older events are
replaced with an LLM summary. Summaries keep the gist and drop the exceptions,
and "Sam bails on weeknights" is an exception.

The fix is not "compact less". It is to stop leaving load-bearing facts in the
transcript at all: note_companion writes to user:prefs, remember() writes to
the memory file, and neither is something a summarizer can paraphrase away.

NOTE ON THE INTERVAL: compaction_interval counts user-initiated invocations,
not raw events. 3 is tuned for a workshop, so it fires within a few turns.
Production values are much larger — or use token_threshold instead.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.google_llm import Gemini

from .config import MODEL
from .memory import recall, remember
from .panel import PanelPlugin
from .tools import get_seatmap, note_companion, search_events

INSTRUCTION = """
You help someone plan a trip to see a band on tour.

Before recommending anything, call recall() to read what you already know about
this person from past bookings. It is not in this conversation. Apply it: who
they go with, which days work, which sections they will not sit in.

Use note_companion when someone mentions who is coming and what limits them —
that fact needs to outlive this chat. Use remember() for preferences and
outcomes that should still be true months from now, never for prices or
availability.

You can search tour dates and read seat maps. Be concrete: name the show, the
city, the date, the section, and the price in US dollars.

Keep answers short. Two or three sentences unless asked for more.
"""

root_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,
    tools=[search_events, get_seatmap, recall, note_companion, remember],
)

# `adk web` looks for `app` before `root_agent`, so this is what actually runs.
app = App(
    name="concert",
    root_agent=root_agent,
    plugins=[PanelPlugin()],
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1,
        # Name the summariser's model explicitly. ADK can borrow it from an
        # LlmAgent root, but a later chapter makes the root a Workflow, which
        # has no model — so say it here once and it keeps working.
        summarizer=LlmEventSummarizer(llm=Gemini(model=MODEL)),
    ),
)
