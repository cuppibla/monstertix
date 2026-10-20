import { Link, useLocation } from "react-router-dom";
import { useBench } from "../lib/bench";
import { useTask } from "./TaskCard";
import { refreshAgentSession } from "./AppFrame";

/** Live prerequisite guidance alongside the hands-on steps, never a substitute for the ADK run. */
export function PurchaseProgress() {
  const {task, error} = useTask();
  const {stage, focus, setDrawerOpen} = useBench();
  const {pathname} = useLocation();
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
    : order ? "Order saved · ready to inspect the purchase"
    : person ? task?.pending?.id === "budget:confirm" ? "Waiting for your budget confirmation" : "Waiting for your ticket budget"
    : queued ? "Budget confirmed · your ticket is in the queue"
    : existing ? "Waiting for the task's next result"
    : "No purchase task has started yet";
  const detail = !loaded ? "Go to 5a and load the chapter once."
    : order ? "5c reads this order's tool response. No new purchase or chat message is needed."
    : person ? "Open the task below. Answer the latest adk_request_input card in Events. This pause needs your reply."
    : queued ? "Continue to 5b: Prepare the changing-world scenario, then Resume. Purchase events appear after that run."
    : existing ? "Let the current run finish. If it stopped with an error, inspect its latest Events before sending anything again."
    : "Go to 5a. In ADK, create a New Session and send the ticket request. Loading the chapter only prepares the code.";
  const destination = order ? "/step/buy/c" : queued ? "/step/buy/b" : "/step/buy/a";
  const canInspect = !!existing;
  return <div className="my-4 rounded-xl border p-3" role="status"
    style={{borderColor:"var(--hairline-strong)", background:"var(--overlay)"}}>
    <p className="text-xs" style={{color:"var(--fg-faint)"}}>5a · Authorize → 5b · Buy → 5c · Inspect</p>
    <p className="mt-1 text-sm font-semibold">{title}</p>
    <p className="mt-1 text-sm" style={{color:"var(--fg-muted)"}}>{detail}</p>
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
