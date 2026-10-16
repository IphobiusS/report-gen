/* Actual application and Flask endpoints over pipes. DOM assertions do not claim visual/browser acceptance. */
'use strict';
const {JSDOM}=require('jsdom'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),transport=require('./flask_transport.cjs')(),checks=[];
const check=(name,value)=>{assert.ok(value,name);checks.push(name);};
async function until(predicate){for(let i=0;i<600;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,20));}throw Error('UI timeout: '+predicate);}
let dom;
(async()=>{
 const html=fs.readFileSync(path.join(root,'webapp/static/index.html'),'utf8');
 dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,doc=w.document;w.fetch=transport.fetch;w.confirm=()=>true;w.alert=()=>{};w.structuredClone=structuredClone;w.AbortController=AbortController;w.AbortSignal=AbortSignal;
 w.ResizeObserver=class{observe(){}disconnect(){}};w.matchMedia=()=>({matches:false});w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;this.querySelector('button')?.focus();};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.HTMLAnchorElement.prototype.click=function(){};w.URL.createObjectURL=()=> 'blob:language-test';w.URL.revokeObjectURL=()=>{};
 w.localStorage.setItem('rg.uiLang','pt-BR');w.localStorage.setItem('rg.previewVisible','0');
 const sources=[...html.matchAll(/<script src="\/static\/([^"]+)"/g)].map(match=>fs.readFileSync(path.join(root,'webapp/static',match[1]),'utf8'));
 w.eval(sources.join('\n')+'\nwindow.qa={S,projectStore,select,setUiLang,doSave,appFetch,refreshProjects,loadProject,openSectionsModal};');const q=w.qa;
 await until(()=>doc.querySelector('.workspace-dashboard'));
 check('pt-BR preference restores before the first Portuguese dashboard',q.S.uiLang==='pt'&&doc.documentElement.lang==='pt-BR'&&doc.querySelector('#newProjectBtn').textContent==='Novo projeto');
 check('Three languages use a named native selector',doc.querySelector('#langToggle').tagName==='SELECT'&&doc.querySelector('#langToggle').options.length===3&&doc.querySelector('#langToggle').getAttribute('aria-label').includes('PT'));
 doc.querySelector('#demoBtn').click();await until(()=>q.S.slug&&!q.projectStore.loading&&!q.projectStore.dirty);
 const before=JSON.stringify(q.S.data),etag=q.projectStore.etag,revision=q.projectStore.revision;
 const titles={es:['Empieza','Define el alcance','Redacta un hallazgo','Conecta la evidencia','Revisa lo que compartes','Entrega y conserva'],en:['Start','Define scope','Write a finding','Connect evidence','Review what you share','Deliver and retain'],pt:['Comece','Defina o escopo','Redija um achado','Conecte as evidências','Revise o que compartilha','Entregue e preserve']};
 for(const language of ['es','en','pt']){
  const control=doc.querySelector('#langToggle');control.value=language;control.dispatchEvent(new w.Event('change',{bubbles:true}));
  check(language+' native selector event updates UI and persisted preference',q.S.uiLang===language&&w.localStorage.getItem('rg.uiLang')===language&&doc.documentElement.lang===(language==='pt'?'pt-BR':language));
  check(language+' leaves authored report and revision unchanged',JSON.stringify(q.S.data)===before&&q.projectStore.etag===etag&&q.projectStore.revision===revision&&!q.projectStore.dirty);
  for(let step=0;step<6;step++){
   q.select('guide',step);
   check(language+' tutorial step '+(step+1)+' has localized title and image description',doc.querySelector('#guideStepTitle').textContent===titles[language][step]&&[...doc.querySelectorAll('.tutorial-screenshot img')].every(img=>img.getAttribute('src').endsWith('-'+language+'.webp')&&img.alt.length>50));
   check(language+' tutorial step '+(step+1)+' preserves report and revision',JSON.stringify(q.S.data)===before&&q.projectStore.etag===etag&&!q.projectStore.dirty);
  }
 }
 q.select('report',-1);
 const language=doc.querySelector('[data-field="lang"]');check('Metadata language selector provides Portuguese',language.querySelector('option[value="pt"]').textContent==='Português (Brasil)');
 const authored=JSON.stringify({findings:q.S.data.findings,sections:q.S.data.report.sections,title:q.S.data.meta.report_title});
 language.value='pt';language.dispatchEvent(new w.Event('change',{bubbles:true}));await q.doSave();
 check('Explicit report language persists with Portuguese UI unchanged',q.S.data.meta.lang==='pt'&&q.S.uiLang==='pt'&&!q.projectStore.dirty);
 check('Report language refreshes section labels immediately',doc.querySelector('#sectionList').textContent.includes(q.S.catBy.findings.title_pt));
 check('Report language edit retains metadata focus',doc.activeElement.matches('[data-field="lang"]'));
 check('Report language edit preserves all authored content',JSON.stringify({findings:q.S.data.findings,sections:q.S.data.report.sections,title:q.S.data.meta.report_title})===authored);
 const stored=await transport.fetch('/api/projects/'+q.S.slug).then(response=>response.json());check('Real Flask saved canonical Portuguese report language',stored.meta.lang==='pt');
 // Import an actual editable ZIP whose accepted language alias remains authored metadata.
 const fixture=spawnSync(process.env.RG_PYTHON||'python',['-c',`
from pathlib import Path
import sys, tempfile, yaml
import project_history
with tempfile.TemporaryDirectory(prefix='report-gen-pt-alias-') as directory:
    root=Path(directory)
    data={'meta':{'report_title':'Alias preservation / ação', 'lang':'pt-BR', 'theme':'corporativo', 'branding':{}},
          'report':{'sections':[{'key':'executive_summary','summary':'Authored English: preserve this paragraph.'}]}, 'findings':[]}
    (root/'engagement.yaml').write_text(yaml.safe_dump(data,allow_unicode=True),encoding='utf-8')
    sys.stdout.buffer.write(project_history.export_bundle(root))
`],{cwd:root,maxBuffer:2*1024*1024});
 assert.equal(fixture.status,0,fixture.stderr.toString());
 const form=new FormData();form.append('file',new Blob([fixture.stdout],{type:'application/zip'}),'portuguese-alias.zip');form.append('slug','portuguese-alias');
 const imported=await q.appFetch('/api/projects/import',{method:'POST',body:form});assert.equal(imported.status,200,await imported.clone().text());
 await q.refreshProjects();await q.loadProject((await imported.json()).slug);
 const importedBefore=JSON.stringify(q.S.data),importedRevision=q.projectStore.etag;
 check('Imported pt-BR alias remains unchanged in report metadata',q.S.data.meta.lang==='pt-BR');
 check('Imported alias uses Portuguese catalog sidebar labels',doc.querySelector('#sectionList').textContent.includes(q.S.catBy.executive_summary.title_pt));
 q.select('section','executive_summary');
 check('Imported alias uses Portuguese section title and field label',doc.querySelector('#editor h2').textContent===q.S.catBy.executive_summary.title_pt&&doc.querySelector('#editor').textContent.includes(q.S.catBy.executive_summary.fields[0].label_pt));
 q.openSectionsModal();
 check('Imported alias uses Portuguese catalog modal labels',doc.querySelector('#sectionsModal input[data-section-key="executive_summary"]').closest('label').textContent.includes(q.S.catBy.executive_summary.title_pt));
 doc.querySelector('#sectionsModal').close();q.setUiLang('en');
 check('Imported alias localization preserves authored text, exact data and revision',JSON.stringify(q.S.data)===importedBefore&&q.projectStore.etag===importedRevision&&!q.projectStore.dirty);
 const importedStored=await transport.fetch('/api/projects/portuguese-alias').then(response=>response.json());
 check('Imported source retains pt-BR and original prose after viewing',importedStored.meta.lang==='pt-BR'&&importedStored.report.sections[0].summary==='Authored English: preserve this paragraph.');
 console.log(JSON.stringify({passed:checks.length,checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{dom?.window.close();transport.close();});
