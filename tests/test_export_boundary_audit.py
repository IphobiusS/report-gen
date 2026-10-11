"""Plain metadata, authored headings and image widths across public formats."""
import zipfile

from docx import Document
from PIL import Image
import pytest

import delivery
import export
from exporters.markdown import parse_exported
from wizard import dump_yaml


def document(language='es', sections=True):
    data = {
        'meta': {'report_title': 'Ensayo sintético', 'lang': language, 'theme': 'serio',
                 'client': 'ACME_[lab] **literal** & <dato>',
                 'assessor': 'Equipo `literal` [nombre](https://example.invalid)'},
        'findings': [
            {'id': identity, 'mode': 'vuln', 'title': 'Caso ' + identity,
             'description_md': '# Encabezado propio\n\nPárrafo exclusivo de ' + identity +
                               '.\n\n## Subtítulo\n\nContenido posterior de ' + identity + '.',
             'walkthrough': [{'command': '<a id="F1"></a>\n# Literal, no es un ancla\n\tvalor  final'}]}
            for identity in ('F1', 'F2')],
    }
    if sections:
        data['report'] = {'sections': [{'key': 'confidentiality'}, {'key': 'findings'},
                                      {'key': 'appendix', 'tools_used': 'Texto fuera de los hallazgos.'}]}
    return data


def prepare(directory, data, fmt):
    dump_yaml(data, directory / 'engagement.yaml')
    captured = delivery.capture(directory, directory / 'snapshot')
    output = export.export(directory / 'engagement.yaml', fmt,
                           directory / ('report.' + delivery.get(fmt).extension))
    return output, captured


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('sections', [True, False])
@pytest.mark.parametrize('fmt', ['html', 'pdf', 'md', 'docx'])
def test_plain_metadata_and_authored_heading_scopes_survive_all_formats(tmp_path, language, sections, fmt):
    data = document(language, sections)
    output, captured = prepare(tmp_path, data, fmt)
    result = delivery.inspect_export(output, fmt, captured)
    assert result['paragraphs_checked'] >= 4
    assert result['finding_association_checked'] is (fmt != 'pdf')
    if fmt != 'pdf':
        assert result['literal_code_blocks_checked'] == 2
    assert data['meta']['client'] == 'ACME_[lab] **literal** & <dato>'


@pytest.mark.parametrize('fmt', ['md', 'docx'])
def test_authored_heading_fix_still_rejects_moving_text_between_findings(tmp_path, fmt):
    output, captured = prepare(tmp_path, document(), fmt)
    delivery.inspect_export(output, fmt, captured)
    member = 'report.md' if fmt == 'md' else 'word/document.xml'
    with zipfile.ZipFile(output) as package:
        files = {name: package.read(name) for name in package.namelist()}
    first, second = (('Contenido posterior de ' + name).encode() for name in ('F1', 'F2'))
    files[member] = files[member].replace(first, b'TEMPORARY_MOVE').replace(second, first).replace(b'TEMPORARY_MOVE', second)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, blob in files.items():
            package.writestr(name, blob)
    with pytest.raises(ValueError, match='Párrafo'):
        delivery.inspect_export(output, fmt, captured)


@pytest.mark.parametrize('unit', ['%', 'cm', 'mm', 'in', 'px', 'pt'])
def test_extreme_decimal_image_width_is_clamped_to_word_page(tmp_path, unit):
    Image.new('RGB', (32, 20), 'red').save(tmp_path / 'proof.png')
    data = document()
    data['findings'] = data['findings'][:1]
    data['findings'][0]['description_md'] = '![Figura](proof.png){width="' + '9' * 400 + unit + '"}'
    output, captured = prepare(tmp_path, data, 'docx')
    result = delivery.inspect_export(output, 'docx', captured)
    assert result['evidence_associations_checked'] == 1
    word = Document(output)
    page = word.sections[-1]
    available = page.page_width - page.left_margin - page.right_margin
    assert all(0 < shape.width <= available for shape in word.inline_shapes)


def test_exported_anchor_parser_retains_fenced_examples_and_exact_ids():
    source = ('<a id="F&amp;amp;1"></a>\n### F&amp;amp;1 Título\n\n'
              '```html\n<a id="F&amp;amp;1"></a>\n# Ejemplo literal\n```\n')
    tree = parse_exported(source)
    assert tree[0].get('data-rg-anchor') == 'F&amp;1'
    assert tree.xpath('string(.//pre)') == '<a id="F&amp;amp;1"></a>\n# Ejemplo literal\n'


def test_markdown_identity_is_not_inferred_from_ambiguous_visible_titles(tmp_path):
    data = document()
    data['findings'][0].update(id='F1', title='X title')
    data['findings'][1].update(id='F1 X', title='title')
    output, captured = prepare(tmp_path, data, 'md')
    assert delivery.inspect_export(output, 'md', captured)['finding_association_checked']


@pytest.mark.parametrize('identity', ['F"1', 'F<1', 'F*1*', 'F&amp;1', 'F_1_'])
def test_markdown_anchor_identity_preserves_literal_punctuation(tmp_path, identity):
    data = document()
    data['findings'] = data['findings'][:1]
    data['findings'][0]['id'] = identity
    output, captured = prepare(tmp_path, data, 'md')
    assert delivery.inspect_export(output, 'md', captured)['finding_association_checked']
