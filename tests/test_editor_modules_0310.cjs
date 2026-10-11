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

function projectSearch(language, data){
  const app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
  const source=app.slice(app.indexOf('function searchTargets()'),app.indexOf('function navTo(nav)'));
  return new Function('S',source+'\nreturn searchProject;')({uiLang:language,data,catBy:{}});
}

for(const language of ['es','en']){
  test(language+': search matches canonically equivalent accents and authored whitespace without mutating content',()=>{
    const data={meta:{},report:{sections:[{key:'unicode',title:'Synthetic chapter',body:'La remediacio\u0301n conserva café y corrective\n\t action.',private_note:'PRIVATE_UNICODE_CANARY'}]},findings:[]};
    const before=JSON.stringify(data),search=projectSearch(language,data);
    for(const query of ['remediación','remediacio\u0301n','cafe\u0301','corrective action','corrective\n\t action']){
      const matches=search(query);
      assert.equal(matches.length,1,query);
      assert.deepEqual(matches[0].nav,{type:'section',key:'unicode'});
      assert.equal(matches[0].snippet.mid,query.normalize('NFC').replace(/\s+/g,' '));
    }
    assert.deepEqual(search('PRIVATE_UNICODE_CANARY'),[]);
    assert.equal(JSON.stringify(data),before);
  });

  test(language+': search highlights original characters after expanding case conversion',()=>{
    const search=projectSearch(language,{meta:{},report:{sections:[{key:'unicode',body:'İ before TARGET after İ'}]},findings:[]});
    assert.equal(search('target')[0].snippet.mid,'TARGET');
    assert.equal(search('İ')[0].snippet.mid,'İ');
    assert.equal(search('i')[0].snippet.mid,'İ');
  });

  test(language+': search snippets preserve complete graphemes at all slice boundaries',()=>{
    for(const [body,query,mid]of [
      ['X😀'+'A'.repeat(29)+'TARGET tail','TARGET','TARGET'],
      ['TARGET'+'A'.repeat(39)+'😀 tail','TARGET','TARGET'],
      ['X👩‍💻'+'A'.repeat(29)+'TARGET tail','TARGET','TARGET'],
      ['before 👩‍💻 after','👩','👩‍💻'],
    ]){
      const search=projectSearch(language,{meta:{},report:{sections:[{key:'unicode',body}]},findings:[]});
      const snippet=search(query)[0].snippet;
      assert.equal(snippet.mid,mid);
      assert.ok(Object.values(snippet).every(part=>part.isWellFormed()));
      assert.ok(!snippet.pre.startsWith('…\u200d'));
    }
  });

  test(language+': global search includes custom section title and body without indexing private fields',()=>{
    const data={meta:{},report:{sections:[{key:'bank-boundaries',title:'Bank boundaries',body:'Quorum evidence narrative.',private_note:'PRIVATE_SECTION_CANARY'}]},findings:[]};
    const before=JSON.stringify(data),search=projectSearch(language,data);
    for(const query of ['Bank boundaries','Quorum evidence']){
      const matches=search(query);
      assert.equal(matches.length,1);
      assert.deepEqual(matches[0].nav,{type:'section',key:'bank-boundaries'});
      assert.equal(matches[0].where,'Bank boundaries');
    }
    assert.deepEqual(search('PRIVATE_SECTION_CANARY'),[]);
    assert.equal(JSON.stringify(data),before);
  });

  test(language+': global search finds a finding by its stable ID without a prose mention',()=>{
    const data={meta:{},findings:Array.from({length:18},(_,i)=>({id:'F'+(i+1),title:'Banking control '+(i+1),description_md:'Synthetic control description.'}))};
    const before=JSON.stringify(data),search=projectSearch(language,data);
    const matches=search(' f18 ');
    assert.equal(matches[0]?.nav.type,'finding');
    assert.equal(matches[0]?.nav.idx,17);
    assert.match(matches[0]?.where,/^F18 /);
    assert.equal(matches[0]?.snippet.mid,'F18');
    assert.equal(search('Banking control 18')[0]?.nav.idx,17);
    assert.deepEqual(search('F180'),[]);
    assert.equal(JSON.stringify(data),before);
  });

  test(language+': exact finding ID outranks many cross-references before the result limit',()=>{
    const data={meta:{report_title:'Review F18'},findings:Array.from({length:55},(_,i)=>({id:'F'+(i+1),title:'Banking control '+(i+1),description_md:'See F18 for related context.',impact_md:'See F18 again.',remediation_md:'Coordinate with F18.'}))};
    // Manual order differs from numeric order: the target is deliberately last.
    data.findings.push(data.findings.splice(17,1)[0]);
    const before=JSON.stringify(data),search=projectSearch(language,data),matches=search('F18');
    assert.equal(matches[0]?.nav.type,'finding');
    assert.equal(matches[0]?.nav.idx,54);
    assert.equal(matches[0]?.snippet.mid,'F18');
    assert.equal(matches.length,40);
    assert.ok(matches.some(row=>row.nav.type==='report'));
    assert.equal(search('banking control 55')[0]?.nav.idx,53);
    assert.equal(JSON.stringify(data),before);
  });
}

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

