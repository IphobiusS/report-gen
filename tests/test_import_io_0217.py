"""Invalid imports fail as input errors without poisoning a local workspace."""
from hashlib import sha256
from io import BytesIO
import json
import struct
import zipfile

import pytest
from PIL import Image

import app as api
import project_history as history
import workspace_backup
from _support import auth_client


def tree(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def bundle(files=None, version=1, compression=zipfile.ZIP_STORED):
    files = files or {'engagement.yaml': b'meta: {report_title: Test}\nfindings: []\n'}
    manifest = dict(format='report-gen-project', version=version,
                    files={name: sha256(blob).hexdigest() for name, blob in files.items()})
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression) as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        for name, blob in files.items(): archive.writestr(name, blob)
    return output.getvalue()


def png():
    output = BytesIO(); Image.new('RGB', (3, 3), 'blue').save(output, 'PNG')
    return output.getvalue()


@pytest.fixture
def local(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    return auth_client(api.app), projects


@pytest.mark.parametrize('original, alias', [('straße', 'strasse'), ('ς', 'σ')])
def test_import_rejects_equivalent_project_slug_and_backup_stays_available(local, original, alias):
    client, projects = local
    assert client.post('/api/projects', json={'slug': original}).status_code == 200
    before = tree(projects)
    response = client.post('/api/projects/import', data={'slug': alias, 'file': (BytesIO(bundle()), 'copy.zip')})
    assert response.status_code == 409
    assert tree(projects) == before
    assert not list(projects.glob('.import-*'))
    output = workspace_backup.export_workspace(projects, projects.parent / 'findings.json', projects.parent / 'designs.json')
    with zipfile.ZipFile(BytesIO(output)) as archive:
        assert 'projects/' + original + '.zip' in archive.namelist()


def test_import_preserves_distinct_unicode_name_and_backup_roundtrip(local):
    client, projects = local
    client.post('/api/projects', json={'slug': 'straße'})
    response = client.post('/api/projects/import', data={'slug': 'strasse-2', 'file': (BytesIO(bundle()), 'copy.zip')})
    assert response.status_code == 200
    assert (projects / 'straße' / 'engagement.yaml').is_file()
    assert (projects / 'strasse-2' / 'engagement.yaml').is_file()
    with zipfile.ZipFile(BytesIO(history.export_bundle(projects / 'strasse-2'))) as archive:
        assert b'Test' in archive.read('engagement.yaml')


def unsupported_method(blob, method=99):
    value = bytearray(blob)
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        for entry in archive.infolist(): struct.pack_into('<H', value, entry.header_offset + 8, method)
    cursor = 0
    while (cursor := value.find(b'PK\x01\x02', cursor)) >= 0:
        struct.pack_into('<H', value, cursor + 10, method); cursor += 4
    return bytes(value)


def corrupt_stream(blob):
    value = bytearray(blob)
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        entry = archive.infolist()[0]
        name_size, extra_size = struct.unpack_from('<HH', value, entry.header_offset + 26)
        start = entry.header_offset + 30 + name_size + extra_size
        value[start:start + entry.compress_size] = b'\xff' * entry.compress_size
    return bytes(value)


INVALID_ARCHIVES = [
    unsupported_method(bundle(), 99),
    unsupported_method(bundle(), 65535),
    corrupt_stream(bundle(compression=zipfile.ZIP_DEFLATED)),
    bundle(version=True),
    bundle({'engagement.yaml': b'meta: {}\nfindings: []\n', 'engagement.yaml/proof.png': png()}),
    bundle({'engagement.yaml/proof.png': png(), 'engagement.yaml': b'meta: {}\nfindings: []\n'}),
    bundle({'engagement.yaml': b'meta: {}\nfindings: []\n', 'engagement.yaml!.png': png(), 'engagement.yaml/proof.png': png()}),
]


@pytest.mark.parametrize('payload', INVALID_ARCHIVES, ids=['unknown99', 'unknown65535', 'corrupt_deflate', 'boolean_version', 'file_parent', 'directory_parent', 'interleaved_sibling'])
def test_invalid_archive_is_422_and_existing_state_is_untouched(local, payload):
    client, projects = local
    client.post('/api/projects', json={'slug': 'keep'})
    before = tree(projects)
    response = client.post('/api/projects/import', data={'slug': 'rejected', 'file': (BytesIO(payload), 'broken.zip')})
    assert response.status_code == 422
    assert response.get_json().get('error')
    assert tree(projects) == before
    assert not (projects / 'rejected').exists()
    assert not list(projects.glob('.import-*'))
    with pytest.raises(ValueError): history.import_bundle(payload, projects / 'cli-rejected')
    assert not (projects / 'cli-rejected').exists()
    assert not list(projects.glob('.import-*'))


def test_image_siblings_with_a_common_prefix_are_not_mistaken_for_directories(local):
    client, projects = local
    value = png()
    payload = bundle({'engagement.yaml': b'meta: {}\nfindings: []\n', 'img/a.png': value, 'img/a.pngx.png': value})
    response = client.post('/api/projects/import', data={'slug': 'siblings', 'file': (BytesIO(payload), 'siblings.zip')})
    assert response.status_code == 200
    assert (projects / 'siblings/img/a.png').read_bytes() == value
    assert (projects / 'siblings/img/a.pngx.png').read_bytes() == value
    assert not list(projects.glob('.import-*'))


@pytest.mark.parametrize('compression', [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_supported_compression_and_nested_unicode_image_are_preserved(local, compression):
    client, projects = local
    name = 'img/pruebas/evidencia ñ.png'; value = png()
    payload = bundle({'engagement.yaml': b'meta: {}\nfindings: []\n', name: value}, compression=compression)
    response = client.post('/api/projects/import', data={'slug': 'valid', 'file': (BytesIO(payload), 'valid.zip')})
    assert response.status_code == 200
    assert (projects / 'valid' / name).read_bytes() == value
    assert not list(projects.glob('.import-*'))
