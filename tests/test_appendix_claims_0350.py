"""Automatic appendix prose describes records without claiming unproved access."""
from copy import deepcopy

from lxml import html
import pytest

import delivery
import engine
import export
import export_contract
from wizard import dump_yaml


INTRO = {
    'es': 'Este apéndice reúne las referencias a artefactos documentadas en el informe. '
          'Su inclusión no acredita acceso, recolección ni validación; deben leerse junto '
          'a las evidencias, los estados de verificación y las limitaciones de cada registro.',
    'en': 'This appendix gathers the artifact references documented in the report. '
          'Inclusion does not establish access, collection or validation; read each reference '
          'alongside the evidence, verification status and limitations of its record.',
    'pt': 'Este apêndice reúne as referências a artefatos documentadas no relatório. '
          'A inclusão não comprova acesso, coleta nem validação; cada referência deve ser '
          'lida junto às evidências, ao estado de verificação e às limitações de seu registro.',
}
OLD_CLAIMS = (
    'Los siguientes artefactos se recolectaron como evidencia de acceso',
    'The following artifacts were collected as evidence of access',
    'Os artefatos a seguir foram coletados como evidência de acesso',
)
NOTE = 'AUTHOR_NOTE_CANARY: collection and access remain unverified.'


def document(language, *, legacy=False):
    data = {
        'meta': {'lang': language, 'report_title': 'Synthetic appendix audit', 'theme': 'serio'},
        'findings': [{
            'id': 'M01', 'mode': 'machine', 'title': 'Synthetic unverified host',
            'verification': 'unverified', 'host': {'name': 'SYNTHETIC_HOST', 'ip': '192.0.2.80'},
            'proof': [
                {'name': 'reference.txt', 'value': 'REFERENCE_VALUE_CANARY'},
                {'name': 'authored.txt', 'value': 'AUTHORED_VALUE_CANARY', 'notes': NOTE},
            ],
        }],
    }
    if not legacy:
        data['report'] = {'sections': [{'key': 'findings'}, {'key': 'appendix'}]}
    return data


def check_text(text, language):
    normalized = export_contract.normal(text)
    assert INTRO[language] in normalized
    assert not any(claim in normalized for claim in OLD_CLAIMS)
    assert 'REFERENCE_VALUE_CANARY' in normalized
    assert 'AUTHORED_VALUE_CANARY' in normalized
    assert NOTE in normalized
    if language == 'es':
        assert 'Archivo de evidencia en el objetivo' in normalized
        assert 'Proof file on target' not in normalized
        assert 'CONFIDENCIAL' in normalized
        assert 'CONFIDENTIAL' not in normalized


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_four_exports_describe_unverified_references_without_claiming_access(tmp_path, language, fmt):
    data = document(language)
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    original = source.read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'capture')
    artifact = export.export(source, fmt, tmp_path / ('appendix.' + ('zip' if fmt == 'md' else fmt)))
    delivery.inspect_export(artifact, fmt, captured)
    profiles = export_contract.profile(artifact, fmt, {'scopes': []})
    text = ' '.join(row['text'] for row in profiles.values())
    text = (html.document_fromstring(artifact.read_text(encoding='utf-8')).text_content()
            if fmt == 'html' else profiles['']['cover_text'] + ' ' + text)
    check_text(text, language)
    assert source.read_bytes() == original


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_legacy_html_appendix_uses_the_same_neutral_prose_without_rewriting_notes(tmp_path, language):
    data = document(language, legacy=True)
    original = deepcopy(data)
    markup = engine.render_html(engine.build_env(), data, tmp_path, {}, False, engine.load_lang(language))
    check_text(html.document_fromstring(markup).text_content(), language)
    assert data == original


def test_explicit_confidentiality_label_remains_authored_content(tmp_path):
    data = document('es')
    data['meta']['branding'] = {'confidential_text': 'AUTHOR_CONFIDENTIALITY_CANARY'}
    markup = engine.render_html(engine.build_env(), data, tmp_path, {}, False, engine.load_lang('es'))
    assert 'AUTHOR_CONFIDENTIALITY_CANARY' in html.document_fromstring(markup).text_content()
