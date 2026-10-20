"""The guard that runs in the instant before the agent spends money.

Two things go wrong between "ready to buy" and "bought", and this callback is
where both are caught:

  AUTHORITY   The agent was told "two tickets, up to $250 each". It is a model.
              It will usually respect that. "Usually" is not a property you
              want of the thing that spends money, so the numbers are checked
              here, in code, against the live price.

  STALE       The agent came back from a forty-minute wait holding
              state["temp:seatmap"] and wants to buy from it. Section A sold
              out twelve minutes in. Nothing was missing from its context — the
              wrong thing was present. So re-read the seat map now, and refuse
              if the plan no longer fits it.

Returning a dict from a before_tool_callback short-circuits the tool: the
agent gets the dict back as if the tool had returned it, and the venue is never
called. Returning None lets the call through.

The checks run in a fixed order, and each refusal carries a `reason` code:

    no_authorization    nobody confirmed a budget for this task
    wrong_seat_count    the agent asked for a different number of seats
    over_authorization  the live price is above the per-seat limit
    stale_plan          fewer seats left than the plan needs
    price_moved         the price changed since the agent last looked

The venue checks inventory again when the order lands. This guard does not
replace that — it keeps the agent from making a request it should already know
will fail, and from making one it was never allowed to make.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import BaseTool, ToolContext

from . import budget, venue


def refresh_before_purchase(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> dict | None:
    """Check authority, then check the world, before any purchase goes through."""
    if tool.name != "purchase":
        return None

    event_id = args.get("event_id")
    section = args.get("section", "A")
    seats = int(args.get("seats", 2))
    if not event_id:
        return None

    # 1. Authority. The person's own numbers, confirmed for this task.
    auth = budget.load(tool_context.state)
    if auth is None:
        return {
            "error": True,
            "reason": "no_authorization",
            "message": "Nobody has confirmed a budget for this task. Buy nothing.",
        }
    if int(seats) != int(auth["seats"]):
        return {
            "error": True,
            "reason": "wrong_seat_count",
            "message": (
                f"The authorization is for {auth['seats']} seats, not {seats}."
            ),
            "authorization": budget.describe(auth),
        }

    # 2. The world, as it is right now — not as it was before the wait.
    live = venue.get(f"/events/{event_id}/seatmap")
    if live.get("error"):
        return {
            "error": True,
            "reason": "stale_plan",
            "message": f"could not read the seat map for {event_id}: {live.get('message', '')}",
        }
    current = next(
        (s for s in live["sections"] if s["section"] == section),
        None,
    )
    if current is None:
        return {
            "error": True,
            "reason": "stale_plan",
            "message": f"section {section} does not exist for {event_id}",
            "actually_available": 0,
        }

    ok, why = budget.allows(auth, seats, current["price"])
    if not ok:
        return {
            "error": True,
            "reason": why,
            "message": (
                f"Section {section} is ${current['price']:g} a seat; the authorization "
                f"is {budget.describe(auth)}. Pick a cheaper section or buy nothing."
            ),
            "live_price": current["price"],
            "per_seat_max": auth["per_seat_max"],
        }

    # What the agent *thought* was true, for a useful error message. The copy
    # queue_up kept (`planned_seatmap`) survives the pause; `temp:seatmap` only
    # exists if this same invocation has read a seat map since it woke.
    snapshot = (tool_context.state.get("temp:seatmap")
                or tool_context.state.get("planned_seatmap") or {})
    believed = next(
        (s for s in snapshot.get("sections", []) if s["section"] == section),
        None,
    )

    if current["available"] < seats:
        return {
            "error": True,
            "reason": "stale_plan",
            "message": (
                f"Section {section} has {current['available']} seats left, "
                f"{seats} requested. Re-read the seat map and pick again."
            ),
            "believed_available": believed.get("available") if believed else None,
            "actually_available": current["available"],
        }

    if believed and believed["price"] != current["price"]:
        return {
            "error": True,
            "reason": "price_moved",
            "message": (
                f"Price for section {section} moved from {believed['price']} to "
                f"{current['price']}. Read the seat map again before buying."
            ),
        }

    # Fresh enough, and allowed. Hand the live price down to the tool and
    # leave a mark that the guard let this call through.
    tool_context.state["temp:verified_price"] = current["price"]
    tool_context.state["temp:guard"] = "passed"
    return None
