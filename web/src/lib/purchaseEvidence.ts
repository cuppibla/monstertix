type Json = Record<string, unknown>;
export type PurchaseEvent = { eventNumber: number; response: Json };
export type PurchaseEvidence = {
  purchase: PurchaseEvent | null;
  guard: PurchaseEvent | null;
  venueOrder: Json | null;
  venueOrderCount: number | null;
};

function record(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Json : {};
}

/** Read the same response the learner can expand in ADK, for this task's order only. */
export function purchaseEvidence(session: unknown, venue: unknown, orderId: string): PurchaseEvidence {
  const events = record(session).events;
  const responses: PurchaseEvent[] = [];
  if (Array.isArray(events)) events.forEach((event, index) => {
    const parts = record(record(event).content).parts;
    if (!Array.isArray(parts)) return;
    parts.forEach(part => {
      const obj = record(part);
      const response = record(obj.functionResponse ?? obj.function_response);
      if (response.name === "purchase") responses.push({eventNumber: index + 1, response: record(response.response)});
    });
  });
  const purchase = responses.filter(e => !e.response.error &&
    (e.response.id ?? e.response.order_id) === orderId).at(-1) ?? null;
  const guard = responses.filter(e => e.response.reason === "stale_plan" &&
    (!purchase || e.eventNumber < purchase.eventNumber)).at(-1) ?? null;
  const state = record(venue);
  const orders = Array.isArray(state.orders) ? state.orders.map(record) : [];
  return {
    purchase, guard,
    venueOrder: orders.find(order => (order.id ?? order.order_id) === orderId) ?? null,
    venueOrderCount: typeof state.order_count === "number" ? state.order_count : null,
  };
}

export function orderId(order: unknown): string {
  if (typeof order === "string") return order;
  const value = record(order);
  return String(value.order_id ?? value.id ?? "");
}
