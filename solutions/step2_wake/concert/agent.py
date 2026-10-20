"""Chapter 2 · Wake the Agent — a prompt cannot start a run.

Same agent as before. It plans the Amsterdam trip beautifully, and at 10:00 on
Tuesday, when the presale opens, this file does nothing at all — because
nothing calls it.

The optional prompt experiment tries telling it not to sleep. That is what
the second instruction below is for; the main path leaves it unused. No new
invocation starts just because you change the wording. Not because the
wording is bad — because no wording can invoke a function. An instruction is
text the model reads at the moment something sends it a message, and it says
nothing about who sends one.

The real fix is a caller: a clock that POSTs to the MonsterTix server, which
hands the message to a Runner, which runs this agent. The agent does not
change. What changes is who starts it.
"""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.apps.app import App

from .config import MODEL
from .memory import recall
from .panel import PanelPlugin
from .tools import get_seatmap, search_events

INSTRUCTION = """
You help someone plan a trip to see a band on tour.

Before recommending anything, call recall() to read what you already know about
this person from past bookings. It is not in this conversation. Apply it: who
they go with, which days work, which sections they will not sit in.

You can search tour dates and read seat maps. Be concrete: name the show, the
city, the date, the section, and the price in US dollars.

Keep answers short. Two or three sentences unless asked for more.
"""

# ── The prompt lab ───────────────────────────────────────────────────────
# Optional: use the editable text box in "Try rewriting the instruction".
# Its "Swap it in" button changes root_agent and restarts the agent for you.
# The code viewer is read-only. The main path keeps INSTRUCTION unchanged.
# "Monitor", "watch", "act on your own" describe behaviour the model has no
# mechanism to perform. It is worth failing at this yourself once.

PROACTIVE_INSTRUCTION = """
You are a proactive ticket assistant.

Monitor the presale for The Midnight Signal. The moment it opens, check whether
the Amsterdam Saturday show still has seats and tell me — do not wait to be
asked, and do not wait for me to say anything. Act on your own.

Keep checking until you have an answer.
"""

root_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,           # Main path: leave this unchanged.
    tools=[search_events, get_seatmap, recall],
)

# `adk web` looks for `app` before `root_agent`. The plugin narrates every tool
# call to the venue's activity feed, so the room can watch the agent work.
app = App(
    name="concert",
    root_agent=root_agent,
    plugins=[PanelPlugin()],
)
