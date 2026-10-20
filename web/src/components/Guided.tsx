import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { learningFetch } from "../lib/learning";
import { guides } from "../lib/guide";
import { useBench } from "../lib/bench";
import { GuideReading } from "./GuideReading";
import { CloudDemo } from "./CloudDemo";

type Check = { id: string; label: string; passed: boolean; detail: string; source: string };
type Receipt = { at: number; attempt_id: string; sessions: string[]; stage: number; fingerprint: string; checks: Check[]; archive: string };
type LearningStatus = {
  next: string; loaded?: boolean; busy?: string | null; checks: Check[]; receipt?: Receipt;
  attempt: null | {id: string; sessions: string[]; created_at: number; error?: string; preparation?: string;
    last_said: string[]; marks: {timer?: {state: string; due_at: number}; scenario?: {steps: string[]; ready: boolean}}};
  task: null | {session_id?: string; kind_label?: string; paused?: string; events?: number;
    pending?: {id: string; kind: string}; pending_message?: string; authorization_text?: string;
    invocations?: number; queue_ticket?: string; last_order?: string; ready_to_buy?: boolean};
  venue?: {up: boolean; orders: number | null; ticket?: {ticket: string; position: number}};
};


function Result({ checks, receipt }: { checks: Check[]; receipt?: Receipt }) {
  if (!checks.length && !receipt) return null;
  const rows = receipt?.checks ?? checks;
  return <section className={`guide-result ${receipt ? "guide-result--earned" : ""}`}>
    <div className="kicker">{receipt ? "Recorded result" : "Evidence from this experiment"}</div>
    <h2>{receipt ? "This experiment produced the evidence." : "What the run has shown so far"}</h2>
    <p className="guide-small">{receipt
      ? `Saved ${new Date(receipt.at * 1000).toLocaleString()}. This record stays when you start another chapter.`
      : "Only observed results are marked. Missing evidence is not an instruction to start over."}</p>
    <ul>{rows.map(row => <li key={row.id}>
      <span className={row.passed ? "guide-pass" : "guide-pending"}>{row.passed ? "✓" : "·"}</span>
      <details><summary>{row.label}</summary><p>{row.detail}</p><small>{row.source}</small></details>
    </li>)}</ul>
    {receipt && <p className="guide-small guide-mono">Session: {receipt.sessions.join(" → ")}<br/>
      Evidence: {receipt.archive} · code {receipt.fingerprint}</p>}
  </section>;
}

type RecordedEvent = {id?:string; author?:string; timestamp?:number; invocation_id?:string;
  node_info?:unknown; output?:unknown; content?:{parts?:{text?:string; function_call?:unknown; function_response?:unknown}[]}};
type RecordSession = {id:string; stored_state:Record<string,unknown>; events:RecordedEvent[]};
function toolResponses(session: RecordSession, name: string) {
  return session.events.flatMap(event=>(event.content?.parts??[]).flatMap(part=>{
    const response = part.function_response as {name?:string;response?:unknown} | undefined;
    return response?.name===name ? [response.response] : [];
  }));
}
function recallText(session: RecordSession): string {
  const value = toolResponses(session,"recall")[0] as {memory?:unknown} | undefined;
  return typeof value?.memory === "string" ? value.memory : JSON.stringify(value??"No recall response yet",null,2);
}
function showText(session: RecordSession): string {
  const value = toolResponses(session,"get_seatmap")[0] as Record<string,unknown> | undefined;
  return value ? JSON.stringify(Object.fromEntries(Object.entries(value).filter(([key])=>
    ["event_id","city","venue","date","weekday","artifact"].includes(key))),null,2) : "No seat map response yet";
}
function MemoryComparison({sessions}: {sessions: (RecordSession|null)[]}) {
  return <div className="guide-comparison">{sessions.map((session,i)=>session&&<section key={session.id}>
    <div className="kicker">Session {i===0?"A":"B"} · {session.events.length} events</div>
    <code>{session.id}</code>
    <h3>What recall() returned</h3>
    <pre>{recallText(session)}</pre>
    <h3>Which show get_seatmap() read</h3>
    <pre>{showText(session)}</pre>
    <p className="guide-small">A separate session keeps separate conversation events. Compare the recalled facts above.</p>
  </section>)}</div>;
}

