import test from "node:test";
import assert from "node:assert/strict";
import {preparePurchaseScenario,completePurchaseScenario} from "../src/lib/purchaseScenario.ts";

function setup(overrides = {}, failAt) {
  const calls = [], visible = [];
  const task = {session_id:"my-session",pending:{kind:"queue"},queue_ticket:"my-ticket",
    queue_event_id:"my-show",authorization:{confirmed:true},last_order:null,...overrides};
  const client = {
    stage:async()=>({step:5}),
    task:async id=>{assert.equal(id,"my-session");return task;},
    venue:async(action,body)=>{calls.push({action,body});return action===failAt?{ok:false,error:"offline"}:{ok:true};},
  };
  return {client,calls,visible,run:()=>preparePurchaseScenario(client,"my-session",label=>visible.push(label))};
}

test("preparation targets the selected show and ticket, and records each observed change",async()=>{
  const f=setup();await f.run();
  assert.deepEqual(f.calls,[
    {action:"sellout",body:{event_id:"my-show",section:"A"}},
    {action:"hang-once",body:{}},
    {action:"advance-queue",body:{ticket:"my-ticket"}},
  ]);
  assert.equal(f.visible.length,3);
});
for(const [label,overrides] of [
  ["another session",{session_id:"other"}],["a human question",{pending:{kind:"person"}}],
  ["no ticket",{queue_ticket:null}],["no authorization",{authorization:{}}],
  ["an existing order",{last_order:"ord-existing"}],
]) test(`refuses ${label} before changing the venue`,async()=>{
  const f=setup(overrides);await assert.rejects(f.run);assert.equal(f.calls.length,0);
});
test("wrong chapter makes no venue changes",async()=>{
  const f=setup();f.client.stage=async()=>({step:3});
  await assert.rejects(f.run,/chapter 5/);assert.equal(f.calls.length,0);
});
test("failed arming never advances the ticket or reports it ready",async()=>{
  const f=setup({},"hang-once");await assert.rejects(f.run,/offline/);
  assert.equal(f.calls.length,2);assert.equal(f.visible.length,1);
});

test("one-click completion prepares before resuming exactly the authorized session",async()=>{
  const f=setup();
  f.client.taskResume=async id=>{assert.equal(f.calls.length,3);assert.equal(id,"my-session");return {ok:true,session_id:id};};
  const result=await completePurchaseScenario(f.client,"my-session",s=>f.visible.push(s));
  assert.equal(result.ok,true);
  assert.match(f.visible.at(-1),/Resuming/);
});
test("one-click completion never answers a human question or repeats a completed purchase",async()=>{
  for(const overrides of [{pending:{kind:"person"}},{last_order:"ord-existing"}]){
    const f=setup(overrides);
    f.client.taskResume=async()=>assert.fail("must not resume");
    await assert.rejects(()=>completePurchaseScenario(f.client,"my-session",()=>{}));
    assert.equal(f.calls.length,0);
  }
});
test("a partial preparation failure does not resume",async()=>{
  const f=setup({},"hang-once");f.client.taskResume=async()=>assert.fail("must not resume");
  await assert.rejects(()=>completePurchaseScenario(f.client,"my-session",()=>{}),/offline/);
});
test("a changed task after preparation does not resume",async()=>{
  const f=setup();const read=f.client.task;let reads=0;
  f.client.task=async id=>({...await read(id),...(++reads>1?{pending:null,last_order:"ord-existing"}:{})});
  f.client.taskResume=async()=>assert.fail("must not resume");
  await assert.rejects(()=>completePurchaseScenario(f.client,"my-session",()=>{}),/changed/);
});
test("duplicate clicks while completing do not send a second resume",async()=>{
  const f=setup();let release;
  f.client.taskResume=()=>new Promise(resolve=>{release=()=>resolve({ok:true,session_id:"my-session"});});
  const first=completePurchaseScenario(f.client,"my-session",()=>{});
  await assert.rejects(()=>completePurchaseScenario(f.client,"my-session",()=>{}),/already/);
  await new Promise(resolve=>setImmediate(resolve));
  release();await first;
  assert.equal(f.calls.length,3);
});
