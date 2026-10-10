#!/usr/bin/env python3
"""Verify and install a release ZIP into an isolated directory, then use it.

This is CI acceptance, not a user's updater: all data is synthetic and the
installation is removed with its temporary directory after the check.
"""
import argparse
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path, PurePosixPath
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener
import zipfile


def unpack(archive, manifest, destination):
    metadata = json.loads(manifest.read_text(encoding='utf-8'))
    if archive.name != metadata['archive'] or hashlib.sha256(archive.read_bytes()).hexdigest() != metadata['sha256']:
        raise ValueError('Archive digest or name differs from the manifest')
    expected = {item['path']: item for item in metadata['files']}
    if len(expected) != len(metadata['files']):
        raise ValueError('Duplicate manifest path')
    stem = archive.stem
    with zipfile.ZipFile(archive) as package:
        seen = set()
        for item in package.infolist():
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                    or len(path.parts) < 2 or path.parts[0] != stem):
                raise ValueError('Unsafe package entry')
            relative = path.relative_to(stem).as_posix()
            if relative not in expected or relative in seen:
                raise ValueError('Unexpected or duplicate archive entry')
            seen.add(relative)
            row = expected[relative]
            mode = item.external_attr >> 16
            if (stat.S_IFMT(mode) != stat.S_IFREG or row['mode'] not in {'100644', '100755'}
                    or mode != int(row['mode'], 8)):
                raise ValueError('Only regular tracked files can be installed')
            data = package.read(item)
            if len(data) != row['size'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Packaged source bytes differ from the manifest')
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(int(row['mode'], 8) & 0o777)
        if seen != set(expected):
            raise ValueError('Packaged source paths differ from the manifest')
    return destination / stem, metadata


def verify(archive, output):
    with tempfile.TemporaryDirectory(prefix='report-gen clean install ') as directory:
        temporary = Path(directory)
        root, metadata = unpack(archive, archive.with_suffix('.json'), temporary / 'application')
        workspace = temporary / 'private workspace'
        launcher = temporary / 'launchers/report-gen'
        if (root / '.venv').exists():
            raise ValueError('The release unexpectedly includes an installed environment')
        subprocess.run([sys.executable, str(root / 'scripts/install.py'), '--workspace', str(workspace),
                        '--launcher', str(launcher), '--lang', 'en'], check=True, cwd=root)
        python = root / '.venv/bin/python'
        diagnosis = json.loads(subprocess.check_output([str(python), str(root / 'diagnostics.py'), '--lang', 'en'],
                                                       text=True, cwd=root))
        if not diagnosis['editor_ready'] or not diagnosis['pdf_ready']:
            raise ValueError('CI installation requires a working editor and PDF engine')
        exports = {}
        for fmt in ('pdf', 'docx', 'md', 'html'):
            target = temporary / ('synthetic.zip' if fmt == 'md' else f'synthetic.{fmt}')
            subprocess.run([str(python), str(root / 'export.py'), str(root / 'examples/design-sample/engagement.yaml'),
                            '--format', fmt, '--out', str(target)], check=True, cwd=root)
            if not target.is_file() or target.stat().st_size < 100:
                raise ValueError(f'Installed {fmt} export did not produce a document')
            data = target.read_bytes()
            if (fmt == 'pdf' and not data.startswith(b'%PDF-')) or (fmt in {'docx', 'md'} and not zipfile.is_zipfile(target)):
                raise ValueError(f'Installed {fmt} export has an invalid container')
            if fmt in {'docx', 'md'}:
                with zipfile.ZipFile(target) as container:
                    member = 'word/document.xml' if fmt == 'docx' else 'report.md'
                    if len(container.read(member)) < 100:
                        raise ValueError(f'Installed {fmt} export is missing its document')
            if fmt == 'html' and b'<html' not in data.lower():
                raise ValueError('Installed HTML export is missing its document')
            exports[fmt] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        with (temporary / 'server.log').open('w+') as log:
            process = subprocess.Popen([str(launcher), '--port', str(port)], stdout=log, stderr=subprocess.STDOUT, cwd=temporary)
            try:
                opener = build_opener(HTTPCookieProcessor(CookieJar()))
                base = f'http://127.0.0.1:{port}'
                deadline = time.monotonic() + 30
                while True:
                    try:
                        with opener.open(base + '/api/session', timeout=2) as response:
                            session = json.load(response)
                        break
                    except (URLError, TimeoutError):
                        if process.poll() is not None or time.monotonic() > deadline:
                            log.seek(0)
                            raise ValueError('Installed launcher did not start: ' + log.read()[-3000:])
                        time.sleep(.2)
                if session['version'] != metadata['version']:
                    raise ValueError('Installed server version differs from the package')
                request = Request(base + '/api/projects', data=json.dumps({'title': 'Clean installation acceptance',
                    'slug': 'clean-install'}).encode(), headers={'Content-Type': 'application/json',
                    'Origin': base, 'X-CSRF-Token': session['csrf']}, method='POST')
                with opener.open(request, timeout=10) as response:
                    created = json.load(response)
                if created['slug'] != 'clean-install' or not (workspace / 'projects/clean-install/engagement.yaml').is_file():
                    raise ValueError('Installed editor did not save to its external workspace')
                if any(path.name != '.gitkeep' for path in (root / 'webapp/projects').iterdir()):
                    raise ValueError('User data leaked into the application folder')
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        result = {'schema': 1, 'status': 'passed', 'commit': metadata['commit'], 'version': metadata['version'],
                  'archive_sha256': metadata['sha256'], 'source_files': len(metadata['files']),
                  'clean_environment': True, 'server_from_launcher': True, 'external_workspace_save': True,
                  'diagnostics': diagnosis, 'exports': exports}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2))
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('out/installed-package.json'))
    args = parser.parse_args(argv)
    try:
        verify(args.archive.resolve(), args.output.resolve())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Clean package acceptance failed: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
