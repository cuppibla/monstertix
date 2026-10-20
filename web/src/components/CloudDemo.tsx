import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { guides } from "../lib/guide";
import { learningFetch } from "../lib/learning";
import { GuideReading } from "./GuideReading";

type Cloud = {configured:boolean;url:string;error:string;
  demo:{session_id?:string;dispatch?:{at:number;job:string;note:string}};
  task:null|{session_id:string;pending?:{kind:string;message:string};queue_ticket?:string;
    last_order?:unknown;authorization?:{confirmed?:boolean;seats?:number;per_seat_max?:number};invocations?:number}};

export function CloudDemo(){
  const guide=guides.cloud;
  const [state,setState]=useState<Cloud|null>(null),[sid,setSid]=useState(""),
    [error,setError]=useState(""),[busy,setBusy]=useState(false);
  async function reload(){try{setState(await learningFetch<Cloud>("/api/cloud-demo"));}catch(e){setError((e as Error).message);}}
  useEffect(()=>{reload();const timer=setInterval(reload,8000);return()=>clearInterval(timer);},[]);
  async function act(action:string){setBusy(true);setError("");try{
    const value=await learningFetch<Cloud>(`/api/cloud-demo/${action}`,{session_id:sid||state?.demo.session_id});
    setState(value);
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <div className="guide-page">
    <div className="kicker">Chapter 6 · instructor demo · {guide.minutes}</div>
    <h1>{guide.title}</h1><p className="guide-intro">{guide.intro}</p>
    <p className="guide-boundary"><b>Task boundary</b> {guide.boundary}</p>
    <section className="guide-action"><div className="kicker">One new thing to observe</div>
      <h2>A real Scheduler request resumes a real cloud task.</h2>
      <p>The instructor prepares a deployed task and confirms its budget on the cloud page. Keep that task waiting in the queue. Enter its session ID here, then bring its venue ticket to the front before triggering Scheduler.</p>
      {!state?.configured?<div className="guide-expect"><b>Cloud not configured here</b>
        <span>Follow the instructor's deployed page, or use the optional deployment route below. No cloud run or order has been verified on this workbench.</span></div>:<>
        <a className="btn" target="_blank" rel="noreferrer" href={state.url}>Open configured cloud page ↗</a>
        <form onSubmit={e=>{e.preventDefault();act("inspect");}}>
          <label htmlFor="cloud-session">Cloud session ID</label>
          <input id="cloud-session" value={sid} onChange={e=>setSid(e.target.value)} placeholder={state.demo.session_id||"Paste the ID from the cloud page"} />
          <button className="btn" disabled={busy||!(sid||state.demo.session_id)}>Inspect this cloud task</button>
        </form>
        {state.task&&<div className="guide-taskline"><div>Session<br/><code>{state.task.session_id}</code></div>
          <div>Waiting on<br/>{state.task.pending?.kind??"nothing"}</div>
          <div>Authorization<br/>{state.task.authorization?.confirmed?`${state.task.authorization.seats} tickets · up to $${state.task.authorization.per_seat_max} each`:"not confirmed"}</div></div>}
        <button className="btn btn--solid" disabled={busy||state.task?.pending?.kind!=="queue"||!state.task?.authorization?.confirmed}
          onClick={()=>act("dispatch")}>{busy?"Working…":"Run the existing Scheduler job"}</button>
        {state.demo.dispatch&&<p className="guide-expect"><b>Dispatch accepted</b>{state.demo.dispatch.job} · {new Date(state.demo.dispatch.at*1000).toLocaleTimeString()}. Check the cloud task and Cloud Run logs next.</p>}
        {state.task?.last_order&&<p className="guide-expect"><b>Cloud task reports an order</b><code>{typeof state.task.last_order==="string"?state.task.last_order:JSON.stringify(state.task.last_order)}</code></p>}
      </>}
      {(error||state?.error)&&<p className="guide-error" role="alert">{error||state?.error}</p>}
      <p className="guide-small">The button dispatches the existing job; it does not deploy resources. A dispatch acknowledgement alone is not proof of completion. Verify the trigger in Cloud Run logs and match the final order ID to the venue.</p>
    </section>
    <div className="guide-flow"><span>Scheduler<br/><b>External caller</b></span><i>→</i><span>Pub/Sub + Cloud Run<br/><b>Read the saved task</b></span><i>→</i><span>Resume<br/><b>Inspect the order</b></span></div>
    <GuideReading slug="cloud"/>
    <section className="guide-action"><div className="kicker">Optional extension · allow 20–30 more minutes</div>
      <h2>Deploy your own copy.</h2><p>The full route includes deployment, a new cloud task, your own budget answers, Scheduler, logs and cleanup. If you create resources, finish the cleanup step too.</p>
      <div className="flex flex-wrap gap-2"><Link className="btn" to="/study/cloud/a">Deploy →</Link><Link className="btn" to="/study/cloud/b">Wake the cloud task →</Link><Link className="btn" to="/study/cloud/c">Cleanup →</Link></div>
    </section>
    <div className="guide-footer"><span>One story: remember the task, wait safely, wake it and finish within the person's limit.</span><Link className="btn" to="/step/meet">Review the course →</Link></div>
  </div>;
}
