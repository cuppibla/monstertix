"""Chapter 5 · Buy Within Agreed Limits — authority, the world, and once.

The graph gets a person at the start and a buyer at the end. The authorization
is numbers the code can check; the guard checks them against the live venue in
a fixed order; and a purchase that fails after committing is retried once with
the same key, so there is still one order.
"""
import pytest

from harness import FakeContext, FakeToolContext, call_node, drive, load_step, needs_model, tool_names

AUTH = {"text": "Two tickets, up to $250 each.", "seats": 2, "per_seat_max": 250.0,
        "confirmed": True, "confirmed_at": "09:41"}
SEATMAP = {
    "event_id": "ms-ams-01", "venue": "Ziggo Dome", "city": "Amsterdam",
    "date": "2026-11-14", "weekday": "Saturday", "captured_at": 0,
    "sections": [
        {"section": "A", "tier": "lower bowl", "price": 210.0, "available": 400},
        {"section": "B", "tier": "upper bowl", "price": 145.0, "available": 900},
        {"section": "C", "tier": "general admission", "price": 95.0, "available": 1200},
    ],
}


def _node_names(workflow) -> list[str]:
    return [getattr(n, "name", getattr(n, "__name__", "?")) for n in workflow.edges[0]]


def _seatmap(**overrides):
    live = {**SEATMAP, "sections": [dict(s) for s in SEATMAP["sections"]]}
    for sec in live["sections"]:
        if sec["section"] in overrides:
            sec.update(overrides[sec["section"]])
    return live


# --- the graph ---------------------------------------------------------------


def test_the_graph_starts_with_a_person_and_ends_with_the_buyer():
    load_step("step5_buy")
    from concert import nightly as n
    assert _node_names(n.nightly) == [
        "__START__", "agree_budget", "open_the_night", "pick_show", "queue_up",
        "check_front", "brief", "concert",
    ]
    assert n.nightly.edges[0][-1] is n.buyer_agent


def test_the_buyer_is_imported_not_rebuilt():
    m = load_step("step5_buy")
    from concert import nightly
    assert nightly.buyer_agent is m.buyer_agent
    assert m.buyer_agent.name == "concert"


def test_which_nodes_rerun_on_resume():
    load_step("step5_buy")
    from concert import nightly as n
    assert n.agree_budget.rerun_on_resume is True, "it has to run again to see the answer"
    assert n.open_the_night.rerun_on_resume is False
    assert n.pick_show.rerun_on_resume is False
    assert n.queue_up.rerun_on_resume is False
    assert n.check_front.rerun_on_resume is True


def test_the_interrupt_ids_are_stable_and_say_who_answers():
    load_step("step5_buy")
    from concert import nightly as n
    assert n.ASK_BUDGET == "budget:ask"
    assert n.CONFIRM_BUDGET == "budget:confirm"
    assert n.QUEUE_WAIT == "queue:wait"


def test_the_buyers_tools_and_guard():
    m = load_step("step5_buy")
    from concert.fence import refresh_before_purchase
    assert set(tool_names(m.buyer_agent)) == {"get_seatmap", "recall", "remember", "purchase"}
    assert m.buyer_agent.before_tool_callback is refresh_before_purchase
    text = m.buyer_agent.instruction.lower()
    assert "never ask" in text
    assert "upper bowl" in text and "section b" in text
    assert "remember()" in text


def test_the_buyer_tries_the_plan_first_and_lets_the_guard_check():
    """The guard is the check, not the model's caution. If the buyer re-read
    the seat map first, the stale_plan refusal would never be seen."""
    m = load_step("step5_buy")
    from concert import nightly as n
    text = m.buyer_agent.instruction.lower()
    assert "do not read the seat map first" in text
    assert text.index("call purchase") < text.index("get_seatmap")
    ctx = FakeContext(state={"authorization": AUTH})
    plan = {"event_id": "ms-ams-01", "city": "Amsterdam", "section": "A",
            "seats": 2, "reason": "Saturday, lower bowl", "ticket": "q_1"}
    out = n.brief(plan, ctx)
    assert "without reading the seat map first" in out.output
    assert ctx.state["ready_to_buy"] is True and ctx.state["ready_at"], \
        "the task card shows 'ready to buy' here, as chapter 4's last node did"
    lost = FakeContext(state={"authorization": AUTH})
    n.brief({**plan, "ticket": "", "lost": True}, lost)
    assert "ready_to_buy" not in lost.state
    assert "2 seats in section A" in out.output
    assert AUTH["text"] in out.output


