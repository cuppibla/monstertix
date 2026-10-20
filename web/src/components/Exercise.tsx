import { createContext, useContext, type ReactNode } from "react";

import type { Exercise as ExerciseSpec, Task } from "../lib/api";
import { t } from "../i18n";
import { FileExplorer } from "./FileExplorer";
import { PromptLab } from "./PromptLab";
import { Inline } from "./Inline";
import { StageBar } from "./StageBar";
import { Turn } from "./Turn";
import { PurchaseProgress } from "./PurchaseProgress";
import { useBench } from "../lib/bench";

/* A block of things to do, placed in the reading with :::exercise id="…".
   Its tasks come from step.yaml: prepare (load a step's code), files (the
   explorer), turn (the numbered actions).

   The apps the actions use are not framed here. The world (the venue panel,
   the MonsterTix page) is in the left column of every page, and the ADK web
   UI opens in a drawer from the top right; an action's button brings the
   right one forward. */

/* One task, rendered where the card puts it. `compact` is the drawer's steps
   column: everything the student does, with the code viewer left to the reading. */
export function TaskView({ task, slug, color, prepared, compact = false }: {
  task: Task; slug: string; color: string; prepared: boolean; compact?: boolean;
}) {
  const { setDrawerOpen } = useBench();
  if (compact && task.kind === "files") {
    return (
      <div className="mt-3">
        <p className="text-[0.78rem]" style={{ color: "var(--fg-faint)" }}>
          {task.lessonAnchor ? "Read the workflow code, then return here to match it to the Events."
            : t("The code viewer for this card is in the reading, behind the drawer.")}
        </p>
        <button type="button" className="btn mt-2" onClick={() => {
          setDrawerOpen(false);
          requestAnimationFrame(() => document.getElementById(task.lessonAnchor ?? `task-${slug}-${task.id}`)
            ?.scrollIntoView({block: "start"}));
        }}>{task.lessonAnchor ? "Read workflow code and explanation →" : "Show code viewer →"}</button>
      </div>
    );
  }
  return (
    <div id={compact ? undefined : `task-${slug}-${task.id}`} className={compact ? "mt-3" : "mt-5"}
      style={{scrollMarginTop: 160}}>
      {task.title && <h3 className="text-[0.98rem] font-semibold">{task.title}</h3>}
      {task.kind === "prepare" && task.step !== undefined && (
        <div className="mt-2">
          {task.explain && (
            <p className="mb-2 text-sm" style={{ color: "var(--fg-muted)" }}><Inline text={task.explain} /></p>
          )}
          <StageBar step={task.step} color={color} prominent scope={task.scope ?? "all"} />
        </div>
      )}
      {task.kind === "prompts" && <PromptLab slug={slug} task={task} color={color} />}
      {task.kind === "files" && <FileExplorer task={task} color={color} stageBar={!prepared} />}
      {task.kind === "turn" && (
        <>
          {task.explain && (
            <p className="mt-1 text-sm" style={{ color: "var(--fg-muted)" }}><Inline text={task.explain} /></p>
          )}
          <Turn items={task.items ?? []} slug={slug} task={task.id} />
        </>
      )}
    </div>
  );
}

/* `:::task id="files"` inside a card's reading puts that task there instead of above the reading. */
const CardTasks = createContext<((id: string) => ReactNode) | null>(null);

export function TaskSlot({ id }: { id: string }) {
  const render = useContext(CardTasks);
  return render ? <>{render(id)}</> : null;
}

export function Exercise({ slug, exercise, color, children, placed = [] }: {
  slug: string;
  exercise: ExerciseSpec;
  color: string;
  /** Reading written inside :::exercise, shown in the card under its tasks. */
  children?: ReactNode;
  /** Tasks the reading places itself with :::task. */
  placed?: string[];
}) {
  // A prepare task already shows which step is loaded; the explorer need not repeat it.
  const prepared = exercise.tasks.some((task) => task.kind === "prepare");
  const render = (id: string) => {
    const task = exercise.tasks.find((candidate) => candidate.id === id);
    return task ? <TaskView task={task} slug={slug} color={color} prepared={prepared} /> : null;
  };
  return (
    <section className="my-7 rounded-3xl border p-5 sm:p-7"
             style={{ borderColor: `color-mix(in srgb, ${color} 40%, var(--hairline))`, background: "var(--card)" }}>
      <div className="kicker" style={{ color }}>{t("Your turn")}</div>
      {slug === "buy" && <PurchaseProgress />}
      {exercise.title && <h2 className="display mt-2 text-[1.35rem] leading-tight">{exercise.title}</h2>}
      {exercise.needs && (
        <p className="mt-2 rounded-lg border px-3 py-1.5 text-[0.84rem]"
           style={{ borderColor: "color-mix(in srgb, var(--amber) 45%, transparent)", color: "var(--fg)" }}>
          <span className="kicker mr-2" style={{ color: "var(--amber)" }}>{t("Needs")}</span>
          <Inline text={exercise.needs.trim()} />
        </p>
      )}
      {exercise.intro && (
        <p className="mt-2 whitespace-pre-line text-[0.95rem]" style={{ color: "var(--fg-muted)" }}>
          <Inline text={exercise.intro.trim()} />
        </p>
      )}
      {exercise.tasks.filter((task) => !placed.includes(task.id)).map((task) => (
        <TaskView key={task.id} task={task} slug={slug} color={color} prepared={prepared} />
      ))}
      {children && (
        <CardTasks.Provider value={render}>
          <div className="mt-6">{children}</div>
        </CardTasks.Provider>
      )}
    </section>
  );
}
