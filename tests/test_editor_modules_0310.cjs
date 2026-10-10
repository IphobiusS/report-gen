'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const CVSS31=require(path.join(root,'webapp/static/cvss31.js'));
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
