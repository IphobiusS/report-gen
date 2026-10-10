"""Export regressions from the 0.21.3 audit, on disposable reports only."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import re
import zipfile

from lxml import etree, html
from PIL import Image
import pytest

import delivery
import export
import export_contract
import workflows
from wizard import dump_yaml


def document(sections=True):
    data = {'meta': {'report_title': 'Ensayo de exportación', 'lang': 'es', 'theme': 'serio'},
            'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'Hallazgo sintético',
                          'severity': 'info', 'cvss': 0, 'description_md': 'Descripción sintética.'}]}
    if sections:
        data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    return data


def prepare(root, data, fmt):
    data = workflows.normalize(deepcopy(data))
    dump_yaml(data, root / 'engagement.yaml')
    captured = delivery.capture(root, root / 'snapshot')
    out = export.export(root / 'engagement.yaml', fmt, root / ('report.' + delivery.get(fmt).extension))
    return out, captured


def edit_zip(path, edit):
    with zipfile.ZipFile(path) as package:
        files = {name: package.read(name) for name in package.namelist()}
    edit(files)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, blob in files.items():
            package.writestr(name, blob)


@pytest.mark.parametrize('sections', [True, False])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
def test_webp_conversion_is_verified_in_cover_and_findings(tmp_path, sections, fmt):
    Image.new('RGBA', (60, 40), (30, 90, 150, 180)).save(tmp_path / 'proof.webp', lossless=True)
    data = document(sections)
    data['meta']['branding'] = {'logo': 'proof.webp', 'client_logo': 'proof.webp', 'cover_image': 'proof.webp'}
    data['findings'][0]['walkthrough'] = [{'figure': {'src': 'proof.webp', 'caption': 'Evidencia WebP'}}]
    out, captured = prepare(tmp_path, data, fmt)
    result = delivery.inspect_export(out, fmt, captured)
    assert result['evidence_associations_checked'] == 1
    assert captured['images']['proof.webp'] != captured['docx_images']['proof.webp']
    assert captured['resources']['proof.webp']['docx_sha256'] == captured['docx_images']['proof.webp']
    if fmt == 'docx':
        with zipfile.ZipFile(out) as package:
            digests = {sha256(package.read(n)).hexdigest() for n in package.namelist() if n.startswith('word/media/')}
        assert captured['docx_images']['proof.webp'] in digests


@pytest.mark.parametrize('mutation', ['pixels', 'move'])
def test_webp_word_mutation_is_rejected_after_native_conversion(tmp_path, mutation):
    Image.new('RGB', (60, 40), 'blue').save(tmp_path / 'proof.webp', lossless=True)
    data = document()
    data['findings'][0]['walkthrough'] = [{'command': 'printf prueba', 'figure': {'src': 'proof.webp', 'caption': 'Evidencia'}}]
    out, captured = prepare(tmp_path, data, 'docx')
    delivery.inspect_export(out, 'docx', captured)

    def mutate(files):
        if mutation == 'pixels':
            member = next(n for n in files if n.startswith('word/media/') and sha256(files[n]).hexdigest() == captured['docx_images']['proof.webp'])
            altered = BytesIO(); Image.new('RGB', (60, 40), 'red').save(altered, format='PNG')
            files[member] = altered.getvalue()
        else:
            tree = etree.fromstring(files['word/document.xml'])
            picture = tree.xpath('//w:p[w:r/w:drawing]', namespaces=export_contract.NS)[-1]
            code = tree.xpath('//w:p[w:pPr/w:pStyle[@w:val="ReportGenCode"]]', namespaces=export_contract.NS)[0]
            code.addprevious(picture)
            files['word/document.xml'] = etree.tostring(tree)
    edit_zip(out, mutate)
    with pytest.raises(ValueError):
        delivery.inspect_export(out, 'docx', captured)


@pytest.mark.parametrize('sections', [True, False])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('score_case', ['absent', 'null', 'empty', 'zero'])
def test_vector_preserves_nullable_empty_and_zero_scores(tmp_path, sections, fmt, language, score_case):
    vector = 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:' + ('N' if score_case == 'zero' else 'H') + '/I:N/A:N'
    data = document(sections)
    data['meta']['lang'] = language
    data['findings'][0].pop('cvss'); data['findings'][0].pop('severity')
    if score_case != 'absent':
        data['findings'][0]['cvss'] = {'null': None, 'empty': '', 'zero': 0}[score_case]
    data['findings'][0]['cvss_vector'] = vector
    out, captured = prepare(tmp_path, data, fmt)
    expected = next(s for s in captured['contract']['scopes'] if s['id'] == 'F1')
    assert ['CVSS 3.1', ('0 ' if score_case == 'zero' else '') + vector] in expected['semantic']['fields']
    assert delivery.inspect_export(out, fmt, captured)['metadata_values_checked'] >= 1
    if fmt == 'html':
        tree = html.document_fromstring(out.read_text())
        finding = tree.get_element_by_id('F1')
        assert finding.xpath('string(.//code[@class="vector"])') == vector
        if score_case == 'zero':
            assert finding.xpath('string(.//span[@class="score"])') == '0'
        else:
            assert not finding.xpath('.//span[@class="score"]')
    elif fmt == 'pdf':
        from pypdf import PdfReader
        text = ' '.join(page.extract_text() or '' for page in PdfReader(out).pages)
        assert vector in re.sub(r'\s+', '', text)
    else:
        assert vector in export_contract.profile(out, fmt)['text']


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
@pytest.mark.parametrize('score_case', ['null', 'empty', 'zero'])
def test_nullable_vector_metadata_mutation_is_rejected(tmp_path, fmt, score_case):
    vector = 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:' + ('N' if score_case == 'zero' else 'H') + '/I:N/A:N'
    altered = vector.replace('/C:N/', '/C:L/').replace('/C:H/', '/C:L/')
    data = document()
    data['findings'][0].pop('severity')
    data['findings'][0].update(cvss={'null': None, 'empty': '', 'zero': 0}[score_case], cvss_vector=vector)
    out, captured = prepare(tmp_path, data, fmt)
    delivery.inspect_export(out, fmt, captured)
    if fmt == 'html':
        tree = html.document_fromstring(out.read_text())
        tree.get_element_by_id('F1').xpath('.//code[@class="vector"]')[0].text = altered
        out.write_text(html.tostring(tree, encoding='unicode'))
    elif fmt == 'md':
        from workflows import md_text
        edit_zip(out, lambda files: files.update({'report.md': files['report.md'].replace(md_text(vector).encode(), md_text(altered).encode(), 1)}))
    else:
        def mutate(files):
            tree = etree.fromstring(files['word/document.xml'])
            node = tree.xpath('//w:t[contains(text(),$vector)]', namespaces=export_contract.NS, vector=vector)[0]
            node.text = node.text.replace(vector, altered)
            files['word/document.xml'] = etree.tostring(tree)
        edit_zip(out, mutate)
    with pytest.raises(ValueError, match='Metadato'):
        delivery.inspect_export(out, fmt, captured)


@pytest.mark.parametrize('sections', [True, False])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_plain_references_preserve_markdown_punctuation_and_are_verified(tmp_path, sections, fmt, language):
    reference = 'Referencia *literal* [anexo](https://example.test) | <b>texto</b>'
    data = document(sections)
    data['meta']['lang'] = language
    data['findings'][0]['references'] = [reference]
    out, captured = prepare(tmp_path, data, fmt)
    assert reference in export_contract.profile(out, fmt)['text']
    delivery.inspect_export(out, fmt, captured)
    if fmt == 'html':
        tree = html.document_fromstring(out.read_text())
        tree.get_element_by_id('F1').xpath('.//ul[@class="refs"]/li')[0].text = 'Referencia alterada'
        out.write_text(html.tostring(tree, encoding='unicode'))
    elif fmt == 'md':
        from workflows import md_text
        edit_zip(out, lambda files: files.update({'report.md': files['report.md'].replace(md_text(reference).encode(), b'Referencia alterada', 1)}))
    else:
        def mutate(files):
            tree = etree.fromstring(files['word/document.xml'])
            node = tree.xpath('//w:t[text()=$text]', namespaces=export_contract.NS, text=reference)[0]
            node.text = 'Referencia alterada'
            files['word/document.xml'] = etree.tostring(tree)
        edit_zip(out, mutate)
    with pytest.raises(ValueError, match='Lista'):
        delivery.inspect_export(out, fmt, captured)


@pytest.mark.parametrize('sections', [True, False])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_linked_evidence_preserves_caption_destination_and_inline_styles(tmp_path, sections, fmt, language):
    Image.new('RGB', (60, 40), 'green').save(tmp_path / 'proof.png')
    data = document(sections)
    data['meta']['lang'] = language
    data['findings'][0]['description_md'] = 'Antes [**negrita** `literal` ![Captura](proof.png) después](https://example.test) fin.'
    out, captured = prepare(tmp_path, data, fmt)
    result = delivery.inspect_export(out, fmt, captured)
    assert result['evidence_associations_checked'] == 1
    if fmt == 'docx':
        with zipfile.ZipFile(out) as package:
            tree = etree.fromstring(package.read('word/document.xml'))
            relations = etree.fromstring(package.read('word/_rels/document.xml.rels'))
        rid = next(n.get('Id') for n in relations if n.get('Target') == 'https://example.test')
        ns = dict(export_contract.NS, r='http://schemas.openxmlformats.org/officeDocument/2006/relationships')
        link = tree.xpath('//w:hyperlink[@r:id=$rid]', namespaces=ns, rid=rid)[0]
        assert link.xpath('.//w:drawing', namespaces=ns)
        assert link.xpath('.//w:r[w:t="negrita"]/w:rPr/w:b', namespaces=ns)
        assert link.xpath('.//w:r[w:t="literal"]/w:rPr/w:rFonts[@w:ascii="DejaVu Sans Mono"]', namespaces=ns)


@pytest.mark.parametrize('mutation', ['destination', 'image', 'context'])
def test_linked_word_evidence_still_rejects_semantic_mutations(tmp_path, mutation):
    Image.new('RGB', (60, 40), 'green').save(tmp_path / 'proof.png')
    data = document()
    data['findings'][0]['walkthrough'] = [
        {'text_md': 'Contexto [![Captura](proof.png)](https://example.test)'},
        {'command': 'printf paso_dos'}]
    out, captured = prepare(tmp_path, data, 'docx')
    delivery.inspect_export(out, 'docx', captured)

    def mutate(files):
        tree = etree.fromstring(files['word/document.xml'])
        if mutation == 'destination':
            rels = etree.fromstring(files['word/_rels/document.xml.rels'])
            next(n for n in rels if n.get('Target') == 'https://example.test').set('Target', 'https://altered.test')
            files['word/_rels/document.xml.rels'] = etree.tostring(rels)
        elif mutation == 'image':
            picture = tree.xpath('//*[local-name()="inline"]')[-1]
            picture.xpath('./*[local-name()="docPr"]')[0].set('descr', 'Otra evidencia')
        else:
            paragraph = tree.xpath('//w:p[.//w:drawing]', namespaces=export_contract.NS)[-1]
            code = tree.xpath('//w:p[w:pPr/w:pStyle[@w:val="ReportGenCode"]]', namespaces=export_contract.NS)[0]
            code.addnext(paragraph)
        files['word/document.xml'] = etree.tostring(tree)
    edit_zip(out, mutate)
    with pytest.raises(ValueError):
        delivery.inspect_export(out, 'docx', captured)


@pytest.mark.parametrize('sections', [True, False])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
def test_empty_fragment_link_returns_to_report_beginning(tmp_path, sections, fmt):
    data = document(sections)
    data['findings'][0]['description_md'] = '[Volver arriba](#)'
    out, captured = prepare(tmp_path, data, fmt)
    assert delivery.inspect_export(out, fmt, captured)['link_targets_checked'] >= 1
    if fmt == 'docx':
        from exporters.navigation import reference_name
        with zipfile.ZipFile(out) as package:
            tree = etree.fromstring(package.read('word/document.xml'))
        bookmark = tree.xpath('//w:bookmarkStart[@w:name=$name]', namespaces=export_contract.NS, name=reference_name(''))
        assert len(bookmark) == 1
        assert bookmark[0].xpath('ancestor::w:tbl', namespaces=export_contract.NS)[-1] == tree.find(export_contract.W + 'body/' + export_contract.W + 'tbl')


def test_none_reference_is_noop_and_empty_reference_is_unique():
    from docx import Document
    from exporters.navigation import add_reference, reference_name
    doc = Document(); paragraph = doc.add_paragraph('Inicio')
    add_reference(paragraph, None)
    assert not doc.element.xpath('//w:bookmarkStart')
    add_reference(paragraph, '')
    add_reference(paragraph, '')
    assert len(doc.element.xpath('//w:bookmarkStart')) == 1
    assert doc.element.xpath('//w:bookmarkStart')[0].get(export_contract.W + 'name') == reference_name('')
    assert paragraph.text == 'Inicio'


@pytest.mark.parametrize('mutation', ['missing', 'wrong'])
def test_word_empty_fragment_target_cannot_be_removed_or_redirected(tmp_path, mutation):
    from exporters.navigation import reference_name
    data = document()
    data['findings'][0]['description_md'] = '[Volver arriba](#)'
    out, captured = prepare(tmp_path, data, 'docx')
    delivery.inspect_export(out, 'docx', captured)

    def mutate(files):
        tree = etree.fromstring(files['word/document.xml'])
        if mutation == 'missing':
            node = tree.xpath('//w:bookmarkStart[@w:name=$name]', namespaces=export_contract.NS, name=reference_name(''))[0]
            identity = node.get(export_contract.W + 'id')
            node.getparent().remove(node)
            end = tree.xpath('//w:bookmarkEnd[@w:id=$identity]', namespaces=export_contract.NS, identity=identity)[0]
            end.getparent().remove(end)
        else:
            node = tree.xpath('//w:hyperlink[@w:anchor=$name]', namespaces=export_contract.NS, name=reference_name(''))[0]
            node.set(export_contract.W + 'anchor', reference_name('F1'))
        files['word/document.xml'] = etree.tostring(tree)
    edit_zip(out, mutate)
    with pytest.raises(ValueError):
        delivery.inspect_export(out, 'docx', captured)
