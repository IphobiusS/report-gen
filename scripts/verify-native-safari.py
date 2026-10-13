#!/usr/bin/env python3
"""Bounded acceptance in Apple's Safari, never Playwright's WebKit substitute.

Uses the W3C protocol exposed by /usr/bin/safaridriver and an isolated synthetic
workspace. Screenshots and explicit checks are evidence, not human acceptance.
"""
import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
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


def title_only_change(original, observed, title):
    expected = deepcopy(original)
    expected['meta']['report_title'] = title
    return observed == expected


def inspect_lifecycle_export(payload, verification, revision, title, findings):
    """Bind browser bytes to the saved revision and its actual HTML contract."""
    from lxml import html
    if verification.get('source_revision') != revision:
        raise ValueError('HTML verification belongs to another saved revision')
    files = verification.get('files', {})
    if len(files) != 1 or not next(iter(files)).endswith('.html'):
        raise ValueError('Expected one verified HTML download')
    filename, record = next(iter(files.items()))
    digest = hashlib.sha256(payload).hexdigest()
    if record.get('sha256') != digest or record.get('bytes') != len(payload):
        raise ValueError('Downloaded HTML bytes do not match verification')
    checks = record.get('checks', {})
    if (checks.get('standalone') is not True or checks.get('static_visibility_checked') is not True
            or checks.get('contract_version') != 3 or checks.get('content_units_checked', 0) < 1):
        raise ValueError('HTML content contract is absent or incomplete')
    tree = html.document_fromstring(payload)
    headings = [' '.join(node.text_content().split()) for node in tree.xpath('//body//h1')]
    if title not in headings:
        raise ValueError('Saved title marker is absent from the HTML report heading')
    visible = ' '.join(tree.xpath('//body//text()[not(ancestor::script or ancestor::style)]'))
    visible = ' '.join(visible.split())
    if not findings or any(' '.join(finding['title'].split()) not in visible for finding in findings):
        raise ValueError('An original finding title is absent from the HTML download')
    return {'filename': filename, 'bytes': len(payload), 'sha256': digest,
            'source_revision': revision, 'finding_titles_checked': len(findings),
            'checks': checks}


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

    def async_script(self, source, *args):
        wrapped = ("const done=arguments[arguments.length-1];(async()=>{" + source
                   + "})().then(value=>done({ok:true,value}),error=>done({ok:false,error:String(error)}));")
        result = self.request('POST', '/execute/async', {'script': wrapped, 'args': list(args)})
        if not result.get('ok'):
            raise RuntimeError('Safari asynchronous operation: ' + result.get('error', 'unknown failure'))
        return result.get('value')

    def click(self, css):
        element = self.request('POST', '/element', {'using': 'css selector', 'value': css})
        self.request('POST', f'/element/{element[ELEMENT]}/click', {})

    def key(self, value):
        self.request('POST', '/actions', {'actions': [{'type': 'key', 'id': 'keyboard',
                     'actions': [{'type': 'keyDown', 'value': value}, {'type': 'keyUp', 'value': value}]}]})
        self.request('DELETE', '/actions')

    def fill(self, css, value):
        element = self.request('POST', '/element', {'using': 'css selector', 'value': css})
        self.request('POST', f'/element/{element[ELEMENT]}/clear', {})
        self.request('POST', f'/element/{element[ELEMENT]}/value', {'text': value})

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


