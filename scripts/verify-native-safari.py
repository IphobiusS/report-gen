#!/usr/bin/env python3
"""Bounded acceptance in Apple's Safari, never Playwright's WebKit substitute.

Uses the W3C protocol exposed by /usr/bin/safaridriver and an isolated synthetic
workspace. Screenshots and explicit checks are evidence, not human acceptance.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import selectors
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ELEMENT = 'element-6066-11e4-a52e-4f735466cecf'
GEOMETRY = """
return {scroll:document.documentElement.scrollWidth,
        width:document.documentElement.clientWidth,
        viewport:innerWidth};
"""


def native_identity(system, capabilities, user_agent):
    """Reject Linux WebKit, Chrome and missing/native-identity evidence."""
    return (system == 'Darwin'
            and str(capabilities.get('browserName', '')).lower() == 'safari'
            and bool(capabilities.get('browserVersion'))
            and str(capabilities.get('platformName', '')).lower() in ('mac', 'macos', 'darwin')
            and 'Version/' in user_agent and 'Safari/' in user_agent
            and not any(token in user_agent for token in ('Chrome/', 'Chromium/', 'Edg/')))


def fits_viewport(geometry):
    return (geometry['width'] > 0 and geometry['viewport'] > 0
            and geometry['scroll'] <= geometry['width'] + 1)


def wait_for(predicate, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.15)
    raise TimeoutError('Native Safari acceptance condition did not become true')


class Driver:
    def __init__(self, port):
        self.base = f'http://127.0.0.1:{port}'
        self.session = None

    def request(self, method, route, body=None, *, session=True):
        if session:
            route = f'/session/{self.session}' + route
        request = Request(self.base + route, method=method,
                          data=None if body is None else json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response).get('value')
        except HTTPError as exc:
            raise RuntimeError(f'WebDriver {route}: {exc.read().decode()}') from exc
        if isinstance(result, dict) and result.get('error'):
            raise RuntimeError(f'WebDriver {route}: {result}')
        return result

    def script(self, source, *args):
        return self.request('POST', '/execute/sync', {'script': source, 'args': list(args)})

    def click(self, css):
        element = self.request('POST', '/element', {'using': 'css selector', 'value': css})
        self.request('POST', f'/element/{element[ELEMENT]}/click', {})

    def key(self, value):
        self.request('POST', '/actions', {'actions': [{'type': 'key', 'id': 'keyboard',
                     'actions': [{'type': 'keyDown', 'value': value}, {'type': 'keyUp', 'value': value}]}]})
        self.request('DELETE', '/actions')

    def screenshot(self, path):
        path.write_bytes(base64.b64decode(self.request('GET', '/screenshot'), validate=True))


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'out/native-safari')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = {'status': 'running', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'system': platform.system(), 'checks': [],
               'scope': 'Native desktop Safari: bilingual tutorial, real project, modal keyboard and root-font enlargement',
               'not_assessed': ['human screen-reader acceptance', 'mobile Safari', 'all export formats']}
    driver_process = server = driver = None

    def save():
        (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')

    def check(name, passed, detail=None):
        results['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
        save()
        if not passed:
            raise AssertionError(name)
        print('PASS ' + name, flush=True)

    try:
        check('Host is macOS with the native SafariDriver executable',
              platform.system() == 'Darwin' and Path('/usr/bin/safaridriver').is_file())
        results['macos'] = subprocess.check_output(['sw_vers'], text=True).strip()
        results['driver_version'] = subprocess.check_output(['/usr/bin/safaridriver', '--version'], text=True).strip()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with (out / 'safaridriver.log').open('w') as log:
            driver_process = subprocess.Popen(['/usr/bin/safaridriver', '-p', str(port)], stdout=log, stderr=log)
        driver = Driver(port)

        def driver_ready():
            if driver_process.poll() is not None:
                raise RuntimeError('SafariDriver exited before session creation')
            try:
                return driver.request('GET', '/status', session=False)
            except URLError:
                return False

        wait_for(driver_ready)
        session = driver.request('POST', '/session', {'capabilities': {'alwaysMatch': {'browserName': 'safari'}}}, session=False)
        driver.session = session['sessionId']
        results['capabilities'] = session['capabilities']
        driver.request('POST', '/timeouts', {'script': 20000, 'pageLoad': 30000, 'implicit': 0})
        driver.request('POST', '/window/rect', {'width': 1366, 'height': 1000, 'x': 0, 'y': 0})
        with (out / 'server.log').open('w') as log:
            server = subprocess.Popen([sys.executable, str(ROOT / 'scripts/browser-server-0212.py')],
                                      cwd=ROOT, stdout=subprocess.PIPE, stderr=log, text=True)
        with selectors.DefaultSelector() as selector:
            selector.register(server.stdout, selectors.EVENT_READ)
            if not selector.select(30):
                raise TimeoutError('Synthetic report-gen server did not start')
            base = json.loads(server.stdout.readline())['url']
        driver.request('POST', '/url', {'url': base})
        ready = "return !document.querySelector('#splash') && typeof GuideUI !== 'undefined' && !projectStore.loading && !projectBusyCount && !!document.querySelector('.workspace-dashboard');"
        wait_for(lambda: driver.script(ready))
        driver.script("localStorage.clear();localStorage.setItem('rg.previewVisible','0');")
        driver.request('POST', '/refresh', {})
        wait_for(lambda: driver.script(ready))
        agent = driver.script('return navigator.userAgent;')
        results['user_agent'] = agent
        check('Session is Apple Safari on macOS', native_identity(platform.system(), session['capabilities'], agent), agent)
        driver.script("window.__nativeErrors=[];addEventListener('error',e=>__nativeErrors.push(String(e.message)));addEventListener('unhandledrejection',e=>__nativeErrors.push(String(e.reason)));")
        check('First visit leaves a nonblocking tutorial invitation', driver.script("return !!document.querySelector('[data-tutorial-invite]') && !document.querySelector('dialog[open]');"))
        driver.script("document.querySelector('.workspace-hero-actions .primary').focus();")
        driver.key('\ue007')
        wait_for(lambda: driver.script("return S.slug && S.data?.findings?.length === 12 && !projectStore.loading && !projectBusyCount;"))
        check('Native keyboard action creates and loads Nimbus', driver.script("return S.sel.type === 'home' && S.data.findings.length === 12;"))
        state = "return JSON.stringify({slug:S.slug,data:S.data,revision:projectStore.revision,etag:projectStore.etag,dirty:projectStore.dirty});"
        original = driver.script(state)
        for language in ('es', 'en'):
            driver.script('setUiLang(arguments[0]);applyUiTheme(arguments[1]);', language, 'dark' if language == 'es' else 'light')
            if not driver.script("const n=document.querySelector('#guideBtn');return !!(n && n.getClientRects().length);"):
                driver.click('#studioMore > summary')
            driver.click('#guideBtn')
            wait_for(lambda: driver.script("return !!document.querySelector('[data-guide-page]');"))
            for step in range(6):
                driver.click(f'[data-guide-step="{step}"]')
                wait_for(lambda: driver.script("return [...document.querySelectorAll('.tutorial-screenshot img')].length>0 && [...document.querySelectorAll('.tutorial-screenshot img')].every(n=>n.complete && n.naturalWidth>500);"))
                check(f'{language} tutorial step {step + 1} loads localized images and focused navigation', driver.script("return [...document.querySelectorAll('.tutorial-screenshot img')].every(n=>n.src.endsWith('-'+arguments[0]+'.webp') && n.alt.length>50) && document.querySelectorAll('[data-guide-step][aria-current=step]').length===1 && document.activeElement===document.querySelector('#guideStepTitle');", language))
                if step in (0, 5):
                    driver.screenshot(out / f'tutorial-{language}-{step + 1}.png')
            driver.click('[data-guide-step="0"]')
            driver.click('[data-tutorial-image]')
            wait_for(lambda: driver.script("return !!document.querySelector('dialog.tutorial-image-dialog[open]');"))
            check(f'{language} screenshot opens as native modal with focused close control', driver.script("return document.querySelector('dialog.tutorial-image-dialog').matches(':modal') && document.activeElement===document.querySelector('[data-tutorial-close]');"))
            driver.key('\ue00c')
            wait_for(lambda: driver.script("return !document.querySelector('dialog[open]');"))
            check(f'{language} Escape restores tutorial trigger focus', driver.script("return document.activeElement.matches('[data-tutorial-image]');"))
            for text_size in (100, 200):
                driver.script("document.documentElement.style.fontSize=arguments[0]+'%';", text_size)
                geometry = driver.script(GEOMETRY)
                check(f'{language} tutorial fits native desktop viewport at {text_size}% root font', fits_viewport(geometry), geometry)
                driver.screenshot(out / f'tutorial-{language}-text-{text_size}.png')
            driver.script("document.documentElement.style.fontSize='100%';")
        driver.script("const n=document.createElement('div');n.id='native-overflow-control';n.style.cssText='position:absolute;left:0;width:20000px;height:1px';document.body.append(n);")
        bad_geometry = driver.script(GEOMETRY)
        check('Negative control detects a deliberately overflowing DOM element', not fits_viewport(bad_geometry), bad_geometry)
        driver.script("document.querySelector('#native-overflow-control').remove();")
        check('Geometry is valid again after removing the control', fits_viewport(driver.script(GEOMETRY)))
        driver.click('#navHome')
        check('Tutorial navigation preserves the exact project and saved revision', driver.script(state) == original)
        check('No runtime errors during the instrumented tutorial journey', driver.script('return __nativeErrors;') == [], driver.script('return __nativeErrors;'))
        driver.screenshot(out / 'nimbus-home.png')
        results['status'] = 'passed'
    except Exception as exc:
        results['status'] = 'failed'
        results['error'] = f'{type(exc).__name__}: {exc}'
        if driver and driver.session:
            try:
                driver.screenshot(out / 'failure.png')
            except Exception:
                pass
        raise
    finally:
        results['finished_utc'] = datetime.now(timezone.utc).isoformat()
        if driver and driver.session:
            try:
                driver.request('DELETE', '')
            except Exception:
                pass
        stop(driver_process)
        stop(server)
        save()


if __name__ == '__main__':
    main()
