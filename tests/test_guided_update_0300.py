"""Updater verifies independent metadata, stages without execution, and retries."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import zipfile

import pytest
import update_helper as updater
import project_history
import workspace_backup

VERSION = '9.8.7'
COMMIT = 'a' * 40
TREE = 'b' * 40


def digest(blob):
    return sha256(blob).hexdigest()


def fixture_release(files=None):
    files = files or {'version.py': f'__version__ = "{VERSION}"\n'.encode(),
        'engine.py': b'raise RuntimeError("DOWNLOADED_CODE_MUST_NOT_RUN")\n',
        'start.py': b'raise RuntimeError("DOWNLOADED_CODE_MUST_NOT_RUN")\n',
        'scripts/install.py': b'raise RuntimeError("DOWNLOADED_CODE_MUST_NOT_RUN")\n',
        'webapp/app.py': b'raise RuntimeError("DOWNLOADED_CODE_MUST_NOT_RUN")\n'}
    stem = f'report-gen-{VERSION}-{COMMIT[:12]}'
    out = BytesIO()
    rows = []
    with zipfile.ZipFile(out, 'w') as archive:
        for name, blob in files.items():
            info = zipfile.ZipInfo(stem + '/' + name)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, blob)
            rows.append({'path': name, 'mode': '100644', 'size': len(blob), 'sha256': digest(blob)})
    package = out.getvalue()
    manifest = {'schema': 1, 'version': VERSION, 'commit': COMMIT, 'tree': TREE,
        'archive': stem + '.zip', 'sha256': digest(package), 'files': rows,
        'release_download': updater.WEB + f'/releases/download/v{VERSION}/{stem}.zip',
        'canonical_download': updater.WEB + '/archive/' + COMMIT + '.zip'}
    payloads = {'zip': package, 'json': json.dumps(manifest).encode(),
        'sha256': (manifest['sha256'] + '  ' + stem + '.zip\n').encode()}
    assets = [{'id': i+1, 'name': stem + '.' + extension, 'state': 'uploaded',
               'size': len(blob), 'digest': 'sha256:' + digest(blob),
               'browser_download_url': updater.WEB + f'/releases/download/v{VERSION}/{stem}.{extension}'}
              for i, (extension, blob) in enumerate(payloads.items())]
    release = {'id': 41, 'tag_name': 'v' + VERSION, 'draft': False, 'prerelease': False,
        'published_at': '2026-10-10T00:00:00Z', 'html_url': updater.WEB + '/releases/tag/v' + VERSION, 'assets': assets}
    responses = {asset['browser_download_url']: payloads[asset['name'].rsplit('.', 1)[1]] for asset in assets}
    responses[updater.API + '/releases/latest'] = json.dumps(release).encode()
    responses[updater.API + '/releases/41'] = json.dumps(release).encode()
    responses[updater.API + '/git/ref/tags/v' + VERSION] = json.dumps({'object': {'type': 'commit', 'sha': COMMIT}}).encode()
    return release, manifest, package, responses


def stub_network(monkeypatch, responses):
    requests = []
    def fetch(url, maximum):
        requests.append(url)
        assert url in responses, url
        blob = responses[url]
        assert len(blob) <= maximum
        return blob
    monkeypatch.setattr(updater, 'fetch', fetch)
    return requests


def project(root):
    paths = (root / 'projects', root / 'library/findings.json', root / 'library/designs.json')
    project_history.save(paths[0] / 'one', {'meta': {'report_title': 'PRIVATE_CLIENT_SENTINEL', 'lang': 'es'}, 'findings': []})
    return paths


def test_check_public_only_and_full_package_verification(monkeypatch):
    _, manifest, package, responses = fixture_release()
    requested = stub_network(monkeypatch, responses)
    plan, observed = updater.inspect_release('0.30.0')
    assert plan['version'] == VERSION and observed == manifest
    assert updater.verified_archive(plan, manifest, package)['engine.py'].startswith(b'raise RuntimeError')
    assert not any(url.endswith('.zip') for url in requested), 'check must not download full archive'
    assert all('PRIVATE' not in url and 'workspace' not in url for url in requested)


@pytest.mark.parametrize('change', ['draft', 'prerelease', 'version', 'extra_asset', 'missing_asset', 'duplicate_asset', 'asset_host',
    'asset_path', 'asset_digest', 'asset_size', 'asset_name_type', 'wrong_tag', 'wrong_checksum', 'changed_manifest', 'duplicate_json'])
def test_bad_release_never_reaches_preparation(monkeypatch, change):
    release, _, _, responses = fixture_release()
    if change in ('draft', 'prerelease'):
        release[change] = True
    elif change == 'version':
        release['tag_name'] = 'v9.8.7-rc1'
    elif change == 'extra_asset':
        release['assets'].append(deepcopy(release['assets'][0]))
    elif change == 'missing_asset':
        release['assets'].pop()
    elif change == 'duplicate_asset':
        release['assets'][1] = deepcopy(release['assets'][0])
    elif change == 'asset_name_type':
        release['assets'][0]['name'] = ['invalid']
    elif change == 'asset_host':
        release['assets'][0]['browser_download_url'] = 'https://attacker.invalid/payload.zip'
    elif change == 'asset_path':
        release['assets'][0]['browser_download_url'] = updater.WEB + '/archive/main.zip'
    elif change == 'asset_digest':
        release['assets'][1]['digest'] = 'sha256:' + '0' * 64
    elif change == 'asset_size':
        release['assets'][0]['size'] = updater.MAX_PACKAGE + 1
    elif change == 'wrong_tag':
        responses[updater.API + '/git/ref/tags/v' + VERSION] = json.dumps({'object': {'type': 'commit', 'sha': 'c'*40}}).encode()
    elif change in ('wrong_checksum', 'changed_manifest'):
        key = 'sha256' if change == 'wrong_checksum' else 'json'
        asset = next(a for a in release['assets'] if a['name'].endswith('.' + key))
        blob = b'altered'
        responses[asset['browser_download_url']] = blob
        asset['size'], asset['digest'] = len(blob), 'sha256:' + digest(blob)
    elif change == 'duplicate_json':
        responses[updater.API + '/releases/latest'] = b'{"id":1,"id":2}'
    if change != 'duplicate_json':
        responses[updater.API + '/releases/latest'] = json.dumps(release).encode()
    stub_network(monkeypatch, responses)
    with pytest.raises(ValueError):
        updater.inspect_release('0.30.0')


@pytest.mark.parametrize('current', ['9.8.7', '10.0.0'])
def test_never_reinstall_same_or_downgrade(monkeypatch, current):
    _, _, _, responses = fixture_release()
    requested = stub_network(monkeypatch, responses)
    assert updater.inspect_release(current) == {'available': False, 'current_version': current, 'latest_version': VERSION}
    assert len(requested) == 1


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/drive', 'a\\b', 'a/../b', 'a//b', 'a/CON.txt',
    'a/name.', 'a/name ', 'a/name:stream', 'a/name\n', '.git/config', '.venv/bin/python',
    'webapp/projects/client/engagement.yaml', 'webapp/library/findings.json', '.report-gen-browser-id', 'a/a?b'])
def test_rejects_unsafe_and_residual_paths(name):
    with pytest.raises(ValueError):
        updater._path(name)


@pytest.mark.parametrize('change', ['truncated', 'symlink', 'duplicate', 'additional', 'wrong_bytes', 'version', 'expanded_limit', 'alias'])
def test_hostile_archive_or_manifest_is_rejected_before_any_write(monkeypatch, change):
    _, manifest, package, responses = fixture_release()
    stub_network(monkeypatch, responses)
    plan, _ = updater.inspect_release('0.30.0')
    if change == 'truncated':
        package = package[:-40]
    elif change == 'expanded_limit':
        monkeypatch.setattr(updater, 'MAX_EXPANDED', 10)
    elif change == 'alias':
        manifest['files'].append({**manifest['files'][0], 'path': 'VERSION.py'})
    else:
        reader = zipfile.ZipFile(BytesIO(package))
        out = BytesIO()
        with zipfile.ZipFile(out, 'w') as archive:
            for info in reader.infolist():
                blob = reader.read(info)
                if info.filename.endswith('/engine.py'):
                    if change == 'symlink':
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    if change == 'wrong_bytes':
                        blob = b'altered'
                if info.filename.endswith('/version.py') and change == 'version':
                    blob = b'__version__ = "0.1.0"\n'
                    manifest['files'][0].update(size=len(blob), sha256=digest(blob))
                archive.writestr(info, blob)
            if change in ('duplicate', 'additional'):
                archive.writestr(reader.infolist()[0].filename if change == 'duplicate' else 'outside.txt', b'bad')
        package = out.getvalue()
        # Even with a self-consistent outer digest, structural and per-file checks hold.
        plan.update(size=len(package), sha256=digest(package))
    with pytest.raises(ValueError):
        updater.verified_archive(plan, manifest, package)


def test_stage_real_workspace_backup_no_execution_private_and_idempotent(tmp_path, monkeypatch):
    _, manifest, package, responses = fixture_release()
    stub_network(monkeypatch, responses)
    plan, _ = updater.inspect_release('0.30.0')
    source = tmp_path / 'workspace'
    paths = project(source)
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    captured = []
    def backup():
        captured.append(True)
        return workspace_backup.export_workspace(*paths)
    arguments = dict(base=tmp_path / 'updates', current=tmp_path / 'old-install', workspace=source,
                     external=True, scope='opaque-workspace', lang='es')
    receipt = updater.prepare(plan, manifest, package, backup, **arguments)
    assert Path(receipt['application']).is_dir()
    assert Path(receipt['backup']).is_file()
    assert digest(Path(receipt['backup']).read_bytes()) == receipt['backup_sha256']
    assert workspace_backup.restore_workspace(Path(receipt['backup']).read_bytes(), tmp_path/'restored/projects',
        tmp_path/'restored/library/findings.json', tmp_path/'restored/library/designs.json')['projects'] == 1
    assert {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()} == before
    assert updater.prepare(plan, manifest, package, backup, **arguments) == receipt
    assert len(captured) == 2
    if os.name != 'nt':
        assert Path(receipt['backup']).stat().st_mode & 0o777 == 0o600
        assert Path(receipt['backup']).parent.stat().st_mode & 0o777 == 0o700
    assert 'PRIVATE_CLIENT_SENTINEL' not in json.dumps(receipt)
    assert str(source) in receipt['commands'][0]
    assert not list((tmp_path/'updates').glob('.preparing-*'))


def test_failed_backup_cleans_stage_and_preserves_every_original(tmp_path, monkeypatch):
    _, manifest, package, responses = fixture_release()
    stub_network(monkeypatch, responses)
    plan, _ = updater.inspect_release('0.30.0')
    def broken():
        raise OSError('PRIVATE_PATH_DO_NOT_LEAK')
    arguments = dict(base=tmp_path/'updates', current=tmp_path/'old', workspace=tmp_path/'workspace', external=True, scope='one')
    with pytest.raises(OSError):
        updater.prepare(plan, manifest, package, broken, **arguments)
    assert list((tmp_path/'updates').iterdir()) == []
    result = updater.prepare(plan, manifest, package, lambda: workspace_backup.export_workspace(tmp_path/'workspace/projects', tmp_path/'workspace/findings.json', tmp_path/'workspace/designs.json'), **arguments)
    (Path(result['application'])/'engine.py').write_bytes(b'changed')
    with pytest.raises(ValueError):
        updater.prepare(plan, manifest, package, lambda: workspace_backup.export_workspace(tmp_path/'workspace/projects', tmp_path/'workspace/findings.json', tmp_path/'workspace/designs.json'), **arguments)


def test_scope_separates_prepared_workspaces_and_legacy_has_migration(tmp_path, monkeypatch):
    _, manifest, package, responses = fixture_release()
    stub_network(monkeypatch, responses)
    plan, _ = updater.inspect_release('0.30.0')
    args = dict(base=tmp_path/'updates', current=tmp_path/'old', workspace=tmp_path/'workspace', external=False)
    first = updater.prepare(plan, manifest, package, lambda: workspace_backup.export_workspace(tmp_path/'one/projects', tmp_path/'one/findings.json', tmp_path/'one/designs.json'), scope='one', **args)
    second = updater.prepare(plan, manifest, package, lambda: workspace_backup.export_workspace(tmp_path/'two/projects', tmp_path/'two/findings.json', tmp_path/'two/designs.json'), scope='two', **args)
    assert first['application'] != second['application']
    assert 'launcher_upgrade.py' in first['commands'][0]
    assert first['migration'] is True
    assert first['workspace'] != str(tmp_path/'workspace')


@pytest.mark.parametrize('url', ['http://github.com/IphobiusS/report-gen', 'https://github.com.evil.invalid/file',
    'https://github.com@evil.invalid/file', 'https://github.com:444/file', 'file:///etc/passwd'])
def test_network_redirect_allowlist(url):
    with pytest.raises(ValueError):
        updater._url(url)


def test_shell_commands_quote_literal_paths(tmp_path):
    stage = tmp_path / "space ' $HOME `cmd`"
    linux = updater.instructions(stage, tmp_path/'old', tmp_path/'private', True, 'en', windows=False)
    import shlex
    import sys
    entry = 'scripts/install.py' if sys.platform.startswith('linux') else 'start.py'
    assert shlex.split(linux['commands'][0])[1] == str(stage/'application'/entry)
    windows = updater.instructions(stage, tmp_path/'old', tmp_path/'private', True, 'en', windows=True)
    assert windows['shell'] == 'PowerShell'
    assert "''" in windows['commands'][0]
    assert '--workspace' in windows['commands'][0]


@pytest.fixture
def local_api(tmp_path, monkeypatch):
    import app as api
    from _support import auth_client
    source = tmp_path/'live-workspace'
    paths = project(source)
    monkeypatch.setattr(api, 'PROJECTS', paths[0])
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(paths[1]))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(paths[2]))
    monkeypatch.setitem(api.app.config, 'WORKSPACE_ROOT', str(source))
    monkeypatch.setitem(api.app.config, 'WORKSPACE_EXTERNAL', True)
    monkeypatch.setitem(api.app.config, 'UPDATE_STAGE_ROOT', str(tmp_path/'updates'))
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    _, _, _, responses = fixture_release()
    calls = stub_network(monkeypatch, responses)
    return api, auth_client(api.app), paths, responses, calls


def test_local_api_requires_consent_csrf_and_binds_workspace(local_api, monkeypatch, tmp_path):
    api, client, paths, _, calls = local_api
    response = client.post('/api/update/check', json={'allow_network': False})
    assert response.status_code == 422
    response = client.post('/api/update/check', json={'allow_network': True}, headers={'X-CSRF-Token': 'invalid'})
    assert response.status_code == 403
    assert not calls
    checked = client.post('/api/update/check', json={'allow_network': True})
    assert checked.status_code == 200, checked.get_json()
    plan = checked.get_json()
    monkeypatch.setattr(api, 'PROJECTS', tmp_path/'another-workspace/projects')
    response = client.post('/api/update/prepare', json={'allow_network': True, 'ack_private_backup': True,
                                                       'preview_token': plan['preview_token']})
    assert response.status_code == 409
    assert not (tmp_path/'updates').exists()
    assert paths[0].exists()


def test_local_api_real_backup_stage_retry_and_no_sensitive_error(local_api, monkeypatch, tmp_path):
    _, client, paths, _, _ = local_api
    checked = client.post('/api/update/check', json={'allow_network': True}).get_json()
    body = {'allow_network': True, 'ack_private_backup': True, 'preview_token': checked['preview_token']}
    exporter = workspace_backup.export_workspace
    def broken(*args):
        raise OSError('/home/SECRET_USERNAME/PRIVATE_CUSTOMER')
    monkeypatch.setattr(workspace_backup, 'export_workspace', broken)
    response = client.post('/api/update/prepare', json=body, headers={'X-UI-Language': 'en'})
    assert response.status_code == 503
    assert 'SECRET' not in response.get_data(as_text=True) and 'PRIVATE_CUSTOMER' not in response.get_data(as_text=True)
    assert list((tmp_path/'updates').iterdir()) == []
    monkeypatch.setattr(workspace_backup, 'export_workspace', exporter)
    response = client.post('/api/update/prepare', json=body, headers={'X-UI-Language': 'en'})
    assert response.status_code == 200, response.get_json()
    receipt = response.get_json()
    assert Path(receipt['backup']).is_file()
    assert '--lang' in receipt['commands'][0] and 'en' in receipt['commands'][0]
    retry = client.post('/api/update/prepare', json=body, headers={'X-UI-Language': 'en'})
    assert retry.get_json() == receipt
    assert len(list((tmp_path/'updates').iterdir())) == 1
    assert 'PRIVATE_CLIENT_SENTINEL' not in response.get_data(as_text=True)
    assert (paths[0]/'one/engagement.yaml').is_file()


def test_changed_release_and_tampered_ticket_require_new_check(local_api):
    _, client, _, responses, _ = local_api
    checked = client.post('/api/update/check', json={'allow_network': True}).get_json()
    body = {'allow_network': True, 'ack_private_backup': True, 'preview_token': checked['preview_token'] + 'x'}
    assert client.post('/api/update/prepare', json=body).status_code == 409
    body['preview_token'] = checked['preview_token']
    release = json.loads(responses[updater.API + '/releases/41'])
    release['assets'][0]['id'] += 10
    responses[updater.API + '/releases/41'] = json.dumps(release).encode()
    assert client.post('/api/update/prepare', json=body).status_code == 409


def test_saved_edit_after_preparation_gets_fresh_backup_without_erasing_old(local_api):
    _, client, paths, _, _ = local_api
    checked = client.post('/api/update/check', json={'allow_network': True}).get_json()
    body = {'allow_network': True, 'ack_private_backup': True, 'preview_token': checked['preview_token']}
    first = client.post('/api/update/prepare', json=body)
    assert first.status_code == 200
    old = first.get_json()
    old_bytes = Path(old['backup']).read_bytes()
    project_history.save(paths[0]/'one', {'meta': {'report_title': 'LATEST_UNBACKED_EDIT', 'lang': 'es'}, 'findings': []})
    second = client.post('/api/update/prepare', json=body)
    assert second.status_code == 200, second.get_json()
    new = second.get_json()
    assert new['snapshot'] != old['snapshot'] and new['backup'] != old['backup']
    assert Path(old['backup']).read_bytes() == old_bytes
    with zipfile.ZipFile(new['backup']) as outer:
        with zipfile.ZipFile(BytesIO(outer.read('projects/one.zip'))) as project_zip:
            assert b'LATEST_UNBACKED_EDIT' in project_zip.read('engagement.yaml')
    assert client.post('/api/update/prepare', json=body).get_json() == new


def test_fingerprint_ignores_created_timestamps_but_keeps_project_content(tmp_path, monkeypatch):
    paths = project(tmp_path/'source')
    first = workspace_backup.export_workspace(*paths)
    monkeypatch.setattr(project_history, 'now', lambda: '2099-01-01T00:00:00Z')
    second = workspace_backup.export_workspace(*paths)
    assert first != second
    assert updater.backup_identity(first) == updater.backup_identity(second)
    project_history.save(paths[0]/'one', {'meta': {'report_title': 'Changed'}, 'findings': []})
    third = workspace_backup.export_workspace(*paths)
    assert updater.backup_identity(third) != updater.backup_identity(first)


def test_transport_truncation_is_a_retryable_error_without_response_data(monkeypatch):
    from http.client import IncompleteRead
    class Response:
        url = updater.API + '/releases/latest'
        status = 200
        headers = {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, maximum):
            raise IncompleteRead(b'UNTRUSTED_PARTIAL_PRIVATE_STRING')
    class Opener:
        def open(self, request, timeout):
            assert request.get_header('Authorization') is None
            return Response()
    monkeypatch.setattr(updater, 'build_opener', lambda *args: Opener())
    with pytest.raises(ValueError) as observed:
        updater.fetch(Response.url, 1024)
    assert 'UNTRUSTED' not in str(observed.value)


def test_expired_preview_requires_fresh_check(local_api, monkeypatch):
    from itsdangerous import TimestampSigner
    _, client, _, _, _ = local_api
    checked = client.post('/api/update/check', json={'allow_network': True}).get_json()
    timestamp = TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner, 'get_timestamp', lambda self: timestamp(self) + 1801)
    response = client.post('/api/update/prepare', json={'allow_network': True, 'ack_private_backup': True,
                                                       'preview_token': checked['preview_token']})
    assert response.status_code == 409
