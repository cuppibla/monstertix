/** Clock logs append across launches. Only the latest launch can describe this run. */
export function latestClockRun(log: string): string {
  const starts = [...log.matchAll(/^\$ python.*monstertix\.clock.*$/gm)];
  return log.slice(starts.at(-1)?.index ?? 0).trim();
}

/** Scope the receipt to one HTTP request, including on a repeating clock. */
export function clockReceipt(log: string): {message?: string; sessionId?: string; said?: string[]} {
  const run = latestClockRun(log);
  const fire = run.lastIndexOf("[clock] firing →");
  if (fire < 0) return {};
  const receipt: {message?: string; sessionId?: string; said?: string[]} = {};
  for (const line of run.slice(fire).split("\n")) {
    const entry = /^\[clock\] (request|response) (.+)$/.exec(line);
    if (!entry) continue;
    try {
      const value = JSON.parse(entry[2]);
      if (!value || typeof value !== "object") continue;
      if (entry[1] === "request" && typeof value.message === "string") receipt.message = value.message;
      if (entry[1] === "response") {
        if (typeof value.session_id === "string") receipt.sessionId = value.session_id;
        if (Array.isArray(value.said)) receipt.said = value.said.filter((s: unknown): s is string => typeof s === "string");
      }
    } catch { /* A log read may end in the middle of a JSON line. Wait for the next poll. */ }
  }
  return receipt;
}

export function clockStatus(log: string, running: boolean) {
  const run = latestClockRun(log);
  const last = run.split("\n").filter(line => line.startsWith("[clock]")).at(-1) ?? "";
  if (last.includes("nothing listening") || last.includes("trigger returned") || last.includes("invalid response:")) {
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
  return last.includes("firing →") || last.startsWith("[clock] request ") || last.startsWith("[clock] response ")
    ? {kind: "running", text: "Request sent. Waiting for the server to finish the agent's run…"}
    : {kind: "waiting", text: "Clock is waiting to send the request. No typing is needed."};
}
