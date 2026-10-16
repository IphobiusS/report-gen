#!/usr/bin/env python3
"""Query the real official updater without staging, installing, or sending case data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def inventory(root):
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-network', action='store_true',
                        help='Explicitly allow the production updater to query public GitHub metadata.')
    args = parser.parse_args()
    if not args.allow_network:
        parser.error('--allow-network is required for this real, opt-in network exercise')
    source, output = args.case.resolve(), args.output.resolve()
    if not (source / 'engagement.yaml').is_file():
        parser.error('--case must contain the frozen engagement.yaml')
    if output == source or source in output.parents or output in source.parents:
        parser.error('--output must not overlap the source case')
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    original = inventory(source)
    producer_paths = ('version.py', 'update_helper.py', 'workspace_paths.py',
                      'webapp/app.py', 'webapp/update_api.py', 'scripts/audit-horizonte-updater.py')
    producer = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in producer_paths}
    result = {
        'schema': 'report-gen-horizonte-updater/1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'Real Flask route and production HTTPS updater; no release or network mocks.',
        'request': {'method': 'POST', 'path': '/api/update/check', 'body': {'allow_network': True}},
        'public_repository': 'IphobiusS/report-gen', 'producer': producer,
        'source_files_before': original, 'status': 'incomplete', 'checks': [],
        'prepare_called': False, 'package_installed': False,
        'limits': ['This exercise never calls /api/update/prepare and never executes update instructions.',
                   'No workspace data, local paths or credentials are supplied to the public request.',
                   'A no-update response checks release metadata and version ordering; it does not verify release assets.'],
    }

    def check(name, passed):
        result['checks'].append({'name': name, 'passed': bool(passed)})

    previous = os.environ.get('REPORT_GEN_WORKSPACE')
    try:
        # Select an external disposable workspace before importing the real app.
        with tempfile.TemporaryDirectory(prefix='report-gen-horizonte-updater-') as directory:
            workspace = Path(directory)
            os.environ['REPORT_GEN_WORKSPACE'] = str(workspace)
            sys.dont_write_bytecode = True
            sys.path[:0] = [str(ROOT), str(ROOT / 'webapp')]
            import app as api
            from version import __version__

            result['version'] = __version__
            shutil.copytree(source, api.PROJECTS / 'horizonte-updater-readonly')
            client = api.app.test_client()
            session = client.get('/api/session').get_json()
            client.environ_base['HTTP_X_CSRF_TOKEN'] = session['csrf']
            before = inventory(workspace)
            response = client.post('/api/update/check', json={'allow_network': True})
            body = response.get_json(silent=True)
            result['http_status'] = response.status_code
            # A preview token is session-bound; it is deliberately excluded from the receipt.
            public_fields = ('available', 'current_version', 'latest_version', 'version',
                             'release_id', 'release_url', 'commit', 'sha256', 'size', 'error')
            result['response'] = {key: body[key] for key in public_fields if key in (body or {})}
            valid = (response.status_code == 200 and isinstance(body, dict)
                     and type(body.get('available')) is bool and body.get('current_version') == __version__)
            check('Official metadata query completed with the real running version', valid)
            if valid:
                latest = body.get('version') if body['available'] else body.get('latest_version')
                try:
                    ordering = tuple(map(int, latest.split('.'))) > tuple(map(int, __version__.split('.')))
                except (AttributeError, ValueError):
                    ordering = None
                check('Availability agrees with the returned release version', ordering is body['available'])
                result['prepare_not_run_reason'] = (
                    'Read-only scope: a newer official release was found but no preparation was requested.'
                    if body['available'] else 'No official release newer than the actual candidate is available.')
            else:
                result['prepare_not_run_reason'] = 'Official release query did not succeed; no plan was accepted.'
            check('Disposable workspace retains every exact file after the query', inventory(workspace) == before)
            result['workspace_files_checked'] = len(before)
    except Exception as exc:
        # Record only the type: exceptions may include machine-specific paths.
        result['exception_type'] = type(exc).__name__
        check('Real updater exercise completed without an unexpected exception', False)
    finally:
        if previous is None:
            os.environ.pop('REPORT_GEN_WORKSPACE', None)
        else:
            os.environ['REPORT_GEN_WORKSPACE'] = previous
        check('Frozen source case remains byte-identical', inventory(source) == original)
        check('Updater and runner sources remain byte-identical',
              all(sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in producer.items()))
        result['status'] = 'passed' if all(item['passed'] for item in result['checks']) else 'not_passed'
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: result.get(key) for key in ('status', 'version', 'http_status', 'response')}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
