import { useState } from "react";

import { isUp, useBench, type WorldTab } from "../lib/bench";
import { APPS, AppFrame, frameHref } from "./AppFrame";
import { ServiceControls, ServiceLog } from "./ServiceControls";
import { t } from "../i18n";

/* The left column of every page: the world the agent acts on, live. Two
   apps, in tabs: the venue panel (the ticket seller, always on) and the
   MonsterTix page (your own server, from Chapter 2). Both frames are kept
   once opened, so a conversation survives a change of section.

   The ADK web UI is not here: it is a development window, not part of the
   world, and opens in a drawer from the button at the top right. */

const TABS: WorldTab[] = ["venue", "monstertix"];

export function WorldRail() {
  const { service, railOpen, setRailOpen, railTab, setRailTab, guided } = useBench();
  const [opened, setOpened] = useState<Set<WorldTab>>(() => new Set([railTab]));
  const [versions, setVersions] = useState<Record<string, number>>({});
  const [logOpen, setLogOpen] = useState(false);

  if (!opened.has(railTab)) setOpened(new Set(opened).add(railTab));

  if (!railOpen) {
    return (
      <div className="flex h-full flex-col items-center gap-3 pt-3">
        <button type="button" className="btn px-1.5" title={t("Show the world")} onClick={() => setRailOpen(true)}>›</button>
        {TABS.map((id) => (
          <span key={id} className="dot" title={t(APPS[id].label)}
                style={{ background: isUp(service(APPS[id].service)) ? "var(--ok)" : "var(--fg-faint)" }} />
        ))}
      </div>
    );
  }

  const app = APPS[railTab];
  const svc = service(app.service);
  const up = isUp(svc);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b px-2 py-1.5" style={{ borderColor: "var(--hairline)" }}>
        {TABS.map((id) => {
          const active = id === railTab;
          return (
            <button key={id} type="button" onClick={() => setRailTab(id)}
                    className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[0.78rem]"
                    style={{ background: active ? "var(--overlay)" : "transparent",
                             color: active ? "var(--fg)" : "var(--fg-muted)", fontWeight: active ? 600 : 400 }}>
              <span className="dot" style={{ width: 6, height: 6,
                    background: isUp(service(APPS[id].service)) ? "var(--ok)" : "var(--fg-faint)" }} />
              {t(APPS[id].label)}
            </button>
          );
        })}
        <div className="ml-auto flex items-center gap-1.5">
          {up && (
            <>
              <button type="button" className="btn" title={t("Reload")}
                      onClick={() => setVersions((v) => ({ ...v, [railTab]: (v[railTab] ?? 0) + 1 }))}>↻</button>
              <a className="btn" href={frameHref(railTab)} target="_blank" rel="noreferrer" title={t("Open in a new tab")}>↗</a>
            </>
          )}
          <button type="button" className="btn px-1.5" title={t("Hide the world")} onClick={() => setRailOpen(false)}>‹</button>
        </div>
      </div>

      {guided && <div className="guide-world-task">
        <b>{guided.slug === "cloud" ? "Local venue · cloud demo uses its own venue" : "This chapter's task"}</b>
        <span>{guided.status}</span>
        {guided.sessionId && <code>{guided.sessionId}</code>}
        {guided.sessionId && <div className="guide-world-metrics"><div><strong>{guided.invocations}</strong><span>invocations</span></div>
          <div><strong>{guided.orders??"—"}</strong><span>venue orders</span></div></div>}
        {guided.position!==null&&<span>Queue position · {guided.position.toLocaleString()} people ahead, not seconds</span>}
        {guided.ticket && <span>Queue ticket · <code>{guided.ticket}</code></span>}
        {guided.orders !== null && <span>{guided.orders} orders in the local venue</span>}
      </div>}
      {/* The venue starts with the workbench and is always on; MonsterTix has a switch. */}
      {railTab === "monstertix" && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-1.5" style={{ borderColor: "var(--hairline)" }}>
          <span className="text-[0.72rem]" style={{ color: "var(--fg-faint)" }}>{t("Your own server and page")}</span>
          <ServiceControls name="monstertix" log={logOpen} onLog={setLogOpen} />
        </div>
      )}
      {railTab === "monstertix" && logOpen && (
        <div className="border-b px-3 py-2" style={{ borderColor: "var(--hairline)" }}>
          <ServiceLog name="monstertix" command={svc?.command} />
        </div>
      )}

      <div className="relative min-h-0 flex-1">
        {TABS.map((id) =>
          opened.has(id) ? (
            <div key={id} className="absolute inset-0" hidden={id !== railTab}>
              <AppFrame id={id} version={versions[id] ?? 0} />
            </div>
          ) : null,
        )}
      </div>
    </div>
  );
}
