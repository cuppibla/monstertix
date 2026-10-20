"""Chapter 1 · Meet MonsterTix — a good agent that only runs when someone types.

It searches the tour, reads seat maps, and reads memory. That is all it can
do. If it grew a way to buy or wait, the chapter would stop making its point.
"""
from harness import drive, load_step, needs_model, tool_names


def test_has_only_the_three_read_only_tools():
    m = load_step("step1_meet")
    assert set(tool_names(m.root_agent)) == {"search_events", "get_seatmap", "recall"}


def test_cannot_buy_or_wait():
    m = load_step("step1_meet")
    names = tool_names(m.root_agent)
    for forbidden in ("purchase", "join_queue", "check_queue"):
        assert forbidden not in names, f"chapter 1 must not be able to {forbidden}"
    from concert import tools
    assert not hasattr(tools, "purchase"), "nothing in the package can spend money yet"


def test_identity_is_concert_and_the_root_is_a_chat_agent():
    from google.adk.agents import LlmAgent
    m = load_step("step1_meet")
    assert isinstance(m.root_agent, LlmAgent)
    assert m.root_agent.name == "concert"
    assert m.app.name == "concert", "adk web, MonsterTix and the seed all address app_name=concert"


def test_memory_is_a_real_memory_service_from_the_start():
    """recall() exists from chapter 1 so the agent's answers make sense; it is
    taught in chapter 3."""
    import inspect
    load_step("step1_meet")
    from concert import memory
    from google.adk.memory import BaseMemoryService
    assert isinstance(memory.memory_service, BaseMemoryService)
    assert inspect.iscoroutinefunction(memory.recall)


@needs_model
def test_it_can_talk_about_the_tour(venue):
    m = load_step("step1_meet")
    t = drive(m.root_agent, ["What Amsterdam dates are there?"])
    assert t.called("search_events")
    assert venue.orders == 0, "chapter 1 must not be able to buy anything"
