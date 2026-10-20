import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";

import { api, type CoursePayload, type StepCard } from "../lib/api";
import { LANGUAGE_NAMES, t } from "../i18n";

function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    document.documentElement.dataset.theme === "light" ? "light" : "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("monstertix.theme", theme);
    } catch {
      /* the page works without it */
    }
  }, [theme]);
  return (
    <button type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title={t("Theme")} className="grid h-7 w-7 place-items-center rounded-md border text-xs"
            style={{ borderColor: "var(--hairline)", color: "var(--fg-faint)" }}>
      {theme === "dark" ? "◐" : "○"}
    </button>
  );
}

function EnvPill() {
  const [env, setEnv] = useState<{ project: string; model: string } | null>(null);
  useEffect(() => {
    api.env().then(setEnv).catch(() => setEnv(null));
  }, []);
  if (!env) return null;
  return (
    <span className="hidden items-center gap-1.5 md:flex">
      {[env.project || t("no project"), env.model].filter(Boolean).map((bit) => (
        <span key={bit} className="rounded-md border px-2 py-0.5 font-mono text-[0.68rem]"
              style={{ borderColor: "var(--hairline)", color: "var(--fg-faint)" }}>
          {bit}
        </span>
      ))}
    </span>
  );
}

export function TopNav({ course, steps, activeSlug, activePart, languages, lang, onLang }: {
  course: CoursePayload["course"];
  steps: StepCard[];
  activeSlug: string;
  activePart: string;
  languages: string[];
  lang: string;
  onLang: (lang: string) => void;
}) {
  const header = useRef<HTMLElement>(null);
  const rail = useRef<HTMLDivElement>(null);
  const activeIndex = steps.findIndex((s) => s.slug === activeSlug);
  const active = steps[activeIndex];
  // Chapters are the course; a step marked `appendix: true` is reference,
  // listed after them and never counted as a chapter.
  const chapters = steps.filter((s) => !s.appendix);
  const appendix = steps.filter((s) => s.appendix);
  const activeChapter = chapters.findIndex((s) => s.slug === activeSlug);
  const named = (active?.parts ?? []).filter((p) => p.id);
  const parts = named.length > 1 ? named : [];

  // The columns below sit under the header; they need its height.
  useEffect(() => {
    if (!header.current) return;
    const observer = new ResizeObserver(([entry]) => {
      document.documentElement.style.setProperty("--nav-height", `${Math.ceil(entry.target.getBoundingClientRect().height)}px`);
    });
    observer.observe(header.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    rail.current?.querySelector<HTMLElement>('[data-active="true"]')
      ?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [activeSlug]);

  return (
    <header ref={header} className="sticky z-20 border-b backdrop-blur-xl"
            style={{ top: "env(safe-area-inset-top, 0px)", borderColor: "var(--hairline)",
                     background: "color-mix(in srgb, var(--stage) 84%, transparent)" }}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2.5">
        <NavLink to={`/step/${steps[0]?.slug ?? ""}`} className="flex items-center gap-2">
          <span className="text-[1.02rem] font-bold tracking-[-0.02em]">{course.title}</span>
        </NavLink>
        <div className="ml-auto flex items-center gap-2">
          <EnvPill />
          {languages.length > 1 && (
            <select value={lang} onChange={(e) => onLang(e.target.value)} aria-label={t("Language")}
                    className="rounded-md border px-1.5 py-1 text-[0.72rem]"
                    style={{ borderColor: "var(--hairline)", background: "var(--input)", color: "var(--fg-muted)" }}>
              {languages.map((code) => (
                <option key={code} value={code}>{LANGUAGE_NAMES[code] ?? code}</option>
              ))}
            </select>
          )}
          <ThemeToggle />
        </div>
      </div>

      <div ref={rail} className="quiet-scroll overflow-x-auto">
        <div className="mx-auto flex w-max items-center gap-1 px-5 pb-2">
          {chapters.map((step, index) => {
            const isActive = step.slug === activeSlug;
            const accent = `var(--${step.color})`;
            return (
              <div key={step.slug} className="flex shrink-0 items-center">
                <NavLink to={`/step/${step.slug}`} data-active={isActive} title={`${step.kicker} · ${step.title}`}
                         className="flex items-center gap-2 rounded-full border px-2 py-1 text-xs whitespace-nowrap"
                         style={{
                           borderColor: isActive ? accent : "var(--hairline)",
                           background: isActive ? `color-mix(in srgb, ${accent} 14%, transparent)` : "transparent",
                           color: isActive ? accent : index < activeChapter ? "var(--fg-faint)" : "var(--fg-muted)",
                         }}>
                  <span className="grid h-[19px] w-[19px] place-items-center rounded-full text-[10px] font-semibold"
                        style={{ background: isActive ? accent : "transparent",
                                 border: isActive ? "none" : "1px solid var(--hairline-strong)",
                                 color: isActive ? "var(--stage)" : "inherit" }}>
                    {index + 1}
                  </span>
                  {isActive && <span className="pr-1 font-semibold">{step.title}</span>}
                </NavLink>
                {index < chapters.length - 1 && <span className="px-0.5 text-[10px]" style={{ color: "var(--hairline-strong)" }}>›</span>}
              </div>
            );
          })}
          {appendix.length > 0 && (
            <>
              <span className="mx-2 h-4 w-px shrink-0" style={{ background: "var(--hairline-strong)" }} aria-hidden />
              {appendix.map((step) => {
                const isActive = step.slug === activeSlug;
                const accent = `var(--${step.color})`;
                return (
                  <NavLink key={step.slug} to={`/step/${step.slug}`} data-active={isActive}
                           title={`${step.kicker} · ${step.title}`}
                           className="flex shrink-0 items-center gap-2 rounded-full border px-2.5 py-1 text-xs whitespace-nowrap"
                           style={{
                             borderColor: isActive ? accent : "var(--hairline)",
                             background: isActive ? `color-mix(in srgb, ${accent} 14%, transparent)` : "transparent",
                             color: isActive ? accent : "var(--fg-faint)",
                           }}>
                    <span className="text-[10px]" aria-hidden>§</span>
                    <span className={isActive ? "pr-1 font-semibold" : ""}>{isActive ? step.title : t("Reference")}</span>
                  </NavLink>
                );
              })}
            </>
          )}
        </div>
      </div>

      {parts.length > 0 && (
        <div className="quiet-scroll overflow-x-auto border-t" style={{ borderColor: "var(--hairline)" }}>
          <div className="flex items-center justify-center gap-2 px-5 py-1.5">
            {parts.map((part) => {
              const isActive = part.id === activePart;
              const accent = `var(--${active.color})`;
              return (
                <NavLink key={part.id} to={`/step/${activeSlug}/${part.id}`}
                         className="flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1 text-xs whitespace-nowrap"
                         style={{ borderColor: isActive ? accent : "var(--hairline)",
                                  background: isActive ? `color-mix(in srgb, ${accent} 12%, transparent)` : "transparent",
                                  color: isActive ? accent : "var(--fg-muted)" }}>
                  <span className="font-mono font-semibold">{active.appendix ? "" : activeChapter + 1}{part.id}</span>
                  <span className={isActive ? "font-medium" : ""}>{part.label}</span>
                </NavLink>
              );
            })}
          </div>
        </div>
      )}
    </header>
  );
}
