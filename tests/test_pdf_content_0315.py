"""PDF text presence includes authored lists and table cells, without structural claims."""
from copy import deepcopy

from lxml import html
import pytest

import engine
import export_contract


def source(markdown, language='en'):
    return {'meta': {'lang': language, 'report_title': 'Synthetic PDF content test'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'title': 'Synthetic observation',
                          'description_md': markdown}]}


def render(data, folder, name):
    markup = engine.render_html(engine.build_env(), data, folder, {}, False,
                                engine.load_lang(data['meta']['lang']))
    path = folder / (name + '.pdf')
    engine.render_pdf_weasyprint(markup, path, folder)
    return path, export_contract.from_tree(html.document_fromstring(markup))


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('kind,original,changed', [
    ('list', '- First control\n- Second control\n- Third control',
     '- First control\n- CHANGED control\n- Third control'),
    ('list', '- First control\n- Second control\n- Third control',
     '- First control\n- Third control'),
    ('list', '- Repeated item\n- Repeated item', '- Repeated item'),
    ('list', '- First control', '- First controller'),
    ('paragraph', 'Approved', 'NotApproved'),
    ('paragraph', 'First control', 'First controller'),
    ('table', '| Control | Result |\n| --- | --- |\n| First | Approved |',
     '| Control | Result |\n| --- | --- |\n| First | NotApproved |'),
    ('table', '| Control | Result |\n| --- | --- |\n| First | Approved |\n| Second | Denied |',
     '| Control | Result |\n| --- | --- |\n| First | Approved |\n| Second | CHANGED |'),
    ('table', '| Control | Result |\n| --- | --- |\n| First | Repeated cell |\n| Second | Repeated cell |',
     '| Control | Result |\n| --- | --- |\n| First | Repeated cell |\n| Second | Replacement |'),
])
def test_changed_or_removed_pdf_list_items_and_cells_are_rejected(tmp_path, language, kind, original, changed):
    data = source(original, language)
    path, expected = render(data, tmp_path, 'original')
    export_contract.inspect(path, 'pdf', expected)
    altered = deepcopy(data)
    altered['findings'][0]['description_md'] = changed
    path, _ = render(altered, tmp_path, 'changed')
    with pytest.raises(ValueError, match='[Ll]ista|[Ll]ist|[Tt]abla|[Tt]able|[Pp]árrafo|[Pp]aragraph'):
        export_contract.inspect(path, 'pdf', expected)


def test_pdf_presence_records_do_not_claim_table_or_list_structure(tmp_path):
    data = source('| Control | Result |\n| --- | --- |\n| First | Approved |\n\n'
                  '1. Parent one\n    1. Nested first\n    2. Nested second\n2. Parent two')
    path, expected = render(data, tmp_path, 'nested')
    checks = export_contract.inspect(path, 'pdf', expected)
    assert checks['pdf_table_cells_checked'] == 4
    assert checks['pdf_list_items_checked'] == 4
    assert checks['authored_tables_checked'] == 0
    assert checks['authored_list_items_order_checked'] == 0
    assert checks['verification_scope'] == 'text_presence_only'
    assert checks['manual_review_required'] is True


@pytest.mark.parametrize('language,theme', [('en', 'corporativo'), ('es', 'ejecutivo'), ('en', 'laboratorio')])
def test_long_pdf_code_keeps_wrapped_logical_lines_together(tmp_path, language, theme):
    lines = [f'RECORD_{i:03d}=' + '0123456789abcdef' * 10 for i in range(100)]
    data = source('```text\n' + '\n'.join(lines) + '\n```', language)
    data['meta']['theme'] = theme
    path, expected = render(data, tmp_path, 'long-code')
    checks = export_contract.inspect(path, 'pdf', expected)
    pages = export_contract.pdf_text_pages(path)
    assert checks['pdf_wrapped_code_lines'] == 100
    # Each complete original line belongs to one physical page, so no footer
    # can be mistaken for a piece of an assessment command.
    for line in lines:
        matching = []
        for index, text in enumerate(pages):
            try:
                export_contract._pdf_code_lines(line, text)
                matching.append(index)
            except ValueError:
                pass
        assert len(matching) == 1
    assert len(pages) < 9  # No heading-only pages left by an indivisible pre.


@pytest.mark.parametrize('language', ['es', 'en'])
def test_one_code_line_taller_than_a_page_preserves_previous_output(tmp_path, language):
    data = source('```text\n' + '0123456789abcdef' * 1300 + '\n```', language)
    markup = engine.render_html(engine.build_env(), data, tmp_path, {}, False,
                                engine.load_lang(language))
    path = tmp_path / 'prior.pdf'
    path.write_bytes(b'previous verified output')
    with pytest.raises(ValueError, match='[Cc]ode|código'):
        engine.render_pdf_weasyprint(markup, path, tmp_path)
    assert path.read_bytes() == b'previous verified output'


