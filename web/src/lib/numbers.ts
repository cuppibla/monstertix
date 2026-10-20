/* Page numbers versus solution numbers.

   Chapters and solution stages are 1:1 now (chapter 4 loads
   `use-solution.sh 4`), so the number a page shows is the number the server
   is asked for. The function stays so every call site reads the same; it
   only ever returns what it is given. */

export function setStages(_steps: { order: number; stage: number | null }[]) {
  /* nothing to map: stages are chapters */
}

/** The page number a solution step is shown as: the same number. */
export function shown(solution: number | null | undefined): number | string {
  return solution == null ? "" : solution;
}
