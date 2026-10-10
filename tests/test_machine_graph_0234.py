"""Documented machine route: scope, projection, real figure binding and PDF flow."""
from copy import deepcopy
import re
from uuid import uuid4

from lxml import html
from PIL import Image
from pypdf import PdfReader
import pytest

import audience
import engine
import export
import publication
from exporters.machine_graph import build


def document(lang='es', phases=2, steps=2):
    return {'meta': {'lang': lang, 'theme': 'corporativo', 'report_title': 'SIMULACION R14',
                     'client': 'Synthetic customer'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'uid': str(uuid4()), 'id': 'M1', 'mode': 'machine', 'title': 'Synthetic machine',
                'host': {'name': 'SYNTHETIC-MACHINE-A', 'ip': '192.0.2.10'},
                'phases': [{'name': f'PHASE-A-{i:03d}', 'steps': [
                    {'lead': f'HEADING-A-{i:03d}-{j:03d}', 'text_md': f'DETAIL-A-{i:03d}-{j:03d}',
                     'command': f'printf synthetic-{i}-{j}'} for j in range(steps)]}
                           for i in range(phases)]}]}


def render(data, directory, enabled=True):
    return engine.render_html(engine.build_env(), data, directory.resolve(), {}, False,
                              engine.load_lang(engine.report_language(data)), machine_graphs=enabled)


def graphs(source):
    return html.document_fromstring(source).xpath('//*[contains(@class,"machine-route-svg")]')


@pytest.mark.parametrize('lang,heading', [('es', 'Recorrido documentado'), ('en', 'Documented route')])
@pytest.mark.parametrize('sections', [False, True])
def test_pdf_scope_and_real_step_labels_without_commands(tmp_path, lang, heading, sections):
    data = document(lang, phases=2, steps=4)
    if not sections:
        data.pop('report')
    old = deepcopy(data)
    markup = render(data, tmp_path)
    tree = html.document_fromstring(markup)
    assert len(graphs(markup)) == 2
    route = tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," machine-route ")]')[0]
    assert heading in route.text_content()
    assert 'HEADING-A-001-003' in route.text_content()
    assert 'printf synthetic' not in route.text_content()
    assert 'DETAIL-A' not in route.text_content()
    assert ('no causalidad probada' if lang == 'es' else 'not proven causality') in route.text_content()
    assert 'Paso 2.4' in markup if lang == 'es' else 'Step 2.4' in markup
    assert data == old


def test_existing_html_and_portable_html_remain_without_graph(tmp_path):
    data = document()
    assert not graphs(render(data, tmp_path, enabled=False))
    assert not graphs(html.tostring(publication.render(data, tmp_path), encoding='unicode'))


def test_graph_respects_publication_redactions_before_labels(tmp_path):
    data = document()
    data['findings'][0]['phases'][0]['name'] = 'PRIVATE_PHASE_0234'
    data['findings'][0]['phases'][0]['steps'][0]['lead'] = 'PRIVATE_HEADING_0234'
    data['publication'] = {'redactions': [
        {'needle': 'PRIVATE_PHASE_0234', 'replacement': 'PUBLIC_PHASE_0234'},
        {'needle': 'PRIVATE_HEADING_0234', 'replacement': 'PUBLIC_HEADING_0234'}]}
    markup = render(data, tmp_path)
    assert 'PRIVATE_PHASE_0234' not in markup and 'PRIVATE_HEADING_0234' not in markup
    assert 'PUBLIC_PHASE_0234' in markup and 'PUBLIC_HEADING_0234' in markup
    assert data['findings'][0]['phases'][0]['name'] == 'PRIVATE_PHASE_0234'