@pytest.mark.parametrize('unit,pages,count', [
    ('A B C', ['A B C footer A B C'], 2),
    ('A B C', ['A B footer', 'C header A B footer', 'C'], 2),
    ('A B C', ['A B footer', 'C'], 1),
    ('A B C', ['A B footer', 'C header A B footer', 'D'], 1),
    ('A B C', ['A B footer', 'C header A B footer'], 1),
    ('A B C', ['A B footer', 'Unrelated page', 'C'], 0),
    ('A B C', ['A footer', 'B footer', 'C'], 1),
    ('A B C', ['A B', 'C A B C'], 2),
    ('A B C', ['A B', 'A B C C'], 1),
    ('A B C', ['A BC'], 0),
    ('alpha beta', ['a l p h a footer', 'b e t a'], 1),
    ('Approved', ['NotApproved'], 0),
    ('First control', ['First controller'], 0),
    ('recovery assurance', ['reco', 'very assurance recovery footer', 'assurance'], 2),
    ('recovery assurance', ['reco', '', 'very assurance'], 0),
])
def test_pdf_occurrences_use_real_nonoverlapping_adjacent_ranges(unit, pages, count):
    found = export_contract._pdf_occurrences(unit, pages)
    assert len(found) == count
    prior = (-1, 0)
    for ranges in found:
        assert (ranges[0][0], ranges[0][1]) >= prior
        assert all(end > start for page, start, end in ranges)
        assert all(b[0] == a[0] + 1 for a, b in zip(ranges, ranges[1:]))
        prior = ranges[-1][0], ranges[-1][2]


@pytest.mark.parametrize('kind', ['li', 'p'])
@pytest.mark.parametrize('mutation', ['none', 'delete', 'alter', 'truncate'])
def test_repeated_pdf_units_cross_pages_without_reusing_one_occurrence(tmp_path, kind, mutation):
    from weasyprint import HTML

    unit = ' '.join(f'word{i:03}' for i in range(125))
    style = ('<style>@page {size:140mm 110mm;margin:14mm;'
             '@bottom-center {content:"Synthetic footer"}}'
             'body{font-size:12pt;line-height:1.5}li,p{padding-bottom:12pt}</style>')
    element = f'<{kind}>{unit}</{kind}>'
    document = '<html><head>' + style + '</head><body>' + element * 2 + '</body></html>'
    expected = export_contract.from_tree(html.document_fromstring(document))
    replacement = {'none': element, 'delete': '',
                   'alter': element.replace('word080', 'CHANGED'),
                   'truncate': f'<{kind}>' + ' '.join(unit.split()[:60]) + f'</{kind}>'}[mutation]
    actual = document.replace(element, replacement, 1)
    target = tmp_path / 'repeated.pdf'
    HTML(string=actual).write_pdf(target)
    if mutation == 'none':
        export_contract.inspect(target, 'pdf', expected)
    else:
        with pytest.raises(ValueError):
            export_contract.inspect(target, 'pdf', expected)


def test_pdf_cover_uses_visible_block_boundaries_and_only_first_page(tmp_path):
    data = source('The original cover title is repeated here for context.\n\nApproved')
    data['meta'].update(report_title='The original cover title is repeated here for context.',
                        report_subtitle='Approved')
    path, expected = render(data, tmp_path, 'cover-valid')
    export_contract.inspect(path, 'pdf', expected)
    # The unchanged body still contains both original values. It cannot
    # substitute for altered first-page metadata, nor can NotApproved supply
    # the standalone Approved subtitle through a substring match.
    altered = deepcopy(data)
    altered['meta']['report_subtitle'] = 'NotApproved'
    path, _ = render(altered, tmp_path, 'cover-changed')
    with pytest.raises(ValueError, match='portada|Cover'):
        export_contract.inspect(path, 'pdf', expected)


def test_wrapped_pdf_cover_title_and_subtitle_keep_independent_boundaries(tmp_path):
    data = source('Synthetic body.')
    data['meta'].update(
        report_title='Independent technical assessment of document workflows and sensitive banking services',
        report_subtitle='Fictional case with executive and technical analysis')
    path, expected = render(data, tmp_path, 'cover-blocks')
    checks = export_contract.inspect(path, 'pdf', expected)
    assert checks['metadata_values_checked'] >= 2
