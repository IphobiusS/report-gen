"""A restored personal template must remain editable, not fail on its counter."""
from hashlib import sha256
from io import BytesIO
import json
import zipfile

import pytest
import app as api
import design_library as designs
import workspace_backup
from storage import revision
from _support import auth_client


@pytest.fixture
def local(tmp_path, monkeypatch):
    projects = tmp_path/'projects'; projects.mkdir()
    path = tmp_path/'designs.json'
    profile = designs.profile('htb-cwee')
    body = dict(name='Reusable design', design=designs.appearance(profile), sections=profile['sections'])
    entry = designs.put_personal(path, body)
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path/'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(path))
    return auth_client(api.app), path, body, entry['id']


def damaged_library(path, field, value):
    data = json.loads(path.read_bytes())
    data['templates'][0][field] = value
    return json.dumps(data).encode()


INVALID_METADATA = [('revision', None), ('revision', 'damaged'), ('revision', True),
                    ('revision', []), ('revision', 0), ('revision', -1), ('name', None), ('name', '')]


@pytest.mark.parametrize('field,value', INVALID_METADATA)
def test_invalid_personal_metadata_fails_as_input_error_without_mutation(local, field, value):
    client, path, body, ident = local
    original = damaged_library(path, field, value)
    path.write_bytes(original)
    assert client.get('/api/design-library').status_code == 422
    updated = client.put('/api/design-library/personal/' + ident, json=body,
                         headers={'If-Match': revision(path)})
    assert updated.status_code == 422
    assert path.read_bytes() == original


@pytest.mark.parametrize('field,value', INVALID_METADATA)
def test_integral_restore_never_activates_a_template_that_cannot_be_edited(local, tmp_path, field, value):
    _, path, _, _ = local
    bad = damaged_library(path, field, value)
    files = {'libraries/findings.json': b'{"format":"report-gen-library","version":1,"templates":[]}',
             'libraries/designs.json': bad}
    manifest = dict(format='report-gen-workspace', version=1,
                    files={name: sha256(blob).hexdigest() for name, blob in files.items()})
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        for name, blob in files.items():
            archive.writestr(name, blob)
    target = tmp_path/'restored'
    with pytest.raises(ValueError):
        workspace_backup.restore_workspace(output.getvalue(), target/'projects', target/'findings.json', target/'designs.json')
    assert not (target/'projects').exists() and not (target/'designs.json').exists()
    assert not list(target.glob('.workspace-*'))


def test_legacy_missing_revision_still_edits_and_restores(local, tmp_path):
    client, path, body, ident = local
    data = json.loads(path.read_bytes())
    del data['templates'][0]['revision']
    path.write_text(json.dumps(data))
    updated = client.put('/api/design-library/personal/' + ident, json=body,
                         headers={'If-Match': revision(path)})
    assert updated.status_code == 200 and updated.get_json()['revision'] == 1
    blob = workspace_backup.export_workspace(api.PROJECTS, path.parent/'findings.json', path)
    target = tmp_path/'valid-restore'
    assert workspace_backup.restore_workspace(blob, target/'projects', target/'findings.json', target/'designs.json')['designs'] == 1
    assert designs.put_personal(target/'designs.json', body, ident)['revision'] == 2


def test_duplicate_personal_identity_does_not_replace_two_rows(local):
    client, path, body, ident = local
    data = json.loads(path.read_bytes())
    data['templates'].append({**data['templates'][0], 'name': 'Another retained design'})
    original = json.dumps(data).encode(); path.write_bytes(original)
    updated = client.put('/api/design-library/personal/' + ident, json=body,
                         headers={'If-Match': revision(path)})
    assert updated.status_code == 422 and path.read_bytes() == original


def test_boolean_library_version_is_not_version_one(local):
    client, path, _, _ = local
    data = json.loads(path.read_bytes()); data['version'] = True
    path.write_text(json.dumps(data))
    assert client.get('/api/design-library').status_code == 422
