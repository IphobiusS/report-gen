'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const CVSS31=require(path.join(root,'webapp/static/cvss31.js'));
const CVSS40=require(path.join(root,'webapp/static/cvss40.js'));
const valid='CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H';
const invalid=[
  'CVSS:3.1/AV:N', valid.replace('/S:U/','/S:Z/'), valid+'/AV:N',
  valid.replace('/AV:N/','/AV:Network/'), valid+'/E:X', valid+'/',
  valid.replace('/C:H/','/C:H:H/'), valid.replace('3.1','3.0'),
  valid.replace('3.1','9.9'), 'anything', '', null, 31,
];

test('CVSS module validates complete vectors without altering its defaults or caller metrics',()=>{
  const metrics=CVSS31.parse(valid),before=JSON.stringify(metrics);
  assert.equal(CVSS31.compute(metrics).score,9.8);
  assert.equal(JSON.stringify(metrics),before);
  for(const vector of invalid)assert.throws(()=>CVSS31.parse(vector));
  for(const metrics of [{S:'Z'},{C:'unknown'},{AV:3}])assert.throws(()=>CVSS31.compute(metrics));
  assert.equal(CVSS31.compute().score,0);
  assert.throws(()=>{CVSS31.metrics.D.C='H';},TypeError);
  assert.equal(CVSS31.compute().score,0);
});

function editor(language, finding){
  const dom=new JSDOM('<!doctype html><html><body><main></main></body></html>',{runScripts:'outside-only',url:'http://localhost/'});
  const app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
  const helpers=app.slice(0,app.indexOf('// ---- shared transport'));
  const source=['cvss31.js','cvss40.js','cvss-editor.js'].map(file=>fs.readFileSync(path.join(root,'webapp/static',file),'utf8')).join('\n');
  dom.window.finding=finding;
  dom.window.eval(helpers+'\n'+source+`
    const S={uiLang:${JSON.stringify(language)}};
    const t=key=>key, scopedResourceURL=value=>value;
    let saves=0,renders=0;
    function scheduleSave(){saves++;}
    function renderMain(){renders++;}
    function renderSidebar(){}
    document.querySelector('main').append(CVSSEditor.widget(window.finding));
    window.state=()=>({saves,renders});
  `);
  return dom;
}

for(const language of ['es','en']){
  test(language+': CVSS 4.0 displays and preserves threat, environmental and supplemental metrics',()=>{
    const vector='CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H/E:U/CR:L/IR:L/AR:L/MAV:P/S:N/AU:Y/R:U/V:C/RE:H/U:Red';
    const result=CVSS40.score(vector),finding={title:'Contextual score',cvss_version:'4.0',cvss:String(result.score),cvss_vector:vector,severity:result.severity,macrovector:result.macrovector};
    const before=JSON.stringify(finding),dom=editor(language,finding);
    try{
      assert.equal(dom.window.document.querySelector('.cvss-score-big').textContent,result.score.toFixed(1));
      assert.equal(dom.window.document.querySelector('.cvss-vec').textContent,vector);
      assert.equal(JSON.stringify(finding),before);assert.equal(dom.window.state().saves,0);
      const select=dom.window.document.querySelector('.cvssbox select');
      select.value='A';select.dispatchEvent(new dom.window.Event('change'));
      const expected=vector.replace('/AV:N/','/AV:A/'),updated=CVSS40.score(expected);
      assert.equal(finding.cvss_vector,expected);assert.equal(finding.cvss,String(updated.score));
      assert.equal(finding.severity,updated.severity);assert.equal(finding.macrovector,updated.macrovector);
      assert.equal(dom.window.document.querySelector('.cvss-vec').textContent,expected);
      assert.equal(dom.window.state().saves,1);
    }finally{dom.window.close();}
  });

  test(language+': malformed CVSS 4.0 warns without rewriting the stored vector',()=>{
    const finding={title:'Malformed contextual score',cvss_version:'4.0',cvss_vector:'CVSS:4.0/AV:N',severity:'low'};
    const before=JSON.stringify(finding),dom=editor(language,finding);
    try{
      assert.equal(dom.window.document.querySelector('[role="status"]').textContent,'cvss_paste_bad');
      assert.equal(JSON.stringify(finding),before);assert.equal(dom.window.state().saves,0);
    }finally{dom.window.close();}
  });

  test(language+': rejected pasted CVSS vectors preserve the entire finding and do not save',()=>{
    const finding={title:'Synthetic finding',cvss_version:'3.1',cvss:'9.8',cvss_vector:valid,severity:'critical'};
    const dom=editor(language,finding),before=JSON.stringify(finding),input=dom.window.document.querySelector('.cvss-paste');
    try{
      for(const vector of invalid.filter(value=>typeof value==='string'&&value)){
        input.value=vector;input.dispatchEvent(new dom.window.Event('change'));
        assert.equal(dom.window.document.querySelector('.cvss-paste-err').textContent,'cvss_paste_bad',vector);
        assert.equal(JSON.stringify(finding),before,vector);
        assert.equal(dom.window.state().saves,0,vector);
      }
      input.value=valid.slice('CVSS:3.1/'.length).replaceAll('/',' / ');
      input.dispatchEvent(new dom.window.Event('change'));
      assert.equal(dom.window.document.querySelector('.cvss-paste-err').textContent,'');
      assert.equal(finding.cvss_vector,valid);assert.equal(finding.cvss,'9.8');
      assert.equal(dom.window.state().saves,1);
    }finally{dom.window.close();}
  });

  test(language+': opening a malformed saved vector warns without silently rewriting it',()=>{
    const finding={title:'Legacy finding',cvss_version:'3.1',cvss_vector:'CVSS:3.1/AV:N',severity:'high'};
    const before=JSON.stringify(finding),dom=editor(language,finding);
    try{
      assert.ok(dom.window.document.querySelector('[role="status"]').textContent.includes('cvss_paste_bad'));
      assert.equal(JSON.stringify(finding),before);assert.equal(dom.window.state().saves,0);
    }finally{dom.window.close();}
  });
}

