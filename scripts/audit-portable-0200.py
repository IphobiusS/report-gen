#!/usr/bin/env python3
"""Check the real Nimbus portable export in Chromium, with and without JS."""
import argparse
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import export

parser = argparse.ArgumentParser()
parser.add_argument('--project', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
checks = []

def check(name, ok):
    checks.append({'name': name, 'passed': bool(ok)})
    (out / 'portable-checks.json').write_text(json.dumps(checks, indent=2))
    assert ok, name

target = out / 'nimbus-informe-portatil-0.20.0.html'
export.export(args.project.resolve() / 'engagement.yaml', 'html', target)
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('http:', 'https:')) else None)
    page.goto(target.as_uri() + '#%E0%A4%A')
    page.wait_for_function('document.fonts.status === "loaded"')
    check('Malformed hash does not throw', not errors)
    check('HTML embeds all images', page.locator('img').evaluate_all('(xs)=>xs.length>=19&&xs.every(x=>x.complete&&x.naturalWidth>0)'))
    check('Reading controls enabled with JavaScript', page.locator('#view').is_visible())
    for width in (360, 390, 768, 1366):
        page.set_viewport_size({'width': width, 'height': 900})
        check(f'Portable HTML fits {width}', page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    page.screenshot(path=str(out / '09-informe-html.png'))
    page.locator('#severity').select_option('critical')
    check('Critical filter retains two findings', page.locator('.finding:visible').count() == 2)
    page.locator('#severity').select_option('')
    page.locator('#view').select_option('executive')
    check('Executive view hides detailed findings', page.locator('.finding:visible').count() == 0)
    nojs = browser.new_context(java_script_enabled=False)
    plain = nojs.new_page()
    plain.goto(target.as_uri())
    check('Without JS complete report remains readable', plain.locator('.finding:visible').count() == 12)
    check('Without JS no inactive toolbar', not plain.locator('#view').is_visible())
    check('Offline report makes no network requests', not requests)
    browser.close()
print(json.dumps({'checks': len(checks), 'artifact': str(target)}, indent=2))
