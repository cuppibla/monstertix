"""The clock exposes its real HTTP exchange, never a fabricated success."""
import importlib.util
import json
import pathlib
import sys
from unittest.mock import MagicMock

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "clock_under_test", pathlib.Path(__file__).resolve().parents[2] / "monstertix/clock.py"
)
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)


def run_clock(monkeypatch, capsys, response, *flags):
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response
    monkeypatch.setattr(clock.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(clock.time, "sleep", lambda delay: None)
    monkeypatch.setattr(sys, "argv", ["clock", "--in", "0", *flags])
    clock.main()
    return client, capsys.readouterr().out


def test_clock_prints_the_request_and_exact_server_reply(monkeypatch, capsys):
    reply = {"session_id": "wake-test", "said": ["Seats available.\nSaturday fits Sam."]}
    client, output = run_clock(monkeypatch, capsys, httpx.Response(200, json=reply))
    assert client.post.call_args.kwargs["json"] == {"message": clock.DEFAULT_MESSAGE}
    encoded = next(line.removeprefix("[clock] response ") for line in output.splitlines()
                   if line.startswith("[clock] response "))
    assert json.loads(encoded) == reply
    assert "done. the agent ran" in output


@pytest.mark.parametrize("response", [
    httpx.Response(503, text="unavailable"),
    httpx.Response(200, text="<html>error page</html>"),
    httpx.Response(200, json=["not a response object"]),
])
def test_failed_or_invalid_response_never_reports_success(monkeypatch, capsys, response):
    _, output = run_clock(monkeypatch, capsys, response)
    assert "done. the agent ran" not in output
    assert "trigger returned 503" in output or "invalid response:" in output


def test_trigger_with_no_wait_is_distinct_from_an_agent_reply(monkeypatch, capsys):
    client, output = run_clock(monkeypatch, capsys,
                               httpx.Response(200, json={"woke": None, "reason": "no queue wait"}), "--trigger")
    assert client.post.call_args.kwargs["json"] == {}
    assert "nothing resumed: no queue wait" in output
    assert "done. the agent ran" not in output
