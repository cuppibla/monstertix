/* Splitting a part's markdown into things React can render.

   Authors write plain markdown, plus a few fenced directives:

       :::section kicker="The shape" headline="Three buildings, one campus."
       Markdown, figures and callouts, all inside one card.
       :::

       :::figure id="zones" caption="Independent failure domains."
       :::

       :::key
       The one sentence worth remembering.
       :::

       :::file path="agent/concert/agent.py" label="Show the file"
       :::

       :::app tab="venue"
       :::

       :::code path="agent/concert/agent.py" highlight="LongRunningFunctionTool" label="…"
       :::

       :::task                      the current task card (Resume current task)
       :::

       :::optional title="…" minutes=10 needs="…"
       Collapsed until opened; off the main line.
       :::

       :::checkpoint
       A question to answer before moving on.
       :::answer
       Collapsed behind "Reveal".
       :::
       :::

   Sections nest, so the parser is line-based rather than a regular
   expression: it tracks how deep it is and only closes at depth zero.
*/

import { marked } from "marked";

import type { PaneTab } from "./api";

export type Block =
  | { kind: "markdown"; html: string }
  | { kind: "callout"; variant: "key" | "note" | "warn"; html: string }
  | { kind: "figure"; id: string; caption: string; src?: string; example?: boolean }
  | { kind: "console"; url: string; label: string; note: string }
  | { kind: "file"; path: string; label: string }
  | { kind: "app"; tabs: PaneTab[] }
  | { kind: "task"; id: string }
  | { kind: "taskcard" }
  | { kind: "terminal"; commands: string[] }
  | { kind: "code"; path: string; highlight: string; label: string; button: boolean }
  | { kind: "exercise"; id: string; plain: boolean; children: Block[] }
  | { kind: "optional"; title: string; minutes: number; needs: string; children: Block[] }
  | { kind: "checkpoint"; title: string; children: Block[] }
  | { kind: "answer"; children: Block[] }
  | { kind: "columns"; children: Block[][] }
  | { kind: "section"; kicker: string; headline: string; children: Block[] };

const OPEN = /^:::(\w+)(.*)$/;
const CLOSE = /^:::\s*$/;

marked.setOptions({ gfm: true, breaks: false });

function render(markdown: string): string {
  const trimmed = markdown.trim();
  return trimmed ? (marked.parse(trimmed, { async: false }) as string) : "";
}

function attribute(raw: string, name: string): string {
  const quoted = new RegExp(`${name}\\s*=\\s*"([^"]*)"`).exec(raw);
  if (quoted) return quoted[1];
  const bare = new RegExp(`${name}\\s*=\\s*(\\S+)`).exec(raw);
  return bare ? bare[1] : "";
}

function flush(buffer: string[], into: Block[]): void {
  const html = render(buffer.join("\n"));
  if (html) into.push({ kind: "markdown", html });
  buffer.length = 0;
}

