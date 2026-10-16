#!/usr/bin/env python3
"""Read one exact successful Actions artifact and split its ZIP bytes unchanged.
No source repository writes, report generation, extraction or release operations.
Never log an authorization token, a signed redirect URL or an HTTP error body.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import zipfile

REPOSITORY = 'IphobiusS/report-gen'
SOURCE_RUN_ID = 38961878169
SOURCE_REVISION = '981a29c08ce3295b9ebc9ea3b0516b3f4c488d89'
SOURCE_WORKFLOW = '.github/workflows/r16-acceptance.yml'
HELPER_BRANCH = 'audit/atlas-evidence-0400-c5'
ARTIFACT_NAME = 'atlas-review-' + SOURCE_REVISION
API_ROOT = 'https://api.github.com'
PART_COUNT = 3
PART_LIMIT = 350 * 1024 * 1024
MAX_MEMBERS = 100_000
MAX_EXPANDED_BYTES = 8 * 1024**3
API_JSON_LIMIT = 8 * 1024 * 1024
CHUNK = 1024 * 1024
DEADLINE_SECONDS = 20 * 60


class BridgeError(Exception):
    """Only controlled, non-sensitive error codes are exposed by main()."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


# Explicitly ignore proxy environment settings: the token goes only to GitHub.
OPENER = build_opener(ProxyHandler({}), NoRedirect())
START = time.monotonic()


def require(ok: bool, code: str) -> None:
    if not ok:
        raise BridgeError(code)


def budget() -> None:
    require(time.monotonic() - START < DEADLINE_SECONDS, 'overall_deadline_exceeded')


def allowed_download_url(url: str) -> None:
    u = urlsplit(url)
    try:
        port = u.port
    except ValueError:
        raise BridgeError('invalid_download_port') from None
    host = (u.hostname or '').lower()
    suffixes = ('.blob.core.windows.net', '.githubusercontent.com', '.s3.amazonaws.com')
    allowed_host = host in ('api.github.com', 'github.com', 's3.amazonaws.com') or host.endswith(suffixes)
    allowed_host = allowed_host or bool(re.fullmatch(r'[a-z0-9.-]+\.s3[.-][a-z0-9-]+\.amazonaws\.com', host))
    require(u.scheme == 'https' and port in (None, 443) and not u.username and not u.password and not u.fragment and allowed_host, 'unapproved_download_redirect')