def test_the_old_shortcuts_are_gone():
    m = load_step("step5_buy")
    from concert import budget, nightly, tools
    for name in ("DEFAULT_BUDGET", "someone_is_there", "mark_attended", "UNATTENDED"):
        assert not hasattr(budget, name), f"budget.{name} must not exist"
        assert not hasattr(nightly, name), f"nightly.{name} must not exist"
    assert not hasattr(tools, "set_budget")
    assert not hasattr(tools, "join_queue") and not hasattr(tools, "check_queue")
    assert not hasattr(m, "budget_split")


# --- budget.py ---------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("Two tickets, up to $250 each.", {"seats": 2, "per_seat_max": 250.0}),
    ("2 tickets max 250 dollars each", {"seats": 2, "per_seat_max": 250.0}),
    ("two seats, no more than $200 each", {"seats": 2, "per_seat_max": 200.0}),
    ("a pair of tickets under $150", {"seats": 2, "per_seat_max": 150.0}),
    ("whatever it costs", None),
    ("up to $300", None),
    ("three tickets", None),
    ("", None),
])
def test_budget_parse(text, expected):
    load_step("step5_buy")
    from concert import budget
    assert budget.parse(text) == expected


def test_budget_load_is_session_scoped_and_needs_confirmation():
    load_step("step5_buy")
    from concert import budget
    assert budget.AUTH_KEY == "authorization"
    assert budget.load({"authorization": AUTH}) == AUTH
    assert budget.load({"user:authorization": AUTH}) is None, \
        "user: state would outlive the booking it was agreed for"
    assert budget.load({"authorization": {**AUTH, "confirmed": False}}) is None, \
        "said is not agreed"
    assert budget.load({}) is None, "a fresh session has nothing agreed"


def test_budget_describe_and_allows():
    load_step("step5_buy")
    from concert import budget
    assert budget.describe(AUTH) == "2 seats, up to $250 each (confirmed 09:41)"
    assert budget.describe(None) == "nothing agreed yet"
    assert budget.allows(AUTH, 2, 210.0) == (True, "")
    assert budget.allows(AUTH, 2, 250.0) == (True, "")
    assert budget.allows(AUTH, 2, 260.0) == (False, "over_authorization")
    assert budget.allows(AUTH, 3, 95.0) == (False, "wrong_seat_count")
    assert budget.allows(None, 2, 95.0) == (False, "no_authorization")


# --- agree_budget, without a model ------------------------------------------


def test_agree_budget_asks_reads_back_then_stores():
    from google.adk.events.request_input import RequestInput
    load_step("step5_buy")
    from concert import nightly as n

    ctx = FakeContext()
    out = call_node(n.agree_budget, None, ctx)
    assert isinstance(out, RequestInput) and out.interrupt_id == n.ASK_BUDGET
    assert "authorization" not in ctx.state

    ctx = FakeContext(resume_inputs={n.ASK_BUDGET: {"result": "Two tickets, up to $250 each."}})
    out = call_node(n.agree_budget, None, ctx)
    assert isinstance(out, RequestInput) and out.interrupt_id == n.CONFIRM_BUDGET
    assert "$250" in out.message and "2 tickets" in out.message
    assert "authorization" not in ctx.state, "read back is not yet agreed"

    ctx = FakeContext(resume_inputs={n.ASK_BUDGET: {"result": "Two tickets, up to $250 each."},
                                     n.CONFIRM_BUDGET: {"result": "Yes, that's right."}})
    call_node(n.agree_budget, None, ctx)
    auth = ctx.state["authorization"]
    assert auth["seats"] == 2 and auth["per_seat_max"] == 250.0
    assert auth["confirmed"] is True and auth["confirmed_at"]
    assert auth["text"] == "Two tickets, up to $250 each."


def test_agree_budget_asks_again_when_it_cannot_read_the_answer():
    from google.adk.events.request_input import RequestInput
    load_step("step5_buy")
    from concert import nightly as n
    ctx = FakeContext(resume_inputs={n.ASK_BUDGET: {"result": "whatever it costs"}})
    out = call_node(n.agree_budget, None, ctx)
    assert isinstance(out, RequestInput) and out.interrupt_id == n.ASK_BUDGET
    assert "up to $250 each" in out.message, "it should spell out the shape it can read"
    assert "authorization" not in ctx.state


def test_agree_budget_passes_straight_through_once_agreed():
    from google.adk import Event
    load_step("step5_buy")
    from concert import nightly as n
    ctx = FakeContext(state={"authorization": AUTH})
    out = call_node(n.agree_budget, None, ctx)
    assert isinstance(out, Event)


# --- fence.py: the order of refusals ----------------------------------------


def _guard(monkeypatch, state, args, live=None):
    from concert import fence, venue
    from google.adk.tools import BaseTool
    monkeypatch.setattr(venue, "get", lambda path, **kw: live if live is not None else _seatmap())
    tool = BaseTool(name="purchase", description="")
    ctx = FakeToolContext(state)
    return fence.refresh_before_purchase(tool, args, ctx), ctx


