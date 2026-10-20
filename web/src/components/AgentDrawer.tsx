import { useEffect, useState } from "react";

import { isUp, useBench } from "../lib/bench";
import { APPS, AppFrame, frameHref } from "./AppFrame";
import { ServiceControls, ServiceLog } from "./ServiceControls";
import { t } from "../i18n";

/* The ADK web UI, in a drawer from the right. It is the development window
   into a run (chat, Events, State, the graph), not part of the world, so it
   is not in the left column: the button at the top right opens it over the
   reading, and Esc or × puts it away. The frame is kept while the drawer is
   closed, so the conversation is where you left it. */

export function AgentDrawer() {
  const { service, drawerOpen, setDrawerOpen } = useBench();
  const [version, setVersion] = useState(0);
  const [logOpen, setLogOpen] = useState(false);
  const [opened, setOpened] = useState(false);
  const svc = service(APPS.agent.service);
  const up = isUp(svc);

  if (drawerOpen && !opened) setOpened(true);

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
    <aside className="drawer" data-open={drawerOpen} aria-hidden={!drawerOpen} aria-label={t("ADK web UI")}>
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2" style={{ borderColor: "var(--hairline)" }}>
        <span className="flex items-center gap-2 text-[0.82rem] font-semibold">
          <span className="dot" style={{ width: 6, height: 6, background: up ? "var(--ok)" : "var(--fg-faint)" }} />
          {t("ADK web UI")}
        </span>
        <span className="hidden text-[0.72rem] sm:inline" style={{ color: "var(--fg-faint)" }}>
          {t("the development window into a run")}
        </span>
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
      <div className="relative min-h-0 flex-1">
        <AppFrame id="agent" version={version} />
      </div>
    </aside>
  );
}
