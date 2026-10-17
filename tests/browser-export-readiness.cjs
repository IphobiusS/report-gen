/* Poll asynchronous API results in Node. Playwright's waitForFunction treats
 * a returned Promise as truthy before its boolean result becomes available. */
'use strict';
async function waitForVerifiedExport(page,id,{timeoutMs=120000,pollMs=100}={}){
  const deadline=Date.now()+timeoutMs;
  let last=null;
  while(Date.now()<deadline){
    last=await page.evaluate(key=>api.get('/api/jobs/'+key),id);
    if(last.id!==id)throw Error('Export status returned another job');
    if(last.stage==='error')throw Error(last.error||'Export failed');
    if(last.stage==='cancelled')throw Error('Export was cancelled');
    if(last.stage==='done'){
      if(last.verification_available!==true)throw Error('Completed export has no verification record');
      return last;
    }
    await new Promise(resolve=>setTimeout(resolve,pollMs));
  }
  throw Error('Export did not complete within '+timeoutMs+' ms; last stage: '+(last?.stage||'unknown'));
}
module.exports={waitForVerifiedExport};
