import { useEffect, useState } from "react";
import { api, type TaskSummary } from "../lib/api";
import { orderId, purchaseEvidence, type PurchaseEvidence } from "../lib/purchaseEvidence";

/** A live extraction from ADK and the venue, with the original event still available. */
export function PurchaseReceipt({ task }: { task: TaskSummary }) {
  const [result, setResult] = useState<{session: string; order: string; evidence: PurchaseEvidence} | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const id = orderId(task.last_order);
  useEffect(() => {
    let active = true;
    setResult(null);
    setError("");
    Promise.all([api.purchaseSession(task), api.purchaseVenue()]).then(([session, venue]) => {
      if (active) setResult({session: task.session_id!, order: id, evidence: purchaseEvidence(session, venue, id)});
    }).catch(() => {
      if (active) setError("The order is saved, but its evidence could not be read. Check that ADK and the Venue are running.");
    });
    return () => { active = false; };
  }, [task.session_id, task.updated, task.app_name, task.user_id, id, retry]);

  const evidence = result?.session === task.session_id && result.order === id ? result.evidence : null;
  if (error) return <div className="mt-3 text-sm" role="alert">
    <p>{error}</p><button className="btn mt-2" onClick={() => setRetry(n => n + 1)}>Read evidence again</button>
  </div>;
  if (!evidence) return <p className="mt-3 text-sm">Reading this order's actual purchase response…</p>;
  const response = evidence.purchase?.response;
  if (!response) return <p className="mt-3 text-sm">Order <code>{id}</code> is saved, but its successful purchase response is not available in this session yet. Open this task in ADK to inspect its latest Events.</p>;
  const retried = response.attempts === 2 && response.duplicate === true;
  const matches = evidence.venueOrder?.idem_key === response.idempotency_key && !!response.idempotency_key;
  const verified = retried && matches && evidence.venueOrderCount === 1;
  return <div className="mt-3 border-t pt-3" style={{borderColor:"var(--hairline)"}}>
    <p className="text-sm font-semibold" style={{color: verified ? "var(--ok)" : "var(--amber)"}}>
      {verified ? "Verified: two requests, one order" : "Order complete · check the retry evidence below"}
    </p>
    <p className="mt-1 text-xs" style={{color:"var(--fg-muted)"}}>
      Live source: ADK Events #{evidence.purchase!.eventNumber} · ✓ purchase, plus the Venue.
    </p>
    <dl className="mt-3 grid gap-3 text-sm">
      <div><dt className="font-mono">attempts: {String(response.attempts ?? "not present")}</dt>
        <dd style={{color:"var(--fg-muted)"}}>{response.attempts === 2
          ? "The purchase tool sent two HTTP requests: the first attempt and one retry."
          : "This order does not show two attempts. The fault may not have been armed before purchase."}</dd></div>
      <div><dt className="font-mono">duplicate: {String(response.duplicate ?? "not present")}</dt>
        <dd style={{color:"var(--fg-muted)"}}>{response.duplicate === true
          ? "The venue recognized the retry and returned the existing order. It did not create another."
          : "This response does not confirm that the venue reused an earlier order."}</dd></div>
      <div><dt>Venue orders: <strong>{evidence.venueOrderCount ?? "unavailable"}</strong> · Order <code>{id}</code></dt>
        <dd style={{color:"var(--fg-muted)"}}>{matches
          ? "This order has the same idempotency key in the tool response and the venue."
          : "The current venue does not contain a matching order and key. It may have been reset."}</dd></div>
    </dl>
    <p className="mt-3 text-xs" style={{color:"var(--fg-muted)"}}>
      {evidence.guard ? `5b's guard also appears at Events #${evidence.guard.eventNumber}: stale_plan.`
        : "No stale_plan refusal was found before this purchase. The sold-out part of 5b is not verified."}
    </p>
    <details className="mt-3">
      <summary className="cursor-pointer text-sm font-medium">Show the actual purchase response (JSON)</summary>
      <pre className="log quiet-scroll mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-lg p-3 text-xs">{JSON.stringify(response, null, 2)}</pre>
    </details>
    <p className="mt-3 text-sm font-medium">What you learned: an error reply does not prove the purchase failed. Reusing the same purchase key lets the venue return the original order safely.</p>
  </div>;
}
