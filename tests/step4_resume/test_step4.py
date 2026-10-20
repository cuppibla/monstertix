"""Chapter 4 · Pause, Restart, Resume — the wait becomes a pause.

The shape of the graph is the lesson. Three nodes must not re-run when the
graph is woken — otherwise every wake-up picks a show again and takes another
queue ticket — and one node must. The run ends at the front of the queue, and
nothing in this chapter can buy.
"""
from harness import FakeContext, call_node, drive, load_step, needs_model, tool_names


def _node_names(workflow) -> list[str]:
    return [getattr(n, "name", getattr(n, "__name__", "?")) for n in workflow.edges[0]]


def test_the_root_is_the_graph_and_the_app_is_resumable():
    from google.adk.workflow import Workflow
    m = load_step("step4_resume")
    assert isinstance(m.root_agent, Workflow), "adk web runs root_agent — from here that is the graph"
    assert isinstance(m.app.root_agent, Workflow), "the loader checks `app` first"
    assert m.app.resumability_config and m.app.resumability_config.is_resumable, \
        "without ResumabilityConfig there is nothing to come back to"
    assert m.app.name == "concert"


def test_the_graph_ends_at_ready_to_buy():
    load_step("step4_resume")
    from concert import nightly as n
    assert _node_names(n.nightly) == [
        "__START__", "open_the_night", "pick_show", "queue_up", "check_front", "ready_to_buy",
    ]


def test_which_nodes_rerun_on_resume():
    load_step("step4_resume")
    from concert import nightly as n
    assert n.open_the_night.rerun_on_resume is False
    assert n.pick_show.rerun_on_resume is False, "a second run would pick a second show"
    assert n.queue_up.rerun_on_resume is False, "a second run would take a second queue ticket"
    assert n.check_front.rerun_on_resume is True, "the gate is the one node that MUST run again"
    assert n.ready_to_buy.rerun_on_resume is False


def test_nothing_in_this_chapter_can_buy():
    load_step("step4_resume")
    from concert import nightly as n, tools
    assert not hasattr(tools, "purchase")
    assert "purchase" not in tool_names(n.picker)
    assert set(tool_names(n.picker)) == {"recall", "search_events", "get_seatmap"}


def test_the_queue_wait_has_a_stable_interrupt_id():
    """Whoever wakes the run answers this id, and reads the prefix to know it
    is a queue wait and not a question for a person."""
    load_step("step4_resume")
    from concert import nightly as n
    assert n.QUEUE_WAIT == "queue:wait"


def test_check_front_pauses_when_not_at_the_front(monkeypatch):
    from google.adk.events.request_input import RequestInput
    load_step("step4_resume")
    from concert import nightly as n, venue
    monkeypatch.setattr(venue, "get", lambda path, **kw: {
        "ticket": "q_1", "position": 14203, "ready": False})
    out = call_node(n.check_front, {"event_id": "ms-ams-01", "ticket": "q_1"})
    assert isinstance(out, RequestInput)
    assert out.interrupt_id == n.QUEUE_WAIT
    assert "14,203" in out.message


def test_check_front_falls_through_at_the_front(monkeypatch):
    from google.adk import Event
    load_step("step4_resume")
    from concert import nightly as n, venue
    monkeypatch.setattr(venue, "get", lambda path, **kw: {"ticket": "q_1", "position": 0, "ready": True})
    out = call_node(n.check_front, {"event_id": "ms-ams-01", "ticket": "q_1"})
    assert isinstance(out, Event)
    assert out.output["ticket"] == "q_1"


def test_check_front_survives_a_lost_ticket(monkeypatch):
    """The venue forgets a ticket (hold expired, or RESET THE VENUE). The run
    must end with lost=True instead of parking forever on a ready that never
    comes."""
    from google.adk import Event
    load_step("step4_resume")
    from concert import nightly as n, venue
    monkeypatch.setattr(venue, "get", lambda path, **kw: {
        "error": True, "status": 404, "message": "no such ticket"})
    out = call_node(n.check_front, {"event_id": "ms-ams-01", "ticket": "q_gone"})
    assert isinstance(out, Event)
    assert out.output.get("lost") is True
    ctx = FakeContext()
    end = call_node(n.ready_to_buy, out.output, ctx)
    assert "ready_to_buy" not in ctx.state
    assert "expired" in str(end.output).lower()


