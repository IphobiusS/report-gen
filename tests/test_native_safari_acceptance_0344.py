"""Native browser receipts must not accept a replacement engine or invalid geometry."""
import importlib.util
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
