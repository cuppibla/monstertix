"""Chapter 4 · Pause, Restart, Resume — the root is now a graph.

The conversational agent from the earlier chapters is still here. But nobody
is typing at 3am, so the thing `adk web` runs is a Workflow: choose the show,
join the queue, pause until the front, say "ready to buy". See nightly.py for
the graph itself.

Two settings on the App make the pause survive a dead process:

    resumability_config      the invocation is written to the session store
                             when it parks, and a later call continues it —
                             same session, same invocation, same ticket.

    events_compaction_config unchanged from the last chapter. The summariser
                             names its own model, because a Workflow root has
                             none to borrow.

Nothing in this chapter buys anything. The run ends at the front of the queue.
"""

from __future__ import annotations

from google.adk.apps.app import App, EventsCompactionConfig, ResumabilityConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models.google_llm import Gemini

from .config import MODEL
from .nightly import nightly
from .panel import PanelPlugin

# THE ROOT IS THE GRAPH. `adk web` runs root_agent, and from here on that is
# the nightly workflow rather than a chat agent.
root_agent = nightly

app = App(
    name="concert",
    root_agent=nightly,
    plugins=[PanelPlugin()],
    # Without this, a RequestInput still stops the run — but there is nothing
    # to come back to. With it, the parked invocation is in the session store
    # and the next call picks it up where it stopped.
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
