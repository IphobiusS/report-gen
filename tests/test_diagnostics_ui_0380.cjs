'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const transport=require('../webapp/static/transport.js').create({fetch:()=>{},workspace:{current:()=>null},getLanguage:()=> 'es',getETag:()=>'',baseURL:()=> 'http://localhost/'});
const locations=require('../webapp/static/diagnostics-ui.js');

test('failed response retains exact error and bounded structured locations without parsing prose',async()=>{
  const diagnostic={code:'export.table',message:'private description',location:{table:1,row:3,cell:2}};
  let reads=0;
  await assert.rejects(transport.requireOk({ok:false,status:422,json:async()=>{reads++;return {error:'Original diagnosis',diagnostics:Array(70).fill(diagnostic)};}}),error=>{
    assert.equal(error.message,'Original diagnosis');assert.equal(error.status,422);
    assert.equal(error.diagnostics.length,64);assert.deepEqual(error.diagnostics[0].location,{table:1,row:3,cell:2});return true;
  });
  assert.equal(reads,1);
  await assert.rejects(transport.requireOk({ok:false,status:422,json:async()=>({error:'table 3 cell 9'})}),error=>error.diagnostics.length===0);
});
test('invalid JSON and null bodies retain the HTTP fallback',async()=>{
  for(const json of [async()=>null,async()=>{throw Error('bad JSON');}])
    await assert.rejects(transport.requireOk({ok:false,status:503,json}),/HTTP 503/);
});
test('locations are translated and zero based protocol indices are shown as human ordinals',()=>{
  const location={field:'description_md',table:1,row:3,cell:2,evidence_index:0};
  assert.match(locations.locationText(location,'es'),/Campo: description_md.*Tabla: 1.*Fila: 3.*Celda: 2.*Evidencia: 1/);
  assert.match(locations.locationText(location,'en'),/Field: description_md.*Table: 1.*Row: 3.*Cell: 2.*Evidence: 1/);
  assert.match(locations.locationText(location,'pt'),/Campo: description_md.*Tabela: 1.*Linha da tabela: 3.*Célula: 2.*Evidência: 1/);
});
test('diagnostics ignore paths, values, invalid coordinates and hostile strings',()=>{
  assert.equal(locations.locationText({path:'/private/source',value:'secret',field:'<img onerror=alert(1)>',row:true,cell:-1,evidence_index:0.5,table:Infinity}), '');
  assert.equal(locations.locationText({field:'x'.repeat(161)}),'');
});
test('DOM renders only bounded structural locations, deduplicates origin and creates no active markup',()=>{
  const dom=new JSDOM('',{runScripts:'outside-only'});
  try {
    dom.window.eval(fs.readFileSync(path.join(root,'webapp/static/diagnostics-ui.js'),'utf8'));
    const api=dom.window.DiagnosticUI,location={format:'csv',record:2,line:3};
    const box=api.render([{location,message:'<img src=x onerror=alert(1)>'},{location},{location:{field:'<script>x</script>'}}],'es',location);
    assert.equal(box.querySelectorAll('p').length,1);assert.equal(box.querySelectorAll('img,script,a').length,0);
    assert.equal(box.textContent,'Formato: csv · Registro: 2 · Línea: 3');
    assert.equal(api.render([{message:'A cell failed'}]),null);
  } finally {dom.window.close();}
});
