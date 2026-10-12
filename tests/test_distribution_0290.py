"""Release trust boundaries, immutable publication and clean-source installation."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


release = module('publish_release_029', 'publish-release.py')
installer = module('install_029', 'install.py')
package = module('verify_installed_029', 'verify-installed-package.py')
COMMIT = 'a' * 40
OTHER = 'b' * 40


def event():
    return {'action': 'completed', 'workflow_run': {'event': 'push', 'head_branch': 'main',
            'head_sha': COMMIT, 'status': 'completed', 'conclusion': 'success', 'name': 'tests',
            'head_repository': {'full_name': release.REPOSITORY}}}


def environment():
    return {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': release.REPOSITORY, 'GITHUB_EVENT_NAME': 'workflow_run'}


class API:
    def __init__(self):
        self.main = COMMIT
        self.tag = None
        self.release = None
        self.assets = {}
        self.mutations = []
        self.run_overrides = {}
        self.after_upload = None
        self.gate_reads = 0
        self.asset_bytes_override = None
        self.latest_override = None

    def request(self, path, method='GET', data=None, **kwargs):
        assert path.startswith(release.route(''))
        suffix = path[len(release.route('')):]
        if method != 'GET':
            self.mutations.append((path, method, data))
        if suffix == 'git/ref/heads/main':
            self.gate_reads += 1
            return {'object': {'sha': self.main}}
        if suffix.startswith('actions/workflows/'):
            filename = suffix.split('/')[2]
            record = {'name': release.WORKFLOWS[filename], 'path': '.github/workflows/' + filename,
                      'head_sha': COMMIT, 'head_branch': 'main', 'event': 'push', 'status': 'completed',
                      'conclusion': 'success', 'head_repository': {'full_name': release.REPOSITORY},
                      'run_number': 1, 'run_attempt': 1, 'id': list(release.WORKFLOWS).index(filename) + 1,
                      'html_url': 'https://github.com/IphobiusS/report-gen/actions/runs/1'}
            return {'workflow_runs': self.run_overrides.get(filename, [record])}
        if suffix.startswith('git/ref/tags/'):
            return None if self.tag is None else {'object': {'type': 'commit', 'sha': self.tag}}
        if suffix == 'git/refs' and method == 'POST':
            assert self.tag is None
            self.tag = data['sha']
            return {'object': {'sha': self.tag}}
        if suffix.startswith('releases?'):
            return [] if self.release is None else [copy.deepcopy(self.release)]
        if suffix == 'releases' and method == 'POST':
            assert self.release is None and data['draft'] is True and data['make_latest'] == 'false'
            self.release = {**data, 'id': 7, 'html_url': 'https://github.com/IphobiusS/report-gen/releases/tag/v0.29.0'}
            return copy.deepcopy(self.release)
        if suffix.startswith('releases/7/assets?'):
            if method == 'POST':
                name = parse_qs(urlsplit(path).query)['name'][0]
                assert name not in self.assets
                self.assets[name] = data
                if self.after_upload:
                    self.after_upload(self)
                return {'name': name}
            return [{'id': index + 10, 'name': name, 'state': 'uploaded', 'size': len(value),
                     'digest': 'sha256:' + hashlib.sha256(value).hexdigest()}
                    for index, (name, value) in enumerate(self.assets.items())]
        if suffix.startswith('releases/assets/'):
            index = int(suffix.rsplit('/', 1)[1]) - 10
            return self.asset_bytes_override or list(self.assets.values())[index]
        if suffix == 'releases/7' and method == 'PATCH':
            assert data == {'draft': False, 'make_latest': 'true'}
            self.release.update(data)
            return copy.deepcopy(self.release)
        if suffix == 'releases/latest':
            return self.latest_override or copy.deepcopy(self.release)
        raise AssertionError((suffix, method))


@pytest.fixture
def publication(tmp_path):
    (tmp_path / 'CHANGELOG.md').write_text('# Cambios 0.29.0 (2026-10-10)\n\n- Actualización.\n\n# Cambios 0.28.0\nOld\n')
    return tmp_path, {'version': '0.29.0', 'commit': COMMIT}, {'source.zip': b'source bytes', 'source.json': b'{}', 'source.sha256': b'digest'}


def test_only_original_actions_event_is_accepted():
    assert release.event_commit(event(), environment()) == COMMIT


@pytest.mark.parametrize('field,value', [('GITHUB_ACTIONS', 'false'), ('GITHUB_REPOSITORY', 'fork/report-gen'),
                                        ('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_EVENT_NAME', 'workflow_dispatch')])
def test_wrong_environment_is_rejected(field, value):
    env = environment(); env[field] = value
    with pytest.raises(release.ReleaseError):
        release.event_commit(event(), env)


@pytest.mark.parametrize('field,value', [('event', 'pull_request'), ('event', 'workflow_dispatch'), ('head_branch', 'feature'),
                                       ('head_sha', 'main'), ('head_sha', COMMIT + ';ls'), ('conclusion', 'failure'),
                                       ('name', 'arbitrary workflow'), ('status', 'in_progress'), ('head_repository', {'full_name': 'fork/report-gen'})])
def test_untrusted_trigger_is_rejected(field, value):
    payload = event(); payload['workflow_run'][field] = value
    with pytest.raises(release.ReleaseError):
        release.event_commit(payload, environment())


def test_completion_action_is_required():
    payload = event(); payload['action'] = 'requested'
    with pytest.raises(release.ReleaseError):
        release.event_commit(payload, environment())


def test_six_exact_receipts_are_required():
    receipts = release.gate_receipts(API(), COMMIT)
    assert len(receipts) == 6 and {row['workflow'] for row in receipts} == set(release.WORKFLOWS.values())


def test_old_success_does_not_mask_in_progress_or_failed_rerun(publication):
    api = API()
    original = api.request(release.route('actions/workflows/tests.yml/runs'))['workflow_runs'][0]
    api.run_overrides['tests.yml'] = [original, {**original, 'run_attempt': 2, 'status': 'in_progress', 'conclusion': None}]
    assert release.publish(api, *publication[:1], COMMIT, *publication[1:])['status'] == 'waiting'
    assert not api.mutations


@pytest.mark.parametrize('filename', ['windows.yml', 'macos.yml', 'renderers.yml'])
@pytest.mark.parametrize('change', ['missing', 'foreign', 'other-sha', 'failed', 'wrong-path'])
def test_each_gate_identity_and_result_is_checked(change, filename):
    api = API()
    original = api.request(release.route(f'actions/workflows/{filename}/runs'))['workflow_runs'][0]
    overrides = {'foreign': {'head_repository': {'full_name': 'fork/report-gen'}}, 'other-sha': {'head_sha': OTHER},
                 'failed': {'conclusion': 'failure'}, 'wrong-path': {'path': '.github/workflows/arbitrary.yml'}}
    api.run_overrides[filename] = [] if change == 'missing' else [{**original, **overrides[change]}]
    if change == 'wrong-path':
        with pytest.raises(release.ReleaseError):
            release.gate_receipts(api, COMMIT)
    else:
        assert release.gate_receipts(api, COMMIT) is None
    assert not api.mutations


def test_stale_head_never_mutates(publication):
    api = API(); api.main = OTHER
    with pytest.raises(release.ReleaseError, match='current main'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert not api.mutations


def test_success_uploads_to_draft_verifies_bytes_then_marks_latest(publication):
    api = API()
    result = release.publish(api, publication[0], COMMIT, *publication[1:])
    assert result['status'] == 'published'
    assert api.tag == COMMIT and api.release['draft'] is False
    assert api.assets == publication[2]
    assert api.mutations[-1][1] == 'PATCH' and api.gate_reads == 3
    assert 'Actualización' in api.release['body'] and 'Old' not in api.release['body']
    before = len(api.mutations)
    assert release.publish(api, publication[0], COMMIT, *publication[1:])['status'] == 'already-published'
    assert len(api.mutations) == before


def test_existing_tag_is_never_rewritten(publication):
    api = API(); api.tag = OTHER
    with pytest.raises(release.ReleaseError, match='increment the version'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert not api.mutations


@pytest.mark.parametrize('change', ['foreign', 'other-commit', 'prerelease'])
def test_existing_release_is_never_repurposed(publication, change):
    api = API(); api.tag = COMMIT
    api.release = {'id': 7, 'draft': True, 'tag_name': 'v0.29.0', 'target_commitish': COMMIT,
                   'body': f'<!-- report-gen-release-v1:{COMMIT} -->'}
    if change == 'foreign': api.release['body'] = 'Manually maintained draft'
    if change == 'other-commit': api.release['target_commitish'] = OTHER
    if change == 'prerelease': api.release['prerelease'] = True
    with pytest.raises(release.ReleaseError):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert not api.mutations


def test_partial_owned_draft_resumes_without_replacing_assets(publication):
    api = API(); api.tag = COMMIT
    api.release = {'id': 7, 'draft': True, 'tag_name': 'v0.29.0', 'target_commitish': COMMIT,
                   'body': f'<!-- report-gen-release-v1:{COMMIT} -->', 'html_url': 'https://example.test/release'}
    api.assets['source.zip'] = publication[2]['source.zip']
    assert release.publish(api, publication[0], COMMIT, *publication[1:])['status'] == 'published'
    uploads = [call for call in api.mutations if call[1] == 'POST']
    assert len(uploads) == 2 and all('source.zip' not in call[0] for call in uploads)


def test_gate_or_head_change_during_upload_leaves_draft(publication):
    api = API(); api.after_upload = lambda current: setattr(current, 'main', OTHER)
    with pytest.raises(release.ReleaseError, match='current main'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert api.release['draft'] is True
    assert not any(call[1] == 'PATCH' for call in api.mutations)


def test_download_mismatch_leaves_draft(publication):
    api = API(); api.asset_bytes_override = b'corrupted'
    with pytest.raises(release.ReleaseError, match='bytes mismatch'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert api.release['draft'] is True


def test_unexpected_asset_is_not_deleted(publication):
    api = API(); api.assets['unrelated.zip'] = b'leave me'
    with pytest.raises(release.ReleaseError, match='Unexpected'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert api.assets == {'unrelated.zip': b'leave me'}
    assert not any(call[1] in {'DELETE', 'PATCH'} for call in api.mutations)


@pytest.mark.parametrize('version', ['../0.29.0', 'v0.29.0', '0.29.0-rc1', '00.29.0'])
def test_release_requires_literal_stable_version(publication, version):
    api = API(); metadata = {**publication[1], 'version': version}
    with pytest.raises(release.ReleaseError):
        release.publish(api, publication[0], COMMIT, metadata, publication[2])
    assert not api.mutations


def test_asset_redirect_does_not_send_token_to_storage_host():
    request = Request('https://api.github.com/repos/IphobiusS/report-gen/releases/assets/1', headers={'Authorization': 'Bearer secret'})
    redirected = release.SafeRedirect().redirect_request(request, None, 302, '', {}, 'https://release-assets.githubusercontent.com/object')
    assert not redirected.has_header('Authorization')
    with pytest.raises(release.ReleaseError):
        release.SafeRedirect().redirect_request(request, None, 302, '', {}, 'http://example.test/object')


def test_default_workspace_is_stable_and_override_explicit(tmp_path):
    assert installer.default_workspace({}, tmp_path) == tmp_path / '.local/share/report-gen'
    assert installer.default_workspace({'XDG_DATA_HOME': str(tmp_path / 'data')}) == tmp_path / 'data/report-gen'
    assert installer.default_workspace({'REPORT_GEN_WORKSPACE': str(tmp_path / 'private')}) == tmp_path / 'private'
    with pytest.raises(ValueError):
        installer.default_workspace({'XDG_DATA_HOME': 'relative'})


def test_installer_rejects_python_310_before_preparing_application(monkeypatch, capsys):
    monkeypatch.setattr(installer.sys, 'platform', 'linux')
    monkeypatch.setattr(installer.sys, 'version_info', (3, 10, 19))
    monkeypatch.setattr(installer, 'install', lambda *args: pytest.fail('Unsupported Python must not install'))
    with pytest.raises(SystemExit) as caught:
        installer.main([])
    assert caught.value.code == 2
    assert 'Python 3.11+' in capsys.readouterr().err


@pytest.mark.skipif(os.name != 'posix', reason='Linux shell launcher')
def test_real_launcher_preserves_spaces_quotes_shell_symbols_and_arguments(tmp_path):
    root = tmp_path / "application with '$() and spaces"
    (root / '.venv/bin').mkdir(parents=True)
    (root / '.venv/bin/python').symlink_to(sys.executable)
    (root / 'start.py').write_text('import json, sys\nprint(json.dumps(sys.argv[1:]))\n')
    workspace = tmp_path / "private 'data $(touch should-not-exist)"
    launcher = tmp_path / 'bin/report-gen'
    installer.replace_owned(launcher, installer.launcher_text(root, workspace, 'en'), installer.MARKER, 0o700)
    result = subprocess.check_output([str(launcher), '--port', '8123'], text=True)
    assert json.loads(result) == ['--workspace', str(workspace), '--lang', 'en', '--port', '8123']
    assert '--ready' not in result and not (tmp_path / 'should-not-exist').exists()


@pytest.mark.parametrize('kind', ['foreign', 'link', 'hardlink', 'parent-link'])
def test_installer_refuses_to_overwrite_unowned_or_linked_files(tmp_path, kind):
    target = tmp_path / 'report-gen'; original = tmp_path / 'original'
    original.write_text(installer.MARKER + 'original')
    if kind == 'foreign': target.write_text('keep user file')
    elif kind == 'link': target.symlink_to(original)
    elif kind == 'hardlink': os.link(original, target)
    else:
        (tmp_path / 'linked').symlink_to(tmp_path, target_is_directory=True)
        target = tmp_path / 'linked/new-launcher'
    with pytest.raises(ValueError):
        installer.replace_owned(target, installer.MARKER + 'new', installer.MARKER, 0o700)
    assert original.read_text() == installer.MARKER + 'original'


def test_install_failure_never_creates_launcher(tmp_path, monkeypatch):
    root = tmp_path / 'app'; root.mkdir()
    (root / 'requirements-audited.txt').touch(); (root / 'start.py').touch()
    def failure(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])
    monkeypatch.setattr(installer.subprocess, 'run', failure)
    launcher = tmp_path / 'launcher'
    with pytest.raises(subprocess.CalledProcessError):
        installer.install(root, tmp_path / 'workspace', launcher)
    assert not launcher.exists()


def test_optional_pdf_failure_is_reported_but_editor_launcher_works(tmp_path, monkeypatch):
    root = tmp_path / 'app'; root.mkdir()
    (root / 'requirements-audited.txt').touch(); (root / 'start.py').touch()
    report = {'editor_ready': True, 'pdf_ready': False, 'checks': []}
    monkeypatch.setattr(installer.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(report)))
    launcher = tmp_path / 'launcher'; desktop = tmp_path / 'applications/report-gen.desktop'
    result = installer.install(root, tmp_path / 'workspace', launcher, desktop)
    assert launcher.exists() and desktop.exists() and result['diagnostics']['pdf_ready'] is False
    assert 'Terminal=true' in desktop.read_text()


def test_desktop_exec_escapes_field_codes_and_shell_characters():
    text = installer.desktop_text(Path('/home/a $b/"quoted"/50%/report-gen'))
    assert '50%%' in text and '\\\\$b' in text and '\\\\"quoted\\\\"' in text
    with pytest.raises(ValueError):
        installer.desktop_text(Path('/home/a=b/report-gen'))


def archive_fixture(tmp_path, entry='start.py', data=b'print("ok")'):
    archive = tmp_path / 'source.zip'
    item = zipfile.ZipInfo('source/' + entry); item.create_system = 3; item.external_attr = 0o100644 << 16
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr(item, data)
    metadata = {'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'files': [{'path': entry, 'mode': '100644', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}
    manifest = archive.with_suffix('.json'); manifest.write_text(json.dumps(metadata))
    return archive, manifest


def test_archive_install_accepts_only_manifest_verified_bytes(tmp_path):
    archive, manifest = archive_fixture(tmp_path)
    root, _ = package.unpack(archive, manifest, tmp_path / 'unpack')
    assert (root / 'start.py').read_bytes() == b'print("ok")'
    metadata = json.loads(manifest.read_text()); metadata['files'][0]['sha256'] = '0' * 64
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='bytes differ'):
        package.unpack(archive, manifest, tmp_path / 'bad')


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'a\\escape'])
def test_archive_install_rejects_unsafe_paths(tmp_path, path):
    archive, manifest = archive_fixture(tmp_path, path)
    with pytest.raises(ValueError):
        package.unpack(archive, manifest, tmp_path / 'unpack')


def test_newer_release_is_never_downgraded(publication):
    api = API(); api.latest_override = {'id': 88, 'tag_name': 'v1.0.0'}
    with pytest.raises(release.ReleaseError, match='downgraded'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert not api.mutations


def test_duplicate_release_asset_is_rejected(publication):
    api = API(); api.assets['source.zip'] = publication[2]['source.zip']
    original = api.request
    def duplicated(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if '/assets?per_page=' in path:
            return result + result
        return result
    api.request = duplicated
    with pytest.raises(release.ReleaseError, match='duplicate'):
        release.verify_assets(api, 7, publication[2], complete=False)


def test_gate_rerun_after_upload_keeps_release_private(publication):
    api = API()
    def rerun(current):
        current.run_overrides['tests.yml'] = []
    api.after_upload = rerun
    with pytest.raises(release.ReleaseError, match='remains a draft'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert api.release['draft'] is True


def test_wrong_archive_hash_never_extracts(tmp_path):
    archive, manifest = archive_fixture(tmp_path)
    archive.write_bytes(archive.read_bytes() + b'corrupt')
    destination = tmp_path / 'not-created'
    with pytest.raises(ValueError, match='digest'):
        package.unpack(archive, manifest, destination)
    assert not destination.exists()


def test_newer_release_created_during_upload_never_loses_latest(publication):
    api = API()
    api.after_upload = lambda current: setattr(current, 'latest_override', {'id': 88, 'tag_name': 'v1.0.0'})
    with pytest.raises(release.ReleaseError, match='downgraded'):
        release.publish(api, publication[0], COMMIT, *publication[1:])
    assert api.release['draft'] is True
    assert not any(call[1] == 'PATCH' for call in api.mutations)
