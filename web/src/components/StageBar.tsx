import { useState } from "react";

import { api } from "../lib/api";
import { useBench } from "../lib/bench";
import { shown } from "../lib/numbers";
import { t } from "../i18n";

/* Which step's code is in agent/, and the button that loads the one this
   page needs. Loading is what the codelab does at the top of every chapter:
   stop the agent, RESET THE VENUE, `./use-solution.sh N --force`, start the
   agent again. The output is kept, so a student can read what it changed.

   With scope="venue" the same bar only resets the venue (orders, queue,
   inventory): the code, the sessions and the memory file stay, and no
   process is touched. That is how an experiment starts from a clean venue
   without losing the task under way. */

export function StageBar({ step, color, prominent = false, scope = "all" }: {
  step: number;
  color: string;
  prominent?: boolean;
  scope?: "all" | "venue";
}) {
  const { stage, refresh, bump } = useBench();
  const [busy, setBusy] = useState(false);
  const [output, setOutput] = useState("");
  const [failed, setFailed] = useState(false);
  const [showOutput, setShowOutput] = useState(false);

  if (!stage) return null;
  const venueOnly = scope === "venue";
  const matches = stage.step === step;
  // Two stages can share an agent; the bar only asks for a load when the code differs.
  const loadedText = stage.step === null
    ? t("No step's code is in agent/.")
    : stage.edited
      ? t("agent/ holds step {n}, with your edits.", { n: shown(stage.step) })
      : t("agent/ holds step {n}.", { n: shown(stage.step) });

  async function load() {
    setBusy(true);
    setFailed(false);
    try {
      const result = await api.stageLoad(step, true, scope);
      setOutput(result.output);
      setFailed(!result.ok);
      setShowOutput(!result.ok);
      await refresh();
      bump();
    } catch {
      setFailed(true);
      setOutput(t("The workbench did not answer."));
    } finally {
      setBusy(false);
    }
  }

  // A venue-only reset is never a warning: the code in place is not its business.
  const calm = matches || venueOnly;
  return (
    <div
      className={`mb-3 rounded-xl border ${prominent ? "px-4 py-3.5" : "px-3.5 py-2"}`}
      style={{
        borderColor: calm ? "var(--hairline)" : "color-mix(in srgb, var(--amber) 55%, transparent)",
        background: calm ? "var(--overlay)" : "color-mix(in srgb, var(--amber) 9%, transparent)",
      }}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm" style={{ color: "var(--fg-muted)" }}>
        <span>
          {venueOnly
            ? t("Reset the venue (orders, queue, inventory). Code, sessions and memory stay.")
            : <>{loadedText}{" "}{matches ? (stage.edited ? "" : t("That is this step's code.")) : t("This step uses step {n}.", { n: shown(step) })}</>}
        </span>
        {(!matches || venueOnly) && <button
          type="button"
          onClick={load}
          disabled={busy}
          className={`ml-auto btn ${matches && !prominent && !venueOnly ? "" : "btn--solid"}`}
          style={matches && !prominent && !venueOnly ? undefined : { background: color, borderColor: color }}
        >
          {busy ? (venueOnly ? t("Resetting…") : t("Loading…"))
            : venueOnly ? t("Reset the venue")
            : matches ? t("Reload step {n}", { n: shown(step) }) : t("Load step {n}", { n: shown(step) })}
        </button>}
      </div>
      {matches && !venueOnly && (
        <details className="mt-2 text-sm">
          <summary style={{color:"var(--fg-faint)"}}>Need to start this chapter over?</summary>
          <p className="mt-2" style={{color:"var(--fg-muted)"}}>
            This resets the venue, clears the current sessions and restores the chapter's code and memory.
            Keep the current task when continuing to the next section. This is not a page refresh.
          </p>
          <button type="button" className="btn mt-2" disabled={busy} onClick={load}>
            {busy ? t("Loading…") : `Reset chapter ${shown(step)} and start over`}
          </button>
        </details>
      )}
      {prominent && (!matches || venueOnly) && (
        <p className="mt-1.5 text-[0.74rem]" style={{ color: "var(--fg-faint)" }}>
          {venueOnly
            ? (matches
                ? t("Presses RESET THE VENUE and nothing else. The agent keeps running; the current session keeps its ticket and authorization.")
                : t("Presses RESET THE VENUE and nothing else. This chapter expects step {n}'s code; load it from an earlier section if agent/ holds something else.", { n: shown(step) }))
            : t("Stops the agent, presses RESET THE VENUE, runs ./use-solution.sh {n} --force, and starts the agent again.", { n: step })}
        </p>
      )}
      {busy && <div className="working-bar mt-2 h-[3px] w-full rounded-full" aria-hidden />}
      {output && (
        <div className="mt-2">
          <button type="button" className="text-[0.72rem] underline" style={{ color: failed ? "var(--bad)" : "var(--fg-faint)" }}
                  onClick={() => setShowOutput(!showOutput)}>
            {failed ? t("It did not load. What it printed") : showOutput ? t("Hide what it printed") : t("What it printed")}
          </button>
          {showOutput && <pre className="log quiet-scroll mt-1.5 max-h-64 overflow-auto rounded-lg p-2.5">{output}</pre>}
        </div>
      )}
    </div>
  );
}
