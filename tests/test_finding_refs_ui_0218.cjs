/* Read-only encoded fragment reservation uses the exact allocator shipped in the editor. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..');
const source=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const block=source.slice(source.indexOf('function findingSequenceError('),source.indexOf('// ---- editor principal'));
const S={uiLang:'es',data:null};const context={S,console,Number,Error,JSON,decodeURIComponent};vm.createContext(context);vm.runInContext(source.slice(0,source.indexOf('// ---- shared transport'))+block,context);
let checks=0;
for(const language of ['es','en']){
 S.uiLang=language;
 for(const [fragment,expected] of [['#F%32','F3'],['#%46%32','F3'],['#F%30%30%32','F3'],['#F%32\nNext line','F3'],['#F%2532','F2'],['#F%E0%A4%A','F2'],['#F%ZZ','F2'],['#F%D9%A2','F2'],['#F%32a','F2']]){
  S.data={findings:[{id:'F1',description_md:'[Removed]('+fragment+')'}]};const wording=S.data.findings[0].description_md;
  assert.equal(context.nextFid(),expected);assert.equal(S.data.findings[0].description_md,wording);checks++;
 }
 for(const fragment of ['#F%393007199254740991','#%469007199254740992']){
  S.data={findings:[{id:'F1',references:['[Removed]('+fragment+')']}]};const before=JSON.stringify(S.data);
  assert.throws(()=>context.nextFid(),/agotó|exhausted/);assert.equal(JSON.stringify(S.data),before);checks++;
 }
}
console.log(JSON.stringify({checks,passed:true}));