type RecordPayload = {sessions: ({id:string; stored_state:Record<string,unknown>; events:RecordedEvent[]} | null)[];
  memory:string; archived?:boolean; memory_change?:{before:string;after:string;added:string[]}};

function Records({ slug, epoch }: { slug: string; epoch: string }) {
  const [open, setOpen] = useState(false);
  const [record, setRecord] = useState<RecordPayload | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {setRecord(await learningFetch<RecordPayload>(`/api/learning/${slug}/records`)); setError("");}
    catch(e) {setError((e as Error).message);}
  }, [slug]);
  useEffect(() => {if (open) load();}, [open, load, epoch]);
  return <details className="guide-more" onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>{slug === "remember" ? "Inspect the two stores · actual events, state and memory"
      : slug === "resume" ? "Inspect the resume · actual invocation and node records"
      : "Inspect the evidence · actual events and state"}</summary>
    {open && <div><button className="btn" onClick={load}>Refresh records</button>
      {error && <p role="alert">{error}</p>}
      {record?.archived && <p className="guide-small">Archived experiment · these records were saved before the live chapter changed.</p>}
      {slug==="remember"&&record&&<MemoryComparison sessions={record.sessions}/>}
      {record?.sessions.map((session,i)=>session ? <section key={session.id} className="guide-session">
        <h3>Session {i+1} · <code>{session.id}</code></h3>
        <details><summary>Persisted session state</summary><pre>{JSON.stringify(session.stored_state,null,2)}</pre></details>
        <details><summary>All events · tool calls, answers and node records</summary><div className="guide-events">{session.events.filter(e=>!e.content?.parts?.every(p=>!p.text&&!p.function_call&&!p.function_response)||e.node_info||e.output).map((event,index)=>
          <details key={event.id??index}><summary>
            <span className="guide-mono">{String(index+1).padStart(2,"0")}</span> {event.author} · {
              event.content?.parts?.some(p=>p.function_response) ? "tool response" :
              event.content?.parts?.some(p=>p.function_call) ? "tool call" : event.node_info ? "node record" : "message"}
            </summary><p className="guide-small">Invocation: {event.invocation_id??"—"} · Event: {event.id??"—"}</p>
            <pre>{JSON.stringify(event,null,2)}</pre></details>)}</div></details>
      </section>:<p key={i} className="guide-small">This session has left the live DB. Its completed experiment is preserved in the receipt archive.</p>)}
      {slug === "remember" && <section className="guide-session"><h3>Memory Service · memory/userx.md</h3>
        {record?.memory_change && <div className="guide-memory-change"><b>New lines written by remember()</b>
          <pre>{record.memory_change.added.join("\n")}</pre></div>}
        <details><summary>Read the complete memory file</summary><pre>{record?.memory}</pre></details><p className="guide-small">This file is separate from the Session DB. It contains selected facts, not a copy of the conversation.</p>
      </section>}
    </div>}
  </details>;
}

