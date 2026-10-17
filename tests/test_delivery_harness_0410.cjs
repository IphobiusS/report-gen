'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {waitForVerifiedExport}=require('./browser-export-readiness.cjs');
test('Delivery acceptance awaits each asynchronous status until verified completion',async()=>{
  const states=['queued','rendering_html','checking_html','packaging','done'];let calls=0,inFlight=0;
  const page={async evaluate(callback,id){assert.equal(id,'expected-job');assert.equal(inFlight++,0,'No overlapping status reads');await new Promise(resolve=>setImmediate(resolve));inFlight--;const stage=states[calls++];return{id,stage,verification_available:stage==='done'};}};
  const result=await waitForVerifiedExport(page,'expected-job',{timeoutMs:1000,pollMs:1});
  assert.equal(calls,5);assert.equal(result.stage,'done');assert.equal(result.verification_available,true);
});
for(const stage of ['error','cancelled'])test('Delivery acceptance fails immediately for '+stage,async()=>{
  let calls=0;const page={async evaluate(_callback,id){calls++;return{id,stage,error:stage==='error'?'Synthetic rendering error':null};}};
  await assert.rejects(waitForVerifiedExport(page,'expected-job',{timeoutMs:1000,pollMs:1}),stage==='error'?/Synthetic rendering error/:/cancelled/);assert.equal(calls,1);
});
test('Missing verification at terminal completion is an error, not a retry',async()=>{
  let calls=0;const page={async evaluate(_callback,id){calls++;return{id,stage:'done',verification_available:false};}};
  await assert.rejects(waitForVerifiedExport(page,'expected-job',{timeoutMs:1000,pollMs:1}),/no verification record/);assert.equal(calls,1);
});
test('Delivery acceptance rejects a status belonging to another export',async()=>{
  const page={async evaluate(){return{id:'different-job',stage:'done',verification_available:true};}};
  await assert.rejects(waitForVerifiedExport(page,'expected-job',{timeoutMs:1000,pollMs:1}),/another job/);
});
test('Delivery acceptance bounds a queue that never finishes',async()=>{
  const page={async evaluate(_callback,id){return{id,stage:'packaging',verification_available:false};}};
  await assert.rejects(waitForVerifiedExport(page,'expected-job',{timeoutMs:20,pollMs:1}),/last stage: packaging/);
});
