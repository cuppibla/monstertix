import { useCallback, useEffect, useState, type ReactNode } from "react";

import { api, type ResumeResult, type TaskSummary } from "../lib/api";
import { useBench } from "../lib/bench";
import { t } from "../i18n";
import { refreshAgentSession } from "./AppFrame";

/* The current task, read from the session store every few seconds: which
   session it is, what it is paused on, the ticket, the authorization, the
   order. Nothing here is remembered by the page; a reload shows the same.

   "Resume current task" answers a queue wait, and only a queue wait, in the
   session that holds it: the same function_response the ADK web UI's answer
   box sends. A wait on a person stays a wait on a person. */

export function useTask(every = 3000): { task: TaskSummary | null; error: boolean; reload: () => Promise<void> } {
  const [task, setTask] = useState<TaskSummary | null>(null);
  const [error, setError] = useState(false);
  const { epoch } = useBench();
  const reload = useCallback(async () => {
    try {
      setTask(await api.task());
      setError(false);
    } catch {
      setError(true);
    }
  }, []);
  useEffect(() => {
    reload();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") reload();
    }, every);
    return () => clearInterval(timer);
  }, [reload, every, epoch]);
  return { task, error, reload };
}

function shortId(id: string | null): string {
  if (!id) return "—";
  return id.length > 14 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id;
}

function whyNot(task: TaskSummary | null): string {
  if (!task || !task.session_id) return t("No task yet: start one in the section before this one.");
  if (!task.pending && task.last_order) return "Order complete. There is no queue wait left to resume.";
  if (!task.pending && task.ready_to_buy) return "Complete: the task reached the front of the queue. Nothing has been bought.";
  if (!task.pending) return t("Nothing is paused.");
  if (task.pending.kind === "person") return t("Waiting for you: answer the pending event.");
  if (task.pending.kind !== "queue") return t("Paused on something that is not a queue wait.");
  return "";
}

/** The button alone: in the task card, and as a `resume: task` turn item. */
export function ResumeButton({ task, onDone, solid = true }: {
  task: TaskSummary | null;
  onDone?: (result: ResumeResult) => void;
  solid?: boolean;
}) {
  const { refresh } = useBench();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const blocked = whyNot(task);

  async function resume() {
    setBusy(true);
    setNote("");
    try {
      const result = await api.taskResume(task?.session_id ?? undefined);
      if (result.ok) {
        const said = (result.said ?? []).slice(-1)[0];
        setNote(t("Resumed via {via}.", { via: result.via ?? "" }) + (said ? ` ${said}` : ""));
        if (result.session_id) refreshAgentSession(result.session_id);
      } else {
        setNote(result.reason ?? t("It did not resume."));
      }
      onDone?.(result);
      await refresh();
    } catch {
      setNote(t("The workbench did not answer."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className={`btn ${solid ? "btn--solid" : ""}`} disabled={busy || !!blocked} onClick={resume}
              title={blocked || t("Answers the queue wait in the session that holds it")}>
        {busy ? t("Resuming…") : t("Resume current task")}
      </button>
      {blocked && !busy && <span className="text-[0.76rem]" role="status"
        style={{ color: !task?.pending && (task?.ready_to_buy || task?.last_order) ? "var(--ok)" : "var(--fg-faint)" }}>{blocked}</span>}
      {note && <span className="text-[0.76rem]" style={{ color: "var(--fg-muted)" }}>{note}</span>}
    </div>
  );
}

function Row({ label, children, mono = false }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-3 py-1 text-[0.86rem]">
      <span className="w-28 shrink-0 text-[0.72rem] uppercase tracking-wide" style={{ color: "var(--fg-faint)" }}>{label}</span>
      <span className={`min-w-0 flex-1 ${mono ? "font-mono text-[0.8rem]" : ""}`} style={{ color: "var(--fg)" }}>{children}</span>
    </div>
  );
}

function orderText(order: Record<string, unknown> | string | null): string {
  if (!order) return "—";
  if (typeof order === "string") return order;
  const seats = order.seats ?? "?";
  const section = order.section ?? "?";
  const event = order.event_id ?? "";
  const id = order.order_id ?? order.id ?? "";
  const total = typeof order.total === "number" ? ` · $${order.total}` : "";
  const dup = order.duplicate ? ` · ${t("duplicate")}` : "";
  return `${seats} × ${t("section")} ${section} · ${event}${total}${id ? ` · ${id}` : ""}${dup}`;
}

export function TaskCard() {
  const { task, reload } = useTask(3000);
  const paused = task?.paused;
  const tone = paused === "queue" ? "var(--amber)" : paused === "you" ? "var(--accent)" : "var(--fg-faint)";
  const pausedText = paused === "queue" ? t("the queue") : paused === "you" ? t("you") : paused === "other" ? t("something else") : "—";

  return (
    <section className="my-6 rounded-2xl border p-5" style={{ borderColor: "var(--hairline)", background: "var(--card)" }}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="kicker" style={{ color: tone }}>{t("Current task")}</div>
          <p className="mt-1 text-[0.95rem] font-medium" style={{ color: "var(--fg)" }}>
            {task?.kind_label ?? t("loading…")}
          </p>
          {paused === "queue" && (
            <p className="mt-1 max-w-xl text-[0.8rem]" style={{ color: "var(--fg-muted)" }}>
              {t("The run stopped itself at check_front and wrote that to the session store. No process is holding the place in line; the venue is. Resume answers the wait and lets it check again.")}
            </p>
          )}
          {paused === "you" && (
            <p className="mt-1 max-w-xl text-[0.8rem]" style={{ color: "var(--fg-muted)" }}>
              {t("The run stopped itself to ask you something. Answer the pending event in ADK; Resume cannot answer for you.")}
            </p>
          )}
        </div>
        <ResumeButton task={task} onDone={() => reload()} />
      </div>
      <div className="mt-3 border-t pt-2" style={{ borderColor: "var(--hairline)" }}>
        <Row label={t("session")} mono>
          <span title={task?.session_id ?? ""}>{shortId(task?.session_id ?? null)}</span>
          {task?.invocations ? <span style={{ color: "var(--fg-faint)" }}> · {t("{n} run(s)", { n: task.invocations })}</span> : null}
          {task?.store ? <span style={{ color: "var(--fg-faint)" }}> · {task.store}</span> : null}
        </Row>
        <Row label={t("paused on")}>
          <span style={{ color: tone }}>{pausedText}</span>
          {task?.pending ? <span className="font-mono text-[0.74rem]" style={{ color: "var(--fg-faint)" }}> · {task.pending.id}</span> : null}
        </Row>
        <Row label={t("ticket")} mono>
          {task?.queue_ticket ? `${task.queue_ticket}${task.queue_event_id ? ` · ${task.queue_event_id}` : ""}` : "—"}
        </Row>
        <Row label={t("authorization")}>{task?.authorization_text || "—"}</Row>
        <Row label={t("ready to buy")}>{task?.ready_to_buy ? t("yes") : "—"}</Row>
        <Row label={t("last order")}>{orderText(task?.last_order ?? null)}</Row>
      </div>
    </section>
  );
}
