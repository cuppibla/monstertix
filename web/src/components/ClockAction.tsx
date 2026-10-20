import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Service, type TurnItem } from "../lib/api";
import { useBench } from "../lib/bench";
import { clockReceipt, clockStatus, latestClockRun } from "../lib/clockStatus";

export function ClockAction({ settings }: { settings: NonNullable<TurnItem["clock"]> }) {
  const { refresh } = useBench();
  const [snapshot, setSnapshot] = useState<{service?: Service; log: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const changing = useRef(false);
  const delay = settings.in ?? 10;
  const every = settings.every ?? 0;
  const trigger = !!settings.trigger;

  const pull = useCallback(async () => {
    const version = generation.current;
    try {
      const [state, output] = await Promise.all([api.services(), api.serviceLog("clock")]);
      if (version !== generation.current) return;
      setSnapshot({service: state.services.find(s => s.name === "clock"), log: output.log});
      setError("");
    } catch {
      if (version === generation.current) setError("Could not read the clock status. Try again when the workbench is available.");
    }
  }, []);

  useEffect(() => {
    void pull();
    const timer = window.setInterval(() => { if (!changing.current) void pull(); }, 1500);
    return () => { window.clearInterval(timer); generation.current++; };
  }, [pull]);

  async function act(action: "restart" | "stop") {
    changing.current = true;
    generation.current++;
    setBusy(true);
    setError("");
    try {
      await api.service("clock", action, {delay, every, trigger});
      await pull();
      await refresh();
    } catch {
      setError("The clock command did not finish. Read its status before trying again.");
    } finally {
      changing.current = false;
      setBusy(false);
    }
  }

  const running = ["running", "starting"].includes(snapshot?.service?.state ?? "");
  const status = snapshot ? clockStatus(snapshot.log, running) : null;
  const log = latestClockRun(snapshot?.log ?? "");
  const receipt = clockReceipt(log);
  return <div className="mt-2">
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="btn btn--solid" disabled={busy || running || !snapshot || !!error}
              onClick={() => act("restart")}>
        {every ? `Fire every ${every}s, first in ${delay}s` : `Fire once, ${delay}s from now`}
      </button>
      {running && <button type="button" className="btn" disabled={busy} onClick={() => act("stop")}>Stop clock</button>}
    </div>
    <p className="mt-2 text-xs" style={{color: "var(--fg-faint)"}}>Latest clock launch</p>
    <p className="mt-1 text-sm" role="status"
       style={{color: error || status?.kind === "error" ? "var(--bad)" : status?.kind === "done" ? "var(--ok)" : "var(--fg-muted)"}}>
      {busy ? "Updating the clock…" : error || status?.text || "Reading clock status…"}
    </p>
    {!trigger && <p className="mt-2 text-sm" style={{color: "var(--fg-muted)"}}>
      The Clock calls the server directly. Watch for its question and reply here;
      the chat on the left stays in your manual conversation.
    </p>}
    {!trigger && receipt.message && <section aria-label="Clock request and reply"
      className="mt-3 rounded-lg border p-3" style={{borderColor: "var(--hairline)", background: "var(--card)"}}>
      <h4 className="text-sm font-semibold">Clock sent</h4>
      <p className="mt-1 text-sm">{receipt.message}</p>
      <h4 className="mt-3 text-sm font-semibold">Agent replied</h4>
      {receipt.said?.length
        ? receipt.said.map((line, i) => <p key={i} className="mt-1 whitespace-pre-wrap text-sm">{line}</p>)
        : <p className="mt-1 text-sm" style={{color: "var(--fg-muted)"}}>
          {status?.kind === "error" ? "No answer received. See the error above."
            : status?.kind === "done" ? "The server returned no text. Inspect the response in the Clock log."
            : status?.kind === "stopped" ? "No answer recorded before the clock stopped."
            : "Waiting for the server’s answer…"}
        </p>}
      {receipt.sessionId && <p className="mt-3 break-all text-xs" style={{color: "var(--fg-faint)"}}>
        This Clock run · {receipt.sessionId}
      </p>}
    </section>}
    {log && <details className="mt-2">
      <summary className="cursor-pointer text-sm">Clock log · latest launch</summary>
      <pre className="log quiet-scroll mt-2 max-h-64 overflow-auto rounded-lg p-2">{log}</pre>
    </details>}
    <details className="mt-2">
      <summary className="cursor-pointer text-sm" style={{color: "var(--fg-faint)"}}>Command run by this button</summary>
      <code className="mt-1 block break-words text-xs">
        python -m monstertix.clock --in {delay}{every ? ` --every ${every}` : ""}{trigger ? " --trigger" : ""}
      </code>
    </details>
  </div>;
}