def open_once(url: str, *, token: str | None = None):
    budget()
    allowed_download_url(url)
    headers = {'User-Agent': 'report-gen-atlas-byte-bridge', 'Accept-Encoding': 'identity'}
    if token is not None:
        # No caller can attach the token to an object-storage or redirect host.
        require(urlsplit(url).netloc == 'api.github.com' and url.startswith(API_ROOT + '/repos/' + REPOSITORY + '/actions/'), 'authorization_destination_rejected')
        headers.update({'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
    try:
        return OPENER.open(Request(url, headers=headers), timeout=60)
    except HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return exc
        code = exc.code
        exc.close()
        raise BridgeError('http_status_' + str(code)) from None
    except (URLError, TimeoutError):
        raise BridgeError('network_request_failed') from None


def api_json(path: str, token: str):
    require(path.startswith('/repos/' + REPOSITORY + '/actions/'), 'unexpected_api_path')
    with open_once(API_ROOT + path, token=token) as response:
        require(response.status == 200, 'unexpected_api_redirect_or_status')
        raw = response.read(API_JSON_LIMIT + 1)
        require(len(raw) <= API_JSON_LIMIT, 'api_response_too_large')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise BridgeError('invalid_api_json') from None


def source_run(token: str) -> dict:
    run = api_json(f'/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}', token)
    require(run.get('id') == SOURCE_RUN_ID and run.get('status') == 'completed' and run.get('conclusion') == 'success', 'source_run_not_successful')
    require(run.get('event') == 'push' and run.get('head_branch') == 'main' and run.get('head_sha') == SOURCE_REVISION, 'source_run_identity_mismatch')
    require(run.get('path') == SOURCE_WORKFLOW and run.get('repository', {}).get('full_name') == REPOSITORY and run.get('head_repository', {}).get('full_name') == REPOSITORY, 'source_run_repository_or_workflow_mismatch')
    return run


def artifact_identity(artifact: dict) -> tuple[int, str]:
    require(type(artifact.get('id')) is int and artifact['id'] > 0 and artifact.get('name') == ARTIFACT_NAME and artifact.get('expired') is False, 'source_artifact_identity_mismatch')
    origin = artifact.get('workflow_run', {})
    require(origin.get('id') == SOURCE_RUN_ID and origin.get('head_sha') == SOURCE_REVISION and origin.get('head_branch') == 'main', 'source_artifact_run_mismatch')
    size = artifact.get('size_in_bytes')
    require(type(size) is int and PART_COUNT <= size <= PART_COUNT * PART_LIMIT, 'source_artifact_size_outside_three_part_budget')
    digest = artifact.get('digest', '')
    require(isinstance(digest, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', digest) is not None, 'source_artifact_missing_sha256')
    return size, digest.removeprefix('sha256:')


def find_artifact(token: str) -> dict:
    matches = []
    for page in range(1, 101):
        data = api_json(f'/repos/{REPOSITORY}/actions/runs/{SOURCE_RUN_ID}/artifacts?per_page=100&page={page}', token)
        rows = data.get('artifacts')
        require(isinstance(rows, list), 'invalid_artifact_listing')
        matches.extend(a for a in rows if a.get('name') == ARTIFACT_NAME)
        if len(rows) < 100:
            break
    else:
        raise BridgeError('artifact_listing_limit_exceeded')
    require(len(matches) == 1, 'expected_exactly_one_named_artifact')
    artifact_identity(matches[0])
    return matches[0]


def download_zip(artifact: dict, token: str, destination: Path) -> tuple[int, str]:
    expected_size, expected_digest = artifact_identity(artifact)
    # Ignore archive_download_url from JSON; construct the fixed GitHub endpoint.
    url = f'{API_ROOT}/repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}/zip'
    for hop in range(6):
        # Authorization is sent once only. EVERY redirect, including same-host,
        # loses Authorization. The signed object-storage URL is never logged.
        with open_once(url, token=token if hop == 0 else None) as response:
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get('Location')
                require(bool(location), 'redirect_missing_location')
                url = urljoin(url, location)
                allowed_download_url(url)
                continue
            require(response.status == 200, 'archive_http_status_invalid')
            length = response.headers.get('Content-Length')
            require(length is None or (length.isdigit() and int(length) == expected_size), 'archive_content_length_mismatch')
            h = hashlib.sha256()
            size = 0
            with destination.open('xb') as target:
                while block := response.read(CHUNK):
                    budget()
                    size += len(block)
                    require(size <= expected_size, 'archive_exceeds_expected_size')
                    target.write(block)
                    h.update(block)
            require(size == expected_size and h.hexdigest() == expected_digest, 'archive_size_or_sha256_mismatch')
            return size, h.hexdigest()
    raise BridgeError('archive_redirect_limit_exceeded')


def validate_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(0 < len(entries) <= MAX_MEMBERS, 'zip_member_count_invalid')
        require(len({e.filename for e in entries}) == len(entries), 'zip_duplicate_member')
        expanded = sum(e.file_size for e in entries)
        require(0 < expanded <= MAX_EXPANDED_BYTES, 'zip_expanded_size_limit')
        for entry in entries:
            budget()
            name = entry.filename
            require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts and '\\' not in name and '\x00' not in name, 'zip_unsafe_member_path')
            require(not stat.S_ISLNK(entry.external_attr >> 16), 'zip_symlink_rejected')
            require(not (entry.flag_bits & 1), 'zip_encrypted_container_rejected')
            # Full bounded streaming read verifies every member's CRC without
            # extracting anything or executing files from the source artifact.
            with archive.open(entry) as stream:
                while stream.read(CHUNK):
                    budget()
        return {'crc_verified': True, 'safe_paths_verified': True, 'members': len(entries), 'expanded_bytes': expanded}


def split_bytes(original: Path, output: Path, size: int, original_digest: str) -> list[dict]:
    part_size = math.ceil(size / PART_COUNT)
    require(part_size <= PART_LIMIT, 'part_size_limit')
    parts = []
    offset = 0
    with original.open('rb') as source:
        for index in range(1, PART_COUNT + 1):
            name = f'atlas-review.zip.part{index:02d}'
            h = hashlib.sha256()
            actual = 0
            with (output / name).open('xb') as target:
                while actual < part_size:
                    budget()
                    block = source.read(min(CHUNK, part_size - actual))
                    if not block:
                        break
                    target.write(block)
                    h.update(block)
                    actual += len(block)
            require(0 < actual <= PART_LIMIT, 'empty_or_oversize_part')
            parts.append({'index': index, 'file': name, 'offset': offset, 'bytes': actual, 'sha256': h.hexdigest()})
            offset += actual
        require(source.read(1) == b'' and offset == size, 'split_length_mismatch')
    reconstructed = hashlib.sha256()
    for part in parts:
        with (output / part['file']).open('rb') as source:
            while block := source.read(CHUNK):
                budget()
                reconstructed.update(block)
    require(reconstructed.hexdigest() == original_digest, 'split_reassembly_digest_mismatch')
    return parts


def execute(output: Path) -> dict:
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY and os.environ.get('GITHUB_REF') == 'refs/heads/' + HELPER_BRANCH, 'bridge_repository_or_branch_mismatch')
    helper_revision = os.environ.get('GITHUB_SHA', '')
    require(re.fullmatch(r'[0-9a-f]{40}', helper_revision) is not None, 'bridge_revision_missing')
    token = os.environ.get('GITHUB_TOKEN')
    require(bool(token), 'github_token_missing')
    run = source_run(token)
    artifact = find_artifact(token)
    with tempfile.TemporaryDirectory(prefix='atlas-zip-verified-', dir=output.parent) as temporary:
        original = Path(temporary) / 'original.zip'
        size, digest = download_zip(artifact, token, original)
        zip_checks = validate_zip(original)
        # Recheck provenance after the transfer; a rerun cannot be approved while
        # it is still in progress and the artifact identity must remain exact.
        final_run = source_run(token)
        require(final_run.get('run_attempt') == run.get('run_attempt'), 'source_run_attempt_changed')
        final_artifact = api_json(f'/repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}', token)
        require(artifact_identity(final_artifact) == (size, digest), 'source_artifact_changed')
        parts = split_bytes(original, output, size, digest)
    manifest = {
        'schema': 'report-gen-ci-artifact-byte-parts/1',
        'status': 'verified_byte_exact_parts',
        'source': {'repository': REPOSITORY, 'run_id': SOURCE_RUN_ID, 'run_attempt': run['run_attempt'], 'head_branch': 'main', 'head_sha': SOURCE_REVISION, 'event': 'push', 'workflow_path': SOURCE_WORKFLOW, 'status': 'completed', 'conclusion': 'success', 'artifact_id': artifact['id'], 'artifact_name': ARTIFACT_NAME, 'artifact_bytes': size, 'artifact_sha256': digest},
        'zip_validation': zip_checks,
        'transport': {'part_count': PART_COUNT, 'maximum_part_bytes': PART_LIMIT, 'operation': 'Split original ZIP bytes; concatenate parts in ascending index to reconstruct. No recompression or member editing.', 'reassembled_sha256_verified': True},
        'parts': parts,
        'bridge': {'repository': REPOSITORY, 'branch': HELPER_BRANCH, 'revision': helper_revision, 'run_id': os.environ.get('GITHUB_RUN_ID'), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'permissions': ['contents:read', 'actions:read']},
        'limits': ['Transport verification only; original acceptance receipts are reviewed separately.', 'No report generation, source modification, archive extraction, release, or write operation against the source run was performed.'],
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    created = False
    try:
        require(not output.exists(), 'output_directory_already_exists')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        created = True
        manifest = execute(output)
        print(json.dumps({'status': manifest['status'], 'source_run_id': SOURCE_RUN_ID, 'source_revision': SOURCE_REVISION, 'artifact_id': manifest['source']['artifact_id'], 'archive_bytes': manifest['source']['artifact_bytes'], 'archive_sha256': manifest['source']['artifact_sha256'], 'parts': manifest['parts']}))
        return 0
    except BridgeError as exc:
        print('Artifact bridge rejected: ' + str(exc), file=sys.stderr)
    except Exception as exc:
        # Exception messages can embed signed request URLs. Expose class only.
        print('Artifact bridge failed: ' + type(exc).__name__, file=sys.stderr)
    finally:
        if created and not (output / 'manifest.json').is_file():
            shutil.rmtree(output)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
