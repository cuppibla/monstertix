import type { TaskSummary } from "./api";

type Client = {
  stage: () => Promise<{step: number | null}>;
  task: (sessionId: string) => Promise<TaskSummary>;
  venue: (action: string, body?: Record<string, unknown>) => Promise<{ok: boolean; error?: string}>;
};

/** Prepare the fake venue. Sending the resume remains the learner's next action. */
export async function preparePurchaseScenario(
  client: Client, sessionId: string, onStep: (label: string) => void,
) {
  if ((await client.stage()).step !== 5) throw new Error("Load chapter 5 before preparing this scenario.");
  const task = await client.task(sessionId);
  if (task.session_id !== sessionId || task.pending?.kind !== "queue" || !task.queue_ticket || !task.queue_event_id) {
    throw new Error("Start the purchase task and wait for its queue pause first.");
  }
  if (!task.authorization?.confirmed) throw new Error("Confirm your budget in ADK Web first.");
  if (task.last_order) throw new Error("This task already has an order. Inspect it instead of preparing another purchase.");
  const changes: [string, string, Record<string, unknown>][] = [
    ["Section A sold out for this show", "sellout", {event_id: task.queue_event_id, section: "A"}],
    ["Next order will commit, then return 503", "hang-once", {}],
    ["Your ticket moved to the front", "advance-queue", {ticket: task.queue_ticket}],
  ];
  for (const [label, action, body] of changes) {
    const result = await client.venue(action, body);
    if (!result.ok) throw new Error(`${label}: ${result.error || "the venue did not apply this change"}. Finish preparation before resuming.`);
    onStep(label);
  }
}
