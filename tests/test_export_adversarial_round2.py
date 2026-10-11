"""Authored Markdown blocks keep their identity and remain verifiable."""
from copy import deepcopy
import zipfile

from PIL import Image
import pytest

import delivery
import export
from exporters.markdown import authored
from safe_markup import _parsed
from wizard import dump_yaml


def data(source):
    return {'meta': {'lang': 'es', 'report_title': 'Synthetic export audit'},
            'findings': [{'id': identity, 'title': 'Finding ' + identity,
                          'description_md': source.replace('IDENTITY', identity),
                          'impact_md': 'Impact ' + identity, 'cwe': 'CWE-79'}
                         for identity in ('F1', 'F2')]}


def prepare(tmp_path, document, fmt):
    Image.new('RGB', (32, 24), 'blue').save(tmp_path / 'proof.png')
    dump_yaml(document, tmp_path / 'engagement.yaml')
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    output = export.export(tmp_path / 'engagement.yaml', fmt,
                           tmp_path / ('report.' + delivery.get(fmt).extension))
    return output, captured


def mutate(output, fmt, transform):
    if fmt == 'html':
        output.write_bytes(transform(output.read_bytes()))
    else:
        with zipfile.ZipFile(output) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        member = 'report.md' if fmt == 'md' else 'word/document.xml'
        members[member] = transform(members[member])
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, blob in members.items():
                archive.writestr(name, blob)


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
@pytest.mark.parametrize('source', ['> Quoted IDENTITY\n>\n> ![Evidence](proof.png)',
                                   '# Heading IDENTITY',
                                   '## ![Heading image IDENTITY](proof.png)'])
def test_block_only_descriptions_are_content_not_metadata(tmp_path, fmt, source):
    document = data(source)
    original = deepcopy(document)
    output, captured = prepare(tmp_path, document, fmt)
    result = delivery.inspect_export(output, fmt, captured)
    assert result['metadata_values_checked'] >= 2  # Genuine CWE metadata remain checked.
    if source.startswith('#'):
        assert result['authored_headings_checked'] == 2
    assert document == original
    assert all(not any('Descripción' in label for label, _ in scope['semantic']['fields'])
               for scope in captured['contract']['scopes'])


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
@pytest.mark.parametrize('mutation', ['delete', 'edit', 'transpose', 'reorder'])
def test_lost_changed_moved_and_reordered_headings_are_rejected(tmp_path, fmt, mutation):
    output, captured = prepare(tmp_path, data('# HEAD_IDENTITY\n\nBody.\n\n## TAIL_IDENTITY'), fmt)
    assert delivery.inspect_export(output, fmt, captured)['authored_headings_checked'] == 4
    def change(blob):
        if mutation == 'delete':
            return blob.replace(b'HEAD_F1', b'')
        if mutation == 'edit':
            return blob.replace(b'HEAD_F1', b'CORRUPTED')
        replacement = b'HEAD_F2' if mutation == 'transpose' else b'TAIL_F1'
        return blob.replace(b'HEAD_F1', b'TEMP_HEADING').replace(replacement, b'HEAD_F1').replace(b'TEMP_HEADING', replacement)
    mutate(output, fmt, change)
    with pytest.raises(ValueError, match='Encabezado'):
        delivery.inspect_export(output, fmt, captured)


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
def test_genuine_metadata_mutation_still_fails_after_block_classification_fix(tmp_path, fmt):
    output, captured = prepare(tmp_path, data('> Blockquote'), fmt)
    delivery.inspect_export(output, fmt, captured)
    mutate(output, fmt, lambda blob: blob.replace(b'CWE-79', b'CWE-89').replace(b'CWE\\-79', b'CWE\\-89'))
    with pytest.raises(ValueError, match='Metadato'):
        delivery.inspect_export(output, fmt, captured)


