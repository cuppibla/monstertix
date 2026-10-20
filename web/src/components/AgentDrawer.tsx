import { useEffect, useState } from "react";

import { isUp, useBench } from "../lib/bench";
import { APPS, AppFrame, frameHref } from "./AppFrame";
import { ServiceControls, ServiceLog } from "./ServiceControls";
import type { Exercise } from "../lib/api";
import { TaskView } from "./Exercise";
import { Inline } from "./Inline";
import { t } from "../i18n";

/* The ADK web UI, in a drawer from the right. It is the development window
   into a run (chat, Events, State, the graph), not part of the world, so it
   is not in the left column: the button at the top right opens it over the
   reading, and Esc or × puts it away. The frame is kept while the drawer is
   closed, so the conversation is where you left it.

   The drawer covers the reading, so the section's steps can ride along: a
   column on its left with every "Your turn" list of the section, buttons
   included. **Steps** at the top shows or hides it. */

function stored(key: string, fallback: boolean): boolean {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value === "true";
  } catch {
    return fallback;
  }
}

/* The section's "Your turn" cards, in order, every task but the code viewer. */
function Steps() {
  const { current } = useBench();
  const cards = (current?.exercises ?? []).filter(({ exercise }) => exercise.tasks.length > 0);
  if (!current || cards.length === 0) {
    return (
      <p className="px-4 py-6 text-[0.8rem]" style={{ color: "var(--fg-faint)" }}>
        {t("This section has nothing to do yet. The reading is behind the drawer.")}
      </p>
    );
  }
  const prepared = (exercise: Exercise) => exercise.tasks.some((task) => task.kind === "prepare");
  return (
    <div className="px-4 py-3">
      {cards.map(({ id, exercise }, index) => (
        <section key={id} className="mb-7 border-b pb-6 last:border-b-0" style={{ borderColor: "var(--hairline)" }}>
          <div className="kicker" style={{ color: "var(--accent)" }}>
            {t("Your turn")}{cards.length > 1 ? ` · ${index + 1} / ${cards.length}` : ""}
          </div>
          {exercise.title && <h3 className="mt-1 text-[0.95rem] font-semibold leading-snug">{exercise.title}</h3>}
          {exercise.needs && (
            <p className="mt-1 text-[0.78rem]" style={{ color: "var(--amber)" }}>
              {t("Needs")}: <Inline text={exercise.needs.trim()} />
            </p>
          )}
          {exercise.intro && (
            <p className="mt-1 text-[0.8rem]" style={{ color: "var(--fg-muted)" }}><Inline text={exercise.intro.trim()} /></p>
          )}
          <div className="text-[0.86rem]">
            {exercise.tasks.map((task) => (
              <TaskView key={task.id} task={task} slug={current.slug} color="var(--accent)" prepared={prepared(exercise)} compact />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function AgentDrawer() {
  const { service, drawerOpen, setDrawerOpen } = useBench();
  const [version, setVersion] = useState(0);
  const [logOpen, setLogOpen] = useState(false);
  const [opened, setOpened] = useState(false);
  const [steps, setStepsState] = useState(() => stored("monstertix.drawer.steps", true));
  const svc = service(APPS.agent.service);
  const up = isUp(svc);

  if (drawerOpen && !opened) setOpened(true);

  const setSteps = (on: boolean) => {
    setStepsState(on);
    try {
      localStorage.setItem("monstertix.drawer.steps", String(on));
    } catch {
      /* the page works without it */
    }
  };

  useEffect(() => {
    if (!drawerOpen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setDrawerOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen, setDrawerOpen]);

  if (!opened) return null;

  return (
    <aside className="drawer" data-open={drawerOpen} data-steps={steps} aria-hidden={!drawerOpen} aria-label={t("ADK web UI")}>
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2" style={{ borderColor: "var(--hairline)" }}>
        <span className="flex items-center gap-2 text-[0.82rem] font-semibold">
          <span className="dot" style={{ width: 6, height: 6, background: up ? "var(--ok)" : "var(--fg-faint)" }} />
          {t("ADK web UI")}
        </span>
        <span className="hidden text-[0.72rem] sm:inline" style={{ color: "var(--fg-faint)" }}>
          {t("the development window into a run")}
        </span>
        <button type="button" className="btn" aria-pressed={steps} onClick={() => setSteps(!steps)}
                style={steps ? { color: "var(--fg)", borderColor: "var(--fg-faint)" } : undefined}
                title={t("Show this section's steps beside the dev UI")}>
          {steps ? t("Hide steps") : t("Show steps")}
        </button>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          {up && (
            <>
              <button type="button" className="btn" title={t("Reload")} onClick={() => setVersion((v) => v + 1)}>↻</button>
              <a className="btn" href={frameHref("agent")} target="_blank" rel="noreferrer" title={t("Open in a new tab")}>↗</a>
            </>
          )}
          <ServiceControls name="agent" log={logOpen} onLog={setLogOpen} />
          <button type="button" className="btn px-2" title={t("Close")} onClick={() => setDrawerOpen(false)}>×</button>
        </div>
      </div>
      {logOpen && (
        <div className="border-b px-3 py-2" style={{ borderColor: "var(--hairline)" }}>
          <ServiceLog name="agent" command={svc?.command} />
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        {steps && (
          <div className="drawer__steps quiet-scroll w-[26rem] shrink-0 overflow-y-auto border-r"
               style={{ borderColor: "var(--hairline)", background: "var(--stage)" }}>
            <Steps />
          </div>
        )}
        <div className="relative min-h-0 min-w-0 flex-1">
          <AppFrame id="agent" version={version} />
        </div>
      </div>
    </aside>
  );
}