def test_guard_ignores_every_other_tool(monkeypatch):
    load_step("step5_buy")
    from concert import fence
    from google.adk.tools import BaseTool
    assert fence.refresh_before_purchase(BaseTool(name="get_seatmap", description=""), {}, FakeToolContext()) is None


def test_guard_refuses_without_authorization_first(monkeypatch):
    load_step("step5_buy")
    out, _ = _guard(monkeypatch, {}, {"event_id": "ms-ams-01", "section": "A", "seats": 2},
                    live=_seatmap(A={"available": 0}))
    assert out["reason"] == "no_authorization", "before anything about the world is looked at"


def test_guard_refuses_the_wrong_seat_count(monkeypatch):
    load_step("step5_buy")
    out, _ = _guard(monkeypatch, {"authorization": AUTH},
                    {"event_id": "ms-ams-01", "section": "C", "seats": 3})
    assert out["reason"] == "wrong_seat_count"


def test_guard_refuses_a_live_price_over_the_limit(monkeypatch):
    load_step("step5_buy")
    out, _ = _guard(monkeypatch, {"authorization": {**AUTH, "per_seat_max": 200.0}},
                    {"event_id": "ms-ams-01", "section": "A", "seats": 2})
    assert out["reason"] == "over_authorization"
    assert out["live_price"] == 210.0


def test_guard_refuses_a_stale_plan(monkeypatch):
    """Section A sold out while the run waited. The old seat map said 400."""
    load_step("step5_buy")
    state = {"authorization": AUTH, "temp:seatmap": _seatmap()}
    out, _ = _guard(monkeypatch, state, {"event_id": "ms-ams-01", "section": "A", "seats": 2},
                    live=_seatmap(A={"available": 0}))
    assert out["reason"] == "stale_plan"
    assert out["believed_available"] == 400 and out["actually_available"] == 0


def test_guard_refuses_a_moved_price(monkeypatch):
    load_step("step5_buy")
    state = {"authorization": AUTH, "temp:seatmap": _seatmap()}
    out, _ = _guard(monkeypatch, state, {"event_id": "ms-ams-01", "section": "C", "seats": 2},
                    live=_seatmap(C={"price": 99.0}))
    assert out["reason"] == "price_moved"


def test_guard_lets_a_good_purchase_through_and_leaves_a_mark(monkeypatch):
    load_step("step5_buy")
    out, ctx = _guard(monkeypatch, {"authorization": AUTH, "temp:seatmap": _seatmap()},
                      {"event_id": "ms-ams-01", "section": "C", "seats": 2})
    assert out is None
    assert ctx.state["temp:verified_price"] == 95.0
    assert ctx.state["temp:guard"] == "passed"


def test_guard_ordering_is_authority_before_the_world(monkeypatch):
    """A request that is wrong in every way is refused for the first reason."""
    load_step("step5_buy")
    state = {"authorization": {**AUTH, "per_seat_max": 100.0}, "temp:seatmap": _seatmap()}
    out, _ = _guard(monkeypatch, state, {"event_id": "ms-ams-01", "section": "A", "seats": 3},
                    live=_seatmap(A={"available": 0, "price": 220.0}))
    assert out["reason"] == "wrong_seat_count"
    out, _ = _guard(monkeypatch, state, {"event_id": "ms-ams-01", "section": "A", "seats": 2},
                    live=_seatmap(A={"available": 0, "price": 220.0}))
    assert out["reason"] == "over_authorization"
    state["authorization"] = AUTH
    out, _ = _guard(monkeypatch, state, {"event_id": "ms-ams-01", "section": "A", "seats": 2},
                    live=_seatmap(A={"available": 0, "price": 220.0}))
    assert out["reason"] == "stale_plan"


# --- purchase: once ----------------------------------------------------------


def test_purchase_retries_once_with_the_same_key(monkeypatch):
    load_step("step5_buy")
    from concert import tools, venue
    seen = []

    def flaky_post(path, payload, headers=None):
        seen.append((payload, headers["Idempotency-Key"]))
        if len(seen) == 1:
            return {"error": True, "status": 503, "message": "try again"}
        return {"id": "ord_1", "event_id": payload["event_id"], "section": payload["section"],
                "seats": payload["seats"], "duplicate": True}

    monkeypatch.setattr(venue, "post", flaky_post)
    ctx = FakeToolContext({"queue_ticket": "q_1"})
    out = tools.purchase("ms-ams-01", "C", 2, ctx)
    assert len(seen) == 2
    assert seen[0][1] == seen[1][1], "the retry must reuse the key, or it is a second purchase"
    assert out["attempts"] == 2
    assert out["idempotency_key"] == seen[0][1]
    assert out["id"] == "ord_1" and out["duplicate"] is True
    assert ctx.state["last_order"] == "ord_1"