@pytest.mark.parametrize('mode', ['prose', 'fence', 'inline', 'mixed'])
def test_anchor_examples_remain_literal_and_do_not_create_finding_boundaries(tmp_path, mode):
    example = '<a id="F1"></a>\n### F1 Finding F1\n'
    sources = {'prose': example, 'fence': '```html\n' + example + '```',
               'inline': '`first\n' + example + 'last`',
               'mixed': example + '\n```html\n' + example + '```\n\n' + example}
    document = data(sources[mode])
    # Deliberate examples refer to F1 even in F2; they never change ownership.
    output, captured = prepare(tmp_path, document, 'md')
    check = delivery.inspect_export(output, 'md', captured)
    assert check['finding_association_checked']
    assert _parsed(authored(sources[mode])) == _parsed(sources[mode])
    if mode == 'fence':
        assert authored(sources[mode]) == sources[mode]
    else:
        with zipfile.ZipFile(output) as archive:
            assert '&lt;a id="F1"></a>' in archive.read('report.md').decode()


def test_heading_marker_cannot_be_injected_with_raw_html():
    from safe_markup import md
    from lxml import html
    tree = html.fragment_fromstring(str(md('<p data-rg-authored-heading="true">Pretend</p>')), create_parent='div')
    assert not tree.xpath('.//*[@data-rg-authored-heading]')


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
def test_generated_finding_title_cannot_substitute_deleted_authored_heading(tmp_path, fmt):
    from lxml import etree, html
    from export_contract import NS
    heading = 'Finding IDENTITY' if fmt == 'html' else 'IDENTITY Finding IDENTITY'
    output, captured = prepare(tmp_path, data('# ' + heading + '\n\nNormal body.'), fmt)
    assert delivery.inspect_export(output, fmt, captured)['authored_headings_checked'] == 2
    def delete(blob):
        if fmt == 'html':
            tree = html.document_fromstring(blob)
            for node in tree.xpath('//*[@data-rg-authored-heading="true"]'):
                node.drop_tree()
            return html.tostring(tree)
        if fmt == 'md':
            for identity in ('F1', 'F2'):
                blob = blob.replace(('\n# ' + heading.replace('IDENTITY', identity) + '\n').encode(), b'\n')
            return blob
        tree = etree.fromstring(blob)
        for node in tree.xpath('//w:p[w:pPr/w:pStyle[@w:val="Heading1"]][not(w:bookmarkStart)]', namespaces=NS):
            node.getparent().remove(node)
        return etree.tostring(tree)
    mutate(output, fmt, delete)
    with pytest.raises(ValueError, match='Encabezado'):
        delivery.inspect_export(output, fmt, captured)


@pytest.mark.parametrize('depth', [128, 256, 512, 1024])
def test_deep_nesting_is_rejected_before_html_parser_can_silently_lose_content(depth):
    from safe_markup import md, raw_image_sources
    source = '> ' * depth + 'DEEPEST_CONTENT\n\n' + '> ' * depth + '![Required](proof.png)'
    for parser in (md, raw_image_sources):
        with pytest.raises(ValueError, match='anidación'):
            parser(source)


def test_supported_nested_quote_preserves_deepest_text_and_image_reference():
    from safe_markup import md, raw_image_sources
    source = '> ' * 64 + 'DEEPEST_CONTENT\n\n' + '> ' * 64 + '![Required](proof.png)'
    assert 'DEEPEST_CONTENT' in str(md(source))
    assert raw_image_sources(source) == {'proof.png'}


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_deep_nesting_export_failure_preserves_source_and_existing_output(tmp_path, fmt):
    document = data('> ' * 256 + 'DEEPEST_CONTENT')
    source = tmp_path / 'engagement.yaml'
    dump_yaml(document, source)
    before = source.read_bytes()
    output = tmp_path / ('report.' + delivery.get(fmt).extension)
    output.write_bytes(b'PREVIOUS_GOOD_OUTPUT')
    with pytest.raises(ValueError, match='anidación'):
        export.export(source, fmt, output)
    assert source.read_bytes() == before
    assert output.read_bytes() == b'PREVIOUS_GOOD_OUTPUT'
