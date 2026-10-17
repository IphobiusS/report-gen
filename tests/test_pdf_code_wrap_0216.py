"""PDF code presence distinguishes physical wrapping from a literal space.

Structured exports continue to certify literal code. PDF extraction only
certifies presence/order and explicitly requires visual whitespace review.
"""
from copy import deepcopy
import unicodedata

import pytest

import export_contract


CANARY = ('CANARIO-SIMULACION-FARO-NO-EJECUTADO-IDENTIFICADOR-LARGO-PARA-COMPROBAR-'
          'ENVOLTURA-DE-CODIGO-EN-PDF-WORD-Y-HTML-SIN-SECRETOS-REALES')


def contract(code):
    return dict(version=3, cover_units=[], scopes=[dict(
        id='', title='', paragraphs=[], paragraphs_md=[], codes=[code],
        semantic=dict(fields=[]))])


def inspect_text(monkeypatch, tmp_path, source, extracted):
    # These are code-presence unit tests, not PDF reader tests. Isolate the
    # extraction boundary, which now corroborates pypdf with a native reader.
    # Real PDF extraction and separator proofs have separate integration tests.
    # pdf_text_pages returns NFC text with discretionary soft hyphens removed;
    # retain that interface while keeping authored spaces and newlines exact.
    page_text = unicodedata.normalize('NFC', extracted).replace('\u00ad', '')
    monkeypatch.setattr(export_contract, 'pdf_text_pages', lambda _source, **_options: [page_text])
    return export_contract.inspect(tmp_path / 'text-presence.pdf', 'pdf', contract(source))


@pytest.mark.parametrize('separator', ['\n', '\r\n', '\n  ', '\n\t'])
def test_pdf_long_code_token_accepts_only_physical_wrap(monkeypatch, tmp_path, separator):
    extracted = CANARY.replace('EN-PDF', 'EN-' + separator + 'PDF')
    result = inspect_text(monkeypatch, tmp_path, CANARY, extracted)
    assert result['content_units_checked'] == 1
    assert result['pdf_wrapped_code_lines'] == 1
    assert result['literal_code_blocks_checked'] == 0
    assert result['verification_scope'] == 'text_presence_only'
    assert result['manual_review_required'] is True


@pytest.mark.parametrize('changed', [
    CANARY.replace('EN-PDF', 'EN- PDF'),
    CANARY.replace('EN-PDF', 'EN-\tPDF'),
    CANARY.replace('EN-PDF', 'EN\nPDF'),
    CANARY.replace('ENVOLTURA', 'ENVOITURA'),
    CANARY.replace('NO-EJECUTADO', 'EJECUTADO'),
    CANARY.replace('PDF-WORD', 'WORD-PDF'),
])
def test_pdf_wrap_tolerance_rejects_literal_space_and_token_mutations(monkeypatch, tmp_path, changed):
    with pytest.raises(ValueError, match='código PDF'):
        inspect_text(monkeypatch, tmp_path, CANARY, changed)


@pytest.mark.parametrize('source,extracted', [
    ("printf '%s' 'A B'", "printf'%s' 'A B'"),
    ("printf '%s' 'A B'", "printf '%s' 'AB'"),
    ("printf '%s' 'A B'", "printf '%d' 'A B'"),
    ('first_command\nsecond_command', 'second_command\nfirst_command'),
    ('repeated_command\nrepeated_command', 'repeated_command'),
])
def test_pdf_code_source_spaces_punctuation_and_line_order_remain_required(monkeypatch, tmp_path, source, extracted):
    with pytest.raises(ValueError, match='código PDF'):
        inspect_text(monkeypatch, tmp_path, source, extracted)


def test_pdf_multiline_code_preserves_presence_without_claiming_literal_whitespace(monkeypatch, tmp_path):
    source = "  first_command 'A B'\n\tsecond_command --label autorización"
    extracted = "first_command 'A\nB'\nsecond_command --label autorizacio\u0301n"
    result = inspect_text(monkeypatch, tmp_path, source, extracted)
    assert result['content_units_checked'] == 2
    assert result['pdf_wrapped_code_lines'] == 1
    assert result['finding_association_checked'] is False


def test_missing_pdf_code_fails_even_with_unrelated_surrounding_text(monkeypatch, tmp_path):
    extracted = 'Cover and metadata remain.\n' + CANARY[:-1] + '\nA footer.'
    expected = deepcopy(contract(CANARY))
    monkeypatch.setattr(export_contract, 'pdf_text_pages', lambda _source, **_options: [extracted])
    with pytest.raises(ValueError, match='código PDF'):
        export_contract.inspect(tmp_path / 'missing.pdf', 'pdf', expected)


def test_missing_pdf_file_is_not_accepted_by_real_extraction(tmp_path):
    with pytest.raises(FileNotFoundError):
        export_contract.pdf_text_pages(tmp_path / 'absent.pdf')
