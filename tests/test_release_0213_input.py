"""Malformed typed YAML values fail as input errors, without partial projects."""
from hashlib import sha256
from io import BytesIO
import json
import zipfile

import pytest
import app as webapp
import input_guard as guard
from _support import auth_client


SCALARS = [
    pytest.param('!!int ""', IndexError, id='empty_integer'),
    pytest.param('!!float ""', IndexError, id='empty_float'),
    pytest.param('!!bool unknown', KeyError, id='unknown_bool'),
    pytest.param('!!int not-an-integer', ValueError, id='invalid_integer'),
    pytest.param('!!float not-a-float', ValueError, id='invalid_float'),
    pytest.param('1' + ':00' * 180 + '.0', OverflowError, id='sexagesimal_float_overflow'),
]


def document(scalar):
    return ('meta: {lang: es, theme: corporativo, report_title: Private input}\n'
            'findings: []\nextension: ' + scalar + '\n').encode('utf-8')


def bundle(blob):
    stream = BytesIO()
    manifest = {'format': 'report-gen-project', 'version': 1,
                'files': {'engagement.yaml': sha256(blob).hexdigest()}}
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        archive.writestr('engagement.yaml', blob)
    return stream.getvalue()


@pytest.mark.parametrize('scalar,cause', SCALARS)
def test_typed_yaml_constructor_errors_become_controlled_value_errors(scalar, cause):
    with pytest.raises(ValueError, match='YAML inválido: valor incompatible') as error:
        guard.load_yaml(document(scalar))
    assert isinstance(error.value.__cause__, cause)
    assert 'Private input' not in str(error.value)


@pytest.mark.parametrize('scalar,cause', SCALARS)
def test_bad_typed_yaml_get_and_zip_import_return_422_without_partial_state(tmp_path, monkeypatch, scalar, cause):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path / 'projects')
    webapp.PROJECTS.mkdir()
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path / 'library' / 'findings.json'))
    monkeypatch.setitem(webapp.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'library' / 'designs.json'))
    directory = webapp.PROJECTS / 'invalid'; directory.mkdir()
    blob = document(scalar)
    (directory / 'engagement.yaml').write_bytes(blob)
    client = auth_client(webapp.app)
    response = client.get('/api/projects/invalid')
    assert response.status_code == 422, response.get_json()
    assert response.get_json()['error'] == 'YAML inválido: valor incompatible con su tipo declarado'
    assert response.headers['Cache-Control'] == 'no-store'
    assert (directory / 'engagement.yaml').read_bytes() == blob
    assert list(directory.iterdir()) == [directory / 'engagement.yaml']
    imported = client.post('/api/projects/import', data={'slug': 'rejected',
                'file': (BytesIO(bundle(blob)), 'invalid.zip')})
    assert imported.status_code == 422, imported.get_json()
    assert imported.get_json()['error'] == 'YAML inválido: valor incompatible con su tipo declarado'
    assert set(path.name for path in webapp.PROJECTS.iterdir()) == {'invalid'}
    assert (directory / 'engagement.yaml').read_bytes() == blob


def test_valid_explicit_yaml_scalars_aliases_merges_and_iso_dates_still_load():
    source = ('defaults: &defaults {report_title: Default, lang: es}\n'
              'meta: {<<: *defaults, report_title: Chosen, date: 2026-10-08}\n'
              'findings: []\nextension: {integer: !!int "1_000", float: !!float "2:30.0", boolean: !!bool YES}\n')
    data = guard.load_yaml(source)
    assert data['meta'] == {'report_title': 'Chosen', 'lang': 'es', 'date': '2026-10-08'}
    assert data['extension'] == {'integer': 1000, 'float': 150.0, 'boolean': True}


@pytest.mark.parametrize('phase,exception', [('_check_yaml_graph', IndexError('unrelated graph bug')),
                                            ('ensure_data_tree', KeyError('unrelated tree bug'))])
def test_errors_outside_yaml_construction_are_not_hidden(monkeypatch, phase, exception):
    def fail(*args):
        raise exception
    monkeypatch.setattr(guard, phase, fail)
    with pytest.raises(type(exception)) as caught:
        guard.load_yaml('meta: {}\nfindings: []\n')
    assert caught.value is exception


def test_storage_failures_in_a_constructor_are_not_relabelled_as_invalid_yaml(monkeypatch):
    error = OSError('unrelated storage error')
    def fail(*args):
        raise error
    monkeypatch.setattr(guard.ProjectLoader, 'construct_document', fail)
    with pytest.raises(OSError) as caught:
        guard.load_yaml('meta: {}\nfindings: []\n')
    assert caught.value is error