def project_lifecycle(driver, out, results, check):
    """API-backed import in Safari, native field editing and UI-queued export.

    File bytes use browser fetch; this does not assess the operating-system
    file picker or download destination dialog. No production state is patched.
    """
    original = driver.script('return {slug:S.slug,data:S.data,etag:projectStore.etag};')
    slug = 'safari-imported-nimbus'
    title = 'SAFARI-R15 persisted synthetic report'
    imported = driver.async_script("""
        const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(S.slug)+'/bundle'));
        const blob=await response.blob();
        const base64=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(blob);});
        const form=new FormData();form.append('file',new File([blob],'nimbus-project.zip',{type:'application/zip'}));form.append('slug',arguments[0]);
        const result=await requireOk(await appFetch('/api/projects/import',{method:'POST',body:form}));
        const body=await result.json();await refreshProjects();await loadProject(body.slug);
        return {slug:S.slug,data:S.data,etag:projectStore.etag,backup_base64:base64};
    """, slug)
    backup = base64.b64decode(imported.pop('backup_base64'), validate=True)
    (out / 'nimbus-source-project.zip').write_bytes(backup)
    check('Safari imports an exact synthetic project copy through the real multipart API',
          imported['slug'] == slug and imported['data'] == original['data'])
    results['lifecycle'] = {'import_method': 'Safari fetch/FormData; OS picker not assessed',
                            'source_slug': original['slug'], 'imported_slug': slug,
                            'backup_sha256': hashlib.sha256(backup).hexdigest(),
                            'imported_revision': imported['etag'].strip(chr(34))}
    driver.click('#navReport')
    wait_for(lambda: driver.script("return !!document.querySelector('#editor [data-field=report_title]');"))
    driver.fill('#editor [data-field=report_title]', title)
    wait_for(lambda: driver.script("return S.data.meta.report_title===arguments[0] && !projectStore.dirty && !projectStore.lastError && projectStore.etag!==arguments[1];", title, imported['etag']))
    saved = driver.script('return {data:S.data,etag:projectStore.etag};')
    check('Native field editing autosaves only the intended title with a new revision',
          title_only_change(original['data'], saved['data'], title)
          and saved['etag'] != imported['etag'])
    driver.screenshot(out / 'nimbus-autosaved-title.png')
    check('No runtime errors during import and autosave', driver.script('return __nativeErrors;') == [])
    driver.request('POST', '/refresh', {})
    wait_for(lambda: driver.script("return !document.querySelector('#splash') && typeof S!=='undefined' && !!S.data && !projectStore.loading && !projectBusyCount;"))
    # Startup intentionally selects the first project. Select the imported copy
    # through the existing select/change handler before checking persisted data.
    driver.script("const s=document.querySelector('#projectSelect');s.value=arguments[0];s.dispatchEvent(new Event('change',{bubbles:true}));", slug)
    wait_for(lambda: driver.script('return S.slug===arguments[0] && !projectStore.loading && !projectBusyCount;', slug))
    reloaded = driver.script('return {data:S.data,etag:projectStore.etag};')
    check('Real reload preserves the exact saved project and revision', reloaded == saved)
    driver.script("window.__nativeErrors=[];addEventListener('error',e=>__nativeErrors.push(String(e.message)));addEventListener('unhandledrejection',e=>__nativeErrors.push(String(e.reason)));")
    unchanged = driver.async_script('return await api.get("/api/projects/"+encodeURIComponent(arguments[0]));', original['slug'])
    check('Import and editing preserve the original Nimbus project', unchanged == original['data'])
    for menu in ('studioMore', 'exportMenu'):
        if not driver.script('return document.getElementById(arguments[0]).open;', menu):
            driver.click('#' + menu + ' > summary')
    previous = driver.async_script('return (await api.get("/api/jobs")).map(job=>job.id);')
    driver.script("const s=document.querySelector('#exportFormat');s.value='html';s.dispatchEvent(new Event('change',{bubbles:true}));")
    driver.click('#downloadBtn')
    def completed():
        return driver.script("return [...document.querySelectorAll('.job-card')].map(r=>({id:r.dataset.job,stage:r.dataset.stage})).find(r=>!arguments[0].includes(r.id)&&['done','error','cancelled'].includes(r.stage))||null;", previous)
    job = wait_for(completed, timeout=90)
    check('Native Safari UI queues and completes an HTML export', job['stage'] == 'done', job)
    exported = driver.async_script("""
        const job=await api.get('/api/jobs/'+arguments[0]);
        const verification=await api.get('/api/jobs/'+arguments[0]+'/verification');
        const response=await requireOk(await appFetch('/api/jobs/'+arguments[0]+'/download'));
        const blob=await response.blob();
        const base64=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(blob);});
        return {job,verification,base64};
    """, job['id'])
    payload = base64.b64decode(exported.pop('base64'), validate=True)
    (out / 'nimbus-safari-export.html').write_bytes(payload)
    (out / 'nimbus-safari-verification.json').write_text(json.dumps(exported, indent=2) + '\n')
    saved_revision = saved['etag'].strip(chr(34))
    check('HTML job belongs to the exact reloaded revision', exported['job']['revision'] == saved_revision)
    contract = inspect_lifecycle_export(payload, exported['verification'], saved_revision, title, original['data']['findings'])
    check('Safari HTML bytes, title, findings and content contract match the saved revision', True, contract)
    results['lifecycle'].update({'saved_revision': saved_revision, 'title_marker': title,
                                 'download_method': 'Safari fetch of the completed UI job; OS save dialog not assessed',
                                 'export': contract})
    check('No runtime errors after reload during HTML export', driver.script('return __nativeErrors;') == [])
    driver.screenshot(out / 'nimbus-html-export-ready.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'out/native-safari')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = {'status': 'running', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'system': platform.system(), 'checks': [],
               'scope': 'Native desktop Safari: bilingual tutorial, modal keyboard, root-font enlargement, browser API import, native editing/autosave/reload and UI-queued verified HTML export',
               'not_assessed': ['human screen-reader acceptance', 'mobile Safari', 'all export formats',
                                'OS file picker and download destination dialog', 'unsaved-draft recovery after storage failure']}
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
        for language in ('es', 'en', 'pt'):
            driver.script("const control=document.querySelector('#langToggle');control.value=arguments[0];control.dispatchEvent(new Event('change',{bubbles:true}));applyUiTheme(arguments[1]);", language, 'dark' if language == 'es' else 'light')
            check(f'{language} language selector updates the UI and document language', driver.script("return S.uiLang===arguments[0] && document.querySelector('#langToggle').value===arguments[0] && document.documentElement.lang===(arguments[0]==='pt'?'pt-BR':arguments[0]);", language))
            # Safari can report descendant rectangles for a closed details.
            # Test the disclosure state, then use the actual visible control.
            if not driver.script("return document.querySelector('#studioMore').open;"):
                driver.click('#studioMore > summary')
            wait_for(lambda: driver.script("return document.querySelector('#studioMore').open && !document.querySelector('#guideBtn').disabled;"))
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
        project_lifecycle(driver, out, results, check)
        results['status'] = 'passed'
    except Exception as exc:
        results['status'] = 'failed'
        results['error'] = f'{type(exc).__name__}: {exc}'
        if driver and driver.session:
            try:
                results['failure_context'] = driver.script("return {url:location.href,selection:typeof S==='undefined'?null:S.sel,menuOpen:document.querySelector('#studioMore')?.open,focused:document.activeElement?.outerHTML,dialogs:[...document.querySelectorAll('dialog[open]')].map(n=>n.className)};")
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
