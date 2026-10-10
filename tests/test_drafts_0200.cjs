const test=require('node:test'),assert=require('node:assert/strict');
const {mergeDraft}=require('../webapp/static/drafts.js');
const {ProjectStore}=require('../webapp/static/save-manager.js');
const timers={setTimeout:()=>1,clearTimeout:()=>{}};
const response=(data,etag='"r1"',status=200)=>({ok:status<400,status,json:async()=>data,headers:{get:()=>etag}});
test('independent edits and literal commands merge without invented whitespace',()=>{const base={a:'one',command:'printf "%s\\n" "a"\r\n'},local={...base,a:'two'},remote={...base,command:'printf "%s\\n" "b"\r\n'};const result=mergeDraft(base,local,remote);assert.deepEqual(result.data,{a:'two',command:remote.command});assert.equal(result.conflicts.length,0);});
test('same field conflict requires choice; server choice is exact',()=>{const r=mergeDraft({text:'a'},{text:'b'},{text:'c'},{'/text':'remote'});assert.equal(r.conflicts.length,1);assert.equal(r.data.text,'c');});
test('UID arrays preserve separate finding edits, deletion versus edit is conflict',()=>{const base={findings:[{uid:'1',title:'a'},{uid:'2',title:'b'}]},local={findings:[{uid:'1',title:'new'},{uid:'2',title:'b'}]},remote={findings:[{uid:'1',title:'a'},{uid:'2',title:'remote'}]};assert.deepEqual(mergeDraft(base,local,remote).data.findings.map(x=>x.title),['new','remote']);const conflict=mergeDraft(base,local,{findings:[base.findings[1]]});assert.equal(conflict.conflicts[0].path,'/findings/1');});
test('opaque arrays are never silently joined',()=>{assert.equal(mergeDraft({steps:['a']},{steps:['a','b']},{steps:['c']}).conflicts.length,1);});
test('draft storage failure leaves pending data and explicitly clears recoverable state',async()=>{const s=new ProjectStore(async()=>response({title:'a'}),()=>{},timers);await s.load('p');s.journal={put:async()=>{throw Error('Quota exceeded')}};s.data.title='b';s.changed();await s.persistDraft();assert.equal(s.data.title,'b');assert.equal(s.recoverableRevision,0);assert.equal(s.draftError.message,'Quota exceeded');assert.equal(s.dirty,true);});
test('conflict does not replace local draft; explicit resolution uses fresh revision',async()=>{const writes=[];const s=new ProjectStore(async(url,options)=>{if(!options)return response({title:'a'});writes.push(options);return writes.length===1?response({error:'Conflict'},null,409):response({},'"r3"');},()=>{},timers);await s.load('p');s.data.title='b';s.changed();await assert.rejects(s.save());assert.equal(s.lastError.status,409);s.adopt({title:'merged'},{data:{title:'remote'},etag:'"r2"'});await s.save();assert.equal(writes[1].headers['If-Match'],'"r2"');assert.equal(s.dirty,false);});

test('draft cleanup refuses a changed record even at the same timestamp',async()=>{
 const {DraftJournal}=require('../webapp/static/drafts.js');const journal=new DraftJournal();let removed=false;
 const snapshot={id:'tab:project',updated:1,data:{text:'old'}};
 journal.run=async(mode,fn)=>{let result;const store={get:()=>{const request={result:{...snapshot,data:{text:'new'}}};queueMicrotask(()=>request.onsuccess());return request;},delete:()=>{removed=true;}};fn(store,x=>result=x);await new Promise(resolve=>queueMicrotask(resolve));return result;};
 assert.equal(await journal.removeUnchanged(snapshot),false);assert.equal(removed,false);
});
