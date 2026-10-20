"""The agent's hands: search the tour, look at seats, write down who is coming.

Each tool here writes to a different place, and the places have different
lifetimes:

    get_seatmap       temp:seatmap        this invocation only
                      an artifact file    kept by the Artifact Service
    note_companion    user:prefs          every session for this user

The memory file is the fourth place — see memory.py. The queue is not a tool:
joining it and checking it are rules, and they live in the graph (nightly.py).
Nothing here spends money yet.
"""

from __future__ import annotations

import json
import time

from google.adk.tools import ToolContext
from google.genai import types

from . import venue


def search_events(city: str = "", weekday: str = "") -> dict:
    """List tour dates. Call with no arguments to see the whole tour.

    This venue sells one artist and one tour, so there is nothing to search by
    name — never ask the user which artist they mean.

    Args:
        city: Optional. Filter to one city, e.g. "Amsterdam".
        weekday: Optional. Filter to one weekday, e.g. "Saturday".

    Returns:
        Tour dates with venue, city, date and weekday.
    """
    return venue.get("/events", city=city, weekday=weekday)


async def get_seatmap(event_id: str, tool_context: ToolContext) -> dict:
    """Look up current sections, prices and availability for one show.

    Args:
        event_id: The event id from search_events, e.g. "ms-ams-01".

    Returns:
        A short summary of sections and prices. The full seat map is saved as
        an artifact rather than returned, so it never enters the prompt.
    """
    seatmap = venue.get(f"/events/{event_id}/seatmap")

    # The venue returns errors as data, so check before indexing into it. A
    # model that invents an event id gets a 404 here, and without this guard
    # the KeyError below takes down the whole run instead of letting the agent
    # look the id up.
    if seatmap.get("error"):
        return {
            "error": True,
            "event_id": event_id,
            "message": f"no show with id {event_id!r}. "
                       "Call search_events to get the real ids, and use one of those.",
        }

    # The whole seat map goes to the Artifact Service as a file. Only the
    # summary below goes back to the model — a prompt does not need 2,500 seat
    # rows to decide between three sections.
    part = types.Part(
        inline_data=types.Blob(
            mime_type="application/json",
            data=json.dumps(seatmap, indent=2).encode(),
        )
    )
    filename = f"seatmap_{event_id}.json"
    await tool_context.save_artifact(filename, part)

    summary = {
        "event_id": event_id,
        "venue": seatmap["venue"],
        "city": seatmap["city"],
        "date": seatmap["date"],
        "weekday": seatmap["weekday"],
        "sections": [
            {"section": s["section"], "price": s["price"], "available": s["available"]}
            for s in seatmap["sections"]
        ],
        "captured_at": seatmap["captured_at"],
        "artifact": filename,
    }
    # `temp:` state lives for this invocation only. It is the right place for a
    # snapshot of the world — and, as a later chapter shows, exactly the wrong
    # thing to trust after a long wait.
    tool_context.state["temp:seatmap"] = summary
    tool_context.state["temp:seatmap_captured"] = time.strftime(
        "%H:%M:%S", time.localtime(seatmap["captured_at"])
    )
    return summary


def note_companion(name: str, constraint: str, tool_context: ToolContext) -> dict:
    """Record who is coming and any constraint they have.

    Args:
        name: Who is coming, e.g. "Sam".
        constraint: What limits them, e.g. "cannot do weeknights".

    Returns:
        The updated companion list.
    """
    # `user:` state belongs to the person, not to this conversation. A new
    # session for the same user starts with it already there — which is the
    # difference between this and a fact left loose in the transcript, where a
    # summary can paraphrase it away.
    prefs = dict(tool_context.state.get("user:prefs", {}))
    prefs[name] = constraint
    tool_context.state["user:prefs"] = prefs
    return {"companions": prefs}