export function parseBlocks(markdown: string): Block[] {
  const lines = markdown.split("\n");
  const blocks: Block[] = [];
  const buffer: string[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const open = OPEN.exec(line);

    if (!open) {
      buffer.push(line);
      index += 1;
      continue;
    }

    flush(buffer, blocks);

    const [, name, rawArgs] = open;

    // Collect this directive's body, allowing directives inside it.
    const inner: string[] = [];
    let depth = 1;
    index += 1;
    while (index < lines.length) {
      const candidate = lines[index];
      if (OPEN.test(candidate)) depth += 1;
      else if (CLOSE.test(candidate)) {
        depth -= 1;
        if (depth === 0) {
          index += 1;
          break;
        }
      }
      inner.push(candidate);
      index += 1;
    }

    const body = inner.join("\n");

    if (name === "figure") {
      blocks.push({
        kind: "figure",
        id: attribute(rawArgs, "id"),
        caption: attribute(rawArgs, "caption"),
        src: attribute(rawArgs, "src") || undefined,
        example: attribute(rawArgs, "example") === "true",
      });
    } else if (name === "exercise") {
      // A "Your turn" inside the reading; its tasks live in step.yaml, under
      // the part's `exercises`, by this id.
      // Anything written inside the block is shown in the card, under its tasks:
      // the walkthrough of the code its file explorer opens.
      blocks.push({ kind: "exercise", id: attribute(rawArgs, "id"), plain: attribute(rawArgs, "plain") === "true",
                    children: parseBlocks(body) });
    } else if (name === "file") {
      // A button that shows a project file, read-only, in place.
      blocks.push({ kind: "file", path: attribute(rawArgs, "path"), label: attribute(rawArgs, "label") });
    } else if (name === "code") {
      // Code from the project: shown in the page's one file explorer (see Content.tsx).
      blocks.push({ kind: "code", path: attribute(rawArgs, "path"), highlight: attribute(rawArgs, "highlight"),
                    label: attribute(rawArgs, "label"),
                    // button="false": only adds its lines to the explorer's highlights.
                    button: attribute(rawArgs, "button") !== "false" });
    } else if (name === "terminal") {
      // A command typed into a terminal, ready to run with Enter (Terminal.tsx).
      // One command per line; a line ending in a backslash continues on the next.
      const commands: string[] = [];
      let current: string[] = [];
      for (const line of body.trim().split("\n")) {
        if (!line.trim() && !current.length) continue;
        current.push(line);
        if (!line.trimEnd().endsWith("\\")) {
          commands.push(current.join("\n").trim());
          current = [];
        }
      }
      if (current.length) commands.push(current.join("\n").trim());
      blocks.push({ kind: "terminal", commands });
    } else if (name === "task") {
      // With an id, inside :::exercise: put that card's task (by id) here, in
      // the reading. With no id: the current task card (TaskCard.tsx), read
      // from the session store, with the Resume current task button.
      const id = attribute(rawArgs, "id");
      blocks.push(id ? { kind: "task", id } : { kind: "taskcard" });
    } else if (name === "optional") {
      // Off the main line: collapsed, with the time it takes and what it needs.
      blocks.push({
        kind: "optional",
        title: attribute(rawArgs, "title"),
        minutes: Number(attribute(rawArgs, "minutes")) || 0,
        needs: attribute(rawArgs, "needs"),
        children: parseBlocks(body),
      });
    } else if (name === "checkpoint") {
      // A question to answer before moving on; an :::answer inside it is collapsed.
      blocks.push({ kind: "checkpoint", title: attribute(rawArgs, "title"), children: parseBlocks(body) });
    } else if (name === "answer") {
      blocks.push({ kind: "answer", children: parseBlocks(body) });
    } else if (name === "app") {
      // An app framed in the reading: tab="agent", or several, tab="agent venue".
      blocks.push({ kind: "app", tabs: attribute(rawArgs, "tab").split(/[\s,]+/).filter(Boolean) as PaneTab[] });
    } else if (name === "console") {
      // A way out to the console from inside the reading, for the things that
      // are worth seeing in the real product rather than only described.
      blocks.push({
        kind: "console",
        url: attribute(rawArgs, "url"),
        label: attribute(rawArgs, "label") || "Open the console",
        note: attribute(rawArgs, "note"),
      });
    } else if (name === "section") {
      blocks.push({
        kind: "section",
        kicker: attribute(rawArgs, "kicker"),
        headline: attribute(rawArgs, "headline"),
        children: parseBlocks(body),
      });
    } else if (name === "columns") {
      // Two or more panels, separated by a line of three dashes.
      blocks.push({
        kind: "columns",
        children: body.split(/^---\s*$/m).map((column) => parseBlocks(column)),
      });
    } else if (name === "key" || name === "note" || name === "warn") {
      blocks.push({ kind: "callout", variant: name, html: render(body) });
    } else {
      const html = render(body);
      if (html) blocks.push({ kind: "markdown", html });
    }
  }

  flush(buffer, blocks);
  return blocks;
}
