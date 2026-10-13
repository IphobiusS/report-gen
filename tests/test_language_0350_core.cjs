'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const helpers=source.slice(0,source.indexOf('// ---- shared transport'));
const dictionary=source.slice(source.indexOf('const I18N ='),source.indexOf('function applyStaticI18n('));
function fixture(language='pt'){
 const state={uiLang:language,data:{meta:{lang:'es',report_title:'Client authored title: ação / العربية'},findings:[]}};
 const context=vm.createContext({S:state});vm.runInContext(helpers+dictionary+'\nthis.catalog=I18N;',context);
 return {context,state,run:code=>vm.runInContext(code,context)};
}
test('all three UI catalogs have complete keys and preserve interpolation placeholders',()=>{
 const {context}=fixture(),catalog=context.catalog;
 assert.equal(Object.keys(catalog.es).length,186);
 for(const language of ['en','pt']){
  assert.deepEqual(Object.keys(catalog[language]).sort(),Object.keys(catalog.es).sort());
  for(const key of Object.keys(catalog.es)){
   assert.ok(catalog[language][key].trim(),language+': '+key);
   assert.deepEqual(catalog[language][key].match(/\{\w+\}/g)||[],catalog.es[key].match(/\{\w+\}/g)||[],language+': '+key);
  }
 }
 assert.equal(catalog.pt.new_project,'Novo projeto');assert.equal(catalog.pt.findings_head,'Achados');
});
test('Portuguese aliases normalize without conflating interface and report language',()=>{
 const {context,state,run}=fixture(),before=JSON.stringify(state.data);
 for(const alias of ['pt','pt-BR','pt-br','PT-bR']){
  assert.equal(context.normalizeUiLanguage(alias),'pt');assert.equal(context.languageTag(alias),'pt-BR');
 }
 assert.equal(context.normalizeUiLanguage('unknown','en'),'en');assert.equal(context.normalizeUiLanguage(null,'pt'),'pt');
 for(const [language,expected]of [['es','Español'],['en','English'],['pt','Português']]){
  state.uiLang=language;assert.equal(run("uiText('Español','English','Português')"),expected);
 }
 assert.equal(JSON.stringify(state.data),before);
});
test('Portuguese OWASP insertion follows report language independently of interface language',()=>{
 const {context,state}=fixture('en');state.data.meta.lang='pt';
 Object.assign(context,{requestedFindingId:()=> 'F1',closeModal:()=>{},document:{querySelector:()=>null},finishAdd:()=>{}});
 vm.runInContext(source.slice(source.indexOf('function insertOwasp('),source.indexOf('// ---- preview / descarga')),context);
 context.insertOwasp({id:'A01',name:'Broken access control',name_es:'Control de acceso roto',name_pt:'Falha no controle de acesso',summary:'English',summary_es:'Español',summary_pt:'Descrição em português',ref:'https://example.test/path?value=ação'});
 assert.equal(state.uiLang,'en');assert.equal(state.data.findings[0].title,'A01 Falha no controle de acesso');
 assert.equal(state.data.findings[0].description_md,'Descrição em português');assert.equal(state.data.findings[0].references[0],'https://example.test/path?value=ação');
});
test('interface language uses an explicit select and report creation exposes Portuguese',()=>{
 const html=fs.readFileSync(path.join(root,'webapp/static/index.html'),'utf8');
 const select=html.match(/<select id="langToggle"[^>]*>([\s\S]*?)<\/select>/);
 assert.ok(select);assert.match(select[0],/aria-label=/);
 assert.deepEqual([...select[1].matchAll(/value="([^"]+)"/g)].map(m=>m[1]),['es','en','pt']);
 assert.match(select[1],/Português \(Brasil\)/);assert.match(html,/<option value="corporativo-pt">Português \(Brasil\)<\/option>/);
 assert.doesNotMatch(source,/function toggleUiLang\(/);
});
