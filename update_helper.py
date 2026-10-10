"""Explicit official-release verification and private staging; never execute it.

GitHub HTTPS plus the official release/tag and every asset digest establishes
provenance here. Checksums are integrity evidence, not independent signatures.
No credentials, authored data or local paths are sent to GitHub.
"""
from hashlib import sha256
from io import BytesIO
from http.client import HTTPException as TransportError
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import sys
import tempfile
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
import zipfile
import zlib

from error_messages import message
from workspace_paths import _no_links

REPO = 'IphobiusS/report-gen'
API = 'https://api.github.com/repos/' + REPO
WEB = 'https://github.com/' + REPO
MAX_PACKAGE = 128 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_FILES = 4000
MAX_MANIFEST = 2 * 1024 * 1024
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
HEX = re.compile(r'[a-f0-9]{64}')
COMMIT = re.compile(r'[a-f0-9]{40}')


def failure():
    return ValueError(message('La publicación no superó la verificación. No se ha instalado ni ejecutado nada.',
                             en='The release did not pass verification. Nothing was installed or executed.'))


def _url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in {
            'api.github.com', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise failure()
    return url


class _Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, maximum):
    """Bounded public request; only explicit check/prepare handlers call this."""
    request = Request(_url(url), headers={'Accept': 'application/vnd.github+json',
                      'User-Agent': 'report-gen-explicit-updater', 'X-GitHub-Api-Version': '2026-03-10'})
    started = time.monotonic()
    try:
        with build_opener(_Redirect()).open(request, timeout=12) as response:
            _url(response.url)
            if response.status != 200:
                raise failure()
            declared = response.headers.get('Content-Length')
            if declared and (not declared.isdigit() or int(declared) > maximum):
                raise failure()
            chunks, count = [], 0
            while block := response.read(min(65536, maximum + 1 - count)):
                chunks.append(block)
                count += len(block)
                if count > maximum or time.monotonic() - started > 60:
                    raise failure()
            return b''.join(chunks)
    except (OSError, ValueError, TransportError) as exc:
        raise ValueError(message('No se pudo comprobar GitHub. Revisa la conexión y vuelve a intentarlo; la instalación actual se conserva.',
                                 en='GitHub could not be checked. Check your connection and retry; the current installation is preserved.')) from exc


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise failure()
        value[key] = item
    return value


def _json(blob):
    try:
        result = json.loads(blob, object_pairs_hook=_unique)
        if not isinstance(result, dict):
            raise failure()
        return result
    except (UnicodeError, ValueError, RecursionError):
        raise failure() from None


def _digest(blob):
    return sha256(blob).hexdigest()


def _asset_blob(asset, maximum):
    blob = fetch(asset['browser_download_url'], maximum)
    if len(blob) != asset['size'] or 'sha256:' + _digest(blob) != asset['digest']:
        raise failure()
    return blob


def _path(name):
    """Portable, exact manifest paths: reject Windows aliases as well as ../."""
    if not isinstance(name, str) or not name or len(name) > 240 or '\\' in name or ':' in name:
        raise failure()
    parts = name.split('/')
    forbidden = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'out', '.report-gen-browser-id'}
    devices = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
    if (PurePosixPath(name).is_absolute() or any(not p or p in ('.', '..') or p.rstrip('. ') != p
        or any(ord(c) < 32 or ord(c) == 127 or c in '<>\"|?*' for c in p) or p.lower() in forbidden
        or p.split('.')[0].lower() in devices for p in parts)
        or (name.startswith('webapp/projects/') and name != 'webapp/projects/.gitkeep')
        or name.startswith('webapp/library/')):
        raise failure()
    return name


