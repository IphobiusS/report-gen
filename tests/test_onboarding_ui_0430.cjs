/* Browser preference and learning contracts independent of native layout. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), {JSDOM} = require('jsdom');
const source = fs.readFileSync(path.join(__dirname, '../webapp/static/onboarding.js'), 'utf8');
let checks = 0;
function check(name, condition) { assert.ok(condition, name); checks++; }
const plain = value => JSON.parse(JSON.stringify(value));
function setup({lang='es', saved=null, blocked=false, corrupt=false, noIdentity=false} = {}) {
  const dom = new JSDOM('<!doctype html><html><body><main class="layout"><aside id="workspaceSidebar"><section data-sidebar-group="project"><h2>Project</h2><button id="navHome">Home</button><button id="navReport">Report</button></section><section data-sidebar-group="content"><button id="workspaceSections">Sections</button><button id="navFindings">Findings</button></section><section data-sidebar-group="evidence"><button data-workflow="evidence">Evidence</button><details id="workspaceResearch"><summary>Research</summary><button data-workflow="assessment_cases">Test plans</button><button data-workflow="http_evidence">HTTP</button></details></section><details id="workspaceFollowup" data-sidebar-group="analysis"><summary>Followup</summary><button data-workflow="retest">Retest</button></details><section data-sidebar-group="delivery"><button data-workflow="review">Review</button><details id="workspaceTools"><summary>Tools</summary><button>Backup</button></details></section></aside><section id="editor" tabindex="-1"><div class="workspace-hero-actions"><button class="primary">Create project</button></div><input data-field="report_title" aria-describedby="existing-hint"><span id="existing-hint">Hint</span><div id="pending"><textarea>Unsubmitted draft</textarea></div></section><button data-studio-nav="deliver">Deliver</button><button id="sidebarToggle"></button></main></body></html>', {url:'http://localhost/',runScripts:'outside-only'});
  const w = dom.window, doc = w.document;
  w.S = {workspace_id:noIdentity?'':'workspace-a',slug:'real-project',uiLang:lang,sel:{type:'report',idx:-1},data:{meta:{report_title:'Real engagement',client:'Example'},findings:[{uid:'f1',status:'reported_fixed',verification:'pending',retests:[]}],evidence:[{uid:'e1',approved:false}],coverage:[{status:'pending'}],report:{sections:[{key:'scope',title:'Scope',objectives:'Test environment'}]}}};
  w.projectBusyCount = 0; w.projectStore = {loading:false,dirty:false,revision:8}; w.requests = [];w.navigation = [];
  w.BrowserWorkspace = {current:() => {if (!w.S.workspace_id) throw Error('unbound'); return w.S.workspace_id;}};
  w.uiText = (es,en,pt) => ({es,en,pt})[w.S.uiLang];
  w.h = (tag,attrs,...children) => {const node=doc.createElement(tag);for(const[key,value]of Object.entries(attrs||{})){if(value==null)continue;if(key.startsWith('on'))node.addEventListener(key.slice(2),value);else node.setAttribute(key,String(value));}for(const child of children.flat(Infinity))if(child!=null)node.append(child instanceof w.Node?child:String(child));return node;};
  w.matchMedia = () => ({matches:false}); w.HTMLElement.prototype.scrollIntoView = () => {};
  w.toast = message => {throw Error(message);}; w.scheduleSave = () => {throw Error('Learning must never save');};
  w.api = {get:() => {throw Error('No request allowed');},post:() => {throw Error('No write allowed');}};
  w.GuideUI = {nextAction:() => ({title:['Revisar la evidencia','Review evidence','Revisar evidências']})};
  w.WorkflowUI = {reviewSnapshot:() => null};
  w.ExperienceUI = {createPractice:async() => false};
  w.select = (type,value) => {w.navigation.push([type,value]);w.S.sel=type==='section'?{type,key:value}:{type,idx:value};};
  if (saved) w.localStorage.setItem('rg.onboarding.v1:workspace-a',JSON.stringify(saved));
  if (corrupt) w.localStorage.setItem('rg.onboarding.v1:workspace-a','{broken');
  if (blocked) Object.defineProperty(w,'localStorage',{value:{getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}}});
  w.eval(source+'\nwindow.Onboarding=OnboardingUI;');w.Onboarding.bind();
  doc.querySelector('#editor').append(w.Onboarding.entry());w.Onboarding.afterRender();
  const click = selector => {const node=doc.querySelector(selector);assert.ok(node,selector);assert.ok(!node.disabled,selector+' enabled');node.click();return node;};
  const mode = value => {const node=doc.querySelector('#onboardingMode');node.value=value;node.dispatchEvent(new w.Event('change'));};
  return {dom,w,doc,click,mode};
}
const flush = () => new Promise(resolve=>setImmediate(resolve));
(async () => {
  for (const lang of ['es','en','pt']) {
    const {dom,w,doc,click,mode} = setup({lang}), data=JSON.stringify(w.S.data), pending=doc.querySelector('#pending textarea');
    check(lang+' first-use chooser is nonmodal and both modes are reachable', !!doc.querySelector('[data-onboarding-choice="guided"]') && !!doc.querySelector('[data-onboarding-choice="complete"]') && !doc.querySelector('dialog'));
    check(lang+' sidebar retains its five top-level task groups', [...doc.querySelector('#workspaceSidebar').children].every(node=>node.hasAttribute('data-sidebar-group')));
    check(lang+' undecided user retains existing collapsed defaults', !doc.querySelector('#workspaceResearch').open);
    pending.focus();pending.setSelectionRange(2,7);mode('guided');
    check(lang+' changing mode preserves pending DOM, focus and selection', pending.isConnected && doc.activeElement===pending && pending.value==='Unsubmitted draft' && pending.selectionStart===2 && pending.selectionEnd===7);
    check(lang+' guided view activates learning and a real metadata highlight', w.Onboarding.state().active && doc.querySelector('[data-field="report_title"]').classList.contains('onboarding-target'));
    check(lang+' existing accessible description is preserved', doc.querySelector('[data-field="report_title"]').getAttribute('aria-describedby')==='existing-hint onboardingStepPurpose');
    check(lang+' chosen mode removes only chooser and keeps practice reachable', !doc.querySelector('[data-onboarding-chooser]') && !!doc.querySelector('[data-onboarding-action="practice"]'));
    check(lang+' placeholder is not selectable after a choice', doc.querySelector('#onboardingMode').options[0].disabled);
    click('[data-onboarding-step="3"]');
    check(lang+' steps can be skipped without navigation', w.Onboarding.state().step===3 && w.navigation.length===0);
    click('[data-onboarding-action="back"]');check(lang+' previous step is resumable',w.Onboarding.state().step===2);
    click('[data-onboarding-action="pause"]');check(lang+' pause removes guidance and preserves description',!doc.querySelector('#onboardingPanel')&&doc.querySelector('[data-field="report_title"]').getAttribute('aria-describedby')==='existing-hint');
    click('#onboardingRouteBtn');check(lang+' persistent launcher resumes previous step',w.Onboarding.state().active&&w.Onboarding.state().step===2);
    mode('complete');check(lang+' complete view expands advanced groups and pauses route',[...doc.querySelectorAll('#workspaceResearch,#workspaceFollowup,#workspaceTools')].every(node=>node.open)&&!w.Onboarding.state().active);
    doc.querySelector('[data-workflow="assessment_cases"]').setAttribute('aria-current','page');mode('guided');
    check(lang+' guided view keeps the current advanced group open',doc.querySelector('#workspaceResearch').open&&!doc.querySelector('#workspaceFollowup').open);
    doc.querySelector('#workspaceTools').open=true;w.Onboarding.update();check(lang+' routine updates respect manual advanced expansion',doc.querySelector('#workspaceTools').open);
    click('[data-onboarding-action="restart"]');for(let step=0;step<6;step++)click('[data-onboarding-action="next"]');
    check(lang+' completing records learning only',w.Onboarding.state().completed&&!w.Onboarding.state().active&&JSON.stringify(w.S.data)===data);
    mode('complete');mode('guided');check(lang+' switching modes preserves completed progress',w.Onboarding.state().completed&&w.Onboarding.state().step===5);
    click('#onboardingHelpBtn');check(lang+' section help has translated goal and example',doc.querySelector('[data-onboarding-help]').textContent.includes({es:'Ejemplo ficticio:',en:'Fictional example:',pt:'Exemplo fictício:'}[lang]));
    w.S.sel={type:'workflow',idx:'http_evidence'};w.Onboarding.afterRender();check(lang+' HTTP help describes original and publication boundary',/original|originais/.test(doc.querySelector('[data-onboarding-help]').textContent));
    w.S.sel={type:'studio',idx:'library'};w.Onboarding.afterRender();check(lang+' library help describes reusable designs',/diseños|designs|modelos/.test(doc.querySelector('[data-onboarding-help]').textContent));
    w.S.sel={type:'insights',idx:'risk'};w.Onboarding.afterRender();check(lang+' business help does not describe tutorial controls',/negocio|business|negócio/.test(doc.querySelector('[data-onboarding-help]').textContent));
    click('[data-onboarding-action="close-help"]');check(lang+' closing help preserves exact pending form',pending.isConnected&&pending.value==='Unsubmitted draft');
    const saved=JSON.parse(w.localStorage.getItem('rg.onboarding.v1:workspace-a'));
    check(lang+' storage contains UI preferences without report content',saved.mode==='guided'&&!JSON.stringify(saved).includes('Real engagement')&&saved.routes['project:real-project'].completed);
    const snapshot=w.Onboarding.state();snapshot.visited.push(91);check(lang+' exposed state is a defensive copy',!w.Onboarding.state().visited.includes(91));
    w.S.slug='second-project';w.Onboarding.update();w.Onboarding.afterRender();check(lang+' a different project has independent learning progress',!w.Onboarding.state().completed&&w.Onboarding.state().step===0);
    w.S.slug='real-project';check(lang+' returning to project restores progress',w.Onboarding.state().completed&&w.Onboarding.state().step===5);
    w.S.workspace_id='workspace-b';w.Onboarding.update();w.Onboarding.afterRender();check(lang+' workspace identities isolate mode and progress',w.Onboarding.state().mode===null&&!w.Onboarding.state().completed);
    w.S.workspace_id='workspace-a';check(lang+' returning to workspace restores chosen mode',w.Onboarding.state().mode==='guided');
    check(lang+' UI-only learning never writes or navigates the project',JSON.stringify(w.S.data)===data&&w.navigation.length===0&&w.projectStore.revision===8);
    dom.window.close();
    const resumed=setup({lang,saved});check(lang+' reload restores mode and completed route',resumed.w.Onboarding.state().mode==='guided'&&resumed.w.Onboarding.state().completed);resumed.dom.window.close();
  }
  for (const options of [{blocked:true},{corrupt:true},{noIdentity:true}]) {
    const {dom,w,doc,mode,click}=setup(options);mode('guided');click('[data-onboarding-step="4"]');click('[data-onboarding-action="pause"]');click('#onboardingRouteBtn');
    check(JSON.stringify(options)+' unavailable or invalid storage keeps session route operable',w.Onboarding.state().step===4&&w.Onboarding.state().active);
    if (!options.corrupt) check(JSON.stringify(options)+' explains session-only persistence',!w.Onboarding.state().storageAvailable&&!!doc.querySelector('[role="status"]'));
    dom.window.close();
  }
  const malformed=setup({saved:{version:1,mode:'administrator',routes:{'project:real-project':{step:100,active:'yes',completed:1,visited:[0,0,4,6,-1,'3'],extra:'discard'}}}});
  check('Malformed preferences are bounded and strictly normalized',malformed.w.Onboarding.state().mode===null&&malformed.w.Onboarding.state().step===0&&!malformed.w.Onboarding.state().active&&JSON.stringify(plain(malformed.w.Onboarding.state().visited))==='[0,4]');malformed.dom.window.close();
  const missingScope=setup();missingScope.w.S.data.report.sections=[];missingScope.w.matchMedia=()=>({matches:true});missingScope.mode('guided');missingScope.click('[data-onboarding-step="1"]');missingScope.click('[data-onboarding-action="open"]');
  check('Scope-less mobile report retains a visible editor fallback and focus without adding scope',missingScope.doc.querySelector('#editor').classList.contains('onboarding-target')&&missingScope.doc.activeElement===missingScope.doc.querySelector('#editor')&&missingScope.w.S.data.report.sections.length===0);
  const indexToggle=missingScope.doc.createElement('button');indexToggle.id='contextIndexToggle';missingScope.doc.querySelector('main').append(indexToggle);missingScope.w.Onboarding.afterRender();
  check('Scope-less report points to the real visible context index opener when present',indexToggle.classList.contains('onboarding-target'));missingScope.dom.window.close();
  const {dom,w,doc,mode,click}=setup();mode('guided');click('[data-onboarding-step="0"]');
  let attempts=0;w.ExperienceUI.createPractice=async()=>{attempts++;return false;};
  const before=JSON.stringify(w.S.data);click('#onboardingPanel [data-onboarding-action="practice"]');await flush();
  check('Failed practice preserves current project and learning',attempts===1&&w.S.slug==='real-project'&&JSON.stringify(w.S.data)===before&&w.Onboarding.state().step===0);
  w.ExperienceUI.createPractice=async()=>{w.S.slug='nimbus-demo-unique';return true;};click('#onboardingPanel [data-onboarding-action="practice"]');await flush();
  check('Successful explicit practice starts a separate project walkthrough',w.S.slug==='nimbus-demo-unique'&&w.Onboarding.state().active&&w.Onboarding.state().step===0);
  click('[data-onboarding-action="open"]');check('Explicit Open invokes only the existing navigation route',JSON.stringify(w.navigation)==='[["report",-1]]');
  w.projectBusyCount=1;w.Onboarding.update();check('Busy project disables mode and learning controls',[...doc.querySelectorAll('[data-onboarding-action],#onboardingMode')].every(node=>node.disabled));
  w.projectBusyCount=0;w.Onboarding.update();check('Controls recover when project is ready',!doc.querySelector('#onboardingMode').disabled);
  dom.window.close();
  console.log(JSON.stringify({passed:checks,scope:'ES/EN/PT onboarding UI state, persistence, form preservation, no technical writes and explicit practice boundary'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
