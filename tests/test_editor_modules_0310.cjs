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
  return new Function('S','window',app.slice(0,app.indexOf('// ---- shared transport'))+source+'\nreturn searchProject;')({uiLang:language,data,catBy:{}},{});
}

function searchActivation(){
  const dom=new JSDOM('<div class="search-wrap"><input id="globalSearch"><div id="searchResults"></div></div><button id="elsewhere">Elsewhere</button>',{runScripts:'outside-only',url:'http://localhost/'});
  const read=name=>fs.readFileSync(path.join(root,'webapp/static',name),'utf8').replace(/\r\n/g,'\n');
  const w=dom.window,app=read('app.js'),workbench=read('workbench.js');
  const between=(source,start,end)=>{
    const first=source.indexOf(start);assert.ok(first>=0,'Missing search fixture start: '+start);
    const last=source.indexOf(end,first+start.length);assert.ok(last>first,'Missing search fixture end: '+end);
    return source.slice(first,last);
  };
  // Run the real input debounce, search renderer and keyboard handlers together.
  // A deterministic clock keeps input and Enter in the same event-loop turn.
  let now=0,next=0;const timers=new Map();
  w.setTimeout=(fn,delay=0)=>{const id=++next;timers.set(id,{fn,at:now+delay});return id;};
  w.clearTimeout=id=>timers.delete(id);
  const advance=ms=>{const end=now+ms;for(;;){const pending=[...timers].filter(([,timer])=>timer.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!pending)break;timers.delete(pending[0]);now=pending[1].at;pending[1].fn();}now=end;};
  w.eval(between(app,'// ---- helpers','// ---- shared transport')+`
    const S={slug:'search-fixture',uiLang:'en',catBy:{},sel:{type:'report',idx:-1},data:{meta:{},report:{sections:[]},findings:Array.from({length:62},(_,i)=>({uid:'stable-'+(i+1),id:'F'+(i+1),title:'Synthetic finding '+(i+1)}))}};
    const projectStore={revision:7,etag:'saved-revision',dirty:false};
    const t=key=>key,scopedResourceURL=value=>value;
    let created=0;
    function addFinding(){created++;}
    function select(type,idx){S.sel={type,idx};}
    const WorkflowUI={navigateIssue:issue=>select('finding',S.data.findings.findIndex(row=>row.uid===issue.finding_uid))};
    function toast(message){throw Error(message);}
  `+read('drafts.js')+'\n'+read('pending-work.js')+'\n'+workbench+'\n'+between(app,'function searchTargets()','function select(type, val)')+'\n'+
    between(app,'  {\n    const si = $("#globalSearch")','  $("#previewBtn").addEventListener')+'\n'+
    `(()=>{const search=WorkbenchUI.search;`+between(workbench,"    $('#globalSearch').addEventListener('focus'","    document.addEventListener('keydown',shortcut);")+`})();\n`+
    between(app,'  document.addEventListener("keydown", e => {\n    const mod','  $("#downloadBtn").addEventListener')+`
    window.searchState={S,projectStore,created:()=>created};
  `);
  const input=w.document.querySelector('#globalSearch'),box=w.document.querySelector('#searchResults');
  const type=value=>{input.value=value;input.dispatchEvent(new w.Event('input',{bubbles:true}));};
  const key=value=>input.dispatchEvent(new w.KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true}));
  return {dom,w,input,box,type,key,advance,state:w.searchState};
}

for(const prior of ['', 'F1'])test('immediate search Enter uses the current query after '+(prior||'empty command list'),async()=>{
  const q=searchActivation();try{
    q.input.value=prior;q.input.focus();
    const before=JSON.stringify(q.state.S.data),store=JSON.stringify(q.state.projectStore);
    q.type('Synthetic finding 62');q.key('Enter');
    assert.equal(q.state.created(),0,'Search must not activate the stale Create finding command');
    assert.equal(q.state.S.data.findings[q.state.S.sel.idx]?.uid,'stable-62');
    assert.equal(q.box.classList.contains('open'),false);
    q.advance(200);
    assert.equal(q.box.classList.contains('open'),false,'A pending input timer must not reopen empty commands');
    assert.equal(q.input.value,'');assert.equal(JSON.stringify(q.state.S.data),before);assert.equal(JSON.stringify(q.state.projectStore),store);
  }finally{await Promise.resolve();q.dom.window.close();}
});

