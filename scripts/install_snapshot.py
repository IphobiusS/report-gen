#!/usr/bin/env python3
"""Private data operations executed only in the selected, prepared Python environment."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workspace_paths import _no_links  # noqa: E402
from error_messages import language_scope  # noqa: E402
from languages import language_argument  # noqa: E402


def write_private(path, payload):
    import os
    _no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())


def locations(workspace):
    workspace = Path(workspace)
    _no_links(workspace)
    return workspace / 'projects', workspace / 'library/findings.json', workspace / 'library/designs.json'


def snapshot(workspace, directory):
    import workspace_backup
    from launcher_upgrade import _pending
    _pending(Path(workspace), external=True)
    payload = workspace_backup.export_workspace(*locations(workspace))
    # Exercise a real restoration before publishing the recovery receipt.
    with tempfile.TemporaryDirectory(prefix='report-gen-install-check-') as temporary:
        counts = workspace_backup.restore_workspace(payload, *locations(Path(temporary)))
    target = Path(directory) / ('workspace-' + uuid.uuid4().hex + '.zip')
    write_private(target, payload)
    digest = sha256(payload).hexdigest()
    if sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError('Saved backup differs from the verified snapshot.')
    return {'backup': str(target), 'backup_sha256': digest,
            'projects': counts['projects'], 'findings': counts['findings'], 'designs': counts['designs']}


def restore(archive, digest, destination):
    import workspace_backup
    archive, destination = Path(archive), Path(destination)
    _no_links(archive); _no_links(destination)
    if not archive.is_file() or archive.stat().st_nlink != 1 or archive.stat().st_size > workspace_backup.MAX_ARCHIVE:
        raise ValueError('Invalid recovery backup.')
    payload = archive.read_bytes()
    if sha256(payload).hexdigest() != digest:
        raise ValueError('Recovery backup checksum differs.')
    if destination.exists():
        raise ValueError('Recovery requires a new directory; current projects are never overwritten.')
    destination.mkdir(mode=0o700, parents=True)
    result = workspace_backup.restore_workspace(payload, *locations(destination))
    return dict(result, workspace=str(destination))


def check_update(application, workspace, directory, lang):
    import ast
    import update_helper
    from workspace_access import exclusive_paths
    application = Path(application)
    tree = ast.parse((application / 'version.py').read_text(encoding='utf-8'))
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    if len(values) != 1:
        raise ValueError('Invalid installed version.')
    result = update_helper.inspect_release(values[0])
    if isinstance(result, dict):
        return result
    plan, manifest = result
    payload = update_helper.fetch(plan['assets']['zip']['browser_download_url'], update_helper.MAX_PACKAGE)
    import workspace_backup
    from launcher_upgrade import _pending
    with exclusive_paths(application, workspace):
        _pending(Path(workspace), external=True)
        receipt = update_helper.prepare(plan, manifest, payload,
            lambda: workspace_backup.export_workspace(*locations(workspace)), base=directory,
            current=application, workspace=Path(workspace), external=True,
            scope=sha256(str(Path(workspace).resolve()).encode()).hexdigest(), lang=lang)
    return dict(receipt, available=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'restore', 'update'])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--application', type=Path, default=ROOT)
    parser.add_argument('--digest')
    parser.add_argument('--lang', type=language_argument, default='es')
    args = parser.parse_args(argv)
    with language_scope(args.lang):
        if args.action == 'snapshot':
            if args.directory is None:
                parser.error('--directory is required')
            result = snapshot(args.workspace, args.directory)
        elif args.action == 'restore':
            if args.archive is None or args.digest is None:
                parser.error('--archive and --digest are required')
            result = restore(args.archive, args.digest, args.workspace)
        else:
            if args.directory is None:
                parser.error('--directory is required')
            result = check_update(args.application, args.workspace, args.directory, args.lang)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