def test_figure_numbers_bound_to_machine_and_linked_evidence_outside_route(tmp_path):
    data = document()
    Image.new('RGB', (100, 50), 'white').save(tmp_path / 'evidence.png')
    data['findings'][0]['phases'][0]['steps'][0]['figure'] = {'src': 'evidence.png', 'caption': 'Caption A'}
    second = deepcopy(data['findings'][0])
    second['id'] = 'M2'
    second['uid'] = str(uuid4())
    second['host']['name'] = 'SYNTHETIC-MACHINE-B'
    second['phases'] = [{'name': 'PHASE-B', 'steps': [{'lead': 'HEADING-B',
                         'figure': {'src': 'evidence.png', 'caption': 'Caption B'}}]}]
    data['findings'].append(second)
    evidence_uid = str(uuid4())
    Image.new('RGB', (100, 50), 'blue').save(tmp_path / 'linked.png')
    data['evidence'] = [{'uid': evidence_uid, 'src': 'linked.png', 'title': 'Linked evidence'}]
    data['findings'][0]['evidence_uids'] = [evidence_uid]
    tree = html.document_fromstring(render(data, tmp_path))
    first_route = tree.xpath('//*[@id="M1"]//*[contains(concat(" ",normalize-space(@class)," ")," machine-route ")]')[0]
    second_route = tree.xpath('//*[@id="M2"]//*[contains(concat(" ",normalize-space(@class)," ")," machine-route ")]')[0]
    assert 'Figuras: 1)' in first_route.text_content()
    assert 'Evidencia vinculada fuera de la ruta' in first_route.text_content()
    assert 'Figuras: 2.' in first_route.text_content()
    assert 'Linked evidence' not in ''.join(g.text_content() for g in graphs(html.tostring(first_route)))
    assert 'Figuras: 3)' in second_route.text_content()
    assert 'HEADING-B' not in first_route.text_content()
    assert 'HEADING-A' not in second_route.text_content()


@pytest.mark.parametrize('kind', ['executive', 'public'])
def test_audience_derivatives_do_not_recreate_private_machine_graph(tmp_path, kind):
    data = document('en')
    uid = data['findings'][0]['uid']
    options = {'profile': kind, 'finding_uids': [uid]}
    if kind == 'public':
        options.update(review_confirmed=True, publish_consent=True, provenance_label='simulation',
                       title='Approved public report', client_alias='Public alias',
                       aliases=[{'needle': 'Synthetic customer', 'replacement': 'Public alias'}],
                       approved_content=[{'finding_uid': uid, 'title': 'Approved title', 'summary': 'Approved summary',
                                          'impact': 'Approved impact', 'remediation': 'Approved remediation'}])
    projected, _ = audience.project(data, options)
    markup = render(projected, tmp_path)
    assert not graphs(markup)
    assert 'HEADING-A' not in markup and 'PHASE-A' not in markup
    assert 'SYNTHETIC-MACHINE-A' not in markup


@pytest.mark.parametrize('case', ['missing_ref', 'missing_file', 'hostile_path'])
def test_graph_does_not_bypass_existing_reference_and_image_boundary(tmp_path, case):
    data = document()
    if case == 'missing_ref':
        data['findings'][0]['evidence_uids'] = [str(uuid4())]
    else:
        data['findings'][0]['phases'][0]['steps'][0]['figure'] = {
            'src': '../outside.png' if case == 'hostile_path' else 'missing.png', 'caption': 'Synthetic missing'}
    with pytest.raises(ValueError):
        render(data, tmp_path)


def test_hostile_labels_are_literal_svg_text_and_alternative_text(tmp_path):
    data = document(phases=1, steps=1)
    hostile = '</text><script>alert(23)</script><image href="https://example.invalid/leak">'
    data['findings'][0]['phases'][0]['name'] = hostile
    data['findings'][0]['phases'][0]['steps'][0]['lead'] = hostile
    tree = html.document_fromstring(render(data, tmp_path))
    assert not tree.xpath('//script|//image|//svg//a')
    assert hostile in tree.text_content()
    assert all('href' not in element.attrib for element in tree.xpath('//svg//*'))


