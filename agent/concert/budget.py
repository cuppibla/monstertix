"""Chapter 5 · Buy Within Agreed Limits — the authorization for THIS task.

The memory file says this person is "comfortable around $200, $250 is the hard
ceiling". That is a preference. It is history. It is not permission to spend
their money tonight.

Authority is different. It is given for one task, by the person, in words they
confirmed:

    "Two tickets, up to $250 each."

So this module keeps two things side by side, and the code checks the second:

    text            the sentence, verbatim, as they confirmed it
    seats           2
    per_seat_max    250.0
    confirmed       True, and when

Why both? The sentence is what you show the person back, and what the buyer
agent reads. The numbers are what the guard in fence.py compares a live price
against in the instant before money moves — a model is good at reading a
sentence and bad at being the last line of defence.

SESSION STATE, NOT `user:`. A budget is agreed for one booking, not forever.
Put it under `user:` and it silently governs every run this person ever makes,
and they are never asked again. So every new session starts with no
authorization and has to agree one. That is the honest trade: a limit that has
to be re-agreed, against a limit that quietly outlives the conversation it
came from.
"""

from __future__ import annotations

import re
import time

AUTH_KEY = "authorization"            # session state key

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1, "single": 1, "a pair of": 2, "pair of": 2,
}
_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a pair of|pair of|a|an|single)"
_SEATS = re.compile(
    rf"\b({_NUM})\s+(?:more\s+)?(?:tickets?|seats?|places?|spots?)\b", re.I
)
_SEATS_FOR = re.compile(r"\b(?:tickets?|seats?)\s+for\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", re.I)
_PRICE = re.compile(
    r"(?:\$\s*(\d+(?:\.\d+)?)"                       # $250
    r"|(\d+(?:\.\d+)?)\s*(?:dollars|usd|bucks)\b"     # 250 dollars
    r"|(?:up to|max(?:imum)?(?: of)?|under|at most|no more than|not more than|ceiling(?: of)?|limit(?: of)?|cap(?: of)?)\s*\$?\s*(\d+(?:\.\d+)?))",  # up to 250
    re.I,
)


def _count(word: str) -> int | None:
    word = word.strip().lower()
    if word.isdigit():
        return int(word)
    return _WORDS.get(word)


def parse(text: str) -> dict | None:
    """Pull the two numbers the guard needs out of what the person said.

        "Two tickets, up to $250 each."       -> {"seats": 2, "per_seat_max": 250.0}
        "2 tickets max 250 dollars each"      -> {"seats": 2, "per_seat_max": 250.0}
        "whatever it costs"                   -> None

    Deliberately narrow. Counts are words one..ten or digits next to
    "tickets"/"seats"; the price is "$250", "250 dollars" or "up to 250". If
    either is missing the answer is None and the person is asked again, with
    the shape spelled out. Conditional budgets — "$100 for the cheap seats,
    $250 for good ones" — are not something a per-seat check can enforce, so
    they are not something this course lets the agent pretend to enforce.
    """
    text = (text or "").strip()
    if not text:
        return None

    seats = None
    m = _SEATS.search(text) or _SEATS_FOR.search(text)
    if m:
        seats = _count(m.group(1))

    price = None
    m = _PRICE.search(text)
    if m:
        price = float(next(g for g in m.groups() if g))

    if not seats or seats < 1 or price is None or price <= 0:
        return None
    return {"seats": seats, "per_seat_max": price}


def load(state) -> dict | None:
    """The authorization for this task, or None if nobody has agreed one.

    Session state only. Not `user:` — see the module docstring.
    """
    auth = state.get(AUTH_KEY)
    if not isinstance(auth, dict) or not auth.get("confirmed"):
        return None
    if "seats" not in auth or "per_seat_max" not in auth:
        return None
    return auth


def make(text: str, parsed: dict) -> dict:
    """The dict that goes into state once the person has confirmed it."""
    return {
        "text": text.strip(),
        "seats": int(parsed["seats"]),
        "per_seat_max": float(parsed["per_seat_max"]),
        "confirmed": True,
        "confirmed_at": time.strftime("%H:%M"),
    }


def describe(auth: dict | None) -> str:
    """One line for a prompt, a log, or the page.

        2 seats, up to $250 each (confirmed 09:41)
    """
    if not auth:
        return "nothing agreed yet"
    seats = auth.get("seats")
    cap = auth.get("per_seat_max")
    cap_text = f"${cap:g}" if isinstance(cap, (int, float)) else str(cap)
    line = f"{seats} seat{'s' if seats != 1 else ''}, up to {cap_text} each"
    if auth.get("confirmed_at"):
        line += f" (confirmed {auth['confirmed_at']})"
    return line


def allows(auth: dict | None, seats: int, price: float) -> tuple[bool, str]:
    """Does this authorization cover `seats` at `price` each?

    Returns (True, "") or (False, reason). The reasons are short codes, so a
    test — or the page — can tell them apart without parsing prose.
    """
    if not auth:
        return False, "no_authorization"
    if int(seats) != int(auth["seats"]):
        return False, "wrong_seat_count"
    if float(price) > float(auth["per_seat_max"]):
        return False, "over_authorization"
    return True, ""
