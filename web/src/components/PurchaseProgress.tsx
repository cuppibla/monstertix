import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useBench } from "../lib/bench";
import { useTask } from "./TaskCard";
import { refreshAgentSession } from "./AppFrame";
import { api } from "../lib/api";
import { completePurchaseScenario } from "../lib/purchaseScenario";
import { PurchaseReceipt } from "./PurchaseReceipt";

/** Live prerequisite guidance alongside the hands-on steps, never a substitute for the ADK run. */
export function PurchaseProgress() {
  const {task, error, reload} = useTask();
  const {stage, focus, setDrawerOpen} = useBench();
  const {pathname} = useLocation();
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState<string[]>([]);
  const [failure, setFailure] = useState("");
  if (error || !task || !stage) return <p role="status" className="my-4 text-sm" style={{color:"var(--fg-muted)"}}>
    {error ? "Cannot read the current task yet. Check that the lab service is running; retrying automatically."
      : "Reading this chapter's current task…"}
  </p>;
  const loaded = stage?.step === 5;
  const order = loaded && !!task?.last_order;
  const person = loaded && task?.pending?.kind === "person";
  const queued = loaded && task?.pending?.kind === "queue" && task.authorization?.confirmed;
  const existing = loaded && task?.session_id && task.session_id !== "two-days-ago";
  const title = !loaded ? "Load chapter 5 to begin"
    : order ? "5b purchase complete · your order is saved"
    : person ? task?.pending?.id === "budget:confirm" ? "Waiting for your budget confirmation" : "Waiting for your ticket budget"
    : queued ? "Budget confirmed · your ticket is in the queue"
    : existing ? "Waiting for the task's next result"
    : "No purchase task has started yet";
  const detail = !loaded ? "Go to 5a and load the chapter once."
    : order ? pathname === "/step/buy/c"
      ? "You have finished buying. Below is the evidence from your own run; no new message or purchase is needed."
      : "You have finished buying. Open 5c to see this order's retry evidence; no new purchase is needed."
    : person ? "Open the task below. Answer the latest adk_request_input card in Events. This pause needs your reply."
    : queued ? "5a is complete. The button below sells out A, arms the commit-then-503 fault, moves your ticket to the front, and resumes once using your confirmed budget."
    : existing ? "Let the current run finish. If it stopped with an error, inspect its latest Events before sending anything again."
    : "Go to 5a. In ADK, create a New Session and send the ticket request. Loading the chapter only prepares the code.";
  const destination = order ? "/step/buy/c" : queued ? "/step/buy/b" : "/step/buy/a";
  const canInspect = !!existing;
  async function complete() {
    if (!task?.session_id || busy) return;
    setBusy(true); setSteps([]); setFailure("");
    try {
      const result = await completePurchaseScenario(api, task.session_id, label => setSteps(s => [...s, label]));
      if (result.session_id) refreshAgentSession(result.session_id);
    } catch (e) { setFailure((e as Error).message); }
    finally { await reload(); setBusy(false); }
  }
  return <div className="my-4 rounded-xl border p-3" role="status"
    style={{borderColor:"var(--hairline-strong)", background:"var(--overlay)"}}>
    <p className="text-xs" style={{color:"var(--fg-faint)"}}>5a · Authorize → 5b · Buy → 5c · Inspect</p>
    <p className="mt-1 text-sm font-semibold">{title}</p>
    <p className="mt-1 text-sm" style={{color:"var(--fg-muted)"}}>{detail}</p>
    {(queued || busy) && <button className="btn btn--solid mt-3" disabled={busy} onClick={complete}>
      {busy ? "Completing 5b…" : "Complete 5b for this task"}
    </button>}
    {steps.length > 0 && !order && <ul className="mt-2 text-xs" aria-live="polite">{steps.map(step => <li key={step}>{step}</li>)}</ul>}
    {failure && <p className="mt-2 text-sm" role="alert" style={{color:"var(--bad)"}}>{failure}</p>}
    {order && pathname === "/step/buy/c" && <PurchaseReceipt key={task.session_id} task={task} />}
    <div className="mt-2 flex flex-wrap gap-2">
      {pathname !== destination && <Link className="btn" to={destination} onClick={() => setDrawerOpen(false)}>
        {order ? "Go to 5c · inspect the retry" : queued ? "Go to 5b · prepare and resume" : "Go to 5a · start here"} →
      </Link>}
      {canInspect && <button type="button" className="btn" onClick={() => {
        refreshAgentSession(task.session_id!);
        focus("agent");
      }}>{person ? "Open the budget question in ADK" : "Open this task in ADK"} →</button>}
    </div>
  </div>;
}