// Async editor boundaries use the complete UI modules and controlled responses.
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function draftRecoveryEditor(){
  const dom=new JSDOM('<!doctype html><html><body><main id="editor" tabindex="-1"></main></body></html>',{runScripts:'outside-only',url:'http://localhost/'});
  dom.window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  dom.window.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new dom.window.Event('close'));};
  dom.window.requests=[];dom.window.toasts=[];dom.window.saved=[];
  const app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
  dom.window.eval(app.slice(0,app.indexOf('// ---- shared transport'))+`
    const scopedResourceURL=value=>value,S={slug:'alpha',uiLang:'en',data:{meta:{report_title:'Alpha'},report:{sections:[]}}};
    const BrowserWorkspace={current:()=> 'workspace'},toast=message=>window.toasts.push(message),invalidateValidation=()=>{};
    const projectStore={slug:'alpha',data:S.data,base:JSON.parse(JSON.stringify(S.data)),revision:0,etag:'a1',recovery:[],
      remote:()=>new Promise((resolve,reject)=>window.requests.push({kind:'remote',slug:S.slug,resolve,reject})),
      adopt(data,remote){this.data=data;this.etag=remote.etag;this.revision++;}};
    const appFetch=(url,options)=>new Promise((resolve,reject)=>window.requests.push({kind:'check',url,options,resolve,reject}));
    const api={get:url=>new Promise((resolve,reject)=>window.requests.push({kind:'inspection',url,resolve,reject}))};
    const requireOk=async response=>{if(!response.ok)throw Error('rejected');return response;};
    const doSave=async()=>{window.saved.push({slug:S.slug,data:JSON.parse(JSON.stringify(S.data))});return true;};
    const renderSidebar=()=>{},renderMain=()=>{};
  `+fs.readFileSync(path.join(root,'webapp/static/drafts.js'),'utf8')+'\n'+fs.readFileSync(path.join(root,'webapp/static/studio.js'),'utf8')+`
    window.recovery={run:StudioUI.resolveDraft,inspect:StudioUI.inspector,state:S,store:projectStore};
  `);
  return dom;
}
const remoteDraft={data:{meta:{report_title:'Alpha on disk'},report:{sections:[]}},etag:'a2'};
const acceptDraft=request=>request.resolve({ok:true,json:async()=>({data:JSON.parse(request.options.body)})});
for(const change of ['project','edit','reload','revision'])test('draft recovery rejects a remote response after '+change,async()=>{
  const dom=draftRecoveryEditor(),{recovery,requests}=dom.window;
  try{
    const pending=recovery.run(),result=assert.rejects(pending,/project changed/i);
    if(change==='project'){recovery.state.slug='beta';recovery.state.data={meta:{report_title:'Beta'}};}
    else if(change==='edit')recovery.store.revision++;
    else if(change==='reload')recovery.state.data=JSON.parse(JSON.stringify(recovery.state.data));
    else recovery.store.etag='new-revision';
    requests[0].resolve(remoteDraft);await result;
    assert.equal(dom.window.document.querySelectorAll('dialog').length,0);
    assert.equal(dom.window.saved.length,0);
  }finally{dom.window.close();}
});

test('latest draft recovery wins when two remote reads finish out of order',async()=>{
  const dom=draftRecoveryEditor(),{recovery,requests}=dom.window;
  try{
    const first=recovery.run(),obsolete=assert.rejects(first,/project changed/i),second=recovery.run();
    requests[1].resolve(remoteDraft);await second;requests[0].resolve(remoteDraft);await obsolete;
    assert.equal(dom.window.document.querySelectorAll('dialog[open]').length,1);
  }finally{dom.window.close();}
});

