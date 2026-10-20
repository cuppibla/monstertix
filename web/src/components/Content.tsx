import { createContext, useContext, useMemo, useState } from "react";

import { api, type Exercise as ExerciseSpec, type PaneTab } from "../lib/api";
import { parseBlocks, type Block } from "../lib/blocks";
import { CodePageProvider, useCodePage, type CodeRef } from "../lib/code";
import { useBench } from "../lib/bench";
import { APPS } from "./AppFrame";
import { FileExplorer } from "./FileExplorer";
import { t } from "../i18n";
import { Exercise, TaskSlot } from "./Exercise";
import { TaskCard } from "./TaskCard";
import { Terminal } from "./Terminal";

/* A part's reading: markdown, plus the directives in lib/blocks.ts. Panels use
   a hairline border on a translucent card, never a coloured edge; a callout is
   told apart by its kicker. */

const CALLOUT = {
  key: { label: "The point", color: "var(--accent)" },
  note: { label: "Developer's note", color: "var(--fg-faint)" },
  warn: { label: "Careful", color: "var(--amber)" },
} as const;

function Callout({ variant, html }: { variant: keyof typeof CALLOUT; html: string }) {
  const { label, color } = CALLOUT[variant];
  return (
    <aside className="my-6 rounded-2xl border p-5" style={{ borderColor: "var(--hairline)", background: "var(--overlay)" }}>
      <div className="kicker mb-2" style={{ color }}>{t(label)}</div>
      <div className="prose [&>p:last-child]:mb-0 [&>p]:text-[var(--fg)]" dangerouslySetInnerHTML={{ __html: html }} />
    </aside>
  );
}

function Section({ kicker, headline, children }: { kicker: string; headline: string; children: Block[] }) {
  return (
    <section className="my-7 rounded-3xl border p-6 sm:p-8" style={{ borderColor: "var(--hairline)", background: "var(--card)" }}>
      {kicker && <div className="kicker" style={{ color: "var(--fg-faint)" }}>{kicker}</div>}
      {headline && <h2 className="display text-balance mt-3 mb-5 text-[1.45rem] leading-[1.2]">{headline}</h2>}
      <Blocks blocks={children} />
    </section>
  );
}

function Columns({ children }: { children: Block[][] }) {
  return (
    <div className="my-6 grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(13rem, 1fr))" }}>
      {children.map((column, index) => (
        <div key={index} className="rounded-2xl border p-4" style={{ borderColor: "var(--hairline)", background: "var(--overlay)" }}>
          <Blocks blocks={column} />
        </div>
      ))}
    </div>
  );
}

/* :::optional — off the main line. Collapsed, with the time it takes and
   what it needs, so skipping it costs nothing and taking it is a choice. */
function Optional({ title, minutes, needs, children }: { title: string; minutes: number; needs: string; children: Block[] }) {
  return (
    <details className="my-6 rounded-2xl border" style={{ borderColor: "var(--hairline)", background: "var(--overlay)" }}>
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3.5 text-[0.92rem]">
        <span className="kicker" style={{ color: "var(--fg-faint)" }}>{t("Optional")}</span>
        <span className="font-medium" style={{ color: "var(--fg)" }}>{title || t("Go deeper")}</span>
        <span className="ml-auto flex items-center gap-2 text-[0.74rem]" style={{ color: "var(--fg-faint)" }}>
          {minutes > 0 && <span>{t("{n} min", { n: minutes })}</span>}
          {needs && <span>· {t("needs {what}", { what: needs })}</span>}
        </span>
      </summary>
      <div className="border-t px-5 pb-5 pt-2" style={{ borderColor: "var(--hairline)" }}>
        <Blocks blocks={children} />
      </div>
    </details>
  );
}

/* :::checkpoint — a question to answer before moving on. The :::answer
   inside it is collapsed: predict first, then reveal. */
function Checkpoint({ title, children }: { title: string; children: Block[] }) {
  return (
    <section className="my-7 rounded-3xl border p-6 sm:p-7"
             style={{ borderColor: "color-mix(in srgb, var(--accent) 45%, var(--hairline))",
                      background: "color-mix(in srgb, var(--accent) 6%, var(--card))" }}>
      <div className="kicker" style={{ color: "var(--accent)" }}>{title || t("Checkpoint")}</div>
      <div className="mt-3 [&>.prose>p]:text-[1.02rem] [&>.prose>p]:font-medium">
        <Blocks blocks={children} />
      </div>
    </section>
  );
}

