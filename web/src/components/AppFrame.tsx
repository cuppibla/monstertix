import { useEffect, useRef, useState } from "react";

import type { PaneTab } from "../lib/api";
import { isUp, useBench } from "../lib/bench";
import { t } from "../i18n";

/* One real app, framed. Each app is a separate process reached through the
   workbench at /svc/<name>/, so the frame is same-origin and only one port
   has to be open.

   The frame lives in the world column or the drawer, both mounted once for
   the whole course, so a conversation survives moving between sections. It
   reloads when its process comes back. The ADK web UI reopens the session
   that was going, the way a student would pick it from the session list
   after a restart. */

export const APPS: Record<PaneTab, { label: string; path: string; service: string }> = {
  agent: { label: "ADK web UI", path: "/svc/agent/dev-ui/?app=concert", service: "agent" },
  venue: { label: "Venue panel", path: "/svc/venue/panel", service: "venue" },
  monstertix: { label: "MonsterTix", path: "/svc/monstertix/", service: "monstertix" },
};

/** Where a frame has got to, so a reload lands on the same screen. */
const where: Partial<Record<PaneTab, string>> = {};

export function frameHref(id: PaneTab): string {
  return where[id] ?? APPS[id].path;
}

export function AppFrame({ id, version = 0, onReload }: {
  id: PaneTab;
  /** Bumped by the owner to force a fresh frame (the ↻ button). */
  version?: number;
  /** Called when the process came back and the frame reloaded itself. */
  onReload?: () => void;
}) {
  const { service, guided } = useBench();
  const boundSession = guided?.sessionId;
  const app = APPS[id];
  const svc = service(app.service);
  const up = isUp(svc);
  const frame = useRef<HTMLIFrameElement>(null);
  const [generation, setGeneration] = useState(0);
  const wasUp = useRef<boolean | null>(null);
  // The src is fixed for the life of one frame. If it followed `where`, the
  // next re-render after the dev UI put `?session=` in its URL would set a new
  // src, which navigates the frame: a reload that cancels the run in flight
  // (ADK logs "Root node concert was cancelled"). A fresh frame (new key)
  // starts from wherever the last one had got to.
  const [src, setSrc] = useState(() => frameHref(id));
  useEffect(() => setSrc(frameHref(id)), [id, version, generation]);

  useEffect(() => {
    if (id === "agent" && boundSession) {
      const target = `${APPS.agent.path}&session=${encodeURIComponent(boundSession)}`;
      where.agent = target;
      setSrc(target);
    }
  }, [id, boundSession]);

  // Remember where the frame had got to (the dev UI keeps its session in the URL).
  useEffect(() => {
    const timer = setInterval(() => {
      try {
        const url = frame.current?.contentWindow?.location;
        if (url && url.pathname.startsWith("/svc/")) where[id] = url.pathname + url.search + url.hash;
      } catch {
        /* not loaded yet */
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [id]);

  // A process that comes back (restarted, or started after a kill) gets a fresh frame.
  useEffect(() => {
    // The services list has not arrived yet: nothing has come back, it is not known yet.
    if (!svc) return;
    if (wasUp.current === false && up) {
      const reload = () => {
        setGeneration((n) => n + 1);
        onReload?.();
      };
      if (id === "agent" && boundSession) {
        where.agent = `${APPS.agent.path}&session=${encodeURIComponent(boundSession)}`;
        reload();
      } else if (id === "agent" && !guided) {
        fetch("/svc/agent/apps/concert/users/user/sessions")
          .then((r) => r.json())
          .then((sessions: { id: string; lastUpdateTime?: number }[]) => {
            const latest = [...sessions].sort((a, b) => (b.lastUpdateTime ?? 0) - (a.lastUpdateTime ?? 0))[0];
            if (latest) where.agent = `${APPS.agent.path}&session=${encodeURIComponent(latest.id)}`;
          })
          .catch(() => {})
          .finally(reload);
      } else {
        reload();
      }
    }
    wasUp.current = up;
  }, [up, id, onReload, boundSession, guided]);

  if (!up) {
    return (
      <div className="grid h-full place-content-center gap-3 px-8 text-center" style={{ color: "var(--fg-faint)" }}>
        <p className="text-sm">
          {svc?.state === "unreachable"
            ? t("{name} is not answering.", { name: t(app.label) })
            : svc?.last === "killed with SIGKILL"
              ? t("{name} was killed. Nothing is answering on its port.", { name: svc.label })
              : t("{name} is not running.", { name: svc?.label ?? t(app.label) })}
        </p>
        {svc?.state === "stopped" && (
          <p className="text-[0.8rem]">{t("Turn it on with the switch at the top right.")}</p>
        )}
        {svc && <p className="font-mono text-[0.68rem]">$ {svc.command}</p>}
      </div>
    );
  }

  return (
    <iframe
      key={`${id}-${version}-${generation}`}
      ref={frame}
      src={src}
      title={t(app.label)}
      allow="autoplay; clipboard-write"
      className="block h-full w-full border-0"
      style={{ background: "var(--card)" }}
    />
  );
}