function validationEditor(){
  const dom=new JSDOM('<!doctype html><html><body><button id="validateBtn">✓</button></body></html>',{runScripts:'outside-only',url:'http://localhost/'});
  const app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
  dom.window.requests=[];dom.window.toasts=[];dom.window.panels=[];
  dom.window.eval(`
    const $=s=>document.querySelector(s),S={slug:'alpha',data:{meta:{report_title:'Alpha'}},uiLang:'es'},projectStore={revision:0};
    const t=key=>key,toast=(...args)=>window.toasts.push(args),requireOk=async response=>{if(!response.ok)throw Error('failed');return response;};
    const appFetch=(url,options)=>new Promise((resolve,reject)=>window.requests.push({url,options,resolve,reject}));
    const closeModal=modal=>modal.remove(),showValidationPanel=issues=>window.panels.push(issues);
    ${app.slice(app.indexOf('let validationGeneration ='),app.indexOf('function showValidationPanel('))}
    window.validation={run:runValidation,invalidate:invalidateValidation,state:S,store:projectStore};
  `);
  return dom;
}
const validationResponse=issues=>({ok:true,json:async()=>({issues})});

test('validation discards older results after an edit, project replacement or UI language change',async()=>{
  for(const change of ['edit','project','language']){
    const dom=validationEditor(),{validation,requests,toasts,panels}=dom.window;
    try{
      const pending=validation.run();assert.equal(requests.length,1);
      if(change==='edit')validation.store.revision++;
      else if(change==='project'){validation.state.slug='beta';validation.state.data={meta:{report_title:'Beta'}};}
      else validation.state.uiLang='en';
      validation.invalidate();
      requests[0].resolve(validationResponse([{level:'error',message:'Old finding'}]));await pending;
      assert.equal(panels.length,0,change);assert.equal(toasts.length,0,change);
      assert.equal(dom.window.document.querySelector('#validateBtn').className,'',change);
      assert.equal(dom.window.document.querySelector('#validateBtn').hasAttribute('aria-busy'),false,change);
    }finally{dom.window.close();}
  }
});

test('only the latest validation request may publish a result and editing clears its old success',async()=>{
  const dom=validationEditor(),{validation,requests,toasts,panels}=dom.window;
  try{
    const first=validation.run(),second=validation.run();
    requests[1].resolve(validationResponse([]));await second;
    assert.equal(dom.window.document.querySelector('#validateBtn').className,'ok');assert.equal(toasts.length,1);
    requests[0].resolve(validationResponse([{level:'error',message:'Obsolete'}]));await first;
    assert.equal(panels.length,0);assert.equal(dom.window.document.querySelector('#validateBtn').className,'ok');
    validation.invalidate();assert.equal(dom.window.document.querySelector('#validateBtn').className,'');
  }finally{dom.window.close();}
});

test('an obsolete failed validation cannot toast an error for the replacement project',async()=>{
  const dom=validationEditor(),{validation,requests,toasts}=dom.window;
  try{
    const pending=validation.run();validation.invalidate();requests[0].reject(Error('Old failure'));await pending;
    assert.equal(toasts.length,0);
  }finally{dom.window.close();}
});