test('immediate Enter with no search match does not create a finding',async()=>{
  const q=searchActivation();try{
    q.input.focus();const before=JSON.stringify(q.state.S.data),selection=JSON.stringify(q.state.S.sel);
    q.type('nonexistent search target');q.key('Enter');q.advance(200);
    assert.equal(q.state.created(),0);assert.equal(JSON.stringify(q.state.S.data),before);assert.equal(JSON.stringify(q.state.S.sel),selection);assert.equal(q.box.querySelectorAll('button').length,0);
  }finally{await Promise.resolve();q.dom.window.close();}
});

for(const key of ['ArrowDown','ArrowUp'])test('immediate search '+key+' focuses only current results and keeps focus after debounce',async()=>{
  const q=searchActivation();try{
    q.input.focus();q.type('Synthetic finding 62');q.key(key);
    const focused=q.w.document.activeElement;assert.equal(focused.tagName,'BUTTON');assert.match(focused.textContent,/Synthetic finding 62/);
    q.advance(200);assert.equal(q.w.document.activeElement,focused);assert.equal(focused.isConnected,true);
    focused.click();assert.equal(q.state.S.data.findings[q.state.S.sel.idx]?.uid,'stable-62');assert.equal(q.state.created(),0);assert.equal(q.box.classList.contains('open'),false);
  }finally{await Promise.resolve();q.dom.window.close();}
});

test('an intentional immediate command runs once and the pending search stays dismissed',async()=>{
  const q=searchActivation();try{
    q.input.focus();q.type('Create finding');q.key('Enter');assert.equal(q.state.created(),1);
    q.advance(200);assert.equal(q.state.created(),1);assert.equal(q.box.classList.contains('open'),false);
  }finally{await Promise.resolve();q.dom.window.close();}
});

test('Escape cancels a pending search without reopening commands',async()=>{
  const q=searchActivation();try{
    q.input.focus();q.type('Synthetic finding 62');q.key('Escape');q.advance(120);
    assert.equal(q.box.classList.contains('open'),false,'Pending search must remain dismissed before blur cleanup');q.advance(80);
    assert.equal(q.state.created(),0);assert.equal(q.input.value,'');assert.equal(q.box.classList.contains('open'),false);
  }finally{await Promise.resolve();q.dom.window.close();}
});

