import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Service, type TurnItem } from "../lib/api";
import { useBench } from "../lib/bench";
import { clockStatus, latestClockRun } from "../lib/clockStatus";

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
