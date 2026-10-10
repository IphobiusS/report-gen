#!/usr/bin/env python3
"""Real browser: a delayed destructive action must not discard another draft."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tool', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path[:0] = [str(args.tool.resolve()), str(args.tool.resolve()/'webapp')]
import app as webapp  # noqa: E402
import engine  # noqa: E402

out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
checks = []; errors = []; pending = []; result = {'passed': False}


def check(name, passed):
    checks.append({'check': name, 'passed': bool(passed)})


def wait(page, expression):
    until = time.monotonic()+30
    while time.monotonic() < until:
        if page.evaluate('() => ('+expression+')'): return
        page.wait_for_timeout(50)
    raise AssertionError('Timeout: '+expression)


with tempfile.TemporaryDirectory(prefix='report-gen-latency-') as temporary:
    webapp.PROJECTS = Path(temporary)/'projects'; webapp.PROJECTS.mkdir()
    webapp.app.config['LIBRARY_PATH'] = str(Path(temporary)/'library.json')
    setup = webapp.app.test_client()
    setup.environ_base['HTTP_X_CSRF_TOKEN'] = setup.get('/api/session').get_json()['csrf']
    for name in ['a', 'b']: assert setup.post('/api/projects', json={'slug': name, 'title': name.upper()}).status_code == 200
    server = webapp.create_local_server(0)
    thread = threading.Thread(target=server.run, daemon=True); thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(); page = browser.new_page()
            page.on('dialog', lambda dialog: dialog.accept())
            page.on('pageerror', lambda error: errors.append(str(error)))
            base = f'http://127.0.0.1:{server.effective_port}'
            page.goto(base); page.locator('#splash').wait_for(state='hidden')
            wait(page, "S.slug==='a' && !projectStore.loading")
            # Keep the sequence inside the editor's 700 ms debounce window.
            # Clock control changes scheduling, not application code or state.
            page.clock.install(time=1_791_014_400_000)
            page.clock.pause_at(1_791_014_400_000)
            def hold(route):
                if route.request.method == 'DELETE': pending.append(route)
                else: route.continue_()
            page.route('**/api/projects/a', hold)
            page.locator('#deleteProjectBtn').click()
            deadline = time.monotonic()+10
            while not pending and time.monotonic()<deadline: page.wait_for_timeout(30)
            check('Delete request reached the controlled delay', bool(pending))
            blocked = page.locator('#projectSelect').is_disabled()
            check('Navigation remains locked while deletion is unresolved', blocked)
            if not blocked:
                page.locator('#projectSelect').select_option('b')
                wait(page, "S.slug==='b' && !projectStore.loading")
                page.locator('[data-field="report_title"]').fill('B - unsaved draft must survive')
                pending[0].fulfill(response=pending[0].fetch())
                wait(page, "S.projects.length===1 && S.slug==='b' && projectStore.slug==='b' && !projectStore.loading && !projectStore.dirty")
                check('Other project draft survives late deletion response',
                      page.locator('[data-field="report_title"]').input_value() == 'B - unsaved draft must survive')
            else:
                check('Editor remains inert during the destructive action', page.locator('.layout').evaluate('(el)=>el.inert'))
                pending[0].fulfill(response=pending[0].fetch())
                wait(page, "S.projects.length===1 && S.slug==='b' && projectStore.slug==='b' && !projectStore.loading")
                check('Navigation unlocks after the action completes', not page.locator('#projectSelect').is_disabled())
                page.clock.resume()
                page.locator('[data-field="report_title"]').fill('B - unsaved draft must survive')
                wait(page, '!projectStore.dirty')
                check('Next project remains editable and saves its draft',
                      engine.load_engagement(webapp.PROJECTS/'b/engagement.yaml')['meta']['report_title'] == 'B - unsaved draft must survive')
            check('Only the chosen project was deleted', not (webapp.PROJECTS/'a').exists() and (webapp.PROJECTS/'b').exists())
            check('No uncaught browser error', not errors)
            page.screenshot(path=str(out/'after-delayed-delete.png'), full_page=True)
            result.update(browser=browser.version, passed=all(c['passed'] for c in checks))
            browser.close()
    finally:
        server.close(); thread.join(timeout=3)
        result.update(checks=checks, errors=errors)
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
sys.exit(0 if result['passed'] else 1)