def _files(manifest):
    rows = manifest.get('files')
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FILES:
        raise failure()
    seen, files, total = set(), {}, 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'path', 'mode', 'size', 'sha256'}:
            raise failure()
        name = _path(row['path'])
        size = row['size']
        if (unicodedata.normalize('NFC', name).casefold() in seen or type(size) is not int or size < 0 or row['mode'] not in ('100644', '100755')
                or not isinstance(row['sha256'], str) or not HEX.fullmatch(row['sha256'])):
            raise failure()
        seen.add(unicodedata.normalize('NFC', name).casefold())
        total += size
        files[name] = row
    if total > MAX_EXPANDED or not {'start.py', 'engine.py', 'version.py', 'scripts/install.py', 'webapp/app.py'} <= files.keys():
        raise failure()
    for name in files:
        if any(str(parent).casefold() in seen for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise failure()
    return files


def inspect_release(current_version, release_id=None):
    if not VERSION.fullmatch(current_version):
        raise failure()
    suffix = '/latest' if release_id is None else '/' + str(release_id)
    if release_id is not None and (type(release_id) is not int or release_id <= 0):
        raise failure()
    release = _json(fetch(API + '/releases' + suffix, MAX_MANIFEST))
    tag = release.get('tag_name', '')
    version = tag[1:] if isinstance(tag, str) and tag.startswith('v') else ''
    if (not VERSION.fullmatch(version) or release.get('draft') is not False or release.get('prerelease') is not False
            or type(release.get('id')) is not int or release['id'] <= 0 or not release.get('published_at')
            or release.get('html_url') != WEB + '/releases/tag/' + tag):
        raise failure()
    if tuple(map(int, version.split('.'))) <= tuple(map(int, current_version.split('.'))):
        return {'available': False, 'current_version': current_version, 'latest_version': version}
    assets = release.get('assets')
    if not isinstance(assets, list) or len(assets) != 3:
        raise failure()
    by_suffix = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise failure()
        name = asset.get('name', '')
        if not isinstance(name, str):
            raise failure()
        match = re.fullmatch(r'report-gen-' + re.escape(version) + r'-([a-f0-9]{12})\.(zip|json|sha256)', name)
        if (not match or match[2] in by_suffix or asset.get('state') != 'uploaded'
                or type(asset.get('id')) is not int or asset['id'] <= 0 or type(asset.get('size')) is not int
                or not 0 < asset['size'] <= (MAX_PACKAGE if match[2] == 'zip' else MAX_MANIFEST)
                or not isinstance(asset.get('digest'), str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', asset['digest'])
                or asset.get('browser_download_url') != WEB + '/releases/download/' + tag + '/' + name):
            raise failure()
        by_suffix[match[2]] = {k: asset[k] for k in ('id', 'name', 'size', 'digest', 'browser_download_url')}
    if set(by_suffix) != {'zip', 'json', 'sha256'}:
        raise failure()
    manifest = _json(_asset_blob(by_suffix['json'], MAX_MANIFEST))
    commit = manifest.get('commit', '')
    if (manifest.get('schema') != 1 or manifest.get('version') != version or not isinstance(commit, str)
            or not COMMIT.fullmatch(commit) or not isinstance(manifest.get('tree'), str)
            or not COMMIT.fullmatch(manifest['tree']) or manifest.get('archive') != by_suffix['zip']['name']
            or manifest.get('sha256') != by_suffix['zip']['digest'][7:]
            or manifest.get('release_download') != by_suffix['zip']['browser_download_url']
            or manifest.get('canonical_download') != WEB + '/archive/' + commit + '.zip'
            or any(asset['name'] != f'report-gen-{version}-{commit[:12]}.{suffix}' for suffix, asset in by_suffix.items())):
        raise failure()
    _files(manifest)
    checksum = _asset_blob(by_suffix['sha256'], MAX_MANIFEST)
    if checksum != (manifest['sha256'] + '  ' + manifest['archive'] + '\n').encode('ascii'):
        raise failure()
    reference = _json(fetch(API + '/git/ref/tags/' + tag, 32768)).get('object')
    for _ in range(4):
        if not isinstance(reference, dict) or not isinstance(reference.get('sha'), str) or not COMMIT.fullmatch(reference['sha']):
            raise failure()
        if reference.get('type') == 'commit':
            break
        if reference.get('type') != 'tag':
            raise failure()
        reference = _json(fetch(API + '/git/tags/' + reference['sha'], 32768)).get('object')
    if not isinstance(reference, dict) or reference.get('type') != 'commit' or reference.get('sha') != commit:
        raise failure()
    plan = {'available': True, 'current_version': current_version, 'version': version, 'commit': commit,
            'release_id': release['id'], 'release_url': release['html_url'], 'assets': by_suffix,
            'sha256': manifest['sha256'], 'size': by_suffix['zip']['size']}
    return plan, manifest


def verified_archive(plan, manifest, payload):
    if len(payload) > MAX_PACKAGE or len(payload) != plan['size'] or _digest(payload) != plan['sha256']:
        raise failure()
    files = _files(manifest)
    prefix = manifest['archive'][:-4] + '/'
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) != len(files):
                raise failure()
            seen, result = set(), {}
            for item in entries:
                if not item.filename.startswith(prefix):
                    raise failure()
                name = _path(item.filename[len(prefix):])
                row = files.get(name)
                if (name in seen or row is None or item.is_dir() or item.flag_bits & 1
                        or stat.S_IFMT(item.external_attr >> 16) != stat.S_IFREG
                        or item.file_size != row['size'] or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or (item.external_attr >> 16) != int(row['mode'], 8)):
                    raise failure()
                seen.add(name)
                blob = archive.read(item)
                if _digest(blob) != row['sha256']:
                    raise failure()
                result[name] = blob
            # AST only: never import downloaded code to learn its version.
            import ast
            if len(result['version.py']) > 8192:
                raise failure()
            tree = ast.parse(result['version.py'])
            versions = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
            if versions != [plan['version']]:
                raise failure()
            return result
    except (zipfile.BadZipFile, RuntimeError, SyntaxError, ValueError, KeyError, RecursionError, zlib.error):
        raise failure() from None


def _write(path, blob, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0), mode)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(blob)
        stream.flush()
        os.fsync(stream.fileno())


def _command(words, windows=False):
    if windows:
        # PowerShell's single-quoted literals only escape the single quote.
        return '& ' + ' '.join("'" + str(word).replace("'", "''") + "'" for word in words)
    return shlex.join(str(word) for word in words)