@pytest.mark.parametrize('phases,steps', [(0, 0), (1, 0), (1, 10), (105, 1)])
def test_no_inferred_phases_and_every_panel_is_bounded(tmp_path, phases, steps):
    data = document(phases=phases, steps=steps)
    markup = render(data, tmp_path)
    expected = (phases * max(1, (steps + 2) // 3) + 2) // 3
    assert len(graphs(markup)) == expected
    for graphic in graphs(markup):
        assert int(graphic.get('height')) <= 448
    if not phases:
        assert 'No hay fases registradas. No se infiere una ruta.' in markup
    if phases and not steps:
        assert 'Pasos registrados: 0' in markup


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_long_labels_are_marked_and_full_text_is_retained(tmp_path, lang):
    data = document(lang, phases=1, steps=1)
    name = 'WWWW ' * 80 + 'PHASE-END-0234'
    lead = 'Long heading with accents autorización ' * 20 + 'LEAD-END-0234'
    data['findings'][0]['phases'][0]['name'] = name
    data['findings'][0]['phases'][0]['steps'][0]['lead'] = lead
    markup = render(data, tmp_path)
    graphic = graphs(markup)[0]
    assert '(...)' in graphic.text_content()
    assert 'PHASE-END-0234' not in graphic.text_content()
    assert 'LEAD-END-0234' not in graphic.text_content()
    assert 'PHASE-END-0234' in markup and 'LEAD-END-0234' in markup


def test_helper_does_not_use_commands_private_extra_metadata_or_source_ids():
    phase = {'name': 'Recorded phase', 'steps': [{'command': 'PRIVATE-COMMAND', 'text_md': 'PRIVATE-PROSE'}]}
    graph = build({'id': 'PRIVATE-ID', 'uid': 'PRIVATE-UID', 'phases': [phase]}, 1)
    text = str(graph)
    assert not any(value in text for value in ('PRIVATE-COMMAND', 'PRIVATE-PROSE', 'PRIVATE-ID', 'PRIVATE-UID'))
    assert 'No step heading recorded' in text


def test_unnumbered_markdown_evidence_is_not_claimed_absent(tmp_path):
    data = document(phases=1, steps=1)
    Image.new('RGB', (100, 50), 'white').save(tmp_path / 'markdown.png')
    data['findings'][0]['phases'][0]['steps'][0]['text_md'] = '![Markdown evidence](markdown.png)'
    markup = render(data, tmp_path)
    assert 'Sin figura numerada para este paso' not in markup
    assert 'Markdown evidence' in markup


def test_continuation_text_has_a_light_canvas_in_dark_pdf_theme(tmp_path):
    data = document(phases=2, steps=4)
    data['meta']['theme'] = 'htb'
    markup = render(data, tmp_path)
    for graphic in graphs(markup):
        canvas = graphic.xpath('./rect[@class="machine-route-canvas"]')[0]
        assert canvas.get('fill') == '#ffffff'
        assert canvas.get('width') == graphic.get('width')
        assert canvas.get('height') == graphic.get('height')


@pytest.mark.parametrize('length', [25, 34])
def test_word_boundary_spill_marks_every_shortened_graph_label(tmp_path, length):
    data = document(phases=1, steps=1)
    label = 'A' * length + ' ' + 'B' * length + ' ' + 'C' * length
    data['findings'][0]['phases'][0]['name'] = label
    data['findings'][0]['phases'][0]['steps'][0]['lead'] = label
    markup = render(data, tmp_path)
    graphic = graphs(markup)[0]
    # The third word cannot fit two lines; both phase and step must disclose it.
    assert graphic.text_content().count('(...)') >= 2
    assert label in html.document_fromstring(markup).text_content()


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_actual_pdf_retains_graph_step_identity_and_all_phase_details(tmp_path, lang):
    data = document(lang, phases=4, steps=4)
    source = render(data, tmp_path)
    path = tmp_path / 'machine-graph.pdf'
    engine.render_pdf_weasyprint(source, path, tmp_path)
    reader = PdfReader(path)
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    normalized = re.sub(r'\s+', '', text)
    assert ('Recorrido documentado' if lang == 'es' else 'Documented route').replace(' ', '') in normalized
    for i in range(4):
        assert f'PHASE-A-{i:03d}' in normalized
        for j in range(4):
            assert f'HEADING-A-{i:03d}-{j:03d}' in normalized
            assert f'DETAIL-A-{i:03d}-{j:03d}' in normalized
            assert f'{i + 1}.{j + 1}' in normalized
    assert len(reader.pages) >= 3


def test_public_pdf_export_activates_graph_but_html_export_does_not(tmp_path):
    import yaml
    data = document(phases=1, steps=1)
    yaml_path = tmp_path / 'engagement.yaml'
    yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')
    pdf = export.export(yaml_path, 'pdf', tmp_path / 'published.pdf')
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(pdf).pages)
    assert 'Recorrido documentado' in text
    published_html = export.export(yaml_path, 'html', tmp_path / 'published.html')
    assert not graphs(published_html.read_text(encoding='utf-8'))
