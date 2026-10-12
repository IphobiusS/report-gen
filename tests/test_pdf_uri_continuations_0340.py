"""URI page continuations use exact, disjoint PDF text ranges and line breaks."""
from html import escape

from lxml import html
import pytest

import engine
import export_contract as contract


URI = 'https://bank.example/identity%2Fstaff?next=%253A%2Foffice#fi-fl-st'
UNIT = 'Review ' + URI + ' complete.'


def observed(raw_pages):
    return {'pages': [contract.normal(page) for page in raw_pages],
            'line_edges': [contract._pdf_line_edges(page) for page in raw_pages]}


def verify(units, raw_pages):
    return contract._pdf_present(units, observed(raw_pages), 'párrafo', 'paragraph')


@pytest.mark.parametrize('cut', [1, 8, 28, 29, 30, 42, len(URI) - 1])
def test_exact_uri_can_continue_at_every_kind_of_short_or_encoded_boundary(cut):
    pages = ['Review ' + URI[:cut] + '\nRUNNING FOOTER',
             'RUNNING HEADER\n' + URI[cut:] + ' complete.']
    assert verify([UNIT], pages)[0] == 1
    # A verified chain cannot supply a second occurrence or its own subunit.
    for wanted in ([UNIT, UNIT], [UNIT, URI]):
        with pytest.raises(ValueError, match='PDF'):
            verify(wanted, pages)
    assert verify([UNIT, UNIT], pages + pages)[0] == 2


@pytest.mark.parametrize('kind', ['changed', 'missing', 'case', 'decoded', 'out-of-order',
                                  'middle-page', 'no-line-end', 'no-line-start', 'prefix-word'])
def test_uri_continuation_does_not_repair_or_skip_different_text(kind):
    cut = URI.index('%2F') + 2
    first, last = URI[:cut], URI[cut:]
    pages = ['Review ' + first + '\nFOOTER', 'HEADER\n' + last + ' complete.']
    if kind == 'changed':
        pages[1] = 'HEADER\nX' + last[1:] + ' complete.'
    elif kind == 'missing':
        pages[1] = 'HEADER\n' + last[1:] + ' complete.'
    elif kind == 'case':
        pages[1] = 'HEADER\n' + last.replace('F', 'f', 1) + ' complete.'
    elif kind == 'decoded':
        pages[0] = 'Review ' + first[:-2] + '/\nFOOTER'
        pages[1] = 'HEADER\n' + last[1:] + ' complete.'
    elif kind == 'out-of-order':
        pages.reverse()
    elif kind == 'middle-page':
        pages.insert(1, 'NO CONTINUATION ON THIS PAGE')
    elif kind == 'no-line-end':
        pages[0] = 'Review ' + first + ' UNRELATED\nFOOTER'
    elif kind == 'no-line-start':
        pages[1] = 'HEADER\nUNRELATED ' + last + ' complete.'
    elif kind == 'prefix-word':
        pages[0] = 'NotReview ' + first + '\nFOOTER'
    with pytest.raises(ValueError, match='PDF'):
        verify([UNIT], pages)


def test_prose_words_do_not_gain_character_level_page_matching():
    pages = ['Review ' + URI + ' App\nFOOTER', 'HEADER\nroved']
    with pytest.raises(ValueError, match='PDF'):
        verify(['Review ' + URI + ' Approved'], pages)


def test_distinct_uri_chains_cannot_reuse_shared_prefixes_or_suffixes():
    other = URI.replace('staff', 'admin')
    cut = URI.index('?')
    pages = [URI[:cut] + '\n' + other[:cut] + '\nFOOTER',
             'HEADER\n' + URI[cut:]]
    with pytest.raises(ValueError, match='PDF'):
        verify([URI, other], pages)
    pages[1] += '\n' + other[cut:]
    assert verify([URI, other], pages)[0] == 2