def test_purchase_does_not_retry_a_refusal(monkeypatch):
    """409 sold out is an answer, not a failure."""
    load_step("step5_buy")
    from concert import tools, venue
    calls = []
    monkeypatch.setattr(venue, "post", lambda path, payload, headers=None: (
        calls.append(1) or {"error": True, "status": 409, "message": "sold_out"}))
    out = tools.purchase("ms-ams-01", "A", 2, FakeToolContext())
    assert len(calls) == 1 and out["attempts"] == 1
    assert out["error"]


def test_purchase_gives_up_after_the_one_retry(monkeypatch):
    load_step("step5_buy")
    from concert import tools, venue
    calls = []
    monkeypatch.setattr(venue, "post", lambda path, payload, headers=None: (
        calls.append(1) or {"error": True, "status": 503, "message": "down"}))
    out = tools.purchase("ms-ams-01", "C", 2, FakeToolContext())
    assert len(calls) == 2 and out["attempts"] == 2 and out["error"]


def test_the_key_is_derived_from_session_and_request():
    import hashlib
    load_step("step5_buy")
    from concert import tools, venue
    captured = {}
    original = venue.post
    venue.post = lambda path, payload, headers=None: (captured.update(headers) or {"id": "x"})
    try:
        tools.purchase("ms-ams-01", "C", 2, FakeToolContext(session_id="abc"))
    finally:
        venue.post = original
    expected = hashlib.sha256(b"abc:ms-ams-01:C:2").hexdigest()[:24]
    assert captured["Idempotency-Key"] == expected


def test_the_venue_deduplicates_on_that_key(venue):
    """The fix, proven against the venue rather than asserted about the code."""
    body = {"event_id": "ms-ams-01", "section": "C", "seats": 2}
    key = {"Idempotency-Key": "test-chapter5"}
    venue.break_next_purchase()
    venue.c.post("/purchase", json=body, headers=key)      # commits, then 503
    venue.c.post("/purchase", json=body, headers=key)      # the retry
    assert venue.orders == 1, "the key should have suppressed the duplicate"


def test_without_a_key_the_retry_buys_twice(venue):
    """The bug, so the suite proves the fix is actually doing something."""
    body = {"event_id": "ms-ams-01", "section": "C", "seats": 2}
    venue.break_next_purchase()
    venue.c.post("/purchase", json=body)
    venue.c.post("/purchase", json=body)
    assert venue.orders == 2


def test_purchase_tool_against_the_real_venue_after_break(venue):
    """The whole thing end to end, without a model: the tool retries, the venue
    returns the original order, there is one order."""
    load_step("step5_buy")
    from concert import tools
    venue.break_next_purchase()
    out = tools.purchase("ms-ams-01", "C", 2, FakeToolContext(session_id="e2e"))
    assert out["attempts"] == 2
    assert out.get("duplicate") is True
    assert venue.orders == 1
    assert venue.order_list[0]["id"] == out["id"]


# --- live --------------------------------------------------------------------

ASK = "Two tickets to The Midnight Signal in Amsterdam for me and Sam."


@needs_model
def test_sell_out_a_then_it_buys_two_in_c(venue):
    """Authority, the world, and the person's preferences, all at once:
    A is gone, B is the upper bowl, C is the only answer."""
    m = load_step("step5_buy")
    answers = ["Two tickets, up to $250 each.", "Yes, that's right."]

    def answer(msg, tr):
        if answers:
            return answers.pop(0)
        venue.sell_out("A")
        venue.skip_the_wait()
        return "go"

    t = drive(m.root_agent, [ASK], on_interrupt=answer)
    assert len(t.interrupts) >= 3, "ask, confirm, then the queue wait"
    assert venue.orders == 1, t
    order = venue.order_list[0]
    assert order["event_id"] == "ms-ams-01"
    assert order["section"] == "C" and order["seats"] == 2
    assert venue.tickets == 0, "buying releases the queue place"
    # The trace the chapter shows: the stale plan is tried, the guard refuses,
    # the buyer looks again, then buys what fits.
    # (the calls before the first purchase are the picker's.)
    buyer = t.calls[t.calls.index("purchase"):]
    assert buyer[0] == "purchase", buyer
    assert "get_seatmap" in buyer, buyer
    assert buyer.count("purchase") == 2, buyer
    assert "remember" in t.calls


@needs_model
def test_no_authorization_means_no_order(venue):
    """Nobody answers the budget question. The run parks and nothing is bought."""
    m = load_step("step5_buy")
    t = drive(m.root_agent, [ASK], on_interrupt=lambda msg, tr: None)
    assert t.interrupts and "ticket" in t.interrupts[0].lower()
    assert venue.orders == 0
    assert venue.tickets == 0, "it must not even join the queue before the limit is agreed"
