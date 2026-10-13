#!/usr/bin/env python3
"""Publish the current main commit only after all required independent push gates.

No downloaded workflow artifact is executed. The package is rebuilt from Git
objects, uploaded to a draft, verified, and only then made public and latest.
Existing tags/assets/releases are never replaced or deleted.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = 'IphobiusS/report-gen'
WORKFLOWS = {
    'tests.yml': 'tests',
    'browser-acceptance.yml': 'Browser acceptance',
    'windows.yml': 'Windows compatibility',
    'macos.yml': 'macOS compatibility',
    'renderers.yml': 'Additional renderer acceptance',
    'source-package.yml': 'Reproducible source package',
}
SHA = re.compile(r'[0-9a-f]{40}')
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')


class ReleaseError(ValueError):
    pass


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != 'https':
            raise ReleaseError('Non-HTTPS asset redirect refused')
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if target.netloc != urlsplit(req.full_url).netloc:
            result.remove_header('Authorization')
        return result


class GitHub:
    def __init__(self, token):
        self.token = token
        self.opener = build_opener(SafeRedirect())

    def request(self, path, method='GET', data=None, *, binary=False, upload=False, missing=False):
        host = 'uploads.github.com' if upload else 'api.github.com'
        if not path.startswith(f'/repos/{REPOSITORY}/'):
            raise ReleaseError('Unexpected API repository')
        body = data if isinstance(data, bytes) else (json.dumps(data).encode() if data is not None else None)
        headers = {'Authorization': f'Bearer {self.token}', 'X-GitHub-Api-Version': '2026-03-10',
                   'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json',
                   'Content-Type': 'application/octet-stream' if upload else 'application/json',
                   'User-Agent': 'report-gen-release'}
        try:
            with self.opener.open(Request(f'https://{host}{path}', data=body, headers=headers, method=method), timeout=90) as response:
                raw = response.read()
                return raw if binary else json.loads(raw)
        except HTTPError as exc:
            if missing and exc.code == 404:
                return None
            raise ReleaseError(f'GitHub {method} failed with HTTP {exc.code}: {path}') from None


def route(path):
    return f'/repos/{REPOSITORY}/{path}'


def event_commit(event, environment):
    if environment.get('GITHUB_ACTIONS') != 'true' or environment.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise ReleaseError('Publication requires the original GitHub Actions repository')
    if environment.get('GITHUB_EVENT_NAME') != 'workflow_run':
        raise ReleaseError('Only a completed workflow_run can publish')
    run = event.get('workflow_run', {})
    if (event.get('action') != 'completed' or run.get('event') != 'push'
            or run.get('head_branch') != 'main' or run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('head_repository', {}).get('full_name') != REPOSITORY
            or run.get('name') not in WORKFLOWS.values()):
        raise ReleaseError('Untrusted or unsuccessful triggering run')
    commit = run.get('head_sha', '')
    if not SHA.fullmatch(commit):
        raise ReleaseError('A full commit SHA is required')
    return commit


def gate_receipts(api, commit):
    if api.request(route('git/ref/heads/main'))['object']['sha'] != commit:
        raise ReleaseError('The selected commit is no longer current main')
    receipts = []
    for filename, name in WORKFLOWS.items():
        query = urlencode({'branch': 'main', 'event': 'push', 'head_sha': commit, 'per_page': 100})
        payload = api.request(route(f'actions/workflows/{filename}/runs?{query}'))
        runs = payload.get('workflow_runs', [])
        # The newest run/attempt must pass; an older success cannot mask a rerun.
        runs = [run for run in runs if run.get('head_sha') == commit and run.get('event') == 'push'
                and run.get('head_branch') == 'main'
                and run.get('head_repository', {}).get('full_name') == REPOSITORY]
        if not runs:
            return None
        latest = max(runs, key=lambda run: (run['run_number'], run.get('run_attempt', 1), run['id']))
        if latest.get('name') != name or latest.get('path') != f'.github/workflows/{filename}':
            raise ReleaseError('Workflow identity does not match the required gate')
        if latest.get('status') != 'completed' or latest.get('conclusion') != 'success':
            return None
        receipts.append({'workflow': name, 'id': latest['id'], 'attempt': latest.get('run_attempt', 1),
                         'url': latest['html_url'], 'commit': commit})
    return receipts


def tag_commit(api, tag):
    ref = api.request(route(f'git/ref/tags/{tag}'), missing=True)
    if ref is None:
        return None
    obj = ref['object']
    for _ in range(5):
        if obj.get('type') == 'commit' and SHA.fullmatch(obj.get('sha', '')):
            return obj['sha']
        if obj.get('type') != 'tag' or not SHA.fullmatch(obj.get('sha', '')):
            break
        obj = api.request(route(f'git/tags/{obj["sha"]}'))['object']
    raise ReleaseError('Tag does not resolve to a commit')


def release_for_tag(api, tag):
    for page in range(1, 11):
        releases = api.request(route(f'releases?per_page=100&page={page}'))
        matches = [release for release in releases if release.get('tag_name') == tag]
        if len(matches) > 1:
            raise ReleaseError('Duplicate releases for the selected tag')
        if matches:
            return matches[0]
        if len(releases) < 100:
            return None
    raise ReleaseError('Release listing exceeded the safe page limit')


def verify_assets(api, release_id, expected, *, complete=True):
    assets = api.request(route(f'releases/{release_id}/assets?per_page=100'))
    seen = set()
    for asset in assets:
        name = asset['name']
        if name in seen or name not in expected or asset.get('state') != 'uploaded':
            raise ReleaseError('Unexpected, duplicate or incomplete release asset')
        seen.add(name)
        data = expected[name]
        if asset.get('size') != len(data):
            raise ReleaseError(f'Release asset size mismatch: {name}')
        digest = hashlib.sha256(data).hexdigest()
        if asset.get('digest') and asset['digest'] != f'sha256:{digest}':
            raise ReleaseError(f'Release asset digest mismatch: {name}')
        downloaded = api.request(route(f'releases/assets/{int(asset["id"])}'), binary=True)
        if hashlib.sha256(downloaded).hexdigest() != digest:
            raise ReleaseError(f'Release asset bytes mismatch: {name}')
    if complete and seen != set(expected):
        raise ReleaseError('Release assets are incomplete')
    return seen


def release_body(repo, metadata, receipts):
    version = metadata['version']
    changes = (repo / 'CHANGELOG.md').read_text(encoding='utf-8')
    match = re.search(rf'^# Cambios {re.escape(version)}(?:\s|\().*?\n(.*?)(?=^# |\Z)', changes, re.M | re.S)
    if not match:
        raise ReleaseError('The literal package version has no changelog entry')
    checks = '\n'.join(f'- [{row["workflow"]}]({row["url"]})' for row in receipts)
    extension = ('El `.oxt` es un complemento opcional de LibreOffice para el ajuste de literales técnicos. '
                 'Se instala por separado desde Herramientas → Extensiones → Añadir y requiere el proveedor Python de LibreOffice. '
                 'Consulta la guía para su alcance; sin el complemento algunas URL pueden saltar antes de llenar la línea.\n\n'
                 if metadata.get('libreoffice_extension') else '')
    return (f'<!-- report-gen-release-v1:{metadata["commit"]} -->\n'
            f'{match.group(1).strip()}\n\n'
            f'## Descarga verificada\n\nCommit: `{metadata["commit"]}`\n\n'
            'El ZIP adjunto contiene las fuentes y el instalador local. Requiere Python 3.11+ '
            '(validado con 3.12) y conexión para instalar dependencias; no es un ejecutable autónomo. '
            'En Linux/Kali: descomprime, entra en la carpeta y ejecuta '
            '`python3 scripts/install.py --desktop`. El instalador no ejecuta sudo ni instala paquetes del sistema. '
            'Los archivos `.sha256` y `.json` permiten comprobar el ZIP y cada archivo del árbol.\n\n'
            f'{extension}'
            f'## Validación de este commit\n\n{checks}\n\n'
            'Las pruebas de Windows no certifican Microsoft Word de escritorio ni sustituyen sesiones humanas.\n')


def guard_latest(api, version):
    latest = api.request(route('releases/latest'), missing=True)
    if latest is not None:
        previous = latest.get('tag_name', '').removeprefix('v')
        if VERSION.fullmatch(previous) and tuple(map(int, previous.split('.'))) > tuple(map(int, version.split('.'))):
            raise ReleaseError('A newer stable release already exists; latest will not be downgraded')


def publish(api, repo, commit, metadata, expected):
    if metadata.get('commit') != commit or not VERSION.fullmatch(metadata.get('version', '')):
        raise ReleaseError('Package commit/version is invalid')
    receipts = gate_receipts(api, commit)
    if receipts is None:
        return {'status': 'waiting', 'commit': commit}
    tag = f'v{metadata["version"]}'
    guard_latest(api, metadata['version'])
    target = tag_commit(api, tag)
    if target is not None and target != commit:
        raise ReleaseError('Existing version tag belongs to another commit; increment the version')
    release = release_for_tag(api, tag)
    marker = f'<!-- report-gen-release-v1:{commit} -->'
    if release is not None:
        if marker not in (release.get('body') or '') or release.get('target_commitish') != commit:
            raise ReleaseError('Existing release is not owned by this exact publication')
        if release.get('prerelease'):
            raise ReleaseError('An existing prerelease will not be repurposed')
        if not release.get('draft'):
            if target != commit:
                raise ReleaseError('Published release tag is missing')
            verify_assets(api, release['id'], expected)
            return {'status': 'already-published', 'url': release['html_url'], 'commit': commit}
    body = release_body(repo, metadata, receipts)
    # Recheck directly before the first mutation. A new push blocks stale jobs.
    if gate_receipts(api, commit) is None:
        return {'status': 'waiting', 'commit': commit}
    if target is None:
        api.request(route('git/refs'), 'POST', {'ref': f'refs/tags/{tag}', 'sha': commit})
    if tag_commit(api, tag) != commit:
        raise ReleaseError('The new tag did not retain the checked commit')
    if release is None:
        release = api.request(route('releases'), 'POST', {'tag_name': tag, 'target_commitish': commit,
            'name': f'report-gen {metadata["version"]}', 'body': body, 'draft': True,
            'prerelease': False, 'make_latest': 'false', 'generate_release_notes': False})
    present = verify_assets(api, release['id'], expected, complete=False)
    for name, data in sorted(expected.items()):
        if name not in present:
            api.request(route(f'releases/{release["id"]}/assets?{urlencode({"name": name})}'),
                        'POST', data, upload=True)
    verify_assets(api, release['id'], expected)
    if gate_receipts(api, commit) is None:
        raise ReleaseError('A gate changed after upload; release remains a draft')
    if tag_commit(api, tag) != commit:
        raise ReleaseError('Tag changed after verification; release remains a draft')
    guard_latest(api, metadata['version'])
    published = api.request(route(f'releases/{release["id"]}'), 'PATCH', {'draft': False, 'make_latest': 'true'})
    if published.get('draft') or published.get('tag_name') != tag:
        raise ReleaseError('GitHub did not confirm publication')
    verify_assets(api, release['id'], expected)
    latest = api.request(route('releases/latest'))
    if latest['id'] != published['id']:
        raise ReleaseError('Published release is not the latest release')
    return {'status': 'published', 'url': published['html_url'], 'commit': commit, 'gates': receipts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        commit = event_commit(json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text()), os.environ)
        api = GitHub(os.environ['GITHUB_TOKEN'])
        receipts = gate_receipts(api, commit)
        if receipts is None:
            print(json.dumps({'status': 'waiting', 'commit': commit}))
            return 0
        if args.check_only:
            print(json.dumps({'status': 'ready', 'commit': commit, 'gates': receipts}))
            return 0
        repo = Path(__file__).resolve().parents[1]
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() != commit:
            raise ReleaseError('Checkout is not the checked triggering commit')
        spec = importlib.util.spec_from_file_location('release_builder', repo / 'scripts/build-release.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='report-gen-release-') as directory:
            output = Path(directory)
            metadata = builder.build_release(repo, commit, output)
            expected = {path.name: path.read_bytes() for path in output.iterdir()}
            result = publish(api, repo, commit, metadata, expected)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Release blocked: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
