"""Build the two-day-old session that Chapter 3 opens.

    python -m seed.session

What it creates, and why each piece is there:

    user:prefs          "Sam can't do weeknights" — a user-scoped fact, so it
                        is visible from any session of this user
    session state       an in-progress booking: the show and the party size
    a real compaction   an actual EventActions.compaction, so the Events tab
                        genuinely shows older turns replaced by a summary
    12 events           six turns of a plausible group chat

Deliberately NOT seeded:

    temp:seatmap        temp state is stripped before it is written, which is
                        exactly the lesson — students create one live by asking
                        for a seat map, and see whether it survives a restart.
    any authorization   the conversation talks about prices and preferences.
                        Nobody in it authorizes a purchase. Chapter 5 is where
                        "willing to spend $250" and "you may buy two tickets at
                        up to $250 each, now" are shown to be different things,
                        and the seed must not blur that.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import time

from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions, EventCompaction
from google.adk.sessions import DatabaseSessionService
from google.genai import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_URL = os.environ.get("SEED_DB_URL", f"sqlite+aiosqlite:///{ROOT}/sessions.db")

APP_NAME = "concert"
SESSION_ID = "two-days-ago"

# One identity everywhere: app "concert", user "user". `adk web` hardcodes
# userId=user and has no user picker, and the MonsterTix server, main.py and the
# workbench all use the same one, so every surface sees the same sessions.
# Seed under any other id and the session exists, is queryable over the API,
# and is completely invisible in the dropdown.
#
# This is separate from MEMORY_USER, which only names the memory file.
USER_ID = os.environ.get("SEED_USER_ID", os.environ.get("ADK_USER_ID", "user"))

DAY = 86_400.0
NOW = time.time()

# (author, text, seconds before now)
TRANSCRIPT = [
    ("user",  "We're thinking about seeing The Midnight Signal. Me, Sam, and maybe Priya.", 2.0 * DAY),
    ("concert", "They've got eight dates. Amsterdam on the 14th and 10th, New York, "
                "Tokyo, Mexico City, Auckland. Amsterdam is closest to you — shall I look "
                "at those two?", 2.0 * DAY - 40),

    ("user",  "Yes. Sam can't do weeknights though, he's bailed on every single one.", 2.0 * DAY - 300),
    ("concert", "Noted — I'll rule out anything midweek. That kills the 10th, "
                "which is a Tuesday. So Amsterdam on Saturday the 14th.", 2.0 * DAY - 340),

    ("user",  "What's it going to cost?", 1.4 * DAY),
    ("concert", "Lower bowl is $210, upper is $145, general admission $95. "
                "Two lower bowl seats would be $420 all in.", 1.4 * DAY - 30),

    ("user",  "Priya's out, she's away that weekend. Just me and Sam.", 1.0 * DAY),
    ("concert", "Two it is. Still Saturday the 14th, still Amsterdam.", 1.0 * DAY - 25),

    ("user",  "You said the upper bowl at Ziggo was bad last time?", 0.6 * DAY),
    ("concert", "You couldn't see from section B in January. I'd stay in the "
                "lower bowl even though it's $65 more each.", 0.6 * DAY - 30),

    ("user",  "Fine. Let's try for the presale.", 0.2 * DAY),
    ("concert", "The presale opens Tuesday at 10am. I'll need to be in the queue "
                "when it does. Before I buy anything I'll check with you on what "
                "you're happy to spend.", 0.2 * DAY - 20),
]

# What compaction did to the first four turns, two days ago.
COMPACTION_SUMMARY = (
    "The user is planning to see The Midnight Signal with friends. They looked "
    "at the Amsterdam dates and settled on a Saturday show because Sam cannot "
    "do weeknights. Pricing was discussed: lower bowl $210, upper $145, GA $95."
)


def _content(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def build() -> None:
    service = DatabaseSessionService(db_url=DB_URL)

    # Start clean so re-running is safe.
    existing = await service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    if existing is not None:
        await service.delete_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
        )

    session = await service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state={
            # user: scope — visible from every session of this user.
            "user:prefs": {"Sam": "cannot do weeknights"},
            # Session scope — this booking only. A new session starts without
            # these, which is the point Chapter 3 makes.
            "target_event_id": "ms-ams-01",
            "party_size": 2,
        },
    )

    for author, text, ago in TRANSCRIPT:
        await service.append_event(
            session,
            Event(
                author=author,
                content=_content(text),
                timestamp=NOW - ago,
                invocation_id=f"seed-{int(ago)}",
            ),
        )

    # A real compaction record over the first four events, so the Events tab
    # shows genuine evidence rather than a story about one.
    await service.append_event(
        session,
        Event(
            author="concert",
            timestamp=NOW - (1.9 * DAY),
            invocation_id="seed-compaction",
            actions=EventActions(
                compaction=EventCompaction(
                    start_timestamp=NOW - (2.0 * DAY),
                    end_timestamp=NOW - (2.0 * DAY - 340),
                    compacted_content=_content(COMPACTION_SUMMARY),
                )
            ),
        ),
    )

    written = await service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    compactions = sum(1 for e in written.events if e.actions and e.actions.compaction)
    oldest = min(e.timestamp for e in written.events)

    print(f"→ database   {DB_URL}")
    print(f"→ session    {APP_NAME}/{USER_ID}/{SESSION_ID}")
    print(f"→ events     {len(written.events)} ({compactions} compaction summary)")
    print(f"→ oldest     {(NOW - oldest) / DAY:.1f} days ago")
    print(f"→ state      {', '.join(sorted(written.state))}")
    print()
    print("✓ seeded. open it in adk web:")
    print(f"    app '{APP_NAME}', user '{USER_ID}', session '{SESSION_ID}'")


if __name__ == "__main__":
    asyncio.run(build())
