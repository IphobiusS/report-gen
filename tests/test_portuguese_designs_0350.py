"""Third-language catalog data must work without translating authored content."""
from copy import deepcopy
from pathlib import Path
import json

import pytest
import yaml

import design_library as lib
from design_samples import sample_data, general_sample_name
import engine

ROOT = Path(__file__).resolve().parents[1]


def localized_nodes(value):
    if isinstance(value, dict):
        if {'es', 'en'} <= value.keys():
            yield value
        for child in value.values():
            yield from localized_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from localized_nodes(child)


def test_catalog_has_explicit_portuguese_for_every_bundled_localized_node():
    for path in ('designs/certifications.json', 'designs/presets.yaml', 'designs/report_sections.yaml'):
        raw = (ROOT / path).read_text(encoding='utf-8')
        data = json.loads(raw) if path.endswith('.json') else yaml.safe_load(raw)
        for node in localized_nodes(data):
            assert isinstance(node.get('pt'), str) and node['pt'].strip(), node
        def suffix_fields(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key.endswith('_en') and key[:-3]+'_es' in value:
                        assert isinstance(value.get(key[:-3]+'_pt'), str) and value[key[:-3]+'_pt'].strip(), (path, key)
                    suffix_fields(child)
            elif isinstance(value, list):
                for child in value:
                    suffix_fields(child)
        suffix_fields(data)


@pytest.mark.parametrize('ident', [p['id'] for p in lib.catalog()['profiles']])
def test_every_portuguese_profile_creates_and_renders_its_own_starter(ident, tmp_path):
    p = lib.profile(ident)
    data = lib.new_report(p, 'Revisão de segurança — órgão fictício', 'pt-BR')
    assert data['meta']['lang'] == 'pt'
    assert data['meta']['branding']['confidential_text'] == 'CONFIDENCIAL'
    assert not data['findings']
    for template, section in zip(p['sections'], data['report']['sections']):
        for key in ('title', 'body'):
            if key in template:
                assert section[key] == template[key]['pt']
    assert lib.guidance(data)['note'] == p['guidance']['note']['pt']
    html = engine.render_html(engine.build_env(), data, tmp_path, {}, False, engine.load_lang('pt'))
    assert '<html lang="pt-BR"' in html
    assert 'Revisão de segurança' in html


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_portuguese_only_personal_content_survives_storage_and_other_report_languages(tmp_path, lang):
    original = {'key': 'custodia', 'title': {'pt': 'Custódia da evidência'},
                'body': {'pt': 'Ação autorizada. URL literal https://example.test/ação?q=órgão'}}
    entry = lib.put_personal(tmp_path / 'designs.json', {
        'name': 'Investigação própria', 'design': lib.appearance(lib.profile('enterprise-incident')),
        'sections': [original, {'key': 'findings'}],
    })
    assert lib.load_personal(tmp_path / 'designs.json')['templates'][0]['sections'][0] == original
    report = lib.new_report(entry, 'Relatório', lang)
    assert report['report']['sections'][0] == {key: value['pt'] if isinstance(value, dict) else value for key, value in original.items()}


def test_portuguese_preview_is_fictional_localized_and_does_not_mutate_profile():
    profile = lib.profile('enterprise-control-review')
    before = deepcopy(profile)
    data = sample_data(profile, 'quiet', 'pt-BR')
    assert profile == before
    assert data['meta']['report_title'] == 'Avaliação de segurança'
    assert data['meta']['report_subtitle'] == 'Revisão de controles / Amostra fictícia'
    assert 'Nenhum cliente foi avaliado.' in data['report']['sections'][0]['body']
    technical = data['report']['sections'][1]['body']
    assert 'sha256sum ./evidence/session.txt' in technical
    assert '| Evidência | Origem | Estado |' in technical
    assert general_sample_name('laboratorio', 'pt-BR') == 'Laboratório'


@pytest.mark.parametrize('lang', ['fr', None, {'pt': True}])
def test_unknown_preview_language_is_rejected_instead_of_spanish_fallback(lang):
    with pytest.raises(ValueError):
        sample_data(lib.profile('offsec-oscp'), lang=lang)


def test_exam_submission_language_is_not_changed_by_portuguese_ui_support():
    for profile in lib.catalog()['profiles']:
        if profile['provider'] == 'HTB':
            assert 'relatórios em inglês' in profile['guidance']['note']['pt']
