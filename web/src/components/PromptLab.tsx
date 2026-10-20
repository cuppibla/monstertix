import { useCallback, useEffect, useRef, useState } from "react";

import { api, type PromptTry, type Task } from "../lib/api";
import { useBench } from "../lib/bench";
import { t } from "../i18n";
import { Inline } from "./Inline";

/* Step 2's prompt lab. Pick a wording (or write one), swap it into
   PROACTIVE_INSTRUCTION, tell the agent the plan, then keep your hands off.
   Each try is a row: how many runs there were after it, how many of those you
   started by typing, and what the venue sold. Every wording ends the same way.

   The swap is the edit the codelab asks for in agent/concert/agent.py, made
   by the workbench, followed by a restart of the agent. */

const WATCH_SECONDS = 60;

function verdict(attempt: PromptTry): { text: string; color: string } {
  if (attempt.orders && attempt.orders > 0) {
    return { text: t("It bought inside a turn you started"), color: "var(--amber)" };
  }
  if (attempt.runs === 0) return { text: t("Nothing ran. You have not told it the plan yet"), color: "var(--fg-faint)" };
  return { text: t("Asleep: no run that you did not start"), color: "var(--red)" };
}

export function PromptLab({ slug, task, color }: { slug: string; task: Task; color: string }) {
  const { refresh, bump, focus } = useBench();
  const presets = task.prompts ?? [];
  const [text, setText] = useState(presets[0]?.text ?? "");
  const [label, setLabel] = useState(presets[0]?.label ?? "");
  const [tries, setTries] = useState<PromptTry[]>([]);
  const [using, setUsing] = useState(false);
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");
  const [watchUntil, setWatchUntil] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);
  const first = useRef(true);

  const load = useCallback(async () => {
    try {
      const state = await api.promptLab(slug, task.id);
      setTries(state.tries);
      setUsing(state.using);
      setProblem(state.error ?? "");
      // Arriving with a wording already swapped in: show that one.
      if (first.current && state.using && state.text) {
        setText(state.text);
        setLabel(presets.find((p) => p.text.trim() === state.text.trim())?.label ?? "");
      }
      first.current = false;
    } catch {
      /* the next poll tries again */
    }
  }, [slug, task.id, presets]);

  useEffect(() => {
    load();
    const poll = window.setInterval(() => document.visibilityState === "visible" && load(), 4000);
    return () => window.clearInterval(poll);
  }, [load]);

  useEffect(() => {
    if (!watchUntil) return;
    timer.current = window.setInterval(() => {
      setNow(Date.now());
      if (Date.now() >= watchUntil) {
        setWatchUntil(0);
        load();
      }
    }, 250);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [watchUntil, load]);

  async function swap() {
    setBusy("swap");
    setProblem("");
    try {
      const result = await api.promptSwap(slug, task.id, text, label || t("Your own wording"));
      if (!result.ok) setProblem(result.error ?? t("It did not swap."));
      await Promise.all([load(), refresh()]);
      bump();
    } catch {
      setProblem(t("The workbench did not answer."));
    } finally {
      setBusy("");
    }
  }

  async function restore() {
    setBusy("restore");
    try {
      await api.promptRestore(slug, task.id);
      setText(presets[0]?.text ?? "");
      setLabel(presets[0]?.label ?? "");
      await Promise.all([load(), refresh()]);
      bump();
    } finally {
      setBusy("");
    }
  }

  async function copyPlan() {
    try {
      await navigator.clipboard.writeText(task.say ?? "");
    } catch {
      /* the text is on screen to select by hand */
    }
    focus("agent");
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  const left = watchUntil ? Math.max(0, Math.ceil((watchUntil - now) / 1000)) : 0;

  return (
    <div className="mt-3">
      {task.explain && (
        <p className="mb-3 text-sm" style={{ color: "var(--fg-muted)" }}><Inline text={task.explain} /></p>
      )}

      <ol className="space-y-4">
        <li>
          <p className="text-[0.92rem] font-semibold">1 · {t("Pick a wording, or write your own")}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {presets.map((preset) => (
              <button key={preset.label} type="button" className="btn"
                      style={label === preset.label ? { borderColor: color, color } : undefined}
                      onClick={() => {
                        setText(preset.text);
                        setLabel(preset.label);
                      }}>
                {preset.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-sm" style={{color: "var(--fg-muted)"}}>
            Edit the text box below, then press Swap it in. The code viewer is read-only.
          </p>
          <textarea aria-label="Optional agent instruction" value={text} rows={8} spellCheck={false}
                    onChange={(e) => {
                      setText(e.target.value);
                      if (presets.some((p) => p.label === label && p.text !== e.target.value)) setLabel("");
                    }}
                    className="mt-2 w-full resize-y rounded-lg border px-3 py-2 font-mono text-[0.78rem] leading-relaxed outline-none"
                    style={{ background: "var(--viewer-bg)", color: "var(--viewer-fg)", borderColor: "var(--hairline-strong)" }} />
          <p className="mt-1 font-mono text-[0.68rem]" style={{ color: "var(--fg-faint)" }}>
            {t("becomes PROACTIVE_INSTRUCTION in {file}, with root_agent using it", { file: task.file ?? "" })}
          </p>
        </li>

        <li>
          <p className="text-[0.92rem] font-semibold">2 · {t("Swap it in")}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button type="button" className="btn btn--solid" style={{ background: color, borderColor: color }}
                    disabled={!!busy || !text.trim()} onClick={swap}>
              {busy === "swap" ? t("Restarting the agent…") : t("Swap it in and restart the agent")}
            </button>
            {using && (
              <button type="button" className="btn" disabled={!!busy} onClick={restore}>
                {busy === "restore" ? t("Restoring…") : t("Put the original file back")}
              </button>
            )}
          </div>
          {problem && <p className="mt-1 text-[0.8rem]" style={{ color: "var(--bad)" }}>{problem}</p>}
        </li>

        <li>
          <p className="text-[0.92rem] font-semibold">3 · {t("Tell it the plan in a new session, then hands off")}</p>
          {task.say && (
            <div className="mt-2 flex items-start gap-2 rounded-lg border px-3 py-2"
                 style={{ borderColor: "var(--hairline)", background: "var(--overlay)" }}>
              <span className="flex-1 text-[0.9rem]">{task.say}</span>
              <button type="button" className="btn shrink-0" onClick={copyPlan}>
                {copied ? t("Copied") : t("Copy · go to {where}", { where: t("ADK web UI") })}
              </button>
            </div>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button type="button" className="btn" disabled={!!watchUntil}
                    onClick={() => setWatchUntil(Date.now() + WATCH_SECONDS * 1000)}>
              {watchUntil ? t("Hands off… {s}s", { s: left }) : t("I sent it. Start the {s}s wait", { s: WATCH_SECONDS })}
            </button>
            {watchUntil > 0 && <div className="working-bar h-[3px] flex-1 rounded-full" aria-hidden />}
          </div>
        </li>
      </ol>

      <div className="mt-5 overflow-x-auto rounded-xl border" style={{ borderColor: "var(--hairline)" }}>
        <table className="w-full text-left text-[0.82rem]">
          <thead>
            <tr style={{ color: "var(--fg-faint)" }}>
              {["#", t("Wording"), t("Runs"), t("Started by you"), t("Tickets"), t("What happened")].map((h) => (
                <th key={h} className="px-3 py-2 font-mono text-[0.64rem] font-medium uppercase tracking-[0.14em]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tries.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-3" style={{ color: "var(--fg-faint)" }}>{t("No wording tried yet.")}</td></tr>
            ) : (
              tries.map((attempt, index) => {
                const v = verdict(attempt);
                return (
                  <tr key={attempt.started} className="border-t align-top" style={{ borderColor: "var(--hairline)" }}>
                    <td className="px-3 py-2 font-mono">{index + 1}</td>
                    <td className="px-3 py-2" title={attempt.text}>
                      {attempt.label || attempt.text.split("\n").find((l) => l.trim())?.slice(0, 60)}
                      {attempt.tools.length > 0 && (
                        <span className="block font-mono text-[0.68rem]" style={{ color: "var(--fg-faint)" }}>{attempt.tools.join(", ")}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono">{attempt.runs}</td>
                    <td className="px-3 py-2 font-mono">{attempt.byYou}</td>
                    <td className="px-3 py-2 font-mono">{attempt.orders ?? "?"}</td>
                    <td className="px-3 py-2" style={{ color: v.color }}>{v.text}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