function Answer({ children }: { children: Block[] }) {
  return (
    <details className="mt-4 rounded-2xl border" style={{ borderColor: "var(--hairline)", background: "var(--overlay)" }}>
      <summary className="cursor-pointer px-4 py-2.5 text-[0.82rem] font-semibold" style={{ color: "var(--fg-muted)" }}>
        {t("Reveal")}
      </summary>
      <div className="border-t px-4 pb-4 pt-1" style={{ borderColor: "var(--hairline)" }}>
        <Blocks blocks={children} />
      </div>
    </details>
  );
}

function Figure({ src, caption }: { src?: string; caption: string }) {
  if (!src) return null;
  const url = /^(https?:)?\//.test(src) ? src : `/content-images/${src}`;
  return (
    <figure className="my-6">
      <img src={url} alt={caption} className="mx-auto rounded-2xl border" style={{ borderColor: "var(--hairline)" }} />
      {caption && <figcaption className="mt-2 text-center text-[0.8rem]" style={{ color: "var(--fg-faint)" }}>{caption}</figcaption>}
    </figure>
  );
}

/* :::app tab="agent venue": buttons that bring those apps forward. */
function ShowApps({ tabs }: { tabs: PaneTab[] }) {
  const { focus } = useBench();
  return (
    <div className="my-4 flex flex-wrap items-center gap-2">
      {tabs.filter((tab) => APPS[tab]).map((tab) => (
        <button key={tab} type="button" className="btn" onClick={() => focus(tab)}>
          {t("Show {where}", { where: t(APPS[tab].label) })} →
        </button>
      ))}
    </div>
  );
}

function ConsoleLink({ url, label, note }: { url: string; label: string; note: string }) {
  return (
    <div className="my-4 flex flex-wrap items-center gap-3">
      <a href={url} target="_blank" rel="noopener noreferrer" className="btn"
         style={{ borderColor: "var(--accent)", color: "var(--accent)" }}>
        {label} ↗
      </a>
      {note && <span className="text-xs" style={{ color: "var(--fg-faint)" }}>{note}</span>}
    </div>
  );
}

