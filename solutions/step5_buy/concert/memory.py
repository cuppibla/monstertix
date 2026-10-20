"""Memory as a file you can read — implementing ADK's real interface.

ADK ships three memory services, and none of them fit a workshop:

    InMemoryMemoryService      memory://       dies on restart, cannot be seeded
    VertexAiRagMemoryService   rag://          needs a Vertex AI RAG corpus
    VertexAiMemoryBankService  agentengine://  needs an Agent Engine resource

So this is the fourth option ADK gives you: subclass `BaseMemoryService`
yourself. It is a two-method interface, and a text file satisfies it.

    add_session_to_memory(session)                  ingest a conversation
    search_memory(app_name=, user_id=, query=)      hand memories back

We implement the second and deliberately no-op the first — see below.

Everything else — Memory Bank, RAG — implements exactly these two methods with
a managed service behind them. Once you have written one, none of them are
mysterious.

WHY THE TOOLS CALL IT DIRECTLY
------------------------------
In production you hand a memory service to the Runner and ADK calls it for you,
via PreloadMemoryTool or LoadMemoryTool. We cannot do that here: `adk web`
builds its services at startup from `--memory_service_uri`, before it imports
any agent code, so there is no moment at which we could register a custom URI
scheme. (The registry is real — `get_service_registry().register_memory_service`
— it just runs too late to help.)

So `recall` and `remember` below are thin wrappers that call the service
directly. The service is the real thing; only the wiring is a workaround, and
the swap is one line in a Runner:

    Runner(agent=root_agent, app_name="concert",
           session_service=...,
           memory_service=MarkdownMemoryService("./memory"))

WHERE THE FILE LIVES
--------------------
On a laptop the root is a directory and the memory is `memory/userx.md`. On
Cloud Run the root is `gs://<bucket>/memory` and the same file is a blob — a
container's disk is thrown away on every restart, so a file there is not
memory at all. The two-method interface does not change when the storage
does; only `_read` and `_write` below know the difference, and the switch is
the path you hand the constructor.
"""

from __future__ import annotations

import os
import pathlib

from google.adk.memory.base_memory_service import (
    BaseMemoryService,
    SearchMemoryResponse,
)
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions import Session
from google.genai import types

# A directory on a laptop, a gs:// prefix on Cloud Run. See the class.
MEMORY_DIR = os.environ.get("MEMORY_DIR", "./memory")
MEMORY_USER = os.environ.get("MEMORY_USER", "userx")