def test_line_offsets_come_only_from_normalized_observed_text():
    raw = '  cafe\u0301\tuno\n  ab\u00adcd\r\nfin  '
    assert contract.normal(raw) == 'café uno abcd fin'
    assert contract._pdf_line_edges(raw) == {'starts': {0, 9, 14}, 'ends': {8, 13, 17}}


@pytest.mark.parametrize('limit', ['_PDF_TEXT_MAX_RANGES', '_PDF_TEXT_MAX_STATES'])
def test_uri_continuation_work_limits_fail_closed(monkeypatch, limit):
    monkeypatch.setattr(contract, limit, 1)
    with pytest.raises(ValueError, match='ambigu') as caught:
        verify([UNIT], ['Review ' + URI[:30] + '\nFOOTER',
                        'HEADER\n' + URI[30:] + ' complete.'])
    assert 'ausente' not in str(caught.value) and 'Missing' not in str(caught.value)


def test_uri_fallback_cannot_materialize_unbounded_partial_or_complete_chains(monkeypatch):
    actual = observed(['Review ' + URI[:30] + '\nFOOTER',
                       'HEADER\n' + URI[30:] + ' complete.'])
    with monkeypatch.context() as bounded:
        bounded.setattr(contract, '_PDF_TEXT_MAX_STATES', 0)
        with pytest.raises(ValueError, match='ambigu'):
            contract._pdf_uri_page_fragments(UNIT, actual['pages'], actual['line_edges'], lambda _n: None)
    work = 0

    def budget(amount):
        nonlocal work
        work += amount
        if work > len(UNIT) + 30:
            contract._pdf_text_check_incomplete()

    with pytest.raises(ValueError, match='ambigu'):
        contract._pdf_uri_page_fragments(UNIT, actual['pages'], actual['line_edges'], budget)


def test_continuation_metric_does_not_count_one_source_unit_twice():
    second = 'Independent ' + URI.replace('staff', 'admin') + ' retained.'
    split = second.index('%2F') + 2
    # The first URI already has a whole-word continuation; only the second
    # needs the URI fallback, which must not recount the first occurrence.
    raw = ['Review ' + URI + '\n' + second[:split] + '\nFOOTER',
           'HEADER\ncomplete.\n' + second[split:]]
    assert verify([UNIT, second], raw) == (2, 2)


def test_real_pdf_continuation_is_verified_and_changed_fragment_rejected(tmp_path, monkeypatch):
    # Inline code participates in the render-only URI hints, like the catalog
    # paragraph that revealed this pre-existing false negative.
    source = ('<html><head><style>@page{size:300px 220px;margin:24px;'
              '@top-center{content:"RUNNING HEADER";font-size:8px}'
              '@bottom-center{content:"RUNNING FOOTER";font-size:8px}}'
              'body{font-family:DejaVu Sans;font-size:11px;line-height:1.3}p{orphans:1;widows:1}'
              '</style></head><body><div style="height:116px"></div>'
              '<p>Review <code>' + escape(URI) + '</code> complete.</p></body></html>')
    expected = contract.from_tree(html.document_fromstring(source))
    target = tmp_path / 'report.pdf'
    engine.render_pdf_weasyprint(source, target, tmp_path)
    result = contract.inspect(target, 'pdf', expected)
    assert result['verification_scope'] == 'text_presence_only'
    assert result['finding_association_checked'] is False
    pages = contract.pdf_text_pages(target)
    assert len(pages) >= 2 and all('RUNNING' in page for page in pages)
    with monkeypatch.context() as old:
        old.setattr(contract, '_pdf_uri_page_fragments', lambda *_args: [])
        with pytest.raises(ValueError, match='PDF'):
            contract.inspect(target, 'pdf', expected)
    changed = source.replace('identity%2Fstaff', 'identity%2fstaff')
    engine.render_pdf_weasyprint(changed, target, tmp_path)
    with pytest.raises(ValueError, match='PDF'):
        contract.inspect(target, 'pdf', expected)
