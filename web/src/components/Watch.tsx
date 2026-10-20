import { useCallback, useEffect, useRef, useState } from "react";

import { api, type CheckCard, type CheckResult } from "../lib/api";
import { t } from "../i18n";
import { Inline } from "./Inline";

/* "Watch": what the step should make happen, ticking on its own while the
   student works. Each row runs a read-only command on this machine (shown
   under "how"), never trusts the page. A row marked `expect: fail` describes a
   failure the step is built to show: it turns amber, not red, when it happens. */

function Row({ card, result }: { card: CheckCard; result?: CheckResult }) {
  const [open, setOpen] = useState(false);
  const passed = result?.passed ?? false;
  const amber = card.expected && passed;
  const mark = !result ? "" : amber ? "!" : passed ? "✓" : "";
  const fill = !result ? "transparent" : amber ? "var(--amber)" : passed ? "var(--ok)" : "transparent";
  // A check that looks only at the newest session, or at what happened since
  // it started, so an old order or an old tool call cannot make it pass.
  const sessionOnly = card.scope === "session"
    || /(^|\s)--current(\s|$)|(^|\s)--since-session(\s|$)/.test(result?.command ?? "");

  return (
    <li className="border-b last:border-b-0" style={{ borderColor: "var(--hairline)" }}>
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-start gap-3 py-2.5 text-left">
        <span className="mt-[3px] grid h-[17px] w-[17px] shrink-0 place-items-center rounded-full text-[10px] font-bold text-white"
              style={{ background: fill, border: passed ? "none" : "1.5px dashed var(--hairline-strong)" }}>
          {mark}
        </span>
        <span className="min-w-0 flex-1">
          <span className="text-[0.92rem]" style={{ color: passed ? "var(--fg)" : "var(--fg-muted)" }}>
            {card.expected && (
              <span className="mr-1.5 rounded px-1 py-[1px] text-[0.62rem] font-semibold uppercase tracking-wide"
                    style={{ color: "var(--amber)", background: "color-mix(in srgb, var(--amber) 14%, transparent)" }}>
                {t("expected")}
              </span>
            )}
            <Inline text={card.label} />
            {sessionOnly && (
              <span className="ml-1.5 rounded px-1 py-[1px] align-middle text-[0.6rem] font-semibold uppercase tracking-wide"
                    title={t("Counts only the newest session, not what earlier runs did.")}
                    style={{ color: "var(--fg-faint)", border: "1px solid var(--hairline-strong)" }}>
                {t("this session only")}
              </span>
            )}
          </span>
          {amber && card.note && (
            <span className="mt-1 block text-[0.82rem]" style={{ color: "var(--fg-faint)" }}><Inline text={card.note} /></span>
          )}
          {result && !passed && card.hint && (
            <span className="mt-1 block text-[0.82rem]" style={{ color: "var(--fg-faint)" }}><Inline text={card.hint} /></span>
          )}
        </span>
        {result && <span className="shrink-0 text-[0.68rem]" style={{ color: "var(--fg-faint)" }}>{open ? t("hide") : t("how")}</span>}
      </button>
      {open && result && (
        <div className="pb-3 pl-[29px]">
          <div className="log quiet-scroll overflow-x-auto rounded-lg px-3 py-2">
            <div style={{ opacity: 0.6 }}>$ {result.command}</div>
            {result.detail && <div className="mt-1">{result.detail}</div>}
          </div>
        </div>
      )}
    </li>
  );
}

export function Watch({ slug, part, checks, expect = [], title, color }: {
  slug: string;
  part: string;
  checks: CheckCard[];
  /** What the ADK web UI and the venue should show, in words. */
  expect?: string[];
  title: string;
  color: string;
}) {
  const [results, setResults] = useState<Record<string, CheckResult>>({});
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  const check = useCallback(async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const payload = await api.check(slug, part);
      setResults(Object.fromEntries(payload.results.map((r) => [r.id, r])));
    } catch {
      /* the next tick tries again */
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, [slug, part]);

  useEffect(() => {
    setResults({});
    if (!checks.length) return;
    check();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") check();
    }, 5000);
    return () => clearInterval(timer);
  }, [check, checks.length]);

  if (!checks.length && !expect.length) return null;
  const done = checks.filter((c) => results[c.id]?.passed).length;

  return (
    <section className="my-8 rounded-3xl border px-5 py-5 sm:px-7" style={{ background: "var(--card)", borderColor: "var(--hairline)" }}>
      {expect.length > 0 && (
        <div className={checks.length ? "mb-5 border-b pb-5" : ""} style={{ borderColor: "var(--hairline)" }}>
          <div className="kicker" style={{ color }}>{t("What you should see")}</div>
          <ul className="mt-3 space-y-2">
            {expect.map((line, index) => (
              <li key={index} className="flex gap-2.5 text-[0.9rem]" style={{ color: "var(--fg-muted)" }}>
                <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full" style={{ background: color }} />
                <span><Inline text={line} /></span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {checks.length > 0 && (
      <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="kicker" style={{ color }}>{title || t("Watch")}</div>
          <p className="mt-1 text-[0.8rem]" style={{ color: "var(--fg-faint)" }}>
            {t("{done} of {total} · these tick on their own as it happens", { done, total: checks.length })}
          </p>
        </div>
        <button type="button" className="btn" disabled={busy} onClick={check}>
          {busy ? t("checking…") : t("check now")}
        </button>
      </div>
      <ul className="mt-3">
        {checks.map((card) => (
          <Row key={card.id} card={card} result={results[card.id]} />
        ))}
      </ul>
      </>
      )}
    </section>
  );
}
