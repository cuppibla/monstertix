import { useEffect, useState } from "react";
import { Navigate, Outlet, Route, BrowserRouter as Router, Routes, useNavigate, useParams } from "react-router-dom";

import { api, type CoursePayload, type PaneTab, type StepFull } from "./lib/api";
import { setStages } from "./lib/numbers";
import { BenchProvider, useBench, type WorldTab } from "./lib/bench";
import { LangProvider, saveLang, savedLang, t } from "./i18n";
import { AgentDrawer } from "./components/AgentDrawer";
import { Content } from "./components/Content";
import { WorldRail } from "./components/WorldRail";
import { TopNav } from "./components/TopNav";
import { Guided } from "./components/Guided";
import { guides } from "./lib/guide";
import { Watch } from "./components/Watch";

/* The bench: the world on the left, the step in the middle, the ADK web UI in
   a drawer from the top right. The world column (the venue panel and the
   MonsterTix page) and the drawer are mounted once, outside the step routes,
   so their frames survive moving between sections. */

function neighbours(course: CoursePayload, slug: string, partId: string) {
  const flat: { slug: string; part: string; label: string }[] = [];
  for (const step of course.steps) {
    const parts = step.parts.length > 1 ? step.parts : [{ id: step.parts[0]?.id ?? "", label: "" }];
    for (const part of parts) flat.push({ slug: step.slug, part: part.id, label: part.label || step.title });
  }
  const index = flat.findIndex((e) => e.slug === slug && (e.part === partId || !e.part));
  return { flat, index, previous: index > 0 ? flat[index - 1] : null, next: index >= 0 && index < flat.length - 1 ? flat[index + 1] : null };
}

const href = (e: { slug: string; part: string }) => (e.part ? `/study/${e.slug}/${e.part}` : `/study/${e.slug}`);

/* Links to the old nine steps still arrive (bookmarks, the codelab's text).
   Each lands on the section of the new course that teaches the same thing. */
const MOVED: Record<string, string> = {
  story: "meet/a",
  asleep: "wake/a",
  trigger: "wake/b",
  context: "remember/a",
  compaction: "remember/c",
  resumption: "resume/a",
  workflow: "resume/a",
  human: "buy/a",
  cloud: "cloud/a",
};

/* The app a section's actions use first, among the two in the world column:
   the column shows it when the section opens. */
function worldTabFor(part: StepFull["parts"][number]): WorldTab | null {
  const seen: PaneTab[] = [];
  for (const exercise of Object.values(part.exercises ?? {})) {
    for (const tab of exercise.apps ?? []) seen.push(tab);
    for (const task of exercise.tasks) {
      for (const item of task.items ?? []) {
        if (item.in) seen.push(item.in);
        if (item.look) seen.push(item.look);
        if (item.press) seen.push("venue");
      }
    }
  }
  return (seen.find((tab) => tab !== "agent") as WorldTab | undefined) ?? null;
}

function StudyPage({ course, lang }: { course: CoursePayload; lang: string }) {
  const { slug = "", part: partParam } = useParams();
  const navigate = useNavigate();
  const { setRailTab, setCurrent, setGuided } = useBench();
  useEffect(() => setGuided(null), [setGuided]);
  const [step, setStep] = useState<StepFull | null>(null);
  const known = course.steps.some((s) => s.slug === slug);
  const moved = !known && MOVED[slug] && course.steps.some((s) => s.slug === MOVED[slug].split("/")[0]) ? MOVED[slug] : "";

  useEffect(() => {
    if (moved) return;
    api.step(slug, lang).then(setStep).catch(() => setStep(null));
    window.scrollTo({ top: 0 });
  }, [slug, partParam, lang, moved]);

  const part = step?.parts.find((p) => p.id === (partParam ?? "")) ?? step?.parts[0] ?? null;
  const partId = part?.id ?? "";
  const many = (step?.parts.length ?? 0) > 1;
  const { previous, next, index, flat } = neighbours(course, slug, partId);
  const accent = `var(--${step?.color ?? "cyan"})`;

  useEffect(() => {
    document.documentElement.style.setProperty("--accent", accent);
  }, [accent]);

  // A section that uses MonsterTix opens with the MonsterTix page in the world column.
  useEffect(() => {
    if (!part) return;
    const tab = worldTabFor(part);
    if (tab) setRailTab(tab);
  }, [part, setRailTab]);

  // The drawer shows this section's steps beside the dev UI.
  useEffect(() => {
    if (!step || !part) return;
    setCurrent({
      slug: step.slug,
      exercises: Object.entries(part.exercises ?? {}).map(([id, exercise]) => ({ id, exercise })),
    });
    return () => setCurrent(null);
  }, [step, part, setCurrent]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (event.key === "ArrowRight" && next) navigate(href(next));
      if (event.key === "ArrowLeft" && previous) navigate(href(previous));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, previous, navigate]);

  if (moved) return <Navigate to={`/step/${moved}`} replace />;

  return (
    <div className="mx-auto max-w-[56rem] pb-24">
      {!step || !part || step.error ? (
        <div className="py-28 text-center text-sm" style={{ color: "var(--fg-faint)" }}>
          {step?.error ? (
            <pre className="log mx-auto max-w-2xl whitespace-pre-wrap rounded-lg p-4 text-left" style={{ color: "var(--bad)" }}>
              {t("This step's step.yaml does not parse:")}{"\n"}{step.error}
            </pre>
          ) : t("loading…")}
        </div>
      ) : (
        <>
          <div className="px-1 pt-12 pb-3 text-center">
            <div className="kicker" style={{ color: accent }}>
              {step.kicker}{many && part.id ? part.id : ""}{many && part.label ? ` · ${part.label}` : ""}
            </div>
            <h1 className="display text-balance mx-auto mt-4 text-[2.2rem] leading-[1.1] sm:text-[2.6rem]">
              {part.headline || step.title}
            </h1>
            {step.summary && (!many || part === step.parts[0]) && (
              <p className="text-balance mx-auto mt-4 max-w-2xl text-[1.02rem] leading-relaxed" style={{ color: "var(--fg-muted)" }}>
                {step.summary}
              </p>
            )}
          </div>

          <Content markdown={part.body} slug={step.slug} color={accent} exercises={part.exercises} stage={step.stage} />
          <Watch slug={step.slug} part={part.id} checks={part.checks} expect={part.expect} title={part.checksTitle} color={accent} />

          <nav className="mt-12 flex items-center justify-between gap-4 border-t pt-6 text-sm" style={{ borderColor: "var(--hairline)" }}>
            {previous ? (
              <button type="button" onClick={() => navigate(href(previous))} className="min-w-0 text-left" style={{ color: "var(--fg-muted)" }}>
                <span className="kicker block" style={{ color: "var(--fg-faint)" }}>{t("back")}</span>
                <span className="truncate">← {previous.label}</span>
              </button>
            ) : <span />}
            <span className="shrink-0 text-xs" style={{ color: "var(--fg-faint)" }}>{index + 1} / {flat.length}</span>
            {next ? (
              <button type="button" onClick={() => navigate(href(next))} className="min-w-0 text-right" style={{ color: accent }}>
                <span className="kicker block" style={{ color: "var(--fg-faint)" }}>{t("next")}</span>
                <span className="truncate font-medium">{next.label} →</span>
              </button>
            ) : <span />}
          </nav>
          {course.course.credit && (
            <p className="mt-12 text-center text-[0.76rem]" style={{ color: "var(--fg-faint)" }}>{course.course.credit}</p>
          )}
        </>
      )}
    </div>
  );
}

