/* Compare real native select paint pixels with their foreground in both UI themes.
 * CSS background alone is not an oracle: WebKit may paint the native control. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn,execFileSync}=require('node:child_process'),{createHash}=require('node:crypto');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(n,d)=>args.includes(n)?args[args.indexOf(n)+1]:d;
const engine=opt('--browser','webkit'),out=path.resolve(opt('--output','out/select-contrast-0345')),python=process.env.RG_PYTHON||'python3';
const playwright=require(require.resolve('playwright',{paths:[root]}));fs.mkdirSync(out,{recursive:true});
const result={engine,checks:[],errors:[],screens:[],states:[],limits:['Native control paint is measured in the browser and operating system used for this run, not every desktop theme.','Closed, enabled select controls are tested in dark/light default and focus states; open OS dropdown menus are not pixel-audited.']};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));const check=(name,passed,detail)=>{result.checks.push({name,passed:!!passed,detail});save();assert.ok(passed,name);};
let server,browser,timer;
const pixels=`import sys,json,math
from PIL import Image
im=Image.open(sys.argv[1]).convert('RGB');meta=json.loads(sys.argv[2]);out=[]
def lum(rgb):
 c=[v/255 for v in rgb];c=[v/12.92 if v<=0.04045 else ((v+.055)/1.055)**2.4 for v in c]
 return sum(a*b for a,b in zip(c,[.2126,.7152,.0722]))
def ratio(a,b):
 x,y=sorted([lum(a),lum(b)]);return (y+.05)/(x+.05)
for item in meta:
 r=item['rect'];fg=item['foreground'];x=round(r['x']);y=round(r['y']);w=round(r['width']);h=round(r['height'])
 # Nine text-free points in the native interior, away from border and arrow.
 points=[(x+6,y+round(h*f)) for f in [.25,.5,.75]]+[(x+round(w*f),y+5) for f in [.2,.4,.6]]+[(x+round(w*f),y+h-6) for f in [.2,.4,.6]]
 backgrounds=[im.getpixel(p) for p in points];rs=[ratio(fg,b) for b in backgrounds]
 crop=im.crop((x+10,y+5,x+w-25,y+h-5));fg_pixels=sum(max(abs(a-b) for a,b in zip(c,fg))<=8 for c in crop.getdata())
 out.append({'id':item['id'],'background_pixels':backgrounds,'foreground':fg,'foreground_matching_pixels':fg_pixels,'minimum_ratio':min(rs),'maximum_ratio':max(rs)})
print(json.dumps(out))`;
(async()=>{try{
 server=spawn(python,[path.join(root,'scripts/browser-server-0210.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});server.stderr.pipe(fs.createWriteStream(path.join(out,'server.log')));
 const base=await new Promise((resolve,reject)=>{let s='';timer=setTimeout(()=>reject(Error('Server startup timeout')),30000);server.stdout.on('data',d=>{s+=d;if(s.includes('\n')){clearTimeout(timer);resolve(JSON.parse(s.split('\n')[0]).url)}});server.once('exit',c=>reject(Error('Server exit '+c)))});
 const executable=opt('--executable',engine==='chromium'?process.env.RG_CHROMIUM_EXECUTABLE:undefined);browser=await playwright[engine].launch({headless:true,...(executable?{executablePath:executable}:{})});result.version=browser.version();
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});page.on('pageerror',e=>result.errors.push(String(e)));
 await page.addInitScript(()=>{localStorage.setItem('rg.uiLang','en');localStorage.setItem('rg.previewVisible','0')});await page.goto(base);await page.getByRole('button',{name:'Try Nimbus demo',exact:true}).click();await page.waitForFunction(()=>S.slug&&!projectStore.loading&&!projectBusyCount);
 await page.locator('#studioMore > summary').click();await page.locator('#exportMenu > summary').click();
 for(const theme of ['dark','light'])for(const state of ['default','focus-project','focus-format']){
  await page.evaluate(theme=>applyUiTheme(theme),theme);if(state==='focus-project')await page.locator('#projectSelect').focus();else if(state==='focus-format')await page.locator('#exportFormat').focus();else await page.evaluate(()=>document.activeElement.blur());
  await page.evaluate(()=>document.fonts.ready);await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const meta=await page.locator('#projectSelect,#exportFormat').evaluateAll(els=>els.map(el=>{const c=getComputedStyle(el),r=el.getBoundingClientRect();return{id:el.id,tag:el.tagName,disabled:el.disabled,focused:el===document.activeElement,appearance:c.appearance,colorScheme:c.colorScheme,color:c.color,background:c.backgroundColor,foreground:c.color.match(/[\d.]+/g).slice(0,3).map(Number),rect:{x:r.x,y:r.y,width:r.width,height:r.height},options:el.options.length}}));
  const dest=path.join(out,theme+'-'+state+'.png');await page.screenshot({path:dest});result.screens.push({path:dest,sha256:createHash('sha256').update(fs.readFileSync(dest)).digest('hex')});
  const paint=JSON.parse(execFileSync(python,['-c',pixels,dest,JSON.stringify(meta)],{encoding:'utf8'}));result.states.push({theme,state,meta,paint});save();
  check(theme+' '+state+' native text paint meets 4.5:1',paint.length===2&&paint.every(p=>p.minimum_ratio>=4.5&&p.foreground_matching_pixels>=8),paint);
  check(theme+' '+state+' controls remain native and enabled',meta.every(m=>m.tag==='SELECT'&&!m.disabled&&m.appearance!=='none'&&m.options>0&&m.focused===(state==='focus-project'?m.id==='projectSelect':state==='focus-format'?m.id==='exportFormat':false)),meta);
 }
 await page.locator('#exportFormat').selectOption('docx');check('Native format selection still changes value',await page.locator('#exportFormat').inputValue()==='docx');
 check('No application JavaScript errors',result.errors.length===0,result.errors);result.passed=true;save();console.log('PASS '+result.checks.length+' select paint checks in '+engine);
 }catch(e){result.failure=String(e.stack||e);result.passed=false;save();console.error(e);process.exitCode=1;}
 finally{clearTimeout(timer);await browser?.close();server?.kill('SIGTERM');}
})();
