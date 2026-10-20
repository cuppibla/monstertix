import { useState } from "react";
import { Link } from "react-router-dom";
import { guides } from "../lib/guide";
import { FileExplorer } from "./FileExplorer";

function More({ title, children }: { title: string; children: React.ReactNode }) {
  return <details className="guide-more"><summary>{title}</summary><div>{children}</div></details>;
}

export function GuideReading({ slug }: { slug: string }) {
  const guide = guides[slug];
  const [source, setSource] = useState(false);
  return <div className="guide-reading">
    <section className="guide-concept">
      <h2>{guide.concept}</h2><p>{guide.explanation}</p>
      {slug === "remember" && <div className="table-scroll"><table>
        <thead><tr><th>What</th><th>Where in this lab</th><th>A new session</th></tr></thead>
        <tbody>
          <tr><td>Conversation and task progress</td><td>Session DB · SQLite</td><td>Old task stays in its original session</td></tr>
          <tr><td>Selected long-term preferences</td><td>Memory Service · Markdown</td><td>recall() can read them again</td></tr>
          <tr><td>user:prefs</td><td>Session Service's user state</td><td>Shared for the same app and user; separate from Memory Service</td></tr>
        </tbody></table></div>}
      {slug === "resume" && <p>A <b>Workflow</b> gives this task named steps: pick a show, join its queue, check your position, and become ready to buy. Each step is a node. Recording its output gives a later run something specific to continue from.</p>}
      {slug === "resume" && <div className="guide-flow">
        <span>Completed nodes<br/><b>Reuse recorded outputs</b></span><i>→</i>
        <span>check_front<br/><b>Query the venue again</b></span><i>→</i>
        <span>ready_to_buy<br/><b>0 orders</b></span>
      </div>}
    </section>
    {slug === "meet" && <More title="Agent, Runner and Venue: three different jobs">
      <p>The <b>agent</b> describes how to decide. The <b>Runner</b> calls the model and tools and saves the events of a run. The <b>venue</b> owns inventory, queue tickets and orders. Stopping the agent does not stop the venue.</p>
      <p>Two tickets means one for you and one for Sam. A queue ticket is a place in line, not a concert ticket. Position counts people ahead of you; it is not a duration in seconds.</p>
    </More>}
    {slug === "wake" && <More title="Follow the caller into a run">
      <pre>{`external one-shot timer\n  → POST /run (this workbench's ADK server)\n  → Runner\n  → model and tools\n  → Session DB events`}</pre>
      <p>The guided button is a real external timer in the workbench. The original <code>monstertix/clock.py</code> is a standalone alternative that posts to your own <code>/wake</code> server. Neither timer depends on the model agreeing to keep watching.</p>
      <p>The local timer is not durable scheduling: if you stop the workbench before it fires, it must be scheduled again. Chapter 6 introduces the cloud caller.</p>
    </More>}
    {slug === "remember" && <>
      <More title="Deep dive · lifetimes and the Artifact Service">
        <p><code>temp:</code> is invocation-scoped. Plain state belongs to a session. <code>user:</code> belongs to the app/user. The separately stored memory file holds only facts that <code>remember()</code> chose to write.</p>
        <img src="/docs-img/04-02-fivestage.png" alt="The lab's storage and lifetime diagram" />
        <p>The Artifact Service stores files such as the full seat map; the tool returns a small summary and a filename. In this lab the artifact path includes the session, so a new session has its own artifact list.</p>
        <p>Both databases surviving does not mean a new session knows what “continue that order” means. You must address the session holding that task.</p>
      </More>
      <More title="Read-only · what compaction changes">
        <p>The supplied summary retains Sam's weekend constraint:</p>
        <blockquote>They looked at the Amsterdam dates and settled on a Saturday show because Sam cannot do weeknights.</blockquote>
        <p>Compaction changes the conversation history presented to the model. The session state, <code>user:prefs</code>, memory file and artifacts are separate. Compare the original turns and summary in the detailed reading; you do not need to trigger a compaction to finish this chapter.</p>
      </More>
    </>}
    {slug === "resume" && <>
      <More title="Deep dive · completed records versus rerun_on_resume">
        <table><thead><tr><th>Node record</th><th>On resume</th></tr></thead><tbody>
          <tr><td>Completed with an output</td><td>Reuse that output without executing the function</td></tr>
          <tr><td>Interrupted; rerun_on_resume=True</td><td>Run the function again with the resume input available</td></tr>
          <tr><td>Interrupted; rerun_on_resume=False</td><td>Use the supplied answer as the node's output</td></tr>
        </tbody></table>
        <p>The flag concerns an unfinished, interrupted node. A graph edge being traversed does not prove the node's function executed again. Check execution records and the venue's side effects.</p>
      </More>
      <More title="Deep dive · the gap that still needs idempotency">
        <p>A process can die after an external write succeeds and before the node's completed output is saved. Resume can then repeat that operation. Reusing completed records cannot close this gap; the receiver must make a repeated write safe. Chapter 5 does that for purchases.</p>
      </More>
      <More title="Optional, read-only · LongRunningFunctionTool">
        <p>The workflow owns the waiting rule here: <code>check_front</code> parks on <code>queue:wait</code>. A long-running tool instead leaves a tool call open and resumes when that call receives a result. This is a conceptual comparison, not a promised loadable replacement experiment.</p>
      </More>
    </>}
    {slug === "buy" && <>
      <More title="Deep dive · read the purchase chain">
        <pre>{`your confirmed authorization\n  → purchase A → guard returns stale_plan (no venue purchase)\n  → refresh seat map → purchase C with key K\n  → venue commits order O, then returns HTTP 503\n  → tool retries once with key K\n  → venue returns order O, duplicate=true`}</pre>
        <p>K and O are placeholders in this explanation. The result card above uses your actual session, key and order. If the agent refreshed before attempting the stale plan, the guard evidence remains missing; the page must not mark an unobserved refusal as passed.</p>
      </More>
      <More title="Deep dive · the identity belongs to the operation">
        <p>The key is derived from the session, show, section and seat count. A retry of the same request carries the same key; a different request can carry a different key. The venue recognizes the key and returns the existing order.</p>
        <p>A 503 does not prove that no order exists. A 409 such as sold-out is a business response and is not the server-failure retry used in this experiment.</p>
      </More>
    </>}
    <details className="guide-more" onToggle={event => {
      if (event.currentTarget.open) setSource(true);
    }}><summary>Source · the code behind this chapter</summary>
      <p className="guide-small">Read-only solution for chapter {guide.number}. Opening it does not reload the experiment.</p>
      {source && <FileExplorer stageBar={false} color="var(--accent)"
        task={{kind:"files", id:"guided-source", stage:guide.number, open:guide.source,
          source:"solution", only:["agent/concert/"], highlight:guide.highlight}} />}
    </details>
    <More title="Optional · full implementation reading and original exercises">
      <p>The original detailed pages remain available for self-study. They include manual tools and stage-loading controls; finish the core experiment before starting another stage.</p>
      <div className="flex flex-wrap gap-2">
        {(slug === "meet" ? ["a","b"] : ["a","b","c"]).map(part =>
          <Link key={part} className="btn" to={`/study/${slug}/${part}`}>Read {guide.number}{part} →</Link>)}
      </div>
    </More>
  </div>;
}