function ChapterPage({course, lang}: {course: CoursePayload; lang: string}) {
  const {slug = "", part} = useParams();
  if (guides[slug]) return part ? <Navigate to={`/step/${slug}`} replace /> : <Guided />;
  return <StudyPage course={course} lang={lang} />;
}

/* The frame around every step: the top bar, the world column, the drawer. */
function Shell({ course, lang, onLang }: { course: CoursePayload; lang: string; onLang: (l: string) => void }) {
  const { slug = "", part = "" } = useParams();
  const { railOpen } = useBench();
  return (
    <>
      <TopNav course={course.course} steps={course.steps} activeSlug={slug} activePart={part}
              languages={course.languages} lang={lang} onLang={onLang} />
      <div className="bench" data-rail={railOpen ? "wide" : "closed"}>
        <aside className="bench__rail"><WorldRail /></aside>
        <main className="bench__main"><Outlet /></main>
      </div>
      <AgentDrawer />
    </>
  );
}

export default function App() {
  const [lang, setLangState] = useState(savedLang);
  const [course, setCourse] = useState<CoursePayload | null>(null);

  useEffect(() => {
    api.course(lang).then((payload) => {
      setStages(payload.steps);
      setCourse(payload);
      // A language nobody has translated yet falls back to English.
      if (payload.lang !== lang) setLangState(payload.lang);
    }).catch(() => setCourse(null));
  }, [lang]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("monstertix.theme");
      document.documentElement.dataset.theme = saved === "light" ? "light"
        : saved === "dark" ? "dark"
        : window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    } catch {
      document.documentElement.dataset.theme = "dark";
    }
  }, []);

  const changeLang = (next: string) => {
    saveLang(next);
    setLangState(next);
  };

  const ambience = (
    <div className="ambience" aria-hidden>
      <div className="ambience__blob ambience__blob--one" />
      <div className="ambience__blob ambience__blob--two" />
      <div className="ambience__grid" />
    </div>
  );

  if (!course) {
    return (
      <>
        {ambience}
        <div className="stage-content grid h-screen place-items-center text-sm" style={{ color: "var(--fg-faint)" }}>
          {t("loading the workshop…")}
        </div>
      </>
    );
  }

  const first = course.steps[0]?.slug ?? "";
  const effective = course.languages.includes(lang) ? lang : "en";
  const page = <ChapterPage course={course} lang={effective} />;
  const study = <StudyPage course={course} lang={effective} />;
  return (
    <LangProvider lang={effective}>
      <BenchProvider>
        <div className="stage-vignette">
          {ambience}
          <Router>
            <Routes>
              <Route path="/" element={<Navigate to={`/step/${first}`} replace />} />
              <Route element={<Shell course={course} lang={effective} onLang={changeLang} />}>
                <Route path="/step/:slug" element={page} />
                <Route path="/step/:slug/:part" element={page} />
                <Route path="/study/:slug" element={study} />
                <Route path="/study/:slug/:part" element={study} />
              </Route>
              <Route path="*" element={<Navigate to={`/step/${first}`} replace />} />
            </Routes>
          </Router>
        </div>
      </BenchProvider>
    </LangProvider>
  );
}
