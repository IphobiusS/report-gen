"""New template families and preservation of single-language personal content."""
from copy import deepcopy
from zipfile import ZipFile

import pytest

import design_library as lib
from design_samples import sample_data
import engine
import export
from provider_branding import provider_mark
from wizard import dump_yaml


NEW_PROFILES = (
    'zeropoint-crto', 'zeropoint-crtl', 'centri-btl1', 'centri-btl2',
    'enterprise-assurance', 'enterprise-incident', 'enterprise-purple-team',
)


@pytest.mark.parametrize('provided,requested', [('en', 'es'), ('es', 'en')])
def test_single_language_personal_sections_survive_creation_and_preview(tmp_path, provided, requested):
    title = 'Investigation scope' if provided == 'en' else 'Alcance de investigación'
    body = 'Preserve the authored evidence register.'
    item = lib.put_personal(tmp_path / 'designs.json', {
        'name': 'One authored language',
        'design': lib.appearance(lib.profile('enterprise-incident')),
        'sections': [{'key': 'single-language', 'title': {provided: title},
                      'body': {provided: body}}, {'key': 'findings'}],
    })
    restored = lib.load_personal(tmp_path / 'designs.json')['templates'][0]
    assert restored == item
    report = lib.new_report(restored, 'Cross-language report', requested)
    assert report['report']['sections'][0] == {
        'key': 'single-language', 'title': title, 'body': body,
    }
    html = engine.render_html(engine.build_env(), report, tmp_path, {}, False, engine.load_lang(requested))
    assert title in html and body in html


def test_catalog_structures_are_bilingual_distinct_and_do_not_invent_results():
    outlines = set()
    for ident in NEW_PROFILES:
        p = lib.profile(ident)
        assert p['guidance']['source'].startswith('https://')
        assert p['guidance']['checked'] == '2026-10-11'
        assert set(p['guidance']['note']) == {'es', 'en'}
        assert p['guidance']['formats'] == ['pdf', 'docx', 'md']
        lib.validate_sections(p['sections'])
        outline = tuple(s['key'] for s in p['sections'])
        assert outline not in outlines
        outlines.add(outline)
        assert outline.count('findings') == 1
        for lang in ('es', 'en'):
            report = lib.new_report(p, 'Audit', lang)
            assert report['findings'] == []
            for s in report['report']['sections']:
                if s['key'] != 'findings':
                    assert s['title'] and s['body'].startswith('TODO: ')
    assert all(lib.profile(p)['purpose'] == 'study'
               for p in ('zeropoint-crto', 'zeropoint-crtl', 'centri-btl1'))


@pytest.mark.parametrize('ident', NEW_PROFILES)
def test_applying_new_family_retains_authored_content_and_has_no_invented_logo(ident, tmp_path):
    original = sample_data(lib.profile('htb-cpts'), lang='en')
    before = deepcopy(original)
    p = lib.profile(ident)
    applied = lib.apply(original, p, 'quiet')
    assert original == before
    assert applied['report'] == original['report']
    assert applied['findings'] == original['findings']
    restored = deepcopy(applied)
    restored['meta']['design'] = original['meta']['design']
    restored['meta']['theme'] = original['meta']['theme']
    assert restored == original
    mark = provider_mark(applied['meta']['design'])
    assert mark['provider'] == p['provider']
    assert mark['svg'] == '' and mark['png'] is None
    html = engine.render_html(engine.build_env(), applied, tmp_path, {}, False, engine.load_lang('en'))
    assert p['provider'] + ' / ' + p['certificate'] in html
    assert 'class="provider-logo"' not in html


def test_word_exports_text_identity_without_optional_provider_logo(tmp_path):
    data = sample_data(lib.profile('enterprise-incident'), lang='en')
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    output = export.export(source, 'docx', tmp_path / 'report.docx')
    with ZipFile(output) as z:
        xml = z.read('word/document.xml').decode()
        assert 'Enterprise / Incident Response' in xml
        assert not any(p.startswith('word/media/') for p in z.namelist())


def test_reviewed_htb_guidance_retains_submission_limits_and_language():
    for p in lib.catalog()['profiles']:
        if p['provider'] != 'HTB':
            continue
        assert 'inglés' in p['guidance']['note']['es']
        assert 'English' in p['guidance']['note']['en']
    cwee = lib.profile('htb-cwee')['guidance']
    assert cwee['formats'] == ['md']
    assert '20 MB' in cwee['note']['es'] and '20 MB' in cwee['note']['en']
    assert 'no cifra' in cwee['note']['es'] and 'does not encrypt' in cwee['note']['en']
