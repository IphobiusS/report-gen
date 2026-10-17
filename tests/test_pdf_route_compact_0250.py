"""Real paged-output regressions for compact routes and procedure headings."""
import json
import re

from lxml import html
from PIL import Image
from pypdf import PdfReader
import pytest

import engine
from exporters.machine_graph import _label_font, _label_lines
from test_machine_graph_0234 import document, render, graphs


THEMES = ['serio', 'corporativo', 'offsec', 'htb', 'ejecutivo', 'laboratorio']


def pdf_pages(data, directory, name='route'):
    markup = render(data, directory)
    output = directory / (name + '.pdf')
    engine.render_pdf_weasyprint(markup, output, directory)
    pages = [re.sub(r'\s+', ' ', page.extract_text() or '') for page in PdfReader(output).pages]
    return markup, pages


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('lang', ['es', 'en'])
def test_three_phases_nine_steps_overview_fits_one_real_pdf_page(tmp_path, theme, lang):
    data = document(lang, phases=3, steps=3)
    data['meta']['theme'] = theme
    (tmp_path / 'case.json').write_text(json.dumps({'lang': lang, 'theme': theme}))
    markup, pages = pdf_pages(data, tmp_path)
    assert len(graphs(markup)) == 1
    title = 'Recorrido documentado' if lang == 'es' else 'Documented route'
    overview = [page for page in pages if title in page]
    assert len(overview) == 1
    assert ('Versión textual' if lang == 'es' else 'Text version') in overview[0]
    assert 'No numbered figure for this step' not in markup
    assert 'Sin figura numerada para este paso' not in markup
    # Diagram and full native alternative occur on that same page. Commands
    # and detailed procedure remain intact elsewhere in the actual PDF.
    complete = ''.join(pages).replace(' ', '')
    for i in range(3):
        assert overview[0].count(f'PHASE-A-{i:03d}') >= 2
        for j in range(3):
            assert overview[0].count(f'HEADING-A-{i:03d}-{j:03d}') >= 2
            assert f'DETAIL-A-{i:03d}-{j:03d}' in complete
            assert f'printfsynthetic-{i}-{j}' in complete


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_mixed_figures_are_qualified_per_step_without_claiming_absent_evidence(tmp_path, lang):
    data = document(lang, phases=3, steps=3)
    Image.new('RGB', (60, 40), 'navy').save(tmp_path / 'evidence.png')
    data['findings'][0]['phases'][1]['steps'][1]['figure'] = {'src': 'evidence.png', 'caption': 'REAL FIGURE 0250'}
    markup, pages = pdf_pages(data, tmp_path)
    tree = html.document_fromstring(markup)
    route = tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," machine-route ")]')[0]
    qualification = 'Sin figura numerada para este paso' if lang == 'es' else 'No numbered figure for this step'
    assert route.text_content().count(qualification) == 8
    assert '2.2' in route.text_content()
    assert ('Figuras: 1)' if lang == 'es' else 'Figures: 1)') in route.text_content()
    assert 'REAL FIGURE 0250' in ' '.join(pages)
    assert all(len(graph.xpath('.//image')) == 0 for graph in graphs(markup))


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_long_labels_and_many_rows_fall_back_without_losing_source(tmp_path, lang):
    data = document(lang, phases=4, steps=4)
    for i, phase in enumerate(data['findings'][0]['phases']):
        phase['name'] = 'WWWW ' * 35 + f'PHASE-END-{i:02d}'
        for j, step in enumerate(phase['steps']):
            step['lead'] = 'autorización ' * 30 + f'STEP-END-{i:02d}-{j:02d}'
    markup, pages = pdf_pages(data, tmp_path)
    assert len(graphs(markup)) == 3
    assert 'machine-route-compact' not in markup.split('<div class="machine-route', 1)[1].split('>', 1)[0]
    assert all(int(graph.get('height')) <= 436 for graph in graphs(markup))
    normalized = re.sub(r'\s+', '', ' '.join(pages))
    for i in range(4):
        assert f'PHASE-END-{i:02d}' in normalized
        for j in range(4):
            assert f'STEP-END-{i:02d}-{j:02d}' in normalized
            assert f'printfsynthetic-{i}-{j}' in normalized
    assert '(...)' in ''.join(graph.text_content() for graph in graphs(markup))


@pytest.mark.parametrize('label', ['W' * 400, '漢字' * 100, 'áéíóú autorización ' * 30, 'A' * 26 + ' ' + 'B' * 26 + ' ' + 'C' * 26])
def test_wide_shortened_labels_fit_actual_node_font_metrics(label):
    lines = _label_lines(label, width=27, pixel_width=192, size=13)
    assert len(lines) <= 2
    assert lines[-1].endswith('(...)')
    assert all(_label_font(13).getlength(line) <= 192 for line in lines)


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('mode', ['vuln', 'machine'])
def test_step_heading_stays_with_table_and_long_command_remains_complete(tmp_path, theme, mode):
    data = document('en', phases=1, steps=1)
    data['meta']['theme'] = theme
    table = '| Row | Value |\n| --- | --- |\n' + '\n'.join(f'| ROW-{i:03d} | VALUE-{i:03d} |' for i in range(20))
    steps = [
        {'lead': 'LONG-COMMAND-HEADING', 'command': '\n'.join(f'CODE-{i:04d}: literal source' for i in range(140))},
        {'lead': 'TABLE-HEADING-0250', 'text_md': table},
    ]
    finding = data['findings'][0]
    finding['mode'] = mode
    if mode == 'machine':
        finding['phases'][0]['steps'] = steps
    else:
        finding.pop('phases')
        finding['walkthrough'] = steps
    _, pages = pdf_pages(data, tmp_path)
    # Ignore the graph's deliberate heading copies for machine findings.
    row_page = next(i for i, page in enumerate(pages) if 'ROW-000' in page)
    assert 'TABLE-HEADING-0250' in pages[row_page]
    assert 'ROW-019' in pages[row_page]
    complete = ''.join(pages)
    assert all(f'CODE-{i:04d}' in complete for i in range(140))
    assert all(f'ROW-{i:03d}' in complete and f'VALUE-{i:03d}' in complete for i in range(20))


@pytest.mark.parametrize('mode', ['vuln', 'machine'])
def test_inline_step_caption_stays_with_first_command_line(tmp_path, mode):
    data = document('en', phases=1, steps=1)
    finding = data['findings'][0]
    finding['mode'] = mode
    steps = [{'lead': f'HTTP-PAIR-{i:03d}',
              'text_md': f'CAPTION-{i:03d}: Reviewed synthetic response with a documented identity and boundary. '
                         'The following request records the selected account, tenant and authorization context '
                         'without inferring a result from a scanner observation.',
              'command': f'GET /synthetic-{i:03d} HTTP/1.1\nHost: example.invalid\nAccept: application/json'}
             for i in range(24)]
    if mode == 'machine':
        finding['phases'][0]['steps'] = steps
    else:
        finding.pop('phases')
        finding['walkthrough'] = steps
    markup, pages = pdf_pages(data, tmp_path)
    tree = html.document_fromstring(markup)
    labels = tree.xpath('//p[@class="step-heading"]')
    assert len(labels) == 24
    for i in range(24):
        assert f'CAPTION-{i:03d}' in labels[i].text_content()
        page = next(page for page in pages if f'GET /synthetic-{i:03d}' in page)
        assert f'HTTP-PAIR-{i:03d}' in page
        assert f'CAPTION-{i:03d}' in page
