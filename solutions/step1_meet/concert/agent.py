"""Chapter 1 · Meet MonsterTix — a good agent that only runs when someone types.

The task for the whole course is one sentence:

    Get two tickets to The Midnight Signal in Amsterdam, for me and Sam.
    Weekend only, no upper bowl.

This agent can already do the planning half. It searches the tour, reads a seat
map, and reads what it learned about this person from past bookings. Ask it
and it gives a genuinely useful answer: the Saturday show, section A, $210.

It also runs only when someone types. Every chapter after this one is about
what has to change so the task can finish without anyone at the keyboard.
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

root_agent = Agent(
    name="concert",
    model=MODEL,
    instruction=INSTRUCTION,
    tools=[search_events, get_seatmap, recall],
)

# `adk web` looks for `app` before `root_agent`. The plugin narrates every tool
# call to the venue's activity feed, so the room can watch the agent work.
app = App(
    name="concert",
    root_agent=root_agent,
    plugins=[PanelPlugin()],
)
