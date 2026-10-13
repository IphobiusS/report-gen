#!/usr/bin/env python3
"""Short recording and clean screenshots of actual UI, using the fictional demo."""
import sys, tempfile, threading, argparse, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]
import app as api
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='rg-demo-video-',ignore_cleanup_errors=True) as tmp:
 api.PROJECTS=Path(tmp)/'projects';api.PROJECTS.mkdir();api.app.config['LIBRARY_PATH']=str(Path(tmp)/'library.json');api.app.config['DESIGN_LIBRARY_PATH']=str(Path(tmp)/'designs.json')
 server=api.create_local_server(0);threading.Thread(target=server.run,daemon=True).start();base=f'http://127.0.0.1:{server.effective_port}'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1366,'height':960},record_video_dir=str(out/'video'),record_video_size={'width':1366,'height':960},reduced_motion='reduce');pg=context.new_page();pg.goto(base);pg.get_by_role('button',name='Probar demo Nimbus',exact=True).wait_for();pg.wait_for_timeout(1200);pg.get_by_role('button',name='Probar demo Nimbus',exact=True).click();pg.wait_for_function('()=>S.slug && !projectStore.loading && projectBusyCount===0');pg.wait_for_timeout(3200)
   pg.screenshot(path=str(out/'01-dashboard-es.png'));pg.get_by_role('button',name='Continuar informe',exact=True).click();pg.wait_for_timeout(1000);pg.screenshot(path=str(out/'02-editor.png'));pg.locator('[data-studio-nav="review"]').click();pg.wait_for_timeout(1500);pg.screenshot(path=str(out/'03-revision.png'));pg.locator('[data-studio-nav="deliver"]').click();pg.wait_for_timeout(1000);pg.screenshot(path=str(out/'04-entrega.png'));pg.get_by_role('button',name='Abrir inspector',exact=True).click();pg.locator('.publication-text').wait_for();pg.wait_for_timeout(1800);pg.screenshot(path=str(out/'05-inspector.png'));pg.keyboard.press('Escape');pg.locator('[data-studio-nav="library"]').click();pg.get_by_role('button',name='Explorar galería',exact=True).click();pg.wait_for_timeout(1700);pg.screenshot(path=str(out/'06-biblioteca.png'));pg.keyboard.press('Escape');pg.locator('[data-studio-nav="work"]').click();pg.locator('#studioMore').evaluate('(e)=>e.open=true');pg.locator('#studioPreferences').evaluate('(e)=>e.open=true');pg.locator('#langToggle').select_option('en');pg.locator('#themeToggle').click();pg.locator('#studioMore').evaluate('(e)=>e.open=false');pg.wait_for_timeout(1500);pg.screenshot(path=str(out/'07-dashboard-en.png'));pg.set_viewport_size({'width':390,'height':844});pg.wait_for_timeout(1000);pg.screenshot(path=str(out/'08-movil.png'));pg.wait_for_timeout(1000);video=pg.video;context.close();video.save_as(str(out/'demo-real-0.20.0.webm'));browser.close()
 finally:
  if 'export_queue' in api.app.extensions:api.app.extensions['export_queue'].close()
  server.close()
shutil.rmtree(out/'video',ignore_errors=True)
