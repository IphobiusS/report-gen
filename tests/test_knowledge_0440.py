"""Offline authoring, isolated copies and revision-guarded catalog insertion."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import zipfile

import pytest

import app as webapp
import finding_library
from knowledge import catalog
import validate
from _support import auth_client


ROOT = Path(__file__).resolve().parents[1]


def sample_document():
    locales = {}
    for lang in ('es', 'en', 'pt'):
        locales[lang] = {key: f'{lang} {key} {{' + '{objetivo}}' for key in catalog.LOCALE_FIELDS}
        locales[lang]['title'] = f'{lang} autorización'
    return {'format': 'report-gen-knowledge', 'schema_version': 1, 'revision': 'test', 'entries': [{
        'id': 'RG-WEB-001', 'category': 'web', 'tags': ['web', 'authz'], 'cwe': 'CWE-862',
        'reviewed_on': '2026-10-17', 'references': [{'title': 'Source', 'url': 'https://cwe.mitre.org/data/definitions/862.html',
        'version': '4', 'accessed_on': '2026-10-17'}], 'mappings': [], 'locales': locales}]}


@pytest.fixture
def isolated_catalog(monkeypatch):
    source = catalog.validate_documents([sample_document()])
    monkeypatch.setattr(catalog, '_bundled', lambda: source)
    return source


@pytest.fixture
def project(tmp_path, monkeypatch, isolated_catalog):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path / 'projects')
    webapp.PROJECTS.mkdir()
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path / 'library' / 'findings.json'))
    client = auth_client(webapp.app)
    response = client.post('/api/projects', json={'slug': 'knowledge', 'title': 'Local knowledge test'})
    assert response.status_code == 200, response.get_json()
    return client, webapp.PROJECTS / 'knowledge', tmp_path / 'library' / 'findings.json'


@pytest.mark.parametrize('change', [
    lambda d: d.update(schema_version=True),
    lambda d: d.update(revision=''),
    lambda d: d.update(entries=[]),
    lambda d: d['entries'].append(deepcopy(d['entries'][0])),
    lambda d: d['entries'][0].update(id='../bad'),
    lambda d: d['entries'][0].update(category='ai'),
    lambda d: d['entries'][0].update(cwe=False),
    lambda d: d['entries'][0].update(cwe=None),
    lambda d: d['entries'][0].update(cwe=0),
    lambda d: d['entries'][0].update(cwe='CWE-unknown'),
    lambda d: d['entries'][0].update(tags=['authz', 'authz']),
    lambda d: d['entries'][0].update(tags=['<script>']),
    lambda d: d['entries'][0].update(reviewed_on='2026-02-31'),
    lambda d: d['entries'][0].update(verification='confirmed'),
    lambda d: d['entries'][0]['locales'].pop('pt'),
    lambda d: d['entries'][0]['locales']['pt'].update(impact_md=''),
    lambda d: d['entries'][0]['locales']['pt'].update(cvss='9.8'),
    lambda d: d['entries'][0]['locales']['pt'].update(impact_md='{{cliente}}'),
    lambda d: d['entries'][0]['references'][0].update(url='javascript:alert(1)'),
    lambda d: d['entries'][0]['references'][0].update(url='https://user:secret@example.org/'),
    lambda d: d['entries'][0]['references'][0].update(url='https://example.org:bad/'),
    lambda d: d['entries'][0]['references'][0].update(accessed_on='yesterday'),
    lambda d: d['entries'][0].update(mappings=[{'framework': 'Example', 'id': '1'}]),
])
def test_authored_records_reject_ambiguous_or_unsafe_contract(change):
    document = sample_document()
    change(document)
    with pytest.raises(ValueError):
        catalog.validate_documents([document])


def test_search_details_are_localized_bounded_and_isolated(isolated_catalog):
    index = catalog.search(lang='pt-BR', q='AUTORIZACAO')
    assert index['total'] == 0  # Synthetic title is deliberately Spanish in all locales.
    index = catalog.search(lang='pt-BR', q='AUTORIZACION', tag='AUTHZ', category='web', limit=1)
    assert index['lang'] == 'pt' and index['total'] == 1 and index['readonly']
    assert catalog.search(offset=1)['entries'] == []
    index['entries'][0]['tags'].clear()
    detail = catalog.entry('RG-WEB-001', 'en')
    detail['references'].clear()
    detail['description_md'] = 'Modified'
    assert catalog.entry('RG-WEB-001')['references']
    assert catalog.search()['entries'][0]['tags'] == ['web', 'authz']
    for options in ({'lang': 'fr'}, {'offset': -1}, {'limit': 101}, {'limit': True}, {'q': 'x' * 201}, {'category': []}):
        with pytest.raises(ValueError):
            catalog.search(**options)


def test_template_and_instantiation_keep_guidance_without_approval(isolated_catalog):
    for lang in ('es', 'en', 'pt-BR'):
        template = catalog.template('RG-WEB-001', lang)
        content = template['content']
        assert 'prerequisites' in content['description_md']
        assert 'false_positives' in content['description_md']
        assert 'assessment_notes' in content['description_md']
        assert 'retest' in content['remediation_md']
        assert 'required_evidence' in content['walkthrough'][0]['text_md']
        first = catalog.instantiate('RG-WEB-001', {'objetivo': 'example.test'}, lang)
        second = catalog.instantiate('RG-WEB-001', {'objetivo': 'second.test'}, lang)
        assert first['uid'] != second['uid'] and first['affected'] == 'example.test'
        assert first['verification'] == second['verification'] == 'unverified'
        assert not ({'severity', 'cvss', 'cvss_vector', 'status', 'retests', 'evidence_uids', 'id'} & first.keys())
        assert '{{objetivo}}' not in json.dumps(first)
        assert '{{objetivo}}' in json.dumps(template)
        validate.require_valid({'meta': {}, 'findings': [dict(first, id='F1')]})
    for values in ({}, {'objetivo': ''}, {'objetivo': 'x', 'verification': 'confirmed'}, {'objetivo': 123}, {'objetivo': 'x' * 2001}):
        with pytest.raises(ValueError):
            catalog.instantiate('RG-WEB-001', values)


def test_read_routes_have_no_personal_or_project_side_effects(project):
    client, directory, library = project
    before = (directory / 'engagement.yaml').read_bytes()
    response = client.get('/api/knowledge?lang=pt-BR&limit=1')
    assert response.status_code == 200 and response.headers['Content-Language'] == 'pt-BR'
    assert response.json['total'] == 1
    assert client.get('/api/knowledge/RG-WEB-001?lang=en').json['title'].startswith('en ')
    assert client.get('/api/knowledge/not-found').status_code == 404
    assert client.get('/api/knowledge?limit=bad').status_code == 422
    assert client.get('/api/knowledge?lang=fr').status_code == 422
    assert client.put('/api/knowledge/RG-WEB-001', json={}).status_code == 405
    assert (directory / 'engagement.yaml').read_bytes() == before and not library.exists()


def test_private_copy_is_append_only_and_rejects_stale_revision(project):
    client, directory, library = project
    before = (directory / 'engagement.yaml').read_bytes()
    existing = finding_library.put(library, {'name': 'Private original', 'tags': [], 'content': {'title': 'Private', 'mode': 'vuln'}})
    tag = client.get('/api/library').headers['ETag']
    response = client.post('/api/knowledge/RG-WEB-001/copy', json={'lang': 'en'}, headers={'If-Match': tag})
    assert response.status_code == 200, response.json
    assert response.json['name'].startswith('en ') and response.headers['ETag'] != tag
    current = finding_library.load(library)
    assert current['templates'][0] == existing and len(current['templates']) == 2
    assert client.post('/api/knowledge/RG-WEB-001/copy', json={'lang': 'en'}, headers={'If-Match': tag}).status_code == 409
    assert client.post('/api/knowledge/RG-WEB-001/copy', json={'lang': 'en'}).status_code == 428
    assert len(finding_library.load(library)['templates']) == 2
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_project_insert_respects_report_language_revision_and_pending_state(project):
    client, directory, library = project
    fetched = client.get('/api/projects/knowledge')
    data = fetched.json
    data['meta']['lang'] = 'pt'
    data['findings'] = [{'id': 'F17', 'uid': '12345678-1234-1234-1234-123456789012',
                         'title': 'Existing finding', 'mode': 'vuln', 'verification': 'confirmed'}]
    saved = client.put('/api/projects/knowledge', json=data, headers={'If-Match': fetched.headers['ETag']})
    assert saved.status_code == 200, saved.json
    tag = client.get('/api/projects/knowledge').headers['ETag']
    payload = {'values': {'objetivo': 'fictional.example'}}
    response = client.post('/api/projects/knowledge/knowledge/RG-WEB-001', json=payload,
                           headers={'If-Match': tag, 'X-UI-Language': 'en'})
    assert response.status_code == 200, response.json
    assert response.json['lang'] == 'pt' and response.headers['Content-Language'] == 'pt-BR'
    added = response.json['data']['findings'][-1]
    assert added['id'] == 'F18' and added['title'].startswith('pt ')
    assert added['verification'] == 'unverified' and 'severity' not in added and 'cvss' not in added
    assert 'evidence_uids' not in added and 'retests' not in added
    assert response.json['data']['findings'][0] == data['findings'][0]
    assert response.headers['ETag'] != tag and not library.exists()
    assert client.post('/api/projects/knowledge/knowledge/RG-WEB-001', json=payload, headers={'If-Match': tag}).status_code == 409
    assert len(client.get('/api/projects/knowledge').json['findings']) == 2
    assert client.get('/api/projects/knowledge/history').json
    fresh = response.headers['ETag']
    before = (directory / 'engagement.yaml').read_bytes()
    for invalid in ({'values': {}}, {'values': {'objetivo': 'x'}, 'verification': 'confirmed'}, {'lang': 'fr', **payload}):
        assert client.post('/api/projects/knowledge/knowledge/RG-WEB-001', json=invalid, headers={'If-Match': fresh}).status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before
    explicit = client.post('/api/projects/knowledge/knowledge/RG-WEB-001', json={'lang': 'es', **payload}, headers={'If-Match': fresh})
    assert explicit.status_code == 200 and explicit.json['data']['findings'][-1]['title'].startswith('es ')
    assert explicit.json['data']['meta']['lang'] == 'pt'


def test_catalog_is_bundled_complete_and_works_outside_source_tree(tmp_path):
    """Exercise importlib.resources from a ZIP, the restrictive wheel resource form."""
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    assert 'knowledge' in project['tool']['setuptools']['packages']
    assert 'data/*.json' in project['tool']['setuptools']['package-data']['knowledge']
    assert 'designs' in project['tool']['setuptools']['packages']
    assert '*.yaml' in project['tool']['setuptools']['package-data']['designs']
    archive = tmp_path / 'knowledge-resources.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        for name in ('__init__.py', 'catalog.py', *(f'data/{name}' for name in catalog.FILES)):
            bundle.write(ROOT / 'knowledge' / name, 'knowledge/' + name)
        for name in ('__init__.py', 'report_sections.yaml', 'presets.yaml'):
            bundle.write(ROOT / 'designs' / name, 'designs/' + name)
        bundle.write(ROOT / 'sections.py', 'sections.py')
    code = '''import json,sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from knowledge import catalog
from pathlib import Path
result=catalog.search(lang='pt-BR',limit=100)
assert result['total'] == 90
assert len(result['entries']) == 90
expected={f'RG-{prefix}-{number:03d}' for prefix,count in {'WEB':18,'API':12,'ID':8,'INF':8,'CLD':8,'MOB':6,'AI':30}.items() for number in range(1,count+1)}
assert {row['id'] for row in result['entries']} == expected
assert all(catalog.entry(row['id'],lang)['title'] for row in result['entries'] for lang in ('es','en','pt'))
assert 'knowledge-resources.zip' in str(__import__('knowledge').__file__)
import sections
assert 'knowledge-resources.zip' in sections.__file__
assert sections.load_catalog()['sections'] and sections.preset_sections('client','pt')
assert catalog.instantiate('RG-AI-001',{'objetivo':'fictional.example'},'pt')['verification']=='unverified'
print(json.dumps({'total':result['total'],'revision':result['revision']}))
'''
    result = subprocess.run([sys.executable, '-c', code, str(archive), str(ROOT)], cwd=tmp_path,
                            check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)['total'] == 90
