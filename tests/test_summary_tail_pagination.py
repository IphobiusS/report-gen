"""A flowing summary does not strand a single final row on its next page."""
from lxml import html
import pdfplumber
import pytest

import engine


@pytest.mark.parametrize('language', ['en', 'es'])
@pytest.mark.parametrize('count', [15, 22])
@pytest.mark.parametrize('table_kind', ['summary', 'workflow'])
def test_final_summary_rows_flow_as_a_group_without_pinning_entire_table(tmp_path, language, count, table_kind):
    data = {'meta': {'lang': language, 'theme': 'corporativo', 'report_title': 'Summary tail'},
            'report': {'sections': [{'key': 'findings_summary'}]},
            'findings': [{'id': f'F{i:03d}', 'title': f'TAILROW{i:03d}', 'severity': 'info', 'cvss': 0}
                         for i in range(count)]}
    if table_kind == 'workflow':
        markdown = '| Finding | Retest requirement |\n| --- | --- |\n' + '\n'.join(
            f'| TAILROW{i:03d} | Synthetic requirement |' for i in range(count))
        data['report']['sections'] = [{'key': 'notes', 'title': 'Retest matrix', 'body': markdown}]
    source = engine.render_html(engine.build_env(), data, tmp_path, {}, False, engine.load_lang(language))
    tree = html.document_fromstring(source)
    table = tree.xpath('//table[contains(@class,"sumtable") or contains(@class,"md-table")]')[0]
    # A deterministic small print area exercises a one-row tail independently
    # of installed fonts or differing translated title lengths. Keep the real
    # generated table and theme pagination rules; only isolate its geometry.
    body = tree.find('body')
    for node in list(body):
        body.remove(node)
    section = html.Element('section', {'class': 'frontsec'})
    section.append(table)
    body.append(section)
    style = html.Element('style')
    style.text = ('@page {size:210mm 105mm;margin:10mm;} '
                  'table tr {height:10mm;} '
                  'table td,table th {padding:0;font-size:8pt;}')
    tree.find('head').append(style)
    output = tmp_path / 'summary.pdf'
    engine.render_pdf_weasyprint(html.tostring(tree, encoding='unicode'), output, tmp_path)
    with pdfplumber.open(output) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
    assert len(pages) >= 2, 'the summary must still flow between pages'
    placements = []
    for i in range(count):
        matches = [p for p, text in enumerate(pages) if f'TAILROW{i:03d}' in text]
        assert len(matches) == 1
        placements.append(matches[0])
    assert placements == sorted(placements), 'summary order must be unchanged'
    assert len(set(placements[-3:])) == 1, 'the final three rows must stay together'
    assert sum(f'TAILROW{i:03d}' in pages[-1] for i in range(count)) >= 3
