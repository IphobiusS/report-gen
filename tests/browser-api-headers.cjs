'use strict';
const assert=require('node:assert/strict');

// Synthetic app responses retain the identity returned by the real server.
// Do not route.fetch() the intercepted mutation: that would perform the write.
async function apiResponseHeaders(context,base){
  const response=await context.request.get(base+'/api/session');
  assert.equal(response.status(),200);
  const identity=response.headers()['x-report-gen-workspace'];
  assert.match(identity,/^[a-f0-9]{64}$/);
  assert.equal(identity,(await response.json()).workspace_id);
  return {'X-Report-Gen-Workspace':identity};
}
module.exports={apiResponseHeaders};
