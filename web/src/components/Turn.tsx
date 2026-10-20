import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, type Job, type PaneTab, type TurnItem } from "../lib/api";
import { useBench } from "../lib/bench";
import { ClockAction } from "./ClockAction";
import { stateText, DOT } from "./ServiceControls";
import { refreshAgentSession } from "./AppFrame";
import { ResumeButton, useTask } from "./TaskCard";
import { t } from "../i18n";
import { Inline } from "./Inline";
import { preparePurchaseScenario } from "../lib/purchaseScenario";

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
  scenario: "⚙",
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
  if (item.scenario) return "scenario";
  return "text";
}

/* `resume: task`: the task card's button, in the numbered list. */
function ResumeItem() {
  const { task, reload } = useTask(3000);
  return (
    <div className="mt-1.5">
      <ResumeButton task={task} onDone={() => reload()} />
      {task?.queue_ticket && <p className="mt-2 text-xs" style={{color:"var(--fg-muted)"}}>
        Ticket: <code>{task.queue_ticket}</code> · Session: <code>{task.session_id}</code>
      </p>}
    </div>
  );
}

function PurchaseScenario() {
  const {task, reload} = useTask();
  const {stage, setDrawerOpen} = useBench();
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState<string[]>([]);
  const [prepared, setPrepared] = useState<string | null>(null);
  const [error, setError] = useState("");
  const ready = !!prepared && prepared === task?.session_id;
  const blocked = stage?.step !== 5 ? "Load chapter 5 first."
    : task?.last_order ? "The order is already placed. Inspect its Events."
    : task?.pending?.kind !== "queue" ? "Start the task in ADK and answer its budget questions first."
    : "";
  useEffect(()=>{setSteps([]);setPrepared(null);setError("");}, [task?.session_id]);
  async function prepare() {
    if (busy || !task?.session_id) return;
    setBusy(true);setSteps([]);setPrepared(null);setError("");
    try {
      await preparePurchaseScenario(api, task.session_id, label=>setSteps(value=>[...value,label]));
      setPrepared(task.session_id);
    } catch(e) {setError((e as Error).message);}
    finally {setBusy(false);await reload();}
  }
  return <div className="mt-2">
    <button className="btn btn--venue" disabled={busy||!!blocked||ready} onClick={prepare}>
      {busy?"Preparing…":ready?"Scenario ready":"Prepare the changing-world scenario"}
    </button>
    {blocked&&<p className="mt-2 text-xs" style={{color:"var(--fg-muted)"}}>{blocked}</p>}
    {blocked && !task?.last_order && <Link className="btn mt-2 inline-flex" to="/step/buy/a"
      onClick={() => setDrawerOpen(false)}>Go to 5a · start the task and confirm the budget →</Link>}
    {steps.length>0&&<ul className="mt-2 text-xs" aria-live="polite">{steps.map(label=><li key={label}>✓ {label}</li>)}</ul>}
    {error&&<p className="mt-2 text-sm" role="alert" style={{color:"var(--bad)"}}>{error}</p>}
    {ready&&task?.pending?.kind==="queue"&&<div className="mt-3">
      <p className="mb-2 text-sm">The agent is still paused. Resume once, then inspect the purchase responses in ADK.</p>
      <ResumeButton task={task} onDone={()=>reload()}/></div>}
    {ready&&!!task?.last_order&&<p className="mt-3 text-sm">
      The order is complete. Inspect its purchase responses in ADK, then continue to Once.
    </p>}
  </div>;
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

/** Read the actual file beside the instruction, including inside the ADK drawer. */
function InspectFile({ path }: { path: string }) {
  const [lines, setLines] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function read() {
    setBusy(true);
    setError("");
    try {
      const result = await api.fileRead(path);
      if (result.error || !result.lines) throw new Error(result.error || "The file could not be read.");
      setLines(result.lines);
    } catch(e) {
      setLines(null);
      setError((e as Error).message);
    } finally { setBusy(false); }
  }
  return <div className="mt-2">
    <button type="button" className="btn" disabled={busy} onClick={read}>
      {busy ? "Reading…" : lines ? "Read latest memory" : "Show memory file"}
    </button>
    {error && <p role="alert" className="mt-1 text-sm" style={{color:"var(--bad)"}}>{error}</p>}
    {lines && <div className="mt-2">
      <p className="text-xs" style={{color:"var(--fg-faint)"}}>{path} · read-only · read when you click</p>
      <pre className="log quiet-scroll mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg p-2">{lines.join("\n")}</pre>
    </div>}
  </div>;
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
  const { refresh, service, focus, setDrawerOpen, bump } = useBench();
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
            {t("Nobody is in line yet. Start the task first; the section before this one does that.")}
          </span>
        )}
      </div>
    );
  } else if (kind === "service") {
    const svc = service(item.service ?? "");
    const name = svc?.label ?? item.service ?? "";
    const alreadyRunning = (item.action ?? "start") === "start" && ["running", "external", "remote"].includes(svc?.state ?? "");
    const starting = (item.action ?? "start") === "start" && svc?.state === "starting";
    const alreadyStopped = ["kill", "stop"].includes(item.action ?? "") && svc?.state === "stopped";
    const label = item.action === "kill" ? `kill -9 · ${name}`
      : item.action === "stop" ? t("Stop {name}", { name })
      : item.action === "restart" ? t("Restart {name}", { name })
      : t("Start {name}", { name });
    control = (
      <div className="mt-1.5">
        <button type="button" className={`btn ${item.action === "kill" ? "btn--danger" : "btn--solid"}`} disabled={busy || alreadyRunning || starting || alreadyStopped}
                onClick={() => act(async () => {
                  const r = await api.service(item.service ?? "", item.action ?? "start");
                  bump();
                  return ["running", "starting", "stopped"].includes(r.state) ? "" : r.detail ?? "";
                })}>
          {busy ? t("Working…") : starting ? `Starting ${name}…` : alreadyRunning ? `${name} is running` : label}
        </button>
        {svc && <p className="mt-2 text-sm" role="status" style={{color: DOT[svc.state]}}>
          {name}: {stateText(svc)}
          {svc.state === "stopped" && item.service === "agent" ? ". The saved task remains in the session database." : ""}
        </p>}
      </div>
    );
  } else if (kind === "look") {
    control = (
      <div className="mt-1.5">
        <button type="button" className="btn" disabled={busy} onClick={() => item.inspectTask ? act(async () => {
          const task = await api.task();
          if (!task.session_id) return "No task found. Start this chapter's task first.";
          refreshAgentSession(task.session_id);
          focus("agent");
          return "";
        }) : item.look && focus(item.look)}>
          {item.inspectTask ? "Open this task in ADK" : t("Show {where}", { where: t(PANE_NAME[item.look as PaneTab] ?? item.look ?? "") })} →
        </button>
      </div>
    );
  } else if (kind === "run") {
    control = <RunItem slug={slug} task={task} index={index} command={item.run ?? ""} />;
  } else if (kind === "resume") {
    control = <ResumeItem />;
  } else if (kind === "scenario") {
    control = <PurchaseScenario />;
  } else if (kind === "clock") {
    control = <ClockAction settings={item.clock ?? {}} />;
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
        {item.inspectFile && <InspectFile path={item.inspectFile} />}
        {item.next && <Link className="btn mt-2 inline-flex" to={item.next.to} onClick={() => setDrawerOpen(false)}>
          {item.next.label} →
        </Link>}
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
