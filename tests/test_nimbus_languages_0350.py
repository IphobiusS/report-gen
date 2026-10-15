"""Localized fictional demos: real import, full graph, portable outputs and strict API."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import runpy
import zipfile

import pytest

import app as webapp
import delivery
import engine
import export
import project_history
import resources
import validate
import workflows
from _support import auth_client
from input_guard import load_yaml

ROOT = Path(__file__).resolve().parents[1]
LOCALIZED_KEYS = {'lang', 'report_title', 'report_subtitle', 'client', 'assessor_title', 'byline',
                  'description', 'title', 'body', 'author', 'notes', 'distribution', 'summary', 'posture',
                  'objectives', 'assumptions', 'approach', 'standards', 'information_gathering',
                  'exploitation', 'cleanup', 'narrative', 'overview', 'short_term', 'medium_term',
                  'long_term', 'changes_cleanup', 'tools_used', 'glossary', 'description_md',
                  'impact_md', 'remediation_md', 'lead', 'text_md', 'caption', 'short_md',
                  'medium_md', 'long_md', 'owner', 'assessor', 'notes_md', 'kind', 'test', 'limitations_md'}


def leaves(value, path=()):
    if isinstance(value, dict):
        return {p: v for key, child in value.items() for p, v in leaves(child, (*path, key)).items()}
    if isinstance(value, list):
        return {p: v for key, child in enumerate(value) for p, v in leaves(child, (*path, key)).items()}
    return {path: value}


def source(lang):
    suffix = '' if lang == 'es' else '-' + lang
    return ROOT / 'examples' / f'nimbus-demo-project{suffix}.zip'


def document(lang):
    with zipfile.ZipFile(source(lang)) as archive:
        return load_yaml(archive.read('engagement.yaml'))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path / 'projects')
    webapp.PROJECTS.mkdir()
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path / 'library.json'))
    return auth_client(webapp.app)


@pytest.mark.parametrize('requested,expected', [('es', 'es'), ('en', 'en'), ('pt', 'pt'),
                                               ('pt-BR', 'pt'), (' PT-br ', 'pt')])
def test_demo_selects_authored_locale_and_preserves_other_projects(client, requested, expected):
    original = client.post('/api/demo', json={}).get_json()['slug']
    before = client.get('/api/projects/' + original).get_json()
    response = client.post('/api/demo', json={'lang': requested})
    assert response.status_code == 200, response.get_json()
    slug = response.get_json()['slug']
    assert slug != original
    actual = client.get('/api/projects/' + slug).get_json()
    expected_document = document(expected)
    workflows.normalize(expected_document)
    assert actual == expected_document
    assert actual['meta']['lang'] == expected
    assert client.get('/api/projects/' + original).get_json() == before
    assert len(list((webapp.PROJECTS / slug / 'img').iterdir())) == 19


@pytest.mark.parametrize('body', [{'lang': 'fr'}, {'lang': ''}, {'lang': None}, {'lang': 1},
                                 {'lang': []}, {'lang': {}}, {'lang': '../../en'},
                                 {'lang': 'en', 'source': 'elsewhere.zip'}])
def test_invalid_demo_locale_does_not_create_a_project(client, body):
    before = set(webapp.PROJECTS.iterdir())
    assert client.post('/api/demo', json=body).status_code == 422
    assert set(webapp.PROJECTS.iterdir()) == before


@pytest.mark.parametrize('lang', ['en', 'pt'])
def test_localized_editions_preserve_all_structure_relationships_and_literal_references(lang):
    original, actual = document('es'), document(lang)
    base, translated = leaves(original), leaves(actual)
    assert translated.keys() == base.keys()
    for path, value in base.items():
        if path[-1] not in LOCALIZED_KEYS:
            assert translated[path] == value, path
    def urls(data):
        return {url.rstrip('.,;)') for value in leaves(data).values() if isinstance(value, str)
                for url in re.findall(r'https?://[^\s<>`]+', value)}
    assert urls(actual) == urls(original)
    # Editorial prose can be reformulated, but code spans and stated CVSS
    # conditions must remain literal rather than becoming translated labels.
    for pattern in (r'`([^`]+)`', r'\b(?:AV|AC|PR|UI|S|C|I|A):[A-Z]\b'):
        literals = lambda data: {token for value in leaves(data).values() if isinstance(value, str)
                                 for token in re.findall(pattern, value)}
        assert literals(actual) == literals(original)
    assert len(actual['findings']) == 12
    assert len(actual['assets']) == 8
    assert len(actual['evidence']) == 18
    assert len(actual['coverage']) == 22
    assert sum(len(item['retests']) for item in actual['findings']) == 6
    assert all(len(item['walkthrough']) == 5 for item in actual['findings'])
    assert resources.referenced_images(actual) == resources.referenced_images(original)
    assert len(resources.referenced_images(actual)) == 19
    assert actual['meta']['assessor'] == original['meta']['assessor']
    assert actual['meta']['lang'] == lang
    assert ('localized editorial edition' if lang == 'en' else 'edição editorial localizada') in actual['report']['sections'][0]['body'].lower()
    validate.require_valid(actual, final=True)
    for finding in actual['findings']:
        assert all(finding[field].strip() for field in ('description_md', 'impact_md', 'remediation_md'))
        assert finding['title'] != original['findings'][int(finding['id'][1:]) - 1]['title']


@pytest.mark.parametrize('lang', ['en', 'pt'])
def test_committed_locale_bundle_rebuilds_exactly_and_has_valid_manifest(lang):
    builder = runpy.run_path(str(ROOT / 'scripts/build-nimbus-translations.py'))
    blob = builder['build'](lang)
    assert blob == source(lang).read_bytes()
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert set(manifest['files']) == set(archive.namelist()) - {'manifest.json'}
        assert len(manifest['files']) == 20
        for name, digest in manifest['files'].items():
            assert sha256(archive.read(name)).hexdigest() == digest
        # Localized copies must not bring the Spanish original back through history.
        assert not any(name.startswith('history/') for name in archive.namelist())


@pytest.mark.parametrize('lang', ['en', 'pt'])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_complete_localized_demo_exports_without_modifying_source(tmp_path, lang, fmt):
    directory = tmp_path / 'project'
    project_history.import_bundle(source(lang).read_bytes(), directory)
    original = deepcopy(engine.load_engagement(directory / 'engagement.yaml'))
    captured = delivery.capture(directory, tmp_path / 'capture')
    destination = tmp_path / ('nimbus.' + ('zip' if fmt == 'md' else fmt))
    artifact = export.export(directory / 'engagement.yaml', fmt, destination)
    checks = delivery.inspect_export(artifact, fmt, captured)
    assert checks['images_verified' if fmt == 'md' else 'image_placements'] >= 19
    assert engine.load_engagement(directory / 'engagement.yaml') == original