def instructions(stage, current, workspace, external, lang, windows=None):
    windows = sys.platform == 'win32' if windows is None else windows
    package = stage / 'application'
    target_workspace = workspace if external else stage / 'workspace'
    commands = []
    if not external:
        commands.append(_command([sys.executable, current / 'launcher_upgrade.py', '--source', current,
                                  '--destination', package, '--workspace', target_workspace, '--lang', lang], windows))
    if sys.platform.startswith('linux') and not windows:
        commands.append(_command(['python3', package / 'scripts/install.py', '--workspace', target_workspace, '--lang', lang]))
        commands.append(_command([Path.home() / '.local/bin/report-gen']))
    else:
        commands.append(_command(['py' if windows else 'python3', package / 'start.py', '--ready', '--workspace', target_workspace, '--lang', lang], windows))
    rollback = [sys.executable, current / 'start.py', '--lang', lang]
    if external:
        rollback.extend(['--workspace', workspace])
    return {'commands': commands, 'rollback_command': _command(rollback, windows),
            'workspace': str(target_workspace), 'shell': 'PowerShell' if windows else 'sh', 'migration': not external}


def backup_identity(blob):
    """Ignore generated archive timestamps, retain every backed-up data digest."""
    try:
        with zipfile.ZipFile(BytesIO(blob)) as archive:
            manifest = _json(archive.read('manifest.json'))
            content = {}
            for name, digest in manifest['files'].items():
                if name.startswith('projects/'):
                    with zipfile.ZipFile(BytesIO(archive.read(name))) as nested:
                        content[name] = _json(nested.read('manifest.json'))['files']
                else:
                    content[name] = digest
            return _digest(json.dumps(content, sort_keys=True, separators=(',', ':')).encode())
    except (zipfile.BadZipFile, KeyError, AttributeError, TypeError, ValueError):
        raise failure() from None


def prepare(plan, manifest, payload, backup_factory, *, base, current, workspace, external, scope, lang='es'):
    """One private receipt per release/workspace/content snapshot; retries reuse it.

    Download verification finishes before backup work. The caller holds the
    workspace lock while backup_factory captures and validates the current disk.
    """
    files = verified_archive(plan, manifest, payload)
    base, current, workspace = (Path(value).absolute() for value in (base, current, workspace))
    _no_links(base)
    for protected in (current, workspace):
        if base == protected or protected in base.parents:
            raise failure()
    if any(ord(char) < 32 or ord(char) == 127 for path in (base, current, workspace) for char in str(path)):
        raise failure()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = backup_factory()
    fingerprint = backup_identity(backup)
    identity = _digest((scope + ':' + fingerprint).encode())[:20]
    final = base / ('update-' + plan['commit'][:12] + '-' + identity)
    for protected in (current, workspace):
        if final == protected or final in protected.parents or protected in final.parents:
            raise failure()
    _no_links(final)
    if final.exists():
        # Refuse changed staging files. Never overwrite an installed package.
        receipt_path = final / 'receipt.json'
        _no_links(receipt_path)
        if not receipt_path.is_file() or receipt_path.stat().st_nlink != 1 or receipt_path.stat().st_size > 32768:
            raise failure()
        receipt = _json(receipt_path.read_bytes())
        if receipt.get('sha256') != plan['sha256'] or receipt.get('workspace_scope') != scope:
            raise failure()
        for name, blob in files.items():
            path = final / 'application' / name
            _no_links(path)
            if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size != len(blob) or path.read_bytes() != blob:
                raise failure()
        backup_path = final / 'workspace-backup.zip'
        _no_links(backup_path)
        if (not backup_path.is_file() or backup_path.stat().st_nlink != 1 or backup_path.stat().st_size > MAX_EXPANDED
                or _digest(backup_path.read_bytes()) != receipt.get('backup_sha256')
                or backup_identity(backup_path.read_bytes()) != fingerprint):
            raise failure()
        expected = instructions(final, current, workspace, external, lang)
        # Rebuild command prose from trusted paths; do not trust a modified receipt.
        receipt.update(expected)
        return receipt
    temporary = Path(tempfile.mkdtemp(prefix='.preparing-', dir=base))
    try:
        for name, blob in files.items():
            _write(temporary / 'application' / name, blob)
        # Preserve executable permissions from the verified manifest, never ZIP defaults.
        for row in manifest['files']:
            if row['mode'] == '100755':
                (temporary / 'application' / row['path']).chmod(0o700)
        _write(temporary / 'workspace-backup.zip', backup)
        receipt = {'schema': 1, 'version': plan['version'], 'commit': plan['commit'], 'sha256': plan['sha256'],
                   'workspace_scope': scope, 'backup_sha256': _digest(backup), 'snapshot': fingerprint,
                   'prepared_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   'application': str(final / 'application'), 'backup': str(final / 'workspace-backup.zip'),
                   **instructions(final, current, workspace, external, lang)}
        _write(temporary / 'receipt.json', (json.dumps(receipt, indent=2) + '\n').encode())
        os.rename(temporary, final)
        return receipt
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