class MarkdownMemoryService(BaseMemoryService):
    """A memory service whose storage is a Markdown file.

    Not a scalable idea, and not the point. The point is that memory is an
    interface, the interface is small, and you can see the whole of your
    agent's long-term knowledge in a text editor.
    """

    def __init__(self, root: str | pathlib.Path):
        root = str(root)
        self.is_bucket = root.startswith("gs://")
        self.root = root.rstrip("/") if self.is_bucket else pathlib.Path(root)

    # --- the storage seam ----------------------------------------------------
    #
    # Everything above this line is the memory service. Everything below is
    # "where is the text". Two methods, so moving from a directory to a bucket
    # is a path change and nothing else.

    def _path(self, user_id: str, *, for_writing: bool = False) -> pathlib.Path:
        """Where this user's memory lives, on a local root.

        Only creates the directory when something is about to be written. It
        used to mkdir on every call, including reads, which silently produced an
        empty `memory/` wherever the process happened to be running and then
        reported "nothing remembered yet" — the same answer you get when the
        memory really is empty, and impossible to tell apart.
        """
        if for_writing and not self.is_bucket:
            self.root.mkdir(parents=True, exist_ok=True)
        return pathlib.Path(self.root) / f"{user_id}.md"

    def location(self, user_id: str) -> str:
        """The file or the blob, as something a person can go and look at."""
        if self.is_bucket:
            return f"{self.root}/{user_id}.md"
        return str(self._path(user_id).resolve())

    def _blob(self, user_id: str):
        # Imported here so a laptop without google-cloud-storage still runs
        # the local path. Only the bucket path needs it, and only on Cloud Run.
        from google.cloud import storage

        bucket_name, _, prefix = self.root[len("gs://"):].partition("/")
        name = f"{prefix}/{user_id}.md" if prefix else f"{user_id}.md"
        return storage.Client().bucket(bucket_name).blob(name)

    def _read(self, user_id: str) -> str | None:
        """The whole memory as text, or None if nothing has been written."""
        if self.is_bucket:
            blob = self._blob(user_id)
            if not blob.exists():
                return None
            return blob.download_as_text()
        path = self._path(user_id)
        return path.read_text() if path.exists() else None

    def _write(self, user_id: str, text: str) -> None:
        if self.is_bucket:
            self._blob(user_id).upload_from_string(text, content_type="text/markdown")
            return
        self._path(user_id, for_writing=True).write_text(text)

    async def add_session_to_memory(self, session: Session) -> None:
        """Ingest a whole conversation. We deliberately do not.

        Memory Bank implements this by running an LLM over the session to pull
        out durable facts. We get the same result more cheaply by letting the
        agent decide what is worth keeping, one sentence at a time, through the
        `remember` tool below — so nothing in this workshop calls this method.

        The no-op is a decision, not an omission. Dumping raw turns into
        memory/<user>.md would fill it with chat and destroy the only thing
        that makes it useful: that a person can open it and read it.
        """
        return None

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> SearchMemoryResponse:
        """Hand back what we know about this person.

        A real implementation would rank by relevance to `query`. At three
        bookings the whole file is smaller than one seat map, so returning it
        is not just simpler — it is more useful. Ranking becomes worth doing at
        the point where the file stops fitting in a prompt, and that is exactly
        when you swap this class for Memory Bank.
        """
        text = self._read(user_id)
        if text is None:
            return SearchMemoryResponse(memories=[])

        return SearchMemoryResponse(
            memories=[
                MemoryEntry(
                    content=types.Content(
                        role="user", parts=[types.Part(text=text)]
                    ),
                    author=user_id,
                    custom_metadata={"source": self.location(user_id)},
                )
            ]
        )


# One instance, shared by the tools below.
memory_service = MarkdownMemoryService(MEMORY_DIR)


# --- the two tools the agent actually calls -------------------------------


async def recall() -> dict:
    """Read everything learned about this person from previous bookings.

    Call this before recommending a show. It holds preferences and past
    bookings that are not in the current conversation.

    Returns:
        The stored memory as text.
    """
    # async, because search_memory is async and ADK already runs your tool
    # inside an event loop. asyncio.run() here raises
    # "cannot be called from a running event loop".
    response = await memory_service.search_memory(
        app_name="concert", user_id=MEMORY_USER, query=""
    )
    if not response.memories:
        # Say WHICH file was missing. "nothing remembered yet" on its own is
        # indistinguishable from reading the wrong path, and MEMORY_USER is easy
        # to have left set to something stale in a shell.
        looked_at = memory_service.location(MEMORY_USER)
        return {
            "memory": "",
            "note": f"nothing remembered yet — no file at {looked_at}",
            "looked_at": looked_at,
            "memory_user": MEMORY_USER,
        }

    entry = response.memories[0]
    return {
        "memory": entry.content.parts[0].text,
        "source": entry.custom_metadata.get("source"),
    }


def remember(fact: str) -> dict:
    """Record a durable fact worth keeping after this conversation ends.

    Use this for preferences and outcomes, not for passing details. "Sam bails
    on weeknights" belongs here. "Row F costs $210 right now" does not.

    Args:
        fact: One sentence, written so it still makes sense months later.

    Returns:
        Confirmation and the file written to.
    """
    existing = memory_service._read(MEMORY_USER)
    if existing is None:
        existing = f"# Memory — {MEMORY_USER}\n"
    if "## Preferences" not in existing:
        existing += "\n## Preferences\n"
    lines = existing.rstrip().splitlines()
    lines.insert(lines.index("## Preferences") + 1, f"- {fact.strip()}")
    memory_service._write(MEMORY_USER, "\n".join(lines) + "\n")
    return {"remembered": fact, "file": memory_service.location(MEMORY_USER)}
