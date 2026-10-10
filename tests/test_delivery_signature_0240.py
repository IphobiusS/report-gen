"""Exact-byte signatures and bounded hostile delivery/key inputs, using real Ed25519."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import base64
import builtins
import json
import os
import stat
import struct
import subprocess
import sys
import zipfile
from types import SimpleNamespace
from uuid import uuid4

import pytest

import delivery_signature as signing
from error_messages import language_scope

ROOT = Path(__file__).resolve().parents[1]


def archive(path, files=None, *, changes=None, extra=(), compression=zipfile.ZIP_DEFLATED):
    files = {'informe.html': b'<html><main>synthetic report</main></html>'} if files is None else files
    manifest = {'format': 'report-gen-delivery', 'version': 1, 'tool_version': '0.24.0',
                'label': 'Synthetic integrity fixture', 'created': '2026-10-09T00:00:00+00:00',
                'source_revision': 'a' * 64, 'warnings': [],
                'files': {name: {'bytes': len(blob), 'sha256': sha256(blob).hexdigest(), 'checks': {}}
                          for name, blob in files.items()}}
    if changes:
        changes(manifest)
    with zipfile.ZipFile(path, 'w', compression) as package:
        for name, blob in files.items():
            package.writestr(name, blob)
        package.writestr('verificacion.json', json.dumps(manifest).encode())
        package.writestr('README.txt', 'Synthetic QA fixture; no real finding or author identity.')
        for name, blob in extra:
            package.writestr(name, blob)
    return path


@pytest.fixture
def material(tmp_path):
    private = tmp_path / 'secret.pem'
    public = tmp_path / 'pin.pem'
    signing.generate_keypair(private, public)
    source = archive(tmp_path / 'delivery.zip')
    sidecar = tmp_path / 'delivery.sig.json'
    return source, private, public, sidecar


def signed(material):
    source, private, public, sidecar = material
    signing.sign_delivery(source, private, sidecar)
    return source, private, public, sidecar


def rewrite(source, mutation):
    with zipfile.ZipFile(source) as original:
        rows = [(entry.filename, original.read(entry)) for entry in original.infolist()]
    mutation(rows)
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_STORED) as package:
        for name, blob in rows:
            package.writestr(name, blob)


def test_real_signature_uses_external_pin_and_preserves_all_inputs(material, monkeypatch):
    source, private, public, sidecar = material
    before = {p: p.read_bytes() for p in (source, private, public)}
    signing.sign_delivery(source, private, sidecar)
    # Any implementation that extracts an archive fails this test immediately.
    monkeypatch.setattr(zipfile.ZipFile, 'extractall', lambda *a, **kw: pytest.fail('extraction'))
    monkeypatch.setattr(zipfile.ZipFile, 'extract', lambda *a, **kw: pytest.fail('extraction'))
    result = signing.verify_delivery(source, sidecar, public)
    assert result['verified'] and result['files_checked'] == 1
    assert result['scope'] == 'exact_zip_and_manifest_bytes'
    assert result['trusted_key'] == 'caller_selected_external_public_key'
    assert {p: p.read_bytes() for p in before} == before
    assert stat.S_IMODE(private.stat().st_mode) == 0o600
    envelope = json.loads(sidecar.read_text())
    assert 'public_key' not in envelope and 'private_key' not in envelope
    assert private.read_bytes() not in sidecar.read_bytes()
    assert len(base64.b64decode(envelope['signature'])) == 64


@pytest.mark.parametrize('mutation', ['recompress', 'readme', 'manifest-whitespace', 'trailing', 'byte', 'add', 'truncate'])
def test_any_archive_or_manifest_byte_mutation_is_rejected(material, mutation):
    source, _, public, sidecar = signed(material)
    if mutation == 'recompress':
        rewrite(source, lambda rows: None)
    elif mutation in {'readme', 'manifest-whitespace', 'add'}:
        def change(rows):
            if mutation == 'add':
                rows.append(('extra.txt', b'not declared'))
            else:
                name = 'README.txt' if mutation == 'readme' else 'verificacion.json'
                rows[:] = [(n, b + b' ' if n == name else b) for n, b in rows]
        rewrite(source, change)
    elif mutation == 'trailing':
        source.write_bytes(source.read_bytes() + b'appended byte')
    elif mutation == 'byte':
        blob = bytearray(source.read_bytes()); blob[80] ^= 1; source.write_bytes(blob)
    else:
        source.write_bytes(source.read_bytes()[:-10])
    with pytest.raises(ValueError):
        signing.verify_delivery(source, sidecar, public)


@pytest.mark.parametrize('mutation', ['signature-byte', 'truncated', 'bad-base64', 'bad-key-hash',
                                    'archive-digest', 'manifest-digest', 'version', 'algorithm',
                                    'unknown-field', 'payload-field', 'bytes-bool', 'manifest-name',
                                    'duplicate-json', 'float-nan', 'too-large'])
def test_detached_signature_fields_fail_closed(material, mutation):
    source, _, public, sidecar = signed(material)
    envelope = json.loads(sidecar.read_text())
    if mutation == 'signature-byte':
        blob = bytearray(base64.b64decode(envelope['signature'])); blob[0] ^= 1
        envelope['signature'] = base64.b64encode(blob).decode()
    elif mutation == 'truncated': envelope['signature'] = base64.b64encode(b'a' * 63).decode()
    elif mutation == 'bad-base64': envelope['signature'] += '\n'
    elif mutation == 'bad-key-hash': envelope['payload']['key_sha256'] = '0' * 64
    elif mutation == 'archive-digest': envelope['payload']['archive']['sha256'] = '0' * 64
    elif mutation == 'manifest-digest': envelope['payload']['manifest']['sha256'] = '0' * 64
    elif mutation == 'version': envelope['version'] = True
    elif mutation == 'algorithm': envelope['algorithm'] = 'Ed25519ph'
    elif mutation == 'unknown-field': envelope['public_key'] = public.read_text()
    elif mutation == 'payload-field': envelope['payload']['untrusted'] = 'yes'
    elif mutation == 'bytes-bool': envelope['payload']['archive']['bytes'] = True
    elif mutation == 'manifest-name': envelope['payload']['manifest']['name'] = 'other.json'
    if mutation == 'duplicate-json':
        sidecar.write_text('{"format": "one", "format": "two"}')
    elif mutation == 'float-nan': sidecar.write_text('{"version":NaN}')
    elif mutation == 'too-large': sidecar.write_bytes(b'a' * (signing.MAX_SIGNATURE_BYTES + 1))
    else: sidecar.write_text(json.dumps(envelope))
    with pytest.raises(ValueError): signing.verify_delivery(source, sidecar, public)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a//b', 'a/./b', 'a\\b', 'C:drive',
                                'NUL.txt', 'trailing.', 'trailing ', 'a\x00hidden', 'spoof\u202e.txt'])
def test_unsafe_archive_paths_are_rejected(material, name):
    source, _, _, _ = material
    # A NUL is preserved in the central/local filenames to avoid ZipInfo silently
    # truncating it while the hostile fixture itself is being constructed.
    if '\x00' in name:
        archive(source, {'aXhidden': b'opaque'})
        source.write_bytes(source.read_bytes().replace(b'aXhidden', b'a\x00hidden'))
    else:
        archive(source, {name: b'opaque'})
    with pytest.raises(ValueError): signing.inspect_delivery(source)


@pytest.mark.parametrize('case', ['duplicate', 'casefold', 'file-dir', 'symlink', 'encrypted',
                                'directory', 'unsupported-compression', 'missing-manifest', 'extra-pin'])
def test_hostile_archive_layout_and_flags_are_rejected(material, case):
    source, _, public, _ = material
    if case == 'duplicate': archive(source, extra=[('informe.html', b'changed')])
    elif case == 'casefold': archive(source, extra=[('INFORME.HTML', b'changed')])
    elif case == 'file-dir': archive(source, {'a': b'one', 'a/b': b'two'})
    elif case == 'directory': archive(source, extra=[('dir/', b'')])
    elif case == 'unsupported-compression': archive(source, compression=zipfile.ZIP_BZIP2)
    elif case == 'extra-pin': archive(source, extra=[('pin.pem', public.read_bytes())])
    elif case == 'missing-manifest':
        rewrite(source, lambda rows: rows.__setitem__(slice(None), [(n, b) for n, b in rows if n != 'verificacion.json']))
    elif case == 'symlink':
        info = zipfile.ZipInfo('link'); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(source, 'a') as package: package.writestr(info, 'outside')
    elif case == 'encrypted':
        blob = bytearray(source.read_bytes())
        for magic, flag_offset in ((b'PK\x03\x04', 6), (b'PK\x01\x02', 8)):
            offset = blob.index(magic) + flag_offset
            flags = struct.unpack_from('<H', blob, offset)[0]
            struct.pack_into('<H', blob, offset, flags | 1)
        source.write_bytes(blob)
    with pytest.raises(ValueError): signing.inspect_delivery(source)


@pytest.mark.parametrize('case', ['version', 'version-bool', 'format', 'hash', 'size', 'record-unknown',
                                'missing-file', 'missing-guide', 'duplicate-json', 'unknown', 'no-files', 'manifest-budget'])
def test_strict_manifest_and_all_declared_files_are_checked(material, case):
    source, _, _, _ = material
    def change(data):
        if case == 'version': data['version'] = 2
        elif case == 'version-bool': data['version'] = True
        elif case == 'format': data['format'] = 'other'
        elif case == 'hash': data['files']['informe.html']['sha256'] = 'a' * 64
        elif case == 'size': data['files']['informe.html']['bytes'] += 1
        elif case == 'record-unknown': data['files']['informe.html']['unknown'] = True
        elif case == 'missing-file': data['files']['ghost.txt'] = deepcopy(data['files']['informe.html'])
        elif case == 'unknown': data['unsupported'] = 1
        elif case == 'no-files': data['files'] = {}
    archive(source, changes=change)
    if case == 'missing-guide':
        rewrite(source, lambda rows: rows.__setitem__(slice(None), [(n, b) for n, b in rows if n != 'README.txt']))
    elif case in {'duplicate-json', 'manifest-budget'}:
        replacement = b'{"format":1,"format":2}' if case == 'duplicate-json' else b'a' * (signing.MAX_DOCUMENT_BYTES + 1)
        rewrite(source, lambda rows: rows.__setitem__(slice(None), [(n, replacement if n == 'verificacion.json' else b) for n, b in rows]))
    with pytest.raises(ValueError): signing.inspect_delivery(source)


@pytest.mark.parametrize('budget', ['archive', 'expanded', 'files', 'metadata'])
def test_existing_resource_budgets_are_checked_before_member_read(material, monkeypatch, budget):
    source, _, _, _ = material
    if budget == 'archive': monkeypatch.setattr(signing, 'MAX_ARCHIVE', source.stat().st_size - 1)
    elif budget == 'expanded': monkeypatch.setattr(signing, 'MAX_EXPANDED', 10)
    elif budget == 'files': monkeypatch.setattr(signing, 'MAX_FILES', 2)
    elif budget == 'metadata': monkeypatch.setattr(signing, 'MAX_DIRECTORY_BYTES', 5)
    monkeypatch.setattr(zipfile.ZipFile, 'open', lambda *a, **kw: pytest.fail('member read before limit gate'))
    with pytest.raises(ValueError): signing.inspect_delivery(source)


@pytest.mark.parametrize('case', ['wrong', 'private-as-public', 'public-as-private', 'malformed',
                                'truncated', 'oversized', 'permissions', 'hardlink', 'symlink'])
def test_wrong_or_unsafe_keys_are_rejected(material, tmp_path, case):
    source, private, public, sidecar = signed(material)
    if case == 'wrong':
        signing.generate_keypair(tmp_path / 'other-secret.pem', tmp_path / 'other-pin.pem')
        public = tmp_path / 'other-pin.pem'
    elif case == 'private-as-public': public = private
    elif case == 'public-as-private':
        public.chmod(0o600)
        with pytest.raises(ValueError): signing.sign_delivery(source, public, tmp_path / 'wrong.sig')
        return
    elif case in {'malformed', 'truncated', 'oversized'}:
        public.write_bytes(b'not a PEM' if case == 'malformed' else public.read_bytes()[:-30] if case == 'truncated'
                           else b'a' * (signing.MAX_KEY_BYTES + 1))
    elif case in {'permissions', 'hardlink', 'symlink'}:
        if case == 'permissions': private.chmod(0o644)
        elif case == 'hardlink': os.link(private, tmp_path / 'alias.pem')
        else:
            link = tmp_path / 'linked-secret.pem'; link.symlink_to(private); private = link
        with pytest.raises(ValueError): signing.sign_delivery(source, private, tmp_path / 'wrong.sig')
        return
    with pytest.raises(ValueError): signing.verify_delivery(source, sidecar, public)


@pytest.mark.parametrize('output', ['source', 'private', 'public', 'existing', 'symlink', 'missing-parent'])
def test_sign_outputs_never_overwrite_or_alias_inputs(material, tmp_path, output):
    source, private, public, sidecar = material
    target = {'source': source, 'private': private, 'public': public}.get(output, sidecar)
    if output == 'existing': target.write_bytes(b'keep')
    elif output == 'symlink': target.symlink_to(private)
    elif output == 'missing-parent': target = tmp_path / 'missing' / 'new.sig'
    before = {p: p.read_bytes() for p in (source, private, public)}
    with pytest.raises(ValueError): signing.sign_delivery(source, private, target)
    assert {p: p.read_bytes() for p in before} == before


def test_keygen_never_overwrites_and_private_is_outside_app_and_projects(material, tmp_path, monkeypatch):
    _, private, public, _ = material
    before = private.read_bytes(), public.read_bytes()
    with pytest.raises(ValueError): signing.generate_keypair(private, public)
    assert (private.read_bytes(), public.read_bytes()) == before
    project = tmp_path / 'report'; project.mkdir(); (project / 'engagement.yaml').write_text('meta: {}')
    with pytest.raises(ValueError): signing.generate_keypair(project / 'secret.pem', tmp_path / 'new-pin.pem')
    monkeypatch.setattr(signing, 'ROOT', tmp_path / 'app')
    signing.ROOT.mkdir()
    with pytest.raises(ValueError): signing.generate_keypair(signing.ROOT / 'secret.pem', tmp_path / 'new-pin.pem')
    assert not (project / 'secret.pem').exists() and not (tmp_path / 'new-pin.pem').exists()


def test_keygen_partial_public_failure_cleans_only_new_private(tmp_path, monkeypatch):
    private = tmp_path / 'private.pem'; public = tmp_path / 'public.pem'
    original = signing._write_new
    def fail(path, blob, mode):
        if path == public:
            raise OSError('synthetic write failure')
        return original(path, blob, mode)
    monkeypatch.setattr(signing, '_write_new', fail)
    with pytest.raises(OSError): signing.generate_keypair(private, public)
    assert not private.exists() and not public.exists()


def test_sign_refuses_own_private_material_in_a_reviewed_member(material):
    source, private, _, sidecar = material
    archive(source, {'anexos/synthetic.txt': private.read_bytes()})
    with pytest.raises(ValueError, match='clave privada'): signing.sign_delivery(source, private, sidecar)
    assert not sidecar.exists()


def test_alias_verification_inputs_are_rejected(material, tmp_path):
    source, _, public, sidecar = signed(material)
    alias = tmp_path / 'alias.json'; os.link(sidecar, alias)
    with pytest.raises(ValueError): signing.verify_delivery(source, sidecar, alias)
    with pytest.raises(ValueError): signing.verify_delivery(source, source, public)


def test_signing_extra_is_lazy_and_missing_dependency_leaves_inspection_working(material, monkeypatch):
    source, private, _, sidecar = material
    original = builtins.__import__
    def without_crypto(name, *args, **kwargs):
        if name.startswith('cryptography'): raise ImportError('synthetic missing optional dependency')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_crypto)
    assert signing.inspect_delivery(source)['files_checked'] == 1
    with pytest.raises(ValueError, match=r'report-gen\[signing\]'): signing.sign_delivery(source, private, sidecar)
    assert not sidecar.exists()


@pytest.mark.parametrize('language,fragment', [('es', 'clave pública externa'), ('en', 'external public key')])
def test_error_language_is_explicit_and_scoped(material, tmp_path, language, fragment):
    source, _, _, sidecar = signed(material)
    signing.generate_keypair(tmp_path / 'wrong.pem', tmp_path / 'wrong-pin.pem')
    with language_scope(language), pytest.raises(ValueError, match=fragment):
        signing.verify_delivery(source, sidecar, tmp_path / 'wrong-pin.pem')


@pytest.mark.parametrize('language', ['es', 'en'])
def test_actual_cli_keygen_sign_verify_and_invalid_exit_codes(tmp_path, language):
    source = archive(tmp_path / 'delivery.zip')
    private = tmp_path / 'secret.pem'; public = tmp_path / 'pin.pem'; signature = tmp_path / 'delivery.sig.json'
    command = [sys.executable, str(ROOT / 'delivery_signature.py'), '--lang', language]
    for arguments in (['keygen', '--private-key', str(private), '--public-key', str(public)],
                      ['sign', str(source), '--private-key', str(private), '--signature', str(signature)],
                      ['verify', str(source), '--signature', str(signature), '--public-key', str(public)]):
        result = subprocess.run(command + arguments, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['language'] == language and not result.stderr
    source.write_bytes(source.read_bytes() + b'bad')
    result = subprocess.run(command + ['verify', str(source), '--signature', str(signature), '--public-key', str(public)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and not result.stdout
    assert json.loads(result.stderr)['language'] == language
    assert private.read_text() not in result.stderr and str(private) not in result.stderr


def test_current_delivery_build_can_be_signed_without_changing_delivery_code(tmp_path):
    import delivery
    import workflows
    from wizard import dump_yaml
    project = tmp_path / 'report'; project.mkdir()
    document = workflows.normalize({'meta': {'report_title': 'Synthetic signing integration', 'theme': 'serio',
                                  'lang': 'en', 'assessor': 'QA'}, 'findings': []})
    dump_yaml(document, project / 'engagement.yaml')
    captured = delivery.capture(project, tmp_path / 'snapshot')
    identity = sha256((project / 'engagement.yaml').read_bytes()).hexdigest()
    blob = delivery.build(tmp_path / 'snapshot', ['md'], identity, 'Synthetic signing QA', captured, tmp_path / 'out')
    source = tmp_path / 'delivery.zip'; source.write_bytes(blob)
    private = tmp_path / 'secret.pem'; public = tmp_path / 'pin.pem'; sidecar = tmp_path / 'delivery.sig.json'
    signing.generate_keypair(private, public)
    signing.sign_delivery(source, private, sidecar)
    assert signing.verify_delivery(source, sidecar, public)['files_checked'] == 1
    assert source.read_bytes() == blob
    with zipfile.ZipFile(BytesIO(blob)) as package:
        assert set(package.namelist()) == {'markdown.zip', 'verificacion.json', 'README.txt'}


def test_archive_limits_match_existing_backup_contract():
    import project_history
    assert (signing.MAX_ARCHIVE, signing.MAX_EXPANDED, signing.MAX_FILES) == (
        project_history.MAX_ARCHIVE, project_history.MAX_EXPANDED, project_history.MAX_FILES)


@pytest.mark.parametrize('profile', ['technical', 'executive', 'public'])
def test_real_audience_deliveries_are_signed_with_recorded_decisions_unchanged(tmp_path, profile):
    import audience
    import workflows
    from wizard import dump_yaml
    project = tmp_path / 'report'; project.mkdir()
    document = workflows.normalize({'meta': {'report_title': 'Synthetic audience signing', 'theme': 'serio',
                                  'lang': 'en', 'assessor': 'QA'}, 'findings': [
        {'id': 'F1', 'title': 'Synthetic control', 'mode': 'vuln', 'severity': 'info', 'cvss': 0,
         'description_md': 'Documented observation', 'impact_md': 'Documented impact',
         'remediation_md': 'Proposed correction'}]})
    dump_yaml(document, project / 'engagement.yaml')
    options = {'profile': profile}
    if profile == 'public':
        uid = document['findings'][0]['uid']
        options.update(finding_uids=[uid], title='Synthetic public case', client_alias='Synthetic client',
            review_confirmed=True, publish_consent=True, provenance_label='simulation',
            aliases=[{'needle': 'Synthetic audience signing', 'replacement': 'Public synthetic fixture'}],
            approved_content=[{'finding_uid': uid, 'title': 'Published control', 'summary': 'Approved observation',
                               'impact': 'Approved impact', 'remediation': 'Approved correction'}])
    captured = audience.capture(document, project, tmp_path / 'snapshot', options)
    blob = audience.build(tmp_path / 'snapshot', ['md'], 'a' * 64, 'Synthetic audience QA', captured, tmp_path / 'out')
    source = tmp_path / 'delivery.zip'; source.write_bytes(blob)
    private = tmp_path / 'secret.pem'; public = tmp_path / 'pin.pem'; sidecar = tmp_path / 'delivery.sig.json'
    signing.generate_keypair(private, public)
    signing.sign_delivery(source, private, sidecar)
    assert signing.verify_delivery(source, sidecar, public)['verified']
    assert source.read_bytes() == blob
    with zipfile.ZipFile(BytesIO(blob)) as package:
        assert json.loads(package.read('verificacion.json'))['audience'] == captured['audience']


@pytest.mark.parametrize('case', ['guidance', 'audience-null', 'profile', 'permission-type', 'unknown', 'plan-count'])
def test_optional_metadata_is_structural_and_does_not_grant_permissions(material, case):
    source, _, _, _ = material
    metadata = {'profile': 'public', 'plan': {'included': [], 'excluded': [], 'finding_count': 1,
                'section_count': 2, 'originals': False, 'attachments': False},
                'public_permission_declared': False, 'provenance_label': None}
    # False is documentary metadata. The signature verifier neither upgrades it
    # nor treats it as evidence that publication is authorized.
    archive(source, changes=lambda data: data.update(audience=deepcopy(metadata)))
    assert signing.inspect_delivery(source)['files_checked'] == 1
    def change(data):
        data['audience'] = deepcopy(metadata)
        if case == 'guidance': data['design_guidance'] = 'invalid'
        elif case == 'audience-null': data['audience'] = None
        elif case == 'profile': data['audience']['profile'] = 'unsupported'
        elif case == 'permission-type': data['audience']['public_permission_declared'] = 'true'
        elif case == 'unknown': data['audience']['unknown'] = 1
        elif case == 'plan-count': data['audience']['plan']['finding_count'] = True
    archive(source, changes=change)
    with pytest.raises(ValueError): signing.inspect_delivery(source)


@pytest.mark.parametrize('operation', ['keygen', 'sign'])
def test_private_operations_reject_unsupported_platform_before_any_file_action(material, monkeypatch, operation):
    source, private, public, sidecar = material
    monkeypatch.setattr(signing, 'os', SimpleNamespace(name='unsupported'))
    with pytest.raises(ValueError, match='POSIX'):
        if operation == 'keygen': signing.generate_keypair(private, public)
        else: signing.sign_delivery(source, private, sidecar)
    assert not sidecar.exists()


@pytest.mark.parametrize('case', ['rsa-public', 'rsa-private', 'encrypted-private'])
def test_other_algorithms_and_password_protected_keys_fail_explicitly(material, tmp_path, case):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    source, private, public, sidecar = signed(material)
    if case.startswith('rsa'):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if case == 'rsa-public':
            public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo))
        else:
            private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                  serialization.NoEncryption()))
    else:
        key = serialization.load_pem_private_key(private.read_bytes(), password=None)
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.BestAvailableEncryption(b'synthetic-QA-only')))
    with pytest.raises(ValueError, match='PEM Ed25519'):
        if case == 'rsa-public': signing.verify_delivery(source, sidecar, public)
        else: signing.sign_delivery(source, private, tmp_path / 'new.sig')
    assert not (tmp_path / 'new.sig').exists()


def test_fifo_input_is_rejected_without_waiting_for_a_producer(material, tmp_path):
    _, private, _, sidecar = material
    fifo = tmp_path / 'input.pipe'; os.mkfifo(fifo, 0o600)
    with pytest.raises(ValueError): signing.sign_delivery(fifo, private, sidecar)
    assert not sidecar.exists()


def test_concurrent_sign_and_verify_keep_exact_bytes_and_one_exclusive_writer(material, tmp_path):
    source, private, public, _ = material
    before = source.read_bytes()
    def operation(number):
        sidecar = tmp_path / f'concurrent-{number}.json'
        signing.sign_delivery(source, private, sidecar)
        return signing.verify_delivery(source, sidecar, public)['verified']
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(operation, range(32)))
    target = tmp_path / 'exclusive.json'
    def same_output(_):
        try:
            signing.sign_delivery(source, private, target)
            return True
        except (ValueError, FileExistsError):
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(same_output, range(16))) == 1
    assert signing.verify_delivery(source, target, public)['verified']
    assert source.read_bytes() == before


@pytest.mark.parametrize('private', [False, True])
@pytest.mark.parametrize('mutation', ['garbage', 'second-key', 'other-block'])
def test_pem_must_be_one_unambiguous_complete_block(material, tmp_path, private, mutation):
    source, secret, public, sidecar = signed(material)
    target = secret if private else public
    original = target.read_bytes()
    if mutation == 'garbage': target.write_bytes(original + b'not part of a PEM key')
    elif mutation == 'second-key': target.write_bytes(original + original)
    else: target.write_bytes(original + (public if private else secret).read_bytes())
    with pytest.raises(ValueError, match='una única clave PEM'):
        if private: signing.sign_delivery(source, secret, tmp_path / 'ambiguous.sig')
        else: signing.verify_delivery(source, sidecar, public)
    assert not (tmp_path / 'ambiguous.sig').exists()


def test_complete_pem_allows_crlf_and_border_whitespace(material):
    source, private, public, sidecar = material
    for path in (private, public):
        path.write_bytes(b'\r\n ' + path.read_bytes().replace(b'\n', b'\r\n') + b' \r\n')
    signing.sign_delivery(source, private, sidecar)
    assert signing.verify_delivery(source, sidecar, public)['verified']


def test_normalized_unicode_name_collisions_are_rejected(material):
    source, _, _, _ = material
    archive(source, {'anexos/re\u0301sume\u0301.txt': b'one', 'anexos/résumé.txt': b'two'})
    with pytest.raises(ValueError, match='Entrada ZIP de entrega no permitida'):
        signing.inspect_delivery(source)


def test_native_delivery_with_valid_nfd_annex_preserves_names_and_exact_signed_bytes(tmp_path):
    import delivery
    import workflows
    from wizard import dump_yaml
    project = tmp_path / 'report'; project.mkdir(); (project / 'attachments').mkdir()
    name = 're\u0301sume\u0301.txt'
    identifier = uuid4(); uid = str(identifier); member = f'attachments/{identifier.hex}.txt'
    annex = b'Synthetic NFD annex fixture only.\n'
    (project / member).write_bytes(annex)
    document = workflows.normalize({'meta': {'report_title': 'Synthetic NFD signing integration', 'theme': 'serio',
        'lang': 'en', 'assessor': 'QA'}, 'findings': [], 'attachments': [{'uid': uid, 'name': name,
        'member': member, 'sha256': sha256(annex).hexdigest(), 'include': True, 'reviewed': True, 'required': True}]})
    dump_yaml(document, project / 'engagement.yaml')
    captured = delivery.capture(project, tmp_path / 'snapshot')
    blob = delivery.build(tmp_path / 'snapshot', ['md'], 'a' * 64, 'Synthetic NFD QA', captured, tmp_path / 'out')
    source = tmp_path / 'delivery.zip'; source.write_bytes(blob)
    private = tmp_path / 'secret.pem'; public = tmp_path / 'pin.pem'; sidecar = tmp_path / 'delivery.sig.json'
    signing.generate_keypair(private, public)
    signing.sign_delivery(source, private, sidecar)
    assert signing.verify_delivery(source, sidecar, public)['files_checked'] == 2
    assert source.read_bytes() == blob
    with zipfile.ZipFile(BytesIO(blob)) as package:
        assert package.read('anexos/' + name) == annex
        manifest = json.loads(package.read('verificacion.json'))
        assert 'anexos/' + name in manifest['files'] and 'anexos/résumé.txt' not in manifest['files']
