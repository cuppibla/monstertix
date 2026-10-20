import test from "node:test";
import assert from "node:assert/strict";
import {clockStatus, latestClockRun} from "../src/lib/clockStatus.ts";

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