for(const change of ['cancel','project','edit'])test('draft-check completion cannot adopt after '+change,async()=>{
  const dom=draftRecoveryEditor(),{recovery,requests}=dom.window;
  try{
    const open=recovery.run();requests[0].resolve(remoteDraft);await open;
    const dialog=dom.window.document.querySelector('dialog');
    [...dialog.querySelectorAll('button')].find(b=>b.textContent==='Apply choices and save').click();
    assert.equal(requests[1].kind,'check');
    if(change==='cancel')dialog.close();
    else if(change==='project'){dialog.close();recovery.state.slug='beta';recovery.state.data={meta:{report_title:'Beta'}};}
    else {recovery.state.data.meta.report_title='Newer local edit';recovery.store.revision++;}
    const before=JSON.stringify(recovery.state.data);acceptDraft(requests[1]);await settle();
    assert.equal(JSON.stringify(recovery.state.data),before);assert.equal(dom.window.saved.length,0);
  }finally{dom.window.close();}
});

test('an unchanged recovery still saves the reviewed merge to its original project',async()=>{
  const dom=draftRecoveryEditor(),{recovery,requests}=dom.window;
  try{
    const open=recovery.run();requests[0].resolve(remoteDraft);await open;
    [...dom.window.document.querySelectorAll('dialog button')].find(b=>b.textContent==='Apply choices and save').click();
    acceptDraft(requests[1]);await settle();
    assert.equal(dom.window.saved.length,1);assert.equal(dom.window.saved[0].slug,'alpha');
    assert.equal(dom.window.saved[0].data.meta.report_title,'Alpha on disk');
  }finally{dom.window.close();}
});

function markdownEditor(){
  const dom=new JSDOM('<!doctype html><html><body><main></main></body></html>',{runScripts:'outside-only',url:'http://localhost/'});
  const app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');dom.window.requests=[];
  dom.window.eval(app.slice(0,app.indexOf('// ---- shared transport'))+`
    const scopedResourceURL=value=>value,S={slug:'alpha',uiLang:'en'},WorkflowUI={uid:()=> 'fixture'};
    const autoGrow=()=>{},scheduleSave=()=>{},requireOk=async r=>{if(!r.ok)throw Error('failed');return r;};
    const api={post:(url,body)=>new Promise((resolve,reject)=>window.requests.push({url,body,resolve,reject}))};
  `+app.slice(app.indexOf('function mdEditor('),app.indexOf('function reportEditor('))+`
    document.querySelector('main').append(mdEditor('Notes',{body:'Older paragraph'},'body'));
    window.editorState=S;
  `);
  return dom;
}
const rendered=text=>({ok:true,json:async()=>({html:'<p>'+text+'</p>'})});
for(const result of ['success','failure'])test('an obsolete Markdown '+result+' cannot replace the latest preview',async()=>{
  const dom=markdownEditor(),{document,requests}=dom.window;
  try{
    document.querySelector('[data-role="p"]').click();document.querySelector('[data-role="w"]').click();
    const textarea=document.querySelector('textarea');textarea.value='Newer paragraph';textarea.dispatchEvent(new dom.window.Event('input'));
    document.querySelector('[data-role="p"]').click();requests[1].resolve(rendered('Newer paragraph'));await settle();
    if(result==='success')requests[0].resolve(rendered('Older paragraph'));else requests[0].reject(Error('Old failed request'));
    await settle();assert.equal(document.querySelector('.mded-prev').textContent,'Newer paragraph');
  }finally{dom.window.close();}
});

for(const change of ['edit','save','reload'])test('publication inspector discards a snapshot after '+change,async()=>{
  const dom=draftRecoveryEditor(),{recovery,requests}=dom.window;
  try{
    const pending=recovery.inspect();await settle();assert.equal(requests[0].kind,'inspection');
    if(change==='edit'){recovery.state.data.meta.report_title='New secret';recovery.store.revision++;}
    else if(change==='save')recovery.store.etag='new-saved-revision';
    else recovery.state.data=JSON.parse(JSON.stringify(recovery.state.data));
    requests[0].resolve({revision:'old-revision',alerts:[],images:[],text:'Previously inspected text',private_captures:0});
    await pending;assert.equal(dom.window.document.querySelectorAll('dialog').length,0);
  }finally{dom.window.close();}
});
