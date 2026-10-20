"""Integrity boundaries of the guided course, independent of model wording."""
import copy
import hashlib
import json
from unittest.mock import Mock

import pytest

from workbench.services import learning as lab, cloud_demo


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(lab.config, "RUNS", tmp_path)
    monkeypatch.setattr(lab.config, "ROOT", tmp_path)
    lab._busy.clear()
    lab.shutdown()
    yield tmp_path
    lab.shutdown()


def attempt(slug="buy"):
    return {"id": "attempt-one", "slug": slug, "stage": lab.STAGES[slug],
            "fingerprint": "code-one", "sessions": ["session-one"], "marks": {}}


def register(a):
    lab._write({"version": 1, "active": {a["slug"]: a["id"]}, "attempts": {a["id"]: a}})


def test_session_selection_is_exact_and_scoped(monkeypatch):
    sessions = [dict(id="session-one-newer", app_name="concert", user_id="user"),
                dict(id="session-one", app_name="concert", user_id="other"),
                dict(id="session-one", app_name="concert", user_id="user")]
    monkeypatch.setattr(lab.task, "sessions", lambda: sessions)
    assert lab._session("session-one") is sessions[2]
    assert lab._session("session") is None


@pytest.mark.parametrize("payload, message", [
    ({"attempt_id": "stale", "text": "yes", "interrupt_id": "budget:confirm"}, "older experiment"),
    ({"attempt_id": "attempt-one", "text": "", "interrupt_id": "budget:confirm"}, "own answer"),
    ({"attempt_id": "attempt-one", "text": "yes", "interrupt_id": "budget:ask"}, "not the current question"),
])
def test_stale_or_empty_answers_never_reach_runner(workspace, monkeypatch, payload, message):
    register(attempt())
    monkeypatch.setattr(lab, "status", lambda _: {"loaded": True, "next": "answer"})
    monkeypatch.setattr(lab, "_session", lambda _: {})
    monkeypatch.setattr(lab.task, "pending_of", lambda _: {"kind": "person", "id": "budget:confirm"})
    run = Mock()
    monkeypatch.setattr(lab, "_run", run)
    with pytest.raises(lab.LearningError, match=message):
        lab.act("buy", "answer", payload)
    run.assert_not_called()


def test_scenario_stops_before_queue_advance_when_arming_fails(workspace, monkeypatch):
    a = attempt()
    register(a)
    monkeypatch.setattr(lab, "_queue", lambda _: (
        {"authorization": {"confirmed": True}, "queue_ticket": "ticket-one", "queue_event_id": "show-one"},
        {"ticket": "ticket-one"}))
    called = []
    def venue(path, body):
        called.append((path, body))
        if path == "/admin/hang-once":
            raise lab.LearningError("offline")
        return {"ok": True}
    monkeypatch.setattr(lab, "_venue", venue)
    with pytest.raises(lab.LearningError, match="offline"):
        lab._scenario(a)
    assert called == [("/admin/sellout", {"event_id": "show-one", "section": "A"}),
                      ("/admin/hang-once", {})]
    assert not lab._active("buy")["marks"]["scenario"]["ready"]


def test_scenario_targets_this_ticket_and_never_runs_agent(workspace, monkeypatch):
    a = attempt()
    register(a)
    monkeypatch.setattr(lab, "_queue", lambda _: (
        {"authorization": {"confirmed": True}, "queue_ticket": "ticket-one", "queue_event_id": "show-one"},
        {"ticket": "ticket-one"}))
    venue, run = Mock(return_value={"ok": True}), Mock()
    monkeypatch.setattr(lab, "_venue", venue)
    monkeypatch.setattr(lab, "_run", run)
    lab._scenario(a)
    assert venue.call_args.args == ("/admin/advance-queue", {"ticket": "ticket-one"})
    assert lab._active("buy")["marks"]["scenario"]["ready"]
    run.assert_not_called()


