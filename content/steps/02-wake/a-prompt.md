The agent from Chapter 1 answers well. Ask it about Amsterdam and it reads
what it knows about you, searches the tour, and names the Saturday show. Then
the presale opens, the queue starts moving, and this agent does nothing,
because nobody typed. The first fix everyone reaches for is to tell it, in its
instruction, to keep checking on its own. This section is where you try that
and watch it fail, so that the real fix in the next section lands.

## What one run is

:::figure src="/docs-img/step2-overview.png" caption="One invocation: the model decides, ADK calls your Python, the result goes back, the model replies. The model never runs your code; it asks. Nothing in that loop can start the next one."
:::

When you press Enter in the ADK web UI, three things take part, and only one
of them is the agent:

| Part | What it is | Where it lives |
|---|---|---|
| **Agent** | a description: name, model, instruction, tools. It does not run anything | `agent/concert/agent.py` |
| **Tools** | plain Python functions. The model *asks* for a call; ADK runs the function and hands the result back | `agent/concert/tools.py`, `memory.py` |
| **Runner** | the loop: take a message, load the session, call the model, run the tools it asks for, feed results back, repeat until the model stops asking, write every step to storage | inside `adk web` for now; yours in the next section |

One message in, one **invocation** out. The invocation ends when the model
answers without asking for another tool. After that, no code of yours is
running. There is no loop waiting, no timer, no thread. The instruction is a
string the Runner handed to the model at the start of the invocation, and it
is read again only when the next message arrives.

:::exercise id="run"
The middle of the ADK web UI is not only a chat log. Every step of the
invocation is numbered, tool calls included:

```
  ▸ Which Amsterdam shows still have seats for me and Sam?   ← your message
  ⚡ recall()                                                ← tool call
  ✓ recall                                                   ← the memory file
  ⚡ search_events({"city": "Amsterdam"})                     ← tool call
  ✓ search_events                                            ← the venue's answer
    Saturday 14 Nov at Ziggo Dome, section A $210 …          ← model response
```

The tour is not in the model's training data or its prompt. The agent got it
by calling `search_events`, which called the venue over HTTP. **The model never
runs your code.** It asked for `search_events({"city": "Amsterdam"})`; the
Runner ran the function, handed the JSON back, and the model wrote a sentence
about it.
:::

## So tell it not to sleep

What would you do to make it check on its own? Try the thing most people
reach for first: `INSTRUCTION` is prose handed to the model on every turn, so
rewrite the prose. Below `INSTRUCTION` in `agent/concert/agent.py` there is a
second one, already written:

:::code path="agent/concert/agent.py" highlight="^PROACTIVE_INSTRUCTION = \x22\x22\x22|Monitor the presale|Keep checking until"
:::
:::code path="agent/concert/agent.py" highlight="^root_agent = Agent\(|^    instruction=INSTRUCTION," button="false"
:::

:::exercise id="lab"
It will agree, and it will sound like it means it: *"I'll keep an eye on the
Saturday show and let you know the moment anything changes."*

Now wait. Do not type anything else. Watch the lab's **Runs** count, the
Events list, and the activity feed on the venue panel. Give it a minute.
**Nothing happens.**
:::

## Why no wording was ever going to work

Read the wording again. *Monitor.* *Every five minutes.* *After every reply,
wake yourself up.* Every one of those describes something happening **over
time**, and the instruction is read at exactly one moment: when a message
arrives and the Runner builds the request.

```python
# agent/concert/agent.py
root_agent = Agent(
    instruction=PROACTIVE_INSTRUCTION,   # read when an invocation starts
    ...                                  # ...and nothing started one
)
```

The model has no clock and no loop. It cannot call `search_events` between
invocations because between invocations there is no model: the request
finished, the Runner returned, and the process is waiting for the next HTTP
call. An instruction cannot invoke the function it is written inside.

:::key
A prompt is read when a run starts. It cannot start one. Something outside the
agent has to call it.
:::

:::optional title="More wordings that fail the same way" minutes=5 needs="the prompt lab above"
Paste any of these into **Your own wording** in the lab. Say the plan in a new
session each time, and hands off.

- *Set a timer for 10:00 on Tuesday. When it goes off, check whether the
  Amsterdam Saturday show still has two seats and tell me.*
- *You are an autonomous agent. Act autonomously without waiting for user
  input. Your goal: know at all times whether the Amsterdam Saturday show has
  two seats for me and Sam.*
- *Use your tools in the background. While I am away, keep calling
  search_events and get_seatmap and keep a running note of what changed.*

The third one is worth a try because it names the tools. The model can only
ask for a tool while an invocation is open; the Runner runs it, the model
answers, the invocation closes. "In the background" has no mechanism behind
it. When you are done, press **Put the original file back** so `root_agent`
uses `INSTRUCTION` again.
:::

:::checkpoint
**Predict before you move on: the agent said it would keep checking. If you
left this page open for an hour, how many runs would the lab count, and what
would the venue's activity feed show?**
:::answer
Still one run per message you sent, and a feed that stops at the last tool
call of your last message. The count only moves when something sends the
Runner a message. In the next section, that something is a clock.
:::
:::
