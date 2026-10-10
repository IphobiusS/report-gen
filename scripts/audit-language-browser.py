import argparse,json,sys,tempfile,threading,time
from pathlib import Path
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--tool',required=True);p.add_argument('--out',required=True);a=p.parse_args();sys.path[:0]=[a.tool,str(Path(a.tool)/'webapp')]
import app as webapp
import engine
checks=[]
def check(name,value):checks.append({'check':name,'passed':bool(value)})
def wait(pg,exp):
 end=time.monotonic()+15
 while time.monotonic()<end:
  if pg.evaluate('()=>('+exp+')'):return
  pg.wait_for_timeout(25)
 raise AssertionError(exp)
with tempfile.TemporaryDirectory() as temp:
 webapp.PROJECTS=Path(temp)/'projects';webapp.PROJECTS.mkdir()
 c=webapp.app.test_client();c.environ_base['HTTP_X_CSRF_TOKEN']=c.get('/api/session').get_json()['csrf']
 for name in ('a','b'):assert c.post('/api/projects',json={'slug':name}).status_code==200
 server=webapp.create_local_server(0);thread=threading.Thread(target=server.run,daemon=True);thread.start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch();pg=browser.new_page();pg.goto(f'http://127.0.0.1:{server.effective_port}');pg.locator('#splash').wait_for(state='hidden');wait(pg,"S.slug==='a' && !projectStore.loading && projectBusyCount===0")
   pg.clock.install(time=1791039600000);pg.clock.pause_at(1791039600000)
   pending=[]
   def hold(route):
    if route.request.method=='GET':pending.append(route)
    else:route.continue_()
   pg.route('**/api/projects/b',hold)
   pg.locator('#projectSelect').select_option('b')
   end=time.monotonic()+10
   while not pending and time.monotonic()<end:pg.wait_for_timeout(25)
   check('GET held during project switch',pending)
   blocked=pg.locator('#langToggle').is_disabled();check('Report language locked during project switch',blocked)
   if not blocked:pg.locator('#langToggle').click()
   pending[0].fulfill(response=pending[0].fetch());wait(pg,"S.slug==='b' && !projectStore.loading && projectBusyCount===0")
   # The user must not lose an accepted language edit on A while B loads.
   lang=engine.load_engagement(webapp.PROJECTS/'a/engagement.yaml')['meta']['lang']
   check('No accepted report edit lost during navigation',blocked or lang=='en')
   pg.clock.resume();check('Report language unlocks afterwards',not pg.locator('#langToggle').is_disabled())
   expected=engine.load_engagement(webapp.PROJECTS/'b/engagement.yaml')['meta']['lang'];pg.locator('#langToggle').click();wait(pg,'!projectStore.dirty')
   check('UI language leaves report language unchanged after navigation',engine.load_engagement(webapp.PROJECTS/'b/engagement.yaml')['meta']['lang']==expected)
   pg.wait_for_load_state('networkidle')
   result={'browser':browser.version,'checks':checks,'passed':all(x['passed'] for x in checks)};browser.close()
 finally:server.close();thread.join(timeout=3)
Path(a.out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
