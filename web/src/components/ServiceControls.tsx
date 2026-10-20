import { useEffect, useRef, useState } from "react";

import { api, type Service } from "../lib/api";
import { useBench } from "../lib/bench";
import { t } from "../i18n";

/* The on/off for one process, wherever the step shows it: the top right of
   the app's card, or beside the clock in step 3.

   On runs the command the codelab gives (shown with the log), off is Ctrl-C.
   The agent also has kill -9 for step 6, which ends it with no chance to clean
   up, and Restart. "log" opens what the process printed: the terminal it
   would have had. */

export const DOT: Record<string, string> = {
  running: "var(--ok)",
  remote: "var(--ok)",
  external: "var(--amber)",
  starting: "var(--amber)",
  unreachable: "var(--bad)",
  stopped: "var(--fg-faint)",
};

/** The one word for a process's state, as the page shows it next to its switch:
    running · starting · stopped · killed · external · remote · unreachable. */
export function stateWord(service: Service): string {
  switch (service.state) {
    case "running":
      return t("running");
    case "starting":
      return service.port ? t("starting") : t("waiting to fire");
    case "external":
      return t("external");
    case "remote":
      return t("remote");
    case "unreachable":
      return t("unreachable");
    default:
      return service.last === "killed with SIGKILL" ? t("killed") : t("stopped");
  }
}

/** The word, plus where: "running · :8000", "external · started in a terminal". */
export function stateText(service: Service): string {
  const word = stateWord(service);
  switch (service.state) {
    case "running":
      return service.port ? `${word} · :${service.port}` : word;
    case "external":
      return `${word} · ${t("started in a terminal")}`;
    case "remote":
      return `${word} · ${t("on Cloud Run")}`;
    case "unreachable":
      return `${word} · ${t("not answering")}`;
    default:
      return word;
  }
}

function Switch({ on, busy, onChange, label }: { on: boolean; busy: boolean; onChange: (next: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      title={on ? t("Turn {name} off", { name: label }) : t("Turn {name} on", { name: label })}
      disabled={busy}
      onClick={() => onChange(!on)}
      className="relative h-[18px] w-[32px] shrink-0 rounded-full transition-colors disabled:opacity-50"
      style={{ background: on ? "var(--accent)" : "var(--hairline-strong)" }}
    >
      <span className={`absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white transition-all ${busy ? "dot--busy" : ""}`}
            style={{ left: on ? 16 : 2 }} />
    </button>
  );
}

export function ServiceLog({ name, command }: { name: string; command?: string }) {
  const [text, setText] = useState("");
  const box = useRef<HTMLPreElement>(null);
  const stick = useRef(true);

  useEffect(() => {
    let alive = true;
    const pull = () => api.serviceLog(name).then((r) => alive && setText(r.log)).catch(() => {});
    pull();
    const timer = setInterval(pull, 1500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [name]);

  useEffect(() => {
    if (box.current && stick.current) box.current.scrollTop = box.current.scrollHeight;
  }, [text]);

  return (
    <div>
      {command && <p className="mb-1 font-mono text-[0.66rem] break-all" style={{ color: "var(--fg-faint)" }}>$ {command}</p>}
      <pre ref={box}
           onScroll={(e) => {
             const el = e.currentTarget;
             stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
           }}
           className="log quiet-scroll m-0 max-h-64 overflow-auto rounded-lg p-2">
        {text.trim() || t("Nothing printed yet.")}
      </pre>
    </div>
  );
}

/** State, switch, kill -9 and Restart (agent), and a log toggle, in one row. */
export function ServiceControls({ name, log, onLog }: { name: string; log: boolean; onLog: (open: boolean) => void }) {
  const { service, refresh, bump } = useBench();
  const [busy, setBusy] = useState("");
  const svc = service(name);
  if (!svc) return null;

  const on = ["running", "starting", "external", "remote"].includes(svc.state);
  const switchable = !["remote", "unreachable", "external"].includes(svc.state);

  async function act(action: string) {
    setBusy(action);
    try {
      await api.service(name, action);
      await refresh();
      bump();
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="flex items-center gap-2">
      <span className="flex items-center gap-1.5 font-mono text-[0.68rem]" style={{ color: "var(--fg-faint)" }}
            title={svc.last || svc.state}>
        <span className={`dot ${svc.state === "starting" || busy ? "dot--busy" : ""}`}
              style={{ width: 7, height: 7, background: DOT[svc.state] ?? "var(--fg-faint)" }} />
        <span className="rounded px-1 py-[1px] text-[0.62rem] font-semibold uppercase tracking-wide"
              style={{ color: DOT[svc.state] ?? "var(--fg-faint)",
                       background: `color-mix(in srgb, ${DOT[svc.state] ?? "var(--fg-faint)"} 14%, transparent)` }}>
          {stateWord(svc)}
        </span>
        {svc.state === "running" && svc.port ? <span>:{svc.port}</span> : null}
        {svc.state === "external" ? <span>{t("started in a terminal")}</span> : null}
        {svc.state === "remote" ? <span>{t("on Cloud Run")}</span> : null}
      </span>
      {name === "agent" && svc.pid !== null && (
        <>
          <button type="button" className="btn btn--danger" disabled={!!busy} onClick={() => act("kill")}
                  title={t("Ends the process at once: no shutdown, no flush")}>kill -9</button>
          <button type="button" className="btn" disabled={!!busy} onClick={() => act("restart")}>{t("Restart")}</button>
        </>
      )}
      {svc.state !== "remote" && (
        <button type="button" className="btn" aria-pressed={log} onClick={() => onLog(!log)}
                style={log ? { color: "var(--fg)", borderColor: "var(--fg-faint)" } : undefined}>
          {t("log")}
        </button>
      )}
      {switchable && <Switch on={on} busy={!!busy} label={svc.label} onChange={(next) => act(next ? "start" : "stop")} />}
    </div>
  );
}
