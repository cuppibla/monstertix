"""Chapter 2 · Wake the Agent — a prompt cannot start a run.

The agent is unchanged except for a second instruction a student swaps in. The
workbench's prompt lab edits that block by regex, so its exact shape is part of
the contract. And the clock's wake-up is an availability check: there is still
no way to buy.
"""
import re

from harness import SOLUTIONS, drive, load_step, needs_model, tool_names

# The same expressions workbench/services/prompts.py uses. If these stop
# matching, the prompt lab silently edits nothing.
BLOCK = re.compile(r'(PROACTIVE_INSTRUCTION = """\n)(.*?)(\n?""")', re.S)
USES = re.compile(r"(\binstruction=)\w+(,)")


def test_the_proactive_block_has_the_shape_the_prompt_lab_edits():
    src = (SOLUTIONS / "step2_wake" / "concert" / "agent.py").read_text()
    block = BLOCK.search(src)
    assert block, 'agent.py needs PROACTIVE_INSTRUCTION = """ on its own line'
    assert block.group(2).strip(), "the proactive wording should not be empty"
    assert "root_agent" in src
    uses = USES.search(src[src.find("root_agent"):])
    assert uses and "INSTRUCTION" in uses.group(0), \
        "root_agent must say instruction=INSTRUCTION, — the lab swaps that word"
    assert "PROACTIVE_INSTRUCTION" not in uses.group(0), \
        "the solution ships with the ordinary instruction wired in"


def test_the_tools_are_the_same_as_chapter_one():
    m = load_step("step2_wake")
    assert set(tool_names(m.root_agent)) == {"search_events", "get_seatmap", "recall"}


def test_it_still_cannot_buy_or_wait():
    """No queue, no long-running tool, no purchase. Nothing to wake."""
    from google.adk.tools import LongRunningFunctionTool
    m = load_step("step2_wake")
    names = tool_names(m.root_agent)
    for forbidden in ("purchase", "join_queue", "check_queue"):
        assert forbidden not in names
    assert not any(isinstance(t, LongRunningFunctionTool) for t in m.root_agent.tools)
    assert m.app.resumability_config is None or not m.app.resumability_config.is_resumable


def test_nothing_in_the_agent_schedules_anything():
    """The point students are asked to find: the agent has no clock of its own.

    Checked against imports rather than text, because the files legitimately
    talk about sleeping and waking.
    """
    import ast, inspect
    load_step("step2_wake")
    from concert import agent, tools

    imported = set()
    for mod in (agent, tools):
        for node in ast.walk(ast.parse(inspect.getsource(mod))):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

    for clock in ("sched", "schedule", "asyncio", "threading", "apscheduler"):
        assert clock not in imported, f"chapter 2's agent must not schedule itself ({clock})"


@needs_model
def test_the_clocks_message_is_a_check_not_a_purchase(venue):
    m = load_step("step2_wake")
    t = drive(m.root_agent, [
        "Check whether the Amsterdam shows still have seats, and tell me what you find."
    ])
    assert t.called("search_events") or t.called("get_seatmap")
    assert venue.orders == 0, "waking the agent in chapter 2 checks; it cannot buy"