/* A file behind a button, read-only, opened in place. */
function FileReveal({ path, label }: { path: string; label: string }) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<string[] | null>(null);
  const [problem, setProblem] = useState("");

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      try {
        const file = await api.fileRead(path);
        if (file.error) setProblem(file.error);
        else setLines(file.lines ?? []);
      } catch {
        setProblem(t("could not read that file"));
      }
    }
  }

  return (
    <div className="my-5">
      <button type="button" onClick={toggle} className="btn" aria-expanded={open}>
        <span className="font-mono" style={{ color: "var(--fg)" }}>{path}</span>
        <span>{open ? t("Hide") : label || t("Show")}</span>
      </button>
      {open && (
        <div className="quiet-scroll mt-3 overflow-auto rounded-2xl border" style={{ maxHeight: 520, background: "var(--viewer-bg)", borderColor: "var(--hairline)" }}>
          {problem ? (
            <p className="p-4 text-[0.8rem]" style={{ color: "var(--fg-muted)" }}>{problem}</p>
          ) : (
            <pre className="m-0 p-3 font-mono text-[0.72rem] leading-[1.55]">
              {(lines ?? []).map((line, i) => (
                <div key={i} className="flex">
                  <span className="w-9 shrink-0 pr-3 text-right select-none" style={{ color: "var(--fg-faint)", opacity: 0.55 }}>{i + 1}</span>
                  <span style={{ color: "var(--viewer-fg)", whiteSpace: "pre-wrap" }}>{line || " "}</span>
                </div>
              ))}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

const Inline = createContext<{ slug: string; color: string; exercises: Record<string, ExerciseSpec> }>({
  slug: "", color: "var(--accent)", exercises: {},
});

function TerminalBlock({ commands }: { commands: string[] }) {
  const { slug } = useContext(Inline);
  return <Terminal slug={slug} commands={commands} />;
}

function placedTasks(blocks: Block[]): string[] {
  return blocks.flatMap((block) =>
    block.kind === "task" ? [block.id]
      : block.kind === "section" || block.kind === "optional" || block.kind === "checkpoint" ? placedTasks(block.children) : []);
}

function InlineExercise({ id, children }: { id: string; children: Block[] }) {
  const { slug, color, exercises } = useContext(Inline);
  const exercise = exercises[id];
  if (!exercise) return null;
  return (
    <Exercise slug={slug} exercise={exercise} color={color} placed={placedTasks(children)}>
      {children.length > 0 ? <Blocks blocks={children} /> : null}
    </Exercise>
  );
}

/* A :::code block. The page's first one becomes its file explorer (unless an
   exercise on the page already has one); the rest open their file in it. */
function CodeBlock({ refIndex, color, showButton }: { refIndex: number; color: string; showButton: boolean }) {
  const page = useCodePage();
  if (!page) return null;
  const ref = page.refs[refIndex];
  if (!ref) return null;
  if (!page.hostedByExercise && refIndex === 0) {
    const dirs = [...new Set(page.refs.map((r) => r.path.split("/").slice(0, -1).join("/") + "/"))];
    return (
      <FileExplorer color={color} stageBar={false}
        task={{ kind: "files", id: "code", open: ref.path, stage: page.stage ?? undefined,
                source: page.stage != null ? "solution" : undefined, only: dirs,
                highlight: ref.highlight, highlightLabel: ref.label }} />
    );
  }
  if (!showButton) return null;
  return (
    <div className="my-4">
      <button type="button" className="btn" onClick={() => page.show(ref)}
              title={t("Opens this file in the file explorer on this page")}>
        <span aria-hidden>↑</span>
        <span className="font-mono" style={{ color: "var(--fg)" }}>{ref.path.split("/").pop()}</span>
        <span>{ref.label ? ref.label : t("Show in the file explorer")}</span>
      </button>
    </div>
  );
}

function Blocks({ blocks }: { blocks: Block[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        switch (block.kind) {
          case "exercise":
            return <InlineExercise key={index} id={block.id}>{block.children}</InlineExercise>;
          case "figure":
            return <Figure key={index} src={block.src} caption={block.caption} />;
          case "file":
            return <FileReveal key={index} path={block.path} label={block.label} />;
          case "console":
            return <ConsoleLink key={index} url={block.url} label={block.label} note={block.note} />;
          case "app":
            return <ShowApps key={index} tabs={block.tabs} />;
          case "task":
            return <TaskSlot key={index} id={block.id} />;
          case "taskcard":
            return <TaskCard key={index} />;
          case "optional":
            return <Optional key={index} title={block.title} minutes={block.minutes} needs={block.needs}>{block.children}</Optional>;
          case "checkpoint":
            return <Checkpoint key={index} title={block.title}>{block.children}</Checkpoint>;
          case "answer":
            return <Answer key={index}>{block.children}</Answer>;
          case "terminal":
            return <TerminalBlock key={index} commands={block.commands} />;
          case "code":
            return <CodeBlock key={index} refIndex={codeIndex.get(block) ?? 0} color="var(--accent)" showButton={block.button} />;
          case "callout":
            return <Callout key={index} variant={block.variant} html={block.html} />;
          case "section":
            return <Section key={index} kicker={block.kicker} headline={block.headline}>{block.children}</Section>;
          case "columns":
            return <Columns key={index}>{block.children}</Columns>;
          default:
            return <div key={index} className="prose table-scroll quiet-scroll" dangerouslySetInnerHTML={{ __html: block.html }} />;
        }
      })}
    </>
  );
}

// Which :::code block is which, in page order (sections nest blocks).
const codeIndex = new WeakMap<Block, number>();

function collectCode(blocks: Block[], into: { block: Block; ref: CodeRef }[]) {
  for (const block of blocks) {
    if (block.kind === "code") into.push({ block, ref: { path: block.path, highlight: block.highlight, label: block.label } });
    else if (block.kind === "section" || block.kind === "exercise" || block.kind === "optional"
             || block.kind === "checkpoint" || block.kind === "answer") collectCode(block.children, into);
    else if (block.kind === "columns") block.children.forEach((column) => collectCode(column, into));
  }
  return into;
}

export function Content({ markdown, slug, color, exercises, stage = null }: {
  markdown: string;
  slug: string;
  color: string;
  exercises: Record<string, ExerciseSpec>;
  /** The step whose solution folder the page's :::code blocks read from. */
  stage?: number | null;
}) {
  const blocks = useMemo(() => parseBlocks(markdown), [markdown]);
  const refs = useMemo(() => {
    const found = collectCode(blocks, []);
    found.forEach(({ block }, index) => codeIndex.set(block, index));
    return found.map(({ ref }) => ref);
  }, [blocks]);
  // An exercise explorer on the page hosts the code; otherwise the first :::code does.
  // Only an explorer of a step's code can host code; one of memory/ or artifacts/ cannot.
  const hostedByExercise = Object.values(exercises).some((e) =>
    e.tasks.some((task) => task.kind === "files" && task.stage != null));
  return (
    <Inline.Provider value={{ slug, color, exercises }}>
      <CodePageProvider refs={refs} stage={stage} hostedByExercise={hostedByExercise}>
        <Blocks blocks={blocks} />
      </CodePageProvider>
    </Inline.Provider>
  );
}
