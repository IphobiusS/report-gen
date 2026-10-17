"""Starter packages create isolated pending work, never claimed assessment results."""
from copy import deepcopy
import json
import pytest

import app as webapp
from knowledge import catalog, work_packages
import project_history
import validate
import workflows
from _support import auth_client


@pytest.fixture
def package_catalog(monkeypatch):
    entries = []
    for prefix, category in catalog.PREFIXES.items():
        entries.append({'id': f'RG-{prefix}-001', 'category': category, 'tags': [category], 'cwe': '',
                        'reviewed_on': '2026-10-17', 'references': [{'title': 'Source', 'url': 'https://owasp.org/',
                        'version': 'test', 'accessed_on': '2026-10-17'}], 'mappings': [],
                        'locales': {lang: {field: lang + ' ' + field + ' {{objetivo}}' for field in catalog.LOCALE_FIELDS}
                                    for lang in ('es', 'en', 'pt')}})
    document = catalog.validate_documents([{'format': 'report-gen-knowledge', 'schema_version': 1,
                                             'revision': 'test', 'entries': entries}])
    monkeypatch.setattr(catalog, '_bundled', lambda: document)
    return document


@pytest.mark.parametrize('lang', ['es', 'en', 'pt-BR'])
@pytest.mark.parametrize('category', catalog.CATEGORIES)
def test_every_package_is_localized_pending_and_unrated(package_catalog, tmp_path, category, lang):
    detail = work_packages.package(category, lang)
    data = work_packages.project(category, lang=lang)
    assert data['meta']['lang'] == catalog.language(lang)
    assert data['findings'] == [] and data['test_cases']
    assert data['meta']['scope'] == [] and data['meta']['assessor'] == ''
    assert data['test_cases'][0]['status'] == 'pending'
    assert not data['test_cases'][0].get('observed')
    assert all(not data['test_cases'][0][key] for key in ('evidence_uids', 'http_evidence_uids', 'asset_uids', 'finding_uids'))
    selected = work_packages.project(category, lang=lang, finding_ids=[detail['entries'][0]['id']])
    finding = selected['findings'][0]
    assert finding['verification'] == 'unverified'
    assert 'severity' not in finding and 'cvss' not in finding and 'retests' not in finding
    assert finding['affected'] == '{{objetivo}}'
    assert selected['test_cases'][0]['finding_uids'] == [finding['uid']]
    assert selected['test_cases'][0]['status'] == 'pending'
    validate.require_valid(selected)
    issues = workflows.review(selected, tmp_path, catalog.language(lang))
    assert any('{{objetivo}}' in issue['message'] for issue in issues)
    assert work_packages.project(category, lang=lang, finding_ids=None)['findings'] == []
    assert not ({'evidence', 'coverage', 'http_evidence'} & data.keys())


@pytest.mark.parametrize('selection', [True, 'RG-WEB-001', {}, ['RG-AI-001'], ['RG-WEB-001'] * 2, [None], [['RG-WEB-001']]])
def test_invalid_or_cross_category_selection_is_rejected(package_catalog, selection):
    with pytest.raises(ValueError):
        work_packages.project('web', finding_ids=selection)


def test_package_and_lesson_reads_are_copied_and_complete(package_catalog):
    assert len(work_packages.packages()['packages']) == 7
    for lang in ('es', 'en', 'pt'):
        lesson = work_packages.example(lang)
        assert lesson['readonly'] and lesson['fictional']
        assert len(lesson['lessons']) == len({row['id'] for row in lesson['lessons']}) == 9
        assert all(row['title'] and row['text'] for row in lesson['lessons'])
        lesson['lessons'].clear()
        assert len(work_packages.example(lang)['lessons']) == 9
    detail = work_packages.package('web')
    detail['entries'].clear()
    assert work_packages.package('web')['entries']
    for options in ({'title': []}, {'client': False}, {'title': 'x' * 501}, {'lang': 'fr'}):
        with pytest.raises(ValueError):
            work_packages.project('web', **options)


@pytest.fixture
def client(tmp_path, monkeypatch, package_catalog):
    projects = tmp_path / 'projects'
    projects.mkdir()
    monkeypatch.setattr(webapp, 'PROJECTS', projects)
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path / 'library.json'))
    result = auth_client(webapp.app)
    response = result.post('/api/projects', json={'slug': 'original', 'title': 'Untouched original'})
    assert response.status_code == 200, response.json
    return result, projects


