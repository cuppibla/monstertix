import test from "node:test";
import assert from "node:assert/strict";
import {purchaseEvidence} from "../src/lib/purchaseEvidence.ts";

const response = (value, snake=false) => ({content:{parts:[{
  [snake ? "function_response" : "functionResponse"]:{name:"purchase",response:value},
}]}});
test("extracts the actual successful response, its event number and the matching venue order",()=>{
  const session={events:[
    {content:{parts:[{text:"attempts: 999"}]}},
    response({error:true,reason:"stale_plan"}),
    response({id:"ord-current",attempts:2,duplicate:true,idempotency_key:"key"}),
  ]};
  const result=purchaseEvidence(session,{orders:[{id:"ord-current",idem_key:"key"}],order_count:1},"ord-current");
  assert.equal(result.purchase.eventNumber,3);
  assert.equal(result.purchase.response.attempts,2);
  assert.equal(result.guard.eventNumber,2);
  assert.equal(result.venueOrder.id,"ord-current");
  assert.equal(result.venueOrderCount,1);
});
test("never borrows a previous order's retry evidence",()=>{
  const result=purchaseEvidence({events:[
    response({id:"ord-old",attempts:2,duplicate:true},true),
    response({id:"ord-current",attempts:1}),
  ]},{orders:[{id:"ord-old"}],order_count:1},"ord-current");
  assert.equal(result.purchase.response.attempts,1);
  assert.equal(result.purchase.response.duplicate,undefined);
  assert.equal(result.venueOrder,null);
});
test("missing events or a reset venue are unknown, not a completed experiment",()=>{
  const result=purchaseEvidence({},{},"ord-current");
  assert.equal(result.purchase,null);
  assert.equal(result.venueOrderCount,null);
});
test("accepts stored snake-case events and preserves response fields without coercion",()=>{
  const result=purchaseEvidence({events:[response({order_id:"ord-current",attempts:"2",duplicate:"true"},true)]},
    {orders:[],order_count:0},"ord-current");
  assert.equal(result.purchase.response.attempts,"2");
  assert.equal(result.purchase.response.duplicate,"true");
  assert.equal(result.venueOrderCount,0);
});
