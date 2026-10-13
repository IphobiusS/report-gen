"""Native browser receipts must not accept a replacement engine or invalid geometry."""
import importlib.util
from copy import deepcopy
import hashlib
from pathlib import Path
import os
import queue
import subprocess
import sys
import threading
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_safari', ROOT / 'scripts/verify-native-safari.py')
safari = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safari)

SAFARI = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/26.0 Safari/605.1.15'
CAPABILITIES = {'browserName': 'Safari', 'browserVersion': '26.0', 'platformName': 'mac'}


def test_native_browser_identity_requires_independent_os_capabilities_and_agent():
    assert safari.native_identity('Darwin', CAPABILITIES, SAFARI)


@pytest.mark.parametrize('system,capabilities,agent', [
    ('Linux', CAPABILITIES, SAFARI),
    ('Darwin', {**CAPABILITIES, 'browserName': 'webkit'}, SAFARI),
    ('Darwin', {**CAPABILITIES, 'browserVersion': ''}, SAFARI),
    ('Darwin', {**CAPABILITIES, 'platformName': 'linux'}, SAFARI),
    ('Darwin', CAPABILITIES, SAFARI.replace('Version/26.0 ', '')),
    ('Darwin', CAPABILITIES, SAFARI + ' Chrome/150.0'),
    ('Darwin', CAPABILITIES, SAFARI + ' Chromium/150.0'),
    ('Darwin', CAPABILITIES, SAFARI + ' Edg/150.0'),
    ('Darwin', {}, SAFARI),
])
def test_engine_substitutes_or_missing_native_evidence_fail(system, capabilities, agent):
    assert not safari.native_identity(system, capabilities, agent)


@pytest.mark.parametrize('geometry,expected', [
    ({'width': 1366, 'scroll': 1366, 'viewport': 1366}, True),
    ({'width': 1366, 'scroll': 20000, 'viewport': 1366}, False),
    ({'width': 0, 'scroll': 0, 'viewport': 1366}, False),
    ({'width': 1366, 'scroll': 1366, 'viewport': 0}, False),
])
def test_overflow_negative_control_and_empty_viewport_cannot_pass(geometry, expected):
    assert safari.fits_viewport(geometry) is expected


def test_wait_is_bounded_for_failed_native_condition():
    with pytest.raises(TimeoutError):
        safari.wait_for(lambda: False, timeout=0)


def test_native_script_refuses_non_mac_without_emitting_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(safari.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(safari.sys, 'argv', ['verify-native-safari', '--output', str(tmp_path)])
    with pytest.raises(AssertionError, match='Host is macOS'):
        safari.main()
    import json
    receipt = json.loads((tmp_path / 'results.json').read_text())
    assert receipt['status'] == 'failed'
    assert receipt['checks'][0]['passed'] is False


@pytest.mark.skipif(os.name != 'posix', reason='POSIX temporary-directory alias regression, as on macOS')
def test_synthetic_server_canonicalizes_its_own_temporary_alias(tmp_path):
    """A /var-like symlink must not make the Mac acceptance server reject itself."""
    import json
    real = tmp_path / 'actual-temp'
    real.mkdir()
    alias = tmp_path / 'temp-alias'
    alias.symlink_to(real, target_is_directory=True)
    process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/browser-server-0212.py')],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT,
                               env={**os.environ, 'TMPDIR': str(alias)})
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        base = json.loads(lines.get(timeout=30))['url']
        with urlopen(base + '/api/projects', timeout=15) as response:
            assert response.status == 200
            projects = json.load(response)
        assert projects == []
    finally:
        safari.stop(process)


def lifecycle_fixture():
    title = 'SAFARI-R15 persisted synthetic report'
    findings = [{'title': 'Boundary café / cafe\u0301'}, {'title': 'Second finding retained'}]
    payload = ('<!doctype html><html><head><meta charset="utf-8"></head><body>'
               '<h1>' + title + '</h1><h2>' + findings[0]['title'] + '</h2>'
               '<h2>' + findings[1]['title'] + '</h2></body></html>').encode()
    checks = {'standalone': True, 'static_visibility_checked': True,
              'contract_version': 3, 'content_units_checked': 2}
    verification = {'source_revision': 'revision-exact', 'files': {'report.html': {
        'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(), 'checks': checks}}}
    return payload, verification, title, findings


def test_safari_lifecycle_contract_binds_actual_bytes_title_findings_and_revision():
    payload, verification, title, findings = lifecycle_fixture()
    result = safari.inspect_lifecycle_export(payload, verification, 'revision-exact', title, findings)
    assert result['finding_titles_checked'] == 2
    assert result['sha256'] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize('mutation', ['revision', 'hash', 'bytes', 'missing_contract',
                                     'incomplete_contract', 'extra_file', 'missing_file', 'wrong_format'])
def test_safari_lifecycle_contract_rejects_stale_or_unverified_downloads(mutation):
    payload, verification, title, findings = lifecycle_fixture()
    record = verification['files']['report.html']
    if mutation == 'revision': verification['source_revision'] = 'another-revision'
    elif mutation == 'hash': record['sha256'] = '0' * 64
    elif mutation == 'bytes': record['bytes'] += 1
    elif mutation == 'missing_contract': record['checks'] = {}
    elif mutation == 'incomplete_contract': record['checks']['static_visibility_checked'] = False
    elif mutation == 'extra_file': verification['files']['other.html'] = deepcopy(record)
    elif mutation == 'missing_file': verification['files'] = {}
    elif mutation == 'wrong_format': verification['files'] = {'report.pdf': record}
    with pytest.raises(ValueError):
        safari.inspect_lifecycle_export(payload, verification, 'revision-exact', title, findings)


@pytest.mark.parametrize('mutation', ['title', 'finding', 'unicode', 'marker_only_in_script'])
def test_safari_lifecycle_checks_content_even_with_recomputed_download_hash(mutation):
    payload, verification, title, findings = lifecycle_fixture()
    text = payload.decode()
    if mutation == 'title': text = text.replace(title, 'Wrong report title')
    elif mutation == 'finding': text = text.replace(findings[1]['title'], 'Lost content')
    elif mutation == 'unicode': text = text.replace('cafe\u0301', 'café')
    else: text = text.replace('<h1>' + title + '</h1>', '<script>' + title + '</script>')
    payload = text.encode()
    verification['files']['report.html'].update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError):
        safari.inspect_lifecycle_export(payload, verification, 'revision-exact', title, findings)


@pytest.mark.parametrize('mutation', ['intended', 'unchanged', 'finding', 'client', 'extra_key'])
def test_safari_project_comparison_allows_only_the_intended_title(mutation):
    original = {'meta': {'report_title': 'Original', 'client': 'Synthetic client'},
                'findings': [{'uid': 'fixed-uid', 'title': 'Original finding'}]}
    observed = deepcopy(original)
    if mutation != 'unchanged': observed['meta']['report_title'] = 'Edited marker'
    if mutation == 'finding': observed['findings'][0]['title'] = 'Unexpected edit'
    if mutation == 'client': observed['meta']['client'] = 'Unexpected client'
    if mutation == 'extra_key': observed['new'] = 'Unexpected field'
    before = deepcopy(original)
    assert safari.title_only_change(original, observed, 'Edited marker') is (mutation == 'intended')
    assert original == before