export function Guided() {
  const {slug = "meet"} = useParams();
  const guide = guides[slug];
  const {setCurrent, setGuided, refresh, bump, focus} = useBench();
  const [state, setState] = useState<LearningStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState("");
  const activeSlug = useRef(slug);
  activeSlug.current = slug;
  const reload = useCallback(async () => {
    if (slug === "cloud") return;
    try {
      const value = await learningFetch<LearningStatus>(`/api/learning/${slug}`);
      if (activeSlug.current === slug) setState(value);
    } catch(e) {if(activeSlug.current === slug) setError((e as Error).message);}
  }, [slug]);

  useEffect(() => {
    setState(null); setError(""); setAnswer(""); setCurrent(null);
    document.documentElement.style.setProperty("--accent", `var(--${slug==="resume"?"cyan":slug==="remember"?"green":"purple"})`);
    window.scrollTo({top:0});
    reload();
    const timer = setInterval(()=>{if(document.visibilityState === "visible")reload();}, 2500);
    return ()=>clearInterval(timer);
  }, [slug, reload, setCurrent]);

  useEffect(() => {
    setGuided({slug, sessionId:state?.task?.session_id??null, status:state?.receipt&&!state.loaded?"Historical result · another chapter is live":state?.task?.kind_label??"Prepare this chapter",
      next:state?.next??"prepare", ticket:state?.task?.queue_ticket??null,
      position:state?.venue?.ticket?.position??null, invocations:state?.task?.invocations??0, orders:state?.venue?.orders??null});
    return ()=>setGuided(null);
  }, [slug,state?.task?.session_id,state?.task?.kind_label,state?.receipt,state?.loaded,state?.next,state?.task?.queue_ticket,
      state?.venue?.orders,state?.venue?.ticket?.position,state?.task?.invocations,setGuided]);

  async function act(action: string, extra: Record<string,unknown> = {}) {
    if(busy)return;
    setBusy(true);setError("");
    try {
      const result = await learningFetch<LearningStatus>(`/api/learning/${slug}/${action}`,
        {attempt_id:state?.attempt?.id,...extra});
      if(activeSlug.current===slug){setState(result);setAnswer("");}
      if(action==="prepare"||action==="restart"||action==="restart-service")bump();
      await refresh();
    } catch(e) {if(activeSlug.current===slug)setError((e as Error).message);}
    finally {setBusy(false);await reload();}
  }

  if (!guide) return null;
  if (slug === "cloud") return <CloudDemo />;
  const next = state?.next??"prepare", attempt=state?.attempt, working=busy||!!state?.busy;
  const action=next==="restart-service" ? {title:"Restart the agent service.",
    text:"The process is stopped. Bring it back with this experiment's existing session and saved state.",
    button:"Restart service", expect:"The same session is available. No request or answer is sent automatically.", prompt:undefined}
    : guide.actions[next], receipt=state?.receipt;
  const phase= next==="prepare"||next==="request"?0
    :slug==="remember"?(next==="remember"?1:2)
    :slug==="resume"?(next==="kill"?1:2)
    :slug==="buy"?(next==="answer"?0:next==="scenario"?1:2):1;
  const keys=Object.keys(guides), nextChapter=keys[keys.indexOf(slug)+1];
  const sessionLink=state?.task?.session_id
    ? `/svc/agent/dev-ui/?app=concert&session=${encodeURIComponent(state.task.session_id)}` : "";
  return <div className="guide-page">
    <div className="kicker">Chapter {guide.number} · {guide.minutes}</div>
    <h1>{guide.title}</h1><p className="guide-intro">{guide.intro}</p>
    <p className="guide-boundary"><b>Task boundary</b> {guide.boundary}</p>
    <div className="guide-phases" aria-label="Chapter flow">
      {guide.phases.map((label,i)=><span key={label} className={!receipt&&phase===i?"active":""}>{i+1} · {label}</span>)}
      <span className={receipt?"active":""}>Result</span>
    </div>
    {!receipt && <section className="guide-action" aria-live="polite">
      <div className="kicker">Your next action</div>
      {next==="prepare"?<>
        <h2>{guide.number===1?"Check the rig, then start the story.":`Prepare chapter ${guide.number}.`}</h2>
        <p>Load this chapter's code, start the agent and create its session in one place.</p>
        <p className="guide-small">This starts a fresh experiment: the venue, live sessions and seeded memory reset.
          Existing learning receipts and their archived records stay available.</p>
        <button className="btn btn--solid" disabled={working||!state}
          onClick={()=>act("prepare",{fresh:!!attempt})}>{working?"Preparing…":`Prepare chapter ${guide.number}`}</button>
        <p className="guide-expect"><b>You will see</b> {slug==="meet"?"A real model reply, with agent and venue reachable.":"The exact session for this chapter, ready for its first request."}</p>
      </>:next==="answer"?<>
        <h2>{state?.task?.pending_message||"Answer this task's question."}</h2>
        <p>This goes to <code>{state?.task?.pending?.id}</code> in the session below. It answers the pending question; it does not start a new chat run.</p>
        <form onSubmit={e=>{e.preventDefault();act("answer",{text:answer,interrupt_id:state?.task?.pending?.id});}}>
          <label htmlFor="guide-answer">Your answer</label>
          <input id="guide-answer" autoComplete="off" value={answer} disabled={working} onChange={e=>setAnswer(e.target.value)}
            placeholder={state?.task?.pending?.id==="budget:ask"?"For example: Two tickets, up to $250 each.":"Confirm the read-back, or correct it."}/>
          <button className="btn btn--solid" disabled={working||!answer.trim()}>{working?"Sending…":"Send my answer"}</button>
        </form><p className="guide-expect"><b>You will see</b> A read-back first; only your confirmation creates authorization.</p>
      </>:next==="waiting"?<>
        <h2>The clock is running. Hands off.</h2>
        <p>Scheduled for {new Date((attempt?.marks.timer?.due_at??0)*1000).toLocaleTimeString()}. When it fires, the workbench sends a new request to the Runner.</p>
        <p className="guide-expect"><b>You will see</b> Another invocation in this session, with a recorded timer source.</p>
      </>:action?<>
        <h2>{action.title}</h2><p>{action.text}</p>
        {action.prompt&&<blockquote>{action.prompt}</blockquote>}
        <button className="btn btn--solid" disabled={working} onClick={()=>act(next)}>{working?"Running…":action.button}</button>
        <p className="guide-expect"><b>You will see</b> {action.expect}</p>
        {next==="scenario"&&attempt?.marks.scenario?.steps?.map(step=><p key={step} className="guide-small">✓ {step}</p>)}
      </>:<>
        <h2>Read what this run actually did.</h2>
        <p>The expected evidence is not complete yet. Open the records below to see whether a tool failed, the agent stopped, or the scenario took another path.</p>
        <button className="btn" onClick={reload}>Refresh evidence</button>
        {slug==="wake"&&<button className="btn ml-2" disabled={working} onClick={()=>act("clock")}>Start the clock again</button>}
      </>}
      {(error||attempt?.error)&&<p className="guide-error" role="alert">{error||attempt?.error}</p>}
      {working&&<div className="working-bar mt-4 h-[3px] rounded-full" aria-label="Action in progress" />}
    </section>}

    {attempt && <div className="guide-taskline">
      <div><span className="guide-small">This experiment</span><br/><code>{state?.task?.session_id??attempt.sessions.join(" → ")}</code></div>
      <div><span className="guide-small">Now</span><br/>{state?.loaded?state?.task?.kind_label:"Another chapter is loaded"}</div>
      {state?.loaded&&<div><span className="guide-small">Invocations</span><br/>{state?.task?.invocations??0}</div>}
      {state?.venue?.ticket&&<div><span className="guide-small">Queue position · not seconds</span><br/>{state.venue.ticket.position.toLocaleString()}</div>}
      {state?.task?.authorization_text&&<div><span className="guide-small">Authorization</span><br/>{state.task.authorization_text}</div>}
      <div className="flex gap-2"><button className="btn" disabled={!state?.loaded||!sessionLink} onClick={()=>focus("agent")}>Inspect in ADK</button>
        {state?.loaded&&sessionLink&&<a className="btn" href={sessionLink} target="_blank" rel="noreferrer">Open this session ↗</a>}</div>
    </div>}
    {attempt?.last_said?.length && !receipt ? <details className="guide-more"><summary>What the agent said</summary>
      {attempt.last_said.map((said,i)=><p key={i} className="whitespace-pre-wrap">{said}</p>)}</details>:null}
    <Result checks={state?.checks??[]} receipt={receipt}/>
    {attempt&&<Records key={`records-${slug}`} slug={slug} epoch={`${attempt.id}:${state?.task?.events??0}`}/>}
    <GuideReading key={`reading-${slug}`} slug={slug}/>
    <details className="guide-more"><summary>Recovery and preparation details</summary>
      <p>A fresh experiment replaces the live task and seeded memory. Earned receipts remain. Use it to deliberately repeat this chapter, not to resume a paused task.</p>
      <button className="btn" disabled={working} onClick={()=>act("prepare",{fresh:true})}>Start a fresh chapter {guide.number} experiment</button>
      {attempt?.preparation&&<pre>{attempt.preparation}</pre>}
    </details>
    <div className="guide-footer"><span>{receipt?"Evidence saved. You can move on.":"You can read ahead; completion requires the experiment's evidence."}</span>
      {nextChapter&&<Link className="btn" to={`/step/${nextChapter}`}>Next · {guides[nextChapter].number} →</Link>}</div>
  </div>;
}