for(const language of ['es','en','pt']){
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

for(const language of ['es','en','pt']){
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
  `+fs.readFileSync(path.join(root,'webapp/static/drafts.js'),'utf8')+'\n'+fs.readFileSync(path.join(root,'webapp/static/pending-work.js'),'utf8')+'\n'+fs.readFileSync(path.join(root,'webapp/static/studio.js'),'utf8')+`
    window.recovery={run:StudioUI.resolveDraft,inspect:StudioUI.inspector,state:S,store:projectStore};
  `);
  return dom;
}
const remoteDraft={data:{meta:{report_title:'Alpha on disk'},report:{sections:[]}},etag:'a2'};
const acceptDraft=request=>request.resolve({ok:true,json:async()=>({data:JSON.parse(request.options.body)})});
for(const change of ['reorder','remove'])test('draft recovery preserves finding identity when accepted draft will '+change,async()=>{
  const dom=draftRecoveryEditor(),{recovery,requests}=dom.window;
  try{
    const rows=[{id:'F1',uid:'first',title:'First finding'},{id:'F2',uid:'selected',title:'Selected finding'},{id:'F3',uid:'last',title:'Last finding'}];
    recovery.state.data.findings=rows;recovery.state.sel={type:'finding',idx:1};
    recovery.store.base=JSON.parse(JSON.stringify(recovery.state.data));
    const candidate={workspace_id:'workspace',slug:'alpha',base:JSON.parse(JSON.stringify(recovery.state.data)),data:JSON.parse(JSON.stringify(recovery.state.data))};
    candidate.data.findings=change==='reorder'?[rows[1],rows[2],rows[0]]:[rows[0],rows[2]];
    const open=recovery.run(candidate);requests[0].resolve({data:JSON.parse(JSON.stringify(recovery.store.base)),etag:'a1'});await open;
    [...dom.window.document.querySelectorAll('dialog button')].find(b=>b.textContent==='Apply choices and save').click();
    acceptDraft(requests[1]);await settle();
    assert.equal(dom.window.saved.length,1);
    if(change==='reorder')assert.equal(recovery.state.data.findings[recovery.state.sel.idx]?.uid,'selected');
    else assert.deepEqual(JSON.parse(JSON.stringify(recovery.state.sel)),{type:'report',idx:-1});
    assert.deepEqual(JSON.parse(JSON.stringify(dom.window.saved[0].data.findings)),candidate.data.findings);
  }finally{dom.window.close();}
});
test('draft recovery exits a deleted custom chapter instead of rendering detached fields',async()=>{
  const dom=draftRecoveryEditor(),{recovery,requests}=dom.window;
  try{
    recovery.state.data.report.sections=[{key:'keep',title:'Kept chapter',body:'Unchanged'},{key:'remove',title:'Removed chapter',body:'Old text'}];recovery.state.sel={type:'section',key:'remove'};
    recovery.store.base=JSON.parse(JSON.stringify(recovery.state.data));
    const candidate={workspace_id:'workspace',slug:'alpha',base:JSON.parse(JSON.stringify(recovery.state.data)),data:JSON.parse(JSON.stringify(recovery.state.data))};candidate.data.report.sections.pop();
    const open=recovery.run(candidate);requests[0].resolve({data:JSON.parse(JSON.stringify(recovery.store.base)),etag:'a1'});await open;
    [...dom.window.document.querySelectorAll('dialog button')].find(b=>b.textContent==='Apply choices and save').click();acceptDraft(requests[1]);await settle();
    assert.deepEqual(JSON.parse(JSON.stringify(recovery.state.sel)),{type:'report',idx:-1});assert.deepEqual(JSON.parse(JSON.stringify(dom.window.saved[0].data.report.sections)),candidate.data.report.sections);
  }finally{dom.window.close();}
});

function findingActionEditor(data){
  const dom=new JSDOM('<!doctype html><html><body><header class="topbar"></header><main id="editor" tabindex="-1"></main></body></html>',{runScripts:'outside-only',url:'http://localhost/'});
  const app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8'),workbench=fs.readFileSync(path.join(root,'webapp/static/workbench.js'),'utf8');
  dom.window.inputData=JSON.parse(JSON.stringify(data));dom.window.toasts=[];
  dom.window.eval(app.slice(0,app.indexOf('// ---- shared transport'))+`
    const scopedResourceURL=value=>value,S={slug:'alpha',uiLang:'en',data:window.inputData,sel:{type:'finding',idx:0}};
    const projectBusyCount=0,t=key=>key,toast=message=>window.toasts.push(message),scheduleSave=()=>{},renderSidebar=()=>{},renderMain=()=>{},ensureFindingIds=()=>{};
    const requestedFindingId=()=> 'F99',select=(type,idx)=>{S.sel={type,idx};},saveToLibrary=()=>{};
    const projectStore={revision:0,etag:'a1'},nextFid=()=> 'F99';
    const appFetch=async(url,options)=>({ok:true,json:async()=>({data:JSON.parse(options.body)})}),requireOk=async response=>response;
    const WorkflowUI={uid:()=> 'new-finding',findingPanel:()=>document.createElement('section')};
    const WorkbenchUI={findingWorkspace:()=>{},findingNavigation:()=>{},findingInspector:()=>{}};
    const vulnEditor=()=>document.createElement('section');
  `+workbench.slice(0,workbench.indexOf('const WorkbenchUI'))+'\n'+app.slice(app.indexOf('function findingEditor('),app.indexOf('function parseCweId('))+'\n'+app.slice(app.indexOf('async function importFindings('),app.indexOf('function addFinding('))+`
    window.actions={state:S,undo:UndoUI.undo,remove:()=>UndoUI.remove(S.data.findings,0),render:()=>document.querySelector('#editor').append(findingEditor(S.data.findings[0])),importFile:file=>importFindings({target:{files:[file]}})};
  `);return dom;
}
for(const removeGroup of [false,true])test('undo removed finding retains only live asset links'+(removeGroup?' and omits deleted group':''),()=>{
  const original={uid:'finding',id:'F1',title:'Preserved finding',root_cause_uid:'group',asset_uids:['kept','deleted'],evidence_uids:['evidence'],retests:[{uid:'retest',notes_md:'Historical verification'}]};
  const dom=findingActionEditor({meta:{client:'Original client'},findings:[original],assets:[{uid:'kept'},{uid:'deleted'}],root_cause_groups:[{uid:'group'}]});
  try{
    const {actions}=dom.window;actions.remove();actions.state.data.assets.splice(1,1);if(removeGroup)actions.state.data.root_cause_groups=[];
    actions.state.data.meta.client='New unrelated edit';actions.undo();
    const restored=JSON.parse(JSON.stringify(actions.state.data.findings[0]));
    assert.deepEqual(restored.asset_uids,['kept']);assert.deepEqual(restored.evidence_uids,original.evidence_uids);assert.deepEqual(restored.retests,original.retests);
    assert.equal(restored.root_cause_uid,removeGroup?undefined:'group');assert.equal(restored.uid,original.uid);assert.equal(restored.title,original.title);
    assert.equal(actions.state.data.meta.client,'New unrelated edit');assert.equal(actions.state.data.assets.length,1);
    assert.match(dom.window.toasts.at(-1),/restored|undone/i);
  }finally{dom.window.close();}
});
test('duplicate finding drops original remediation correspondence while retaining independent authored content',()=>{
  const original={uid:'original',id:'F1',mode:'vuln',title:'Original',owner:'Planned owner',due_date:'2026-11-30',status:'reported_fixed',verification:'confirmed',reported_remediation:'Received only for the original finding',retests:[{uid:'retest',result:'partial'}],walkthrough:[{text_md:'Original nested text'}],asset_uids:['asset'],evidence_uids:['evidence']};
  const dom=findingActionEditor({findings:[original]});
  try{
    const {actions,document}=dom.window;actions.render();[...document.querySelectorAll('button')].find(b=>b.textContent==='duplicate_finding').click();
    const [source,copy]=actions.state.data.findings;
    assert.equal(copy.id,'F99');assert.equal(copy.uid,'new-finding');assert.equal(copy.reported_remediation,undefined);assert.equal(copy.retests,undefined);
    assert.equal(copy.status,'open');assert.equal(copy.verification,'unverified');assert.deepEqual(JSON.parse(JSON.stringify(source)),original);
    assert.equal(copy.owner,original.owner);assert.equal(copy.due_date,original.due_date);
    copy.walkthrough[0].text_md='Copy edit';assert.equal(source.walkthrough[0].text_md,'Original nested text');
    assert.deepEqual(JSON.parse(JSON.stringify(copy.asset_uids)),original.asset_uids);assert.deepEqual(JSON.parse(JSON.stringify(copy.evidence_uids)),original.evidence_uids);
  }finally{dom.window.close();}
});
test('JSON finding import resets identity-bound outcomes while preserving owner and due date plans',async()=>{
  const imported={uid:'prior-identity',id:'F1',mode:'vuln',title:'Reusable authored content',owner:'Planned owner',due_date:'2026-11-30',status:'verified_fixed',verification:'confirmed',reported_remediation:'Original correspondence',retests:[{uid:'old-retest',result:'fixed'}],import_source:{reviewed:true},description_md:'Keep this authored explanation.'};
  const before=JSON.stringify(imported),dom=findingActionEditor({findings:[]});
  try{
    await dom.window.actions.importFile(new dom.window.File(['['+before+']'],'findings.json',{type:'application/json'}));
    const rows=dom.window.actions.state.data.findings;assert.equal(rows.length,1);
    const copy=rows[0];assert.notEqual(copy.uid,imported.uid);assert.notEqual(copy.id,imported.id);
    assert.equal(copy.status,'open');assert.equal(copy.verification,'unverified');assert.equal(copy.reported_remediation,undefined);assert.equal(copy.retests,undefined);assert.equal(copy.import_source.reviewed,false);
    assert.equal(copy.owner,imported.owner);assert.equal(copy.due_date,imported.due_date);assert.equal(copy.description_md,imported.description_md);assert.equal(JSON.stringify(imported),before);
  }finally{dom.window.close();}
});

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
