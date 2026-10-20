import { useEffect, useRef, useState } from "react";

import { api, type Job, type PaneTab, type TurnItem } from "../lib/api";
import { useBench } from "../lib/bench";
import { ServiceControls, ServiceLog } from "./ServiceControls";
import { ResumeButton, useTask } from "./TaskCard";
import { t } from "../i18n";
import { Inline } from "./Inline";

/* "Your turn": the numbered things a student does in a step.

   Every item says where it happens. A message is typed into the ADK web UI
   (the drawer) or the MonsterTix page (the left column); the copy button
   brings that app forward. A venue button is the same POST the panel makes;
   a service action is the same as the app's own switch; a command runs on
   this machine and shows its output here. */

const PANE_NAME: Record<PaneTab, string> = {
  monstertix: "MonsterTix",
  venue: "Venue panel",
  agent: "ADK web UI",
};

const ICON: Record<string, string> = {
  say: "💬",
  answer: "↩",
  press: "🔴",
  service: "⚙",
  look: "👀",
  run: "$",
  clock: "⏰",
  resume: "▶",
  text: "•",
};

function kindOf(item: TurnItem): string {
  if (item.say) return "say";
  if (item.answer) return "answer";
  if (item.press) return "press";
  if (item.service) return "service";
  if (item.look) return "look";
  if (item.run) return "run";
  if (item.clock) return "clock";
  if (item.resume) return "resume";
  return "text";
}

/* `resume: task`: the task card's button, in the numbered list. */
function ResumeItem() {
  const { task, reload } = useTask(3000);
  return (
    <div className="mt-1.5">
      <ResumeButton task={task} onDone={() => reload()} />
    </div>
  );
}

function CopyLine({ text, tab, label }: { text: string; tab?: PaneTab; label: string }) {
  const { focus } = useBench();
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard blocked: the text is on screen to select by hand */
    }
    if (tab) focus(tab);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }
  return (
    <div className="mt-1.5 flex items-start gap-2 rounded-lg border px-3 py-2"
         style={{ borderColor: "var(--hairline)", background: "var(--overlay)" }}>
      <span className="flex-1 text-[0.9rem]" style={{ color: "var(--fg)" }}>{text}</span>
      <button type="button" className="btn shrink-0" onClick={copy}>
        {copied ? t("Copied") : label}
      </button>
    </div>
  );
}

/* The clock has no app to show, so its state, switch and log sit here. */
function ClockState() {
  const [log, setLog] = useState(false);
  return (
    <div className="mt-2">
      <ServiceControls name="clock" log={log} onLog={setLog} />
      {log && <div className="mt-2"><ServiceLog name="clock" /></div>}
    </div>
  );
}

