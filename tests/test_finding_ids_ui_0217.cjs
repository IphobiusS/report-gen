/* Exercise the exact editor allocation and action helpers without reimplementing them. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..');
const source=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const allocationStart=source.includes('function findingSequenceError(')?source.indexOf('function findingSequenceError('):source.indexOf('function nextFid(');
const allocation=source.slice(allocationStart,source.indexOf('// ---- editor principal'));
const ensure=source.slice(source.indexOf('function ensureFindingIds('),source.indexOf('const projectStore'));
const add=source.slice(source.indexOf('function addFinding('),source.indexOf('function finishAdd('));
const insert=source.slice(source.indexOf('function insertOwasp('),source.indexOf('// ---- preview / descarga'));
let calls=[];const S={uiLang:'es',data:null};
const context={S,console,Number,Error,JSON,WorkflowUI:{uid:()=> 'UID'},toast:(message,kind)=>calls.push({message,kind}),finishAdd:()=>calls.push({add:true}),closeModal:()=>{},$:()=>null,openOwasp:()=>{}};
vm.createContext(context);vm.runInContext(allocation+ensure+add+insert,context);
let checks=0;function check(name,fn){fn();checks++;console.log('PASS '+name);}
for(const language of ['es','en']) {
 S.uiLang=language;
 for(const exhausted of [Number.MAX_SAFE_INTEGER,Number.MAX_SAFE_INTEGER+1]){
  for(const action of ['blank','owasp'])check(language+' / '+exhausted+' / '+action+' preserves the exhausted document and announces an error',()=>{
   S.data={meta:{lang:'es'},finding_sequence:exhausted,findings:[{id:'F'+exhausted,uid:'original'}]};calls=[];const before=JSON.stringify(S.data);
   if(action==='blank')context.addFinding('blank');else context.insertOwasp({id:'A01',name_es:'Caso',name:'Case'});
   assert.equal(JSON.stringify(S.data),before);assert.equal(calls.length,1);assert.equal(calls[0].kind,'err');assert.match(calls[0].message,language==='es'?/Se agotó.*editando y exportando/:/exhausted.*edited and exported/);
  });
 }
 for(const limit of ['F'+(Number.MAX_SAFE_INTEGER+1),'F'+'9'.repeat(5000)])check(language+' / oversized ID fails before any allocation mutation',()=>{
  S.data={findings:[{id:limit}]};const before=JSON.stringify(S.data);assert.throws(()=>context.nextFid(),/agotó|exhausted/);assert.equal(JSON.stringify(S.data),before);
 });
 check(language+' / last safe allocation is exact and subsequent allocation is rejected',()=>{
  S.data={finding_sequence:Number.MAX_SAFE_INTEGER-1,findings:[]};assert.equal(context.nextFid(),'F'+Number.MAX_SAFE_INTEGER);const before=JSON.stringify(S.data);assert.throws(()=>context.nextFid(),/agotó|exhausted/);assert.equal(JSON.stringify(S.data),before);
 });
 check(language+' / missing identifiers are checked before any UID or counter changes',()=>{
  S.data={finding_sequence:Number.MAX_SAFE_INTEGER-1,findings:[{},{}]};const before=JSON.stringify(S.data);assert.throws(()=>context.ensureFindingIds(),/agotó|exhausted/);assert.equal(JSON.stringify(S.data),before);
 });
 check(language+' / removed referenced identifiers remain reserved',()=>{
  S.data={finding_sequence:8,findings:[{id:'F02'}],body:'[Removed](#F21)'};assert.equal(context.nextFid(),'F22');assert.equal(S.data.finding_sequence,22);
 });
 check(language+' / maximum existing identifier remains editable without allocating',()=>{
  S.data={finding_sequence:Number.MAX_SAFE_INTEGER,findings:[{id:'F'+Number.MAX_SAFE_INTEGER,uid:'original'}]};const before=JSON.stringify(S.data);context.ensureFindingIds();assert.equal(JSON.stringify(S.data),before);
 });
 check(language+' / Unicode numeric-looking identifiers remain opaque',()=>{
  S.data={finding_sequence:0,findings:[{id:'F١',uid:'original'}]};assert.equal(context.nextFid(),'F1');assert.equal(S.data.findings[0].id,'F١');
 });
 check(language+' / a bounded report with many references avoids argument-spread limits',()=>{
  S.data={finding_sequence:1,findings:[{id:'F1',description_md:'[Canary](#F1) '.repeat(150000)}]};assert.equal(context.nextFid(),'F2');
 });
}
console.log(JSON.stringify({checks,passed:true}));