def test_action_copy_cannot_erase_receipt_written_by_poll(workspace):
    a = attempt()
    register(a)
    stale_copy = copy.deepcopy(a)
    a["receipt"] = {"at": 10, "archive": "evidence.json"}
    lab._save(a)
    stale_copy["marks"]["resume"] = {"at": 11}
    lab._save(stale_copy)
    assert lab._active("buy")["receipt"] == a["receipt"]


def test_archived_records_remain_readable_after_stage_reset(workspace, monkeypatch):
    a = attempt("remember")
    register(a)
    session = {"id": "session-one", "stored_state": {"plan": "Saturday"}, "events": []}
    monkeypatch.setattr(lab, "_session", lambda _: session)
    monkeypatch.setattr(lab, "_memory", lambda: "aisle seats")
    lab._archive(a)
    monkeypatch.setattr(lab, "_session", lambda _: None)
    monkeypatch.setattr(lab, "_memory", lambda: "new chapter memory")
    lab._archive(a)
    records = lab.records("remember")
    assert records["archived"]
    assert records["sessions"] == [session]
    assert records["memory"] == "aisle seats"


def test_second_purchase_identity_cannot_hide_from_one_order_check(monkeypatch):
    a = attempt()
    def key(section):
        return hashlib.sha256(f"session-one:show:{section}:2".encode()).hexdigest()[:24]
    session = {"id": "session-one", "stored_state": {"authorization": {
        "confirmed": True, "seats": 2, "per_seat_max": 250}}, "events": [{"content": {"parts": [
        {"function_call": {"name": "purchase", "args": {"event_id": "show", "section": "C", "seats": 2}}},
        {"function_call": {"name": "purchase", "args": {"event_id": "show", "section": "A", "seats": 2}}},
        {"function_response": {"name": "purchase", "response": {
            "id": "order-one", "idempotency_key": key("C"), "attempts": 2, "duplicate": True}}},
    ]}}]}
    monkeypatch.setattr(lab, "_session", lambda _: session)
    venue = {"orders": [{"id": "order-one", "idem_key": key("C"), "seats": 2, "unit_price": 190}]}
    checks = {c["id"]: c["passed"] for c in lab.evidence(a, venue)}
    assert checks["order"] and checks["retry"] and not checks["guard"]
    venue["orders"].append({"id": "order-two", "idem_key": key("A"), "seats": 2, "unit_price": 240})
    assert not next(c for c in lab.evidence(a, venue) if c["id"] == "order")["passed"]


def test_cloud_dispatch_rejects_another_latest_task(workspace, monkeypatch):
    settings = {"url": "https://example.test", "project": "project", "region": "region", "job": "job"}
    monkeypatch.setattr(cloud_demo, "_settings", lambda: settings)
    cloud_demo._save({"session_id": "task-one", "url": settings["url"]})
    monkeypatch.setattr(cloud_demo, "_task", lambda *_: {
        "pending": {"kind": "queue"}, "authorization": {"confirmed": True}})
    monkeypatch.setattr(lab, "_json", lambda *_: {"session_id": "task-two"})
    dispatch = Mock()
    monkeypatch.setattr(cloud_demo.subprocess, "run", dispatch)
    with pytest.raises(lab.LearningError, match="Another cloud session"):
        cloud_demo.act("dispatch", {"session_id": "task-one"})
    dispatch.assert_not_called()


def test_queue_advance_only_changes_named_ticket(tmp_path, monkeypatch):
    from venue import app as venue
    monkeypatch.setattr(venue, "_conn", None)
    monkeypatch.setattr(venue, "DB_PATH", str(tmp_path / "venue-test.db"))
    venue.seed()
    event = venue.list_events()["events"][0]["id"]
    first = venue.join_queue({"event_id": event})
    second = venue.join_queue({"event_id": event})
    venue.advance_queue({"ticket": first["ticket"]})
    assert venue.check_queue(first["ticket"])["ready"]
    assert not venue.check_queue(second["ticket"])["ready"]
    venue.db().close()
