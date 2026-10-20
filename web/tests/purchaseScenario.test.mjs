import test from "node:test";
import assert from "node:assert/strict";
import {preparePurchaseScenario} from "../src/lib/purchaseScenario.ts";

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
