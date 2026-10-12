"""PDF heading occurrences are counted without reusing their physical text."""
from html import escape

from lxml import html
import pytest
from weasyprint import HTML

import export_contract as contract


def document(body, language='en'):
    return (f'<html lang="{language}"><head><style>'
            '@page{size:A4;margin:40px}body{font-family:DejaVu Sans}'
            'h2{width:200px;overflow-wrap:anywhere;font-size:14px}'
            '</style></head><body>' + body + '</body></html>')


def headings(values, kinds):
    result = []
    for index, (value, kind) in enumerate(zip(values, kinds)):
        if kind == 'finding':
            result.append(f'<section class="finding" id="F{index}">'
                          '<h2 class="f-title">' + escape(value) + '</h2></section>')
        else:
            result.append('<h2 data-rg-authored-heading="true">' + escape(value) + '</h2>')
    return ''.join(result)


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('values', [
    ['Approval gate', 'Approval gate'],
    ['Approved', 'Approved with conditions'],
    ['control alpha', 'alpha beta'],
])
@pytest.mark.parametrize('kinds', [
    ['authored', 'authored'], ['finding', 'finding'], ['authored', 'finding'],
])
def test_actual_pdf_requires_disjoint_heading_occurrences(tmp_path, language, values, kinds):
    source = document(headings(values, kinds), language)
    expected = contract.from_tree(html.document_fromstring(source))
    path = tmp_path / 'headings.pdf'
    HTML(string=source).write_pdf(path)
    result = contract.inspect(path, 'pdf', expected)
    assert result['authored_headings_checked'] == kinds.count('authored')
    assert result['finding_association_checked'] is False
    assert result['verification_scope'] == 'text_presence_only'

    # Recreate a PDF with actual visible content removed or overlapping. No
    # extractor, expected-value profile or allocator is mocked by this test.
    changed = ['control alpha beta'] if values[0] == 'control alpha' else values[1:]
    HTML(string=document(headings(changed, kinds[-1:]), language)).write_pdf(path)
    with pytest.raises(ValueError, match='encabezado|heading'):
        contract.inspect(path, 'pdf', expected)


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('title', [
    'artifact-' + '0123456789abcdef' * 12,
    'https://bank.example/control/' + '0123456789abcdef' * 12 + '?state=pending',
])
def test_actual_pdf_accepts_complete_wrapped_finding_title_but_not_lost_letter(tmp_path, language, title):
    source = document(headings([title], ['finding']), language)
    expected = contract.from_tree(html.document_fromstring(source))
    path = tmp_path / 'title.pdf'
    HTML(string=source).write_pdf(path)
    observed = contract.pdf_text_pages(path)
    assert title not in contract.normal(' '.join(observed))
    assert ''.join(''.join(observed).split()) == title
    result = contract.inspect(path, 'pdf', expected)
    assert result['content_units_checked'] == 1
    changed = title[:73] + title[74:]
    HTML(string=document(headings([changed], ['finding']), language)).write_pdf(path)
    with pytest.raises(ValueError, match='encabezado|heading'):
        contract.inspect(path, 'pdf', expected)


def test_pdf_heading_allocation_retains_fail_closed_work_limit(tmp_path, monkeypatch):
    source = document(headings(['Approval gate'], ['authored']))
    path = tmp_path / 'heading.pdf'
    HTML(string=source).write_pdf(path)
    expected = contract.from_tree(html.document_fromstring(source))
    monkeypatch.setattr(contract, '_PDF_TEXT_MAX_STATES', 0)
    with pytest.raises(ValueError, match='ambigu'):
        contract.inspect(path, 'pdf', expected)
