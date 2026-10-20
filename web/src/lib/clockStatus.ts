/** Clock logs append across launches. Only the latest launch can describe this run. */
export function latestClockRun(log: string): string {
  const starts = [...log.matchAll(/^\$ python.*monstertix\.clock.*$/gm)];
  return log.slice(starts.at(-1)?.index ?? 0).trim();
}

export function clockStatus(log: string, running: boolean) {
  const run = latestClockRun(log);
  const last = run.split("\n").filter(line => line.startsWith("[clock]")).at(-1) ?? "";
  if (last.includes("nothing listening") || last.includes("trigger returned")) {
    return {kind: "error", text: "The request failed. Check the clock log below and make sure MonsterTix is running."};
  }
  if (last.includes("nothing resumed:")) {
    return {kind: "done", text: "The server answered. There was no eligible queue wait to resume."};
  }
  if (last.includes("done. the agent ran")) {
    return {kind: "done", text: running && /--every [1-9]/.test(run)
      ? "Check complete. The clock will send another request after its interval."
      : "Check complete. The one-shot clock exits after the server answers; this is normal."};
  }
  if (!running) {
    return run ? {kind: "stopped", text: "Clock stopped. No completed response is recorded for this launch."}
      : {kind: "idle", text: "Ready. Click the button to schedule a request; no typing is needed."};
  }
  return last.includes("firing →")
    ? {kind: "running", text: "Request sent. Waiting for the server to finish the agent's run…"}
    : {kind: "waiting", text: "Clock is waiting to send the request. No typing is needed."};
}