@pytest.mark.parametrize('lang', ['es', 'en', 'pt-BR'])
def test_new_project_creation_preserves_existing_and_defaults_to_no_findings(client, lang):
    browser, projects = client
    before = (projects / 'original' / 'engagement.yaml').read_bytes()
    response = browser.post('/api/work-packages/web/projects', json={'lang': lang, 'title': 'Prepared work', 'client': 'Example'})
    assert response.status_code == 200, response.json
    assert response.headers['Content-Language'] == ('pt-BR' if lang == 'pt-BR' else lang)
    assert response.json['test_count'] == 1 and response.json['finding_count'] == 0
    slug = response.json['slug']
    assert slug.startswith('work-web-') and slug != 'original'
    stored = browser.get('/api/projects/' + slug).json
    assert stored['meta']['report_title'] == 'Prepared work' and stored['meta']['client'] == 'Example'
    assert stored['meta']['lang'] == catalog.language(lang)
    assert (projects / slug / 'img').is_dir()
    assert stored['findings'] == [] and stored['test_cases'][0]['status'] == 'pending'
    assert (projects / 'original' / 'engagement.yaml').read_bytes() == before


def test_explicit_findings_and_failures_never_modify_customer_project(client, monkeypatch):
    browser, projects = client
    before = (projects / 'original' / 'engagement.yaml').read_bytes()
    assert browser.get('/api/work-packages?lang=pt-BR').json['lang'] == 'pt'
    assert browser.get('/api/work-packages/example?lang=en').json['readonly']
    assert browser.get('/api/work-packages/web?lang=en').status_code == 200
    assert browser.get('/api/work-packages/unknown').status_code == 404
    assert browser.get('/api/work-packages?lang=fr').status_code == 422
    assert {path.name for path in projects.iterdir()} == {'original'}
    assert webapp.app.test_client().post('/api/work-packages/web/projects', json={}).status_code == 403
    for payload in ({'finding_ids': ['RG-AI-001']}, {'finding_ids': ['RG-WEB-001', 'RG-WEB-001']},
                    {'slug': 'original'}, {'lang': 'fr'}, {'title': []}, {'finding_ids': [None]}):
        assert browser.post('/api/work-packages/web/projects', json=payload).status_code == 422
    assert {path.name for path in projects.iterdir()} == {'original'}
    response = browser.post('/api/work-packages/web/projects', json={'lang': 'en', 'finding_ids': ['RG-WEB-001']})
    assert response.status_code == 200, response.json
    created = browser.get('/api/projects/' + response.json['slug']).json
    assert created['findings'][0]['verification'] == 'unverified'
    assert created['findings'][0]['affected'] == '{{objetivo}}'
    assert created['test_cases'][0]['finding_uids'] == [created['findings'][0]['uid']]
    prior_paths = {path.name for path in projects.iterdir()}
    def fail_save(*args, **kwargs):
        raise ValueError('Synthetic storage failure before commit')
    monkeypatch.setattr(project_history, 'save', fail_save)
    assert browser.post('/api/work-packages/ai/projects', json={}).status_code == 422
    assert {path.name for path in projects.iterdir()} == prior_paths
    assert (projects / 'original' / 'engagement.yaml').read_bytes() == before


def test_real_packages_cover_all_ninety_patterns_and_preserve_unrated_status():
    """Full bundle acceptance, independent of the small contract-test fixture."""
    for lang in ('es', 'en', 'pt'):
        total = 0
        for package in work_packages.packages(lang)['packages']:
            identities = [entry['id'] for entry in package['entries']]
            data = work_packages.project(package['id'], lang=lang, finding_ids=identities)
            assert len(data['findings']) == len(data['test_cases']) == len(identities)
            assert all(finding['verification'] == 'unverified' and 'severity' not in finding and 'cvss' not in finding
                       for finding in data['findings'])
            assert all(row['status'] == 'pending' and not row.get('observed') and not row['evidence_uids'] for row in data['test_cases'])
            validate.require_valid(data)
            original = deepcopy(data)
            data['findings'][0]['description_md'] = 'User edit'
            assert catalog.entry(identities[0], lang)['description_md'] != 'User edit'
            assert '{{objetivo}}' in json.dumps(original)
            total += len(identities)
        assert total == 90
