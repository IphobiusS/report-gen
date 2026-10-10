"""Legacy sources without a language keep engine's historical English fallback."""
from copy import deepcopy
from lxml import html
import pytest

import delivery
import export
import export_contract
import publication
import validate
from wizard import dump_yaml


def document(language, sections):
    data = {'meta': {'report_title': 'Legacy language contract', 'theme': 'serio'},
            'assets': [{'name': 'Documented asset canary', 'target': 'https://scope.example'}],
            'coverage': [{'test': 'Unexecuted test canary', 'status': 'pending', 'notes': 'Synthetic; not executed.'}],
            'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'LANGUAGE_FINDING_CANARY', 'severity': 'info', 'cvss': 0,
                          'description_md': 'Documentary synthetic condition.', 'owner': 'Synthetic team'}]}
    if language != 'absent': data['meta']['lang'] = None if language == 'null' else ''
    if sections: data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    return data


@pytest.mark.parametrize('language', ['absent', 'null', 'empty'])
@pytest.mark.parametrize('sections', [False, True])
def test_legacy_language_is_consistent_in_rendered_body_and_dom(language, sections, tmp_path):
    data = document(language, sections)
    before = deepcopy(data)
    errors = [m for lev, m in validate.validate(data) if lev == 'error']
    if language == 'empty': assert any('lang' in m for m in errors)
    else: assert not errors
    tree = publication.render(data, tmp_path)
    text = tree.text_content()
    assert tree.get('lang') == 'en'
    assert 'Assessed assets' in text and 'Coverage and limitations' in text
    assert 'Remediation tracking and retest' in text
    assert 'Activos evaluados' not in text and 'Resumen de hallazgos' not in text
    assert data == before


@pytest.mark.parametrize('language', ['absent', 'null'])
@pytest.mark.parametrize('sections', [False, True])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_legacy_language_keeps_one_fallback_through_capture_and_four_exports(language, sections, fmt, tmp_path):
    data = document(language, sections)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'captured')
    artifact = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('legacy.' + ('zip' if fmt == 'md' else fmt)))
    text = export_contract.profile(artifact, fmt)['text']
    assert 'Assessed assets' in text and 'Coverage and limitations' in text
    assert 'Activos evaluados' not in text and 'Cobertura y limitaciones' not in text
    assert 'Documented asset canary' in text and 'Unexecuted test canary' in text
    if fmt == 'html':
        tree = html.document_fromstring(artifact.read_text())
        assert tree.get('lang') == 'en'
        assert tree.xpath('//nav/@aria-label') == ['Report reading']
    delivery.inspect_export(artifact, fmt, captured)
    assert (tmp_path / 'engagement.yaml').read_bytes() == source


@pytest.mark.parametrize('language,expected', [('es', 'Activos evaluados'), ('en', 'Assessed assets')])
def test_explicit_language_is_never_replaced_by_fallback(language, expected, tmp_path):
    data = document('absent', True); data['meta']['lang'] = language
    before = deepcopy(data)
    tree = publication.render(data, tmp_path)
    assert tree.get('lang') == language
    assert expected in tree.text_content()
    assert data == before


@pytest.mark.parametrize('sections', [False, True])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_empty_language_keeps_existing_final_validation_error_without_replacing_output(sections, fmt, tmp_path):
    data = document('empty', sections)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    output = tmp_path / ('existing.' + ('zip' if fmt == 'md' else fmt))
    output.write_bytes(b'EXISTING_ARTIFACT_CANARY')
    with pytest.raises(ValueError, match='lang'):
        export.export(tmp_path / 'engagement.yaml', fmt, output)
    assert output.read_bytes() == b'EXISTING_ARTIFACT_CANARY'
    assert (tmp_path / 'engagement.yaml').read_bytes() == source
