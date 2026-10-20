import test from "node:test";
import assert from "node:assert/strict";
import {clockReceipt, clockStatus, latestClockRun} from "../src/lib/clockStatus.ts";

const launch = "$ python -m monstertix.clock --in 10\n";
const success = launch + "[clock] firing → POST /wake\n[clock] done. the agent ran and you were not involved.\n";

test("a successful one-shot exits normally instead of looking broken", () => {
  assert.equal(clockStatus(success, false).kind, "done");
  assert.match(clockStatus(success, false).text, /normal/);
});
test("previous success cannot make a new waiting or interrupted launch complete", () => {
  const log = success + "\n" + launch + "[clock] first fire in 10s, once only\n";
  assert.equal(clockStatus(log, true).kind, "waiting");
  assert.equal(clockStatus(log, false).kind, "stopped");
  assert.equal(latestClockRun(log).includes("done."), false);
});
test("sent request stays pending until the server responds", () => {
  assert.equal(clockStatus(launch + "[clock] firing → POST /wake\n", true).kind, "running");
});
test("failed request never reports completion even after an earlier success", () => {
  for (const message of ["nothing listening at localhost", "trigger returned 503"]) {
    assert.equal(clockStatus(success + "\n" + launch + `[clock] ${message}\n`, false).kind, "error");
  }
});
test("repeating clock shows the current request, not an earlier successful one", () => {
  const log = success.replace("--in 10", "--in 5 --every 30");
  assert.match(clockStatus(log, true).text, /another request/);
  assert.equal(clockStatus(log + "[clock] firing → POST /wake\n", true).kind, "running");
  assert.equal(clockStatus(log + "[clock] stopped.\n", false).kind, "stopped");
});
test("empty logs and no-op resume are distinct from a completed agent run", () => {
  assert.equal(clockStatus("", false).kind, "idle");
  assert.match(clockStatus(launch + "[clock] nothing resumed: no task\n", false).text, /no eligible queue wait/);
});

const receipt = '[clock] request {"message":"Check seats"}\n'
  + '[clock] response {"session_id":"wake-a","said":["Saturday has seats.\\nTwo sections available."]}\n';

test("receipt preserves the real multiline reply and exact session", () => {
  assert.deepEqual(clockReceipt(launch + "[clock] firing → POST /wake\n" + receipt), {
    message: "Check seats", sessionId: "wake-a", said: ["Saturday has seats.\nTwo sections available."],
  });
});
test("a new launch or repeat cannot show the previous answer as its own", () => {
  const done = launch + "[clock] firing → POST /wake\n" + receipt;
  assert.deepEqual(clockReceipt(done + launch), {});
  const pending = done + '[clock] firing → POST /wake\n[clock] request {"message":"Next check"}\n';
  assert.deepEqual(clockReceipt(pending), {message: "Next check"});
  assert.equal(clockStatus(pending, true).kind, "running");
});
test("partial or malformed replies do not create an answer or report completion", () => {
  const partial = launch + '[clock] firing → POST /wake\n[clock] request {"message":"Check seats"}\n'
    + '[clock] response {"said":';
  assert.deepEqual(clockReceipt(partial), {message: "Check seats"});
  assert.equal(clockStatus(partial + "\n[clock] invalid response: not JSON\n", false).kind, "error");
  assert.deepEqual(clockReceipt(launch + '[clock] firing → POST /wake\n[clock] response null\n'), {});
});
