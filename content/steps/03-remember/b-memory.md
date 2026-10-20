The agent picked Saturday without asking. The Tuesday show is $10 cheaper per seat and listed first, and nothing in your message said which night. The reason is one sentence in a text file written after a booking months ago. This section traces that sentence from the file, through a tool return, into the choice, and then has you write one of your own.

:::exercise id="run"
:::

## Key code: memory is an interface, and ours is a file

:::figure src="/docs-img/04-02-contextmgnt.png" caption="Memory as an interface, with a file behind it"
:::

ADK's long-term memory is an interface called `BaseMemoryService`. It has two methods:

```python
# google.adk.memory.BaseMemoryService — ADK's interface, not your file
async def add_session_to_memory(session)                   # take a conversation in
async def search_memory(*, app_name, user_id, query)       # hand memories back
```

ADK ships three implementations:

| Class | URI | What it needs |
|---|---|---|
| `InMemoryMemoryService` | `memory://` | nothing. Loses everything when you stop the process |
| `VertexAiRagMemoryService` | `rag://` | a Vertex AI RAG corpus |
| `VertexAiMemoryBankService` | `agentengine://` | an Agent Engine resource |

None of them fit a workshop. The first cannot be seeded and forgets on restart; the other two need cloud resources that take minutes to create. So `memory.py` is the fourth option ADK gives you: subclass the interface yourself. A Markdown file satisfies it.

:::code path="agent/concert/memory.py" highlight="^class MarkdownMemoryService|async def search_memory|async def add_session_to_memory"
:::

`search_memory` reads `memory/userx.md` and returns it as one `MemoryEntry` inside a `SearchMemoryResponse`. Those are ADK's types; Memory Bank returns the same objects with a managed service behind them. Ours has a file, chosen for one reason: you can open it and read it. Your agent's entire long-term knowledge is a page of text.

`add_session_to_memory` is deliberately a no-op. Memory Bank implements it by running a model over the whole session to extract durable facts. Here the agent decides what is worth keeping, one sentence at a time, through `remember`. Dumping raw turns into the file would destroy the only thing that makes it useful: that a person can read it.

### The read path and the write path

:::code path="agent/concert/memory.py" highlight="^async def recall|await memory_service\.search_memory\(|^def remember|path\.write_text\("
:::

**`recall()`** calls `memory_service.search_memory(app_name="concert", user_id=MEMORY_USER, query="")` and returns `{"memory": <the file>, "source": <path>}`. That return becomes a `function_response` event, which is how the text reaches the model. Open the `✓ recall` row and the whole file is sitting in it. **Until `recall` has run, the model has not seen a word of it.** The instruction says to call it before recommending anything; the choice of `ms-ams-01` is the model reading "Sam bails on weeknights" out of that return and applying it.

**`remember(fact)`** opens the same file, inserts one bullet under `## Preferences`, and writes it back. That is the only writer. **The conversation is never turned into memory on its own.** "Noted!" in the chat is a sentence in this session's events; it is in the file only if `⚡ remember` ran. You watched the difference: the file changed when the tool ran, and it contains your one sentence, not the transcript.

### How the services are wired

Two of the three services are chosen on the command line. The third is not, and the reason is worth knowing precisely:

| Service | Where you set it | This workshop |
|---|---|---|
| session | `--session_service_uri` on `adk web` | `sqlite+aiosqlite:///$WORKSHOP/sessions.db` |
| artifact | `--artifact_service_uri` on `adk web` | `file://$WORKSHOP/artifacts` |
| **memory** | **nowhere on the command line** | `MEMORY_DIR`, read inside `memory.py` |

:::code path="agent/concert/memory.py" highlight="^MEMORY_DIR =|^MEMORY_USER =|^memory_service ="
:::

In production you hand a memory service to the `Runner` and ADK calls it for you, through `PreloadMemoryTool` or `LoadMemoryTool`:

```python
Runner(agent=root_agent, app_name="concert",
       session_service=...,
       memory_service=MarkdownMemoryService("./memory"))
```

`adk web` cannot be handed an object. It builds its services at startup from `--memory_service_uri`, before it imports any agent code, so there is no moment at which `memory.py` could register a custom URI scheme. (The registry exists, `get_service_registry().register_memory_service`; it just runs too late to help.) So `recall` and `remember` call the service directly. The service is the real thing; only the wiring is a workaround, and the swap back is the one line above.

:::note
`MEMORY_USER=userx` names the **file**, `memory/userx.md`. It is not an ADK user id. Every surface in this workshop addresses ADK as app `concert`, user `user`; the memory file name is a separate setting.
:::

:::checkpoint
**The agent replied "Got it, I'll remember that" and there was no `⚡ remember` event. Will it know next week?**
:::answer
No. The sentence is in this session's `events` rows and nowhere else. The memory file is written only by `remember()`, and `add_session_to_memory` does nothing in this implementation. Next week's session will call `recall()`, get the file, and the file will not have it. A promise in chat is session state at best; a fact in memory is an explicit write.
:::
:::
