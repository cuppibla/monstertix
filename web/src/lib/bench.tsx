/* What every part of the bench shares: the services and which step is loaded
   (polled from the server, never stored here), which app the world column
   shows, and whether the ADK web drawer is open. */

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { api, type Exercise, type PaneTab, type Service, type Stage } from "./api";

/** The apps in the left column: the world the agent acts on. */
export type WorldTab = Exclude<PaneTab, "agent">;

/** The section on screen: its slug and its "Your turn" cards, in order. */
export type Current = { slug: string; exercises: { id: string; exercise: Exercise }[] };

type Bench = {
  services: Service[];
  stage: Stage | null;
  refresh: () => Promise<void>;
  service: (name: string) => Service | undefined;
  /** The world column: open, or folded to a strip. */
  railOpen: boolean;
  setRailOpen: (open: boolean) => void;
  /** Which app the world column shows: the venue panel or the MonsterTix page. */
  railTab: WorldTab;
  setRailTab: (tab: WorldTab) => void;
  /** The ADK web UI, in a drawer from the top right. */
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  /** Bring an app forward: the venue and MonsterTix in the world column, the dev UI in its drawer. */
  focus: (tab: PaneTab) => void;
  /** The section on screen, so the drawer can show its steps beside the dev UI. */
  current: Current | null;
  setCurrent: (current: Current | null) => void;
  /** Bumped when something reloads code or restarts a process, so frames and files re-read. */
  epoch: number;
  bump: () => void;
};

const BenchContext = createContext<Bench | null>(null);

function stored<T extends string>(key: string, fallback: T): T {
  try {
    return (localStorage.getItem(key) as T) || fallback;
  } catch {
    return fallback;
  }
}

function store(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* the page works without it */
  }
}

export function BenchProvider({ children }: { children: ReactNode }) {
  const [services, setServices] = useState<Service[]>([]);
  const [stage, setStage] = useState<Stage | null>(null);
  const [railOpen, setRailOpenState] = useState(() => stored("monstertix.rail", "open") === "open");
  const [railTab, setRailTab] = useState<WorldTab>("venue");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [current, setCurrent] = useState<Current | null>(null);
  const [epoch, setEpoch] = useState(0);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const payload = await api.services();
      setServices(payload.services);
      setStage(payload.stage);
    } catch {
      /* the workbench restarting: keep the last picture */
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 2500);
    return () => clearInterval(timer);
  }, [refresh]);

  const setRailOpen = useCallback((open: boolean) => {
    setRailOpenState(open);
    store("monstertix.rail", open ? "open" : "closed");
  }, []);

  const focus = useCallback((tab: PaneTab) => {
    if (tab === "agent") {
      setDrawerOpen(true);
    } else {
      setRailTab(tab);
      setRailOpen(true);
    }
  }, [setRailOpen]);

  const value: Bench = {
    services,
    stage,
    refresh,
    service: (name) => services.find((s) => s.name === name),
    railOpen,
    setRailOpen,
    railTab,
    setRailTab,
    drawerOpen,
    setDrawerOpen,
    focus,
    current,
    setCurrent,
    epoch,
    bump: () => setEpoch((n) => n + 1),
  };
  return <BenchContext.Provider value={value}>{children}</BenchContext.Provider>;
}

export function useBench(): Bench {
  const bench = useContext(BenchContext);
  if (!bench) throw new Error("useBench outside BenchProvider");
  return bench;
}

export function isUp(service?: Service) {
  return !!service && ["running", "external", "remote"].includes(service.state);
}