def test_ready_to_buy_records_it_in_state_and_buys_nothing():
    load_step("step4_resume")
    from concert import nightly as n
    ctx = FakeContext()
    plan = {"event_id": "ms-ams-01", "city": "Amsterdam", "section": "A",
            "seats": 2, "reason": "Saturday, lower bowl", "ticket": "q_1"}
    out = call_node(n.ready_to_buy, plan, ctx)
    assert ctx.state["ready_to_buy"] is True
    assert ctx.state["ready_at"]
    assert "Ready to buy" in out.output
    assert "Nothing is bought" in out.output


def test_queue_up_writes_the_ticket_and_the_plan_to_state(monkeypatch):
    load_step("step4_resume")
    from concert import nightly as n, venue
    joined = []
    monkeypatch.setattr(venue, "post", lambda path, payload, headers=None: (
        joined.append(payload) or {"ticket": "q_new", "position": 14203, "ready": False}))
    ctx = FakeContext()
    plan = {"event_id": "ms-ams-01", "city": "Amsterdam", "section": "A",
            "seats": 2, "reason": "Saturday, lower bowl"}
    out = call_node(n.queue_up, plan, ctx)
    assert joined == [{"event_id": "ms-ams-01"}]
    assert ctx.state["queue_ticket"] == "q_new"
    assert ctx.state["queue_event_id"] == "ms-ams-01"
    assert ctx.state["plan"]["section"] == "A"
    assert out.output["ticket"] == "q_new"


def test_queue_up_reuses_a_ticket_it_already_holds(monkeypatch):
    """The at-least-once window: a crash between the venue POST and the node's
    return means the next run arrives here again. Holding a live ticket for
    the same show, it must not take another."""
    load_step("step4_resume")
    from concert import nightly as n, venue
    posted = []
    monkeypatch.setattr(venue, "post", lambda path, payload, headers=None: (
        posted.append(payload) or {"ticket": "q_second", "position": 14203, "ready": False}))
    monkeypatch.setattr(venue, "get", lambda path, **kw: {"ticket": "q_first", "position": 9000, "ready": False})
    ctx = FakeContext(state={"queue_ticket": "q_first", "queue_event_id": "ms-ams-01"})
    plan = {"event_id": "ms-ams-01", "city": "Amsterdam", "section": "A", "seats": 2, "reason": "r"}
    out = call_node(n.queue_up, plan, ctx)
    assert posted == [], "already in line — joining again would lose the place"
    assert out.output["ticket"] == "q_first"
    assert ctx.state["queue_ticket"] == "q_first"

    # But a ticket the venue has forgotten is no ticket: join again.
    monkeypatch.setattr(venue, "get", lambda path, **kw: {"error": True, "status": 404})
    out = call_node(n.queue_up, plan, ctx)
    assert posted == [{"event_id": "ms-ams-01"}]
    assert out.output["ticket"] == "q_second"


@needs_model
def test_it_parks_on_check_front_with_exactly_one_ticket(venue):
    m = load_step("step4_resume")
    t = drive(m.root_agent,
              ["Two tickets to The Midnight Signal in Amsterdam for me and Sam."],
              on_interrupt=lambda msg, tr: None)
    assert t.interrupts, "the run should park on check_front"
    assert "queue" in t.interrupts[-1].lower()
    assert venue.tickets == 1
    assert venue.orders == 0


@needs_model
def test_waking_after_skip_the_wait_reaches_ready_to_buy_on_the_same_ticket(venue):
    """rerun_on_resume=False, proven rather than asserted."""
    m = load_step("step4_resume")

    def answer(msg, tr):
        venue.skip_the_wait()
        return "go"

    t = drive(m.root_agent,
              ["Two tickets to The Midnight Signal in Amsterdam for me and Sam."],
              on_interrupt=answer)
    assert any("Ready to buy" in s for s in t.said), t
    assert venue.tickets == 1, "waking the graph must not re-join the queue"
    assert venue.orders == 0, "nothing is bought in this chapter"