function RunItem({ slug, task, index, command }: { slug: string; task: string; index: number; command: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const timer = useRef<number | null>(null);

  const poll = () => {
    api.job(slug, task, index).then((next) => {
      setJob(next);
      if (next.state === "running") timer.current = window.setTimeout(poll, 1000);
    }).catch(() => {});
  };

  useEffect(() => {
    poll();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, task, index]);

  async function run() {
    setJob(await api.jobStart(slug, task, index));
    timer.current = window.setTimeout(poll, 600);
  }

  const running = job?.state === "running";
  return (
    <div className="mt-1.5">
      <div className="flex items-center gap-2">
        <code className="inline-code flex-1 truncate py-1">{command}</code>
        <button type="button" className="btn btn--solid shrink-0" disabled={running} onClick={run}>
          {running ? t("Running…") : job?.state === "done" ? t("Run again") : t("Run")}
        </button>
      </div>
      {job && job.state !== "idle" && (
        <>
          {running && <div className="working-bar mt-1.5 h-[3px] w-full rounded-full" aria-hidden />}
          <pre className="log quiet-scroll mt-1.5 max-h-80 overflow-auto rounded-lg p-2.5">{job.log}</pre>
          {job.state === "done" && (
            <p className="mt-1 text-[0.72rem]" style={{ color: job.code === 0 ? "var(--ok)" : "var(--bad)" }}>
              {job.code === 0 ? t("Finished.") : t("Exited with code {code}.", { code: job.code ?? "?" })}
            </p>
          )}
        </>
      )}
    </div>
  );
}

/* Whether the venue has anyone in line, polled while a button needs it. */
function useInLine(watch: boolean): boolean {
  const [inLine, setInLine] = useState(false);
  useEffect(() => {
    if (!watch) return;
    let alive = true;
    const pull = () => api.venueState().then((s) => alive && setInLine(s.queue > 0)).catch(() => {});
    pull();
    const timer = window.setInterval(pull, 2000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [watch]);
  return inLine;
}

function Item({ item, slug, task, index }: { item: TurnItem; slug: string; task: string; index: number }) {
  const { refresh, service, focus } = useBench();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const kind = kindOf(item);
  const inLine = useInLine(item.needs === "queue");

  async function act(fn: () => Promise<string>) {
    setBusy(true);
    setNote("");
    try {
      setNote(await fn());
      await refresh();
    } catch {
      setNote(t("The workbench did not answer."));
    } finally {
      setBusy(false);
    }
  }

  let control = null;
  if (kind === "say" || kind === "answer") {
    const where = item.in ? t(PANE_NAME[item.in]) : "";
    control = (
      <>
        {kind === "answer" && (
          <p className="mt-1 text-[0.78rem]" style={{ color: "var(--amber)" }}>
            {t("Type this in the event's own response box, not the main chat box.")}
          </p>
        )}
        <CopyLine text={item.say ?? item.answer ?? ""} tab={item.in}
                  label={where ? t("Copy · go to {where}", { where }) : t("Copy")} />
      </>
    );
  } else if (kind === "press") {
    control = (
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        <button type="button" className="btn btn--venue" disabled={busy || (item.needs === "queue" && !inLine)}
                onClick={() => act(async () => {
                  const r = await api.venue(item.venue ?? "", item.body);
                  return r.ok ? t("Pressed.") : t("The venue said no: {error}", { error: r.error ?? "" });
                })}>
          {item.press}
        </button>
        <button type="button" className="btn" onClick={() => focus("venue")}>{t("See the panel")}</button>
        {item.needs === "queue" && !inLine && (
          <span className="text-[0.74rem]" style={{ color: "var(--amber)" }}>
            {t("Waiting for the agent to join the queue. Nobody is in line yet.")}
          </span>
        )}
      </div>
    );
  } else if (kind === "service") {
    const svc = service(item.service ?? "");
    const name = svc?.label ?? item.service ?? "";
    const label = item.action === "kill" ? `kill -9 · ${name}`
      : item.action === "stop" ? t("Stop {name}", { name })
      : item.action === "restart" ? t("Restart {name}", { name })
      : t("Start {name}", { name });
    control = (
      <div className="mt-1.5">
        <button type="button" className={`btn ${item.action === "kill" ? "btn--danger" : "btn--solid"}`} disabled={busy}
                onClick={() => act(async () => {
                  const r = await api.service(item.service ?? "", item.action ?? "start");
                  return r.detail ?? "";
                })}>
          {busy ? t("Working…") : label}
        </button>
      </div>
    );
  } else if (kind === "look") {
    control = (
      <div className="mt-1.5">
        <button type="button" className="btn" onClick={() => item.look && focus(item.look)}>
          {t("Show {where}", { where: t(PANE_NAME[item.look as PaneTab] ?? item.look ?? "") })} →
        </button>
      </div>
    );
  } else if (kind === "run") {
    control = <RunItem slug={slug} task={task} index={index} command={item.run ?? ""} />;
  } else if (kind === "resume") {
    control = <ResumeItem />;
  } else if (kind === "clock") {
    const delay = item.clock?.in ?? 10;
    const every = item.clock?.every ?? 0;
    const trigger = !!item.clock?.trigger;
    control = (
      <div className="mt-1.5">
        <button type="button" className="btn btn--solid" disabled={busy}
                onClick={() => act(async () => {
                  const r = await api.service("clock", "restart", { delay, every, trigger });
                  return r.state === "stopped" ? t("The clock did not start; open its log on the left.") : t("The clock is set. Hands off the keyboard.");
                })}>
          {every ? t("Fire every {every}s, first in {delay}s", { every, delay }) : t("Fire once, {delay}s from now", { delay })}
        </button>
        <code className="inline-code ml-2 text-[0.72rem]">
          python -m monstertix.clock --in {delay}{every ? ` --every ${every}` : ""}{trigger ? " --trigger" : ""}
        </code>
        <ClockState />
      </div>
    );
  }

  return (
    <li className="flex gap-3 border-b py-3 last:border-b-0" style={{ borderColor: "var(--hairline)" }}>
      <span className="mt-[1px] grid h-6 w-6 shrink-0 place-items-center rounded-full font-mono text-[0.7rem] font-bold"
            style={{ background: "var(--overlay)", border: "1px solid var(--hairline-strong)", color: "var(--fg-muted)" }}
            title={kind}>
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        {item.text && (
          <p className="text-[0.92rem]" style={{ color: "var(--fg-muted)" }}>
            <span className="mr-1.5" aria-hidden>{ICON[kind]}</span>
            <Inline text={item.text} />
          </p>
        )}
        {control}
        {note && <p className="mt-1 text-[0.74rem]" style={{ color: "var(--fg-faint)" }}>{note}</p>}
      </div>
    </li>
  );
}

export function Turn({ items, slug, task }: { items: TurnItem[]; slug: string; task: string }) {
  return (
    <ol className="mt-2">
      {items.map((item, index) => (
        <Item key={index} item={item} slug={slug} task={task} index={index} />
      ))}
    </ol>
  );
}
