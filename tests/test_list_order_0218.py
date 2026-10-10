"""Export checks must reject reordered procedural lists in every structured format."""
import zipfile

from lxml import etree, html
import pytest

import delivery
import export
import publication
from wizard import dump_yaml


FIRST = ['Contain the synthetic exposure first', 'Validate the correction second']
SECOND = ['Monitor residual risk third', 'Record the proposed retest fourth']


@pytest.fixture(params=['sections', 'legacy'])
def report(tmp_path, request):
    data = {
        'meta': {'report_title': 'Public synthetic list order check', 'lang': 'en', 'theme': 'corporativo'},
        'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Procedural list order',
                      'severity': 'info', 'cvss': 0,
                      'description_md': '\n'.join('- ' + value for value in FIRST)
                                        + '\n\n' + '\n'.join(str(i) + '. ' + value for i, value in enumerate(SECOND, 1)),
                      'impact_md': 'Synthetic fixture only; no assessment executed.',
                      'remediation_md': 'Retain the proposed procedure order.'}],
    }
    if request.param == 'sections':
        data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    dump_yaml(data, tmp_path / 'engagement.yaml')
    return tmp_path, publication.snapshot(tmp_path, tmp_path / 'reference')


def swap_lists(source, target, fmt):
    if fmt == 'html':
        tree = html.document_fromstring(source.read_text())
        groups = [node for node in tree.xpath('//*[@id="F01"]//ul|//*[@id="F01"]//ol')
                  if node.xpath('./li[normalize-space(.)="' + FIRST[0] + '"]')
                  or node.xpath('./li[normalize-space(.)="' + SECOND[0] + '"]')]
        assert len(groups) == 2
        first, second = groups
        parent = first.getparent()
        a, b = parent.index(first), parent.index(second)
        parent.remove(first); parent.remove(second)
        parent.insert(a, second); parent.insert(b, first)
        target.write_text(html.tostring(tree, encoding='unicode'))
        return
    with zipfile.ZipFile(source) as package:
        blobs = {name: package.read(name) for name in package.namelist()}
    if fmt == 'md':
        first = '\n'.join('- ' + value for value in FIRST)
        second = '\n'.join(str(i) + '. ' + value for i, value in enumerate(SECOND, 1))
        content = blobs['report.md'].decode()
        assert content.count(first) == content.count(second) == 1
        blobs['report.md'] = content.replace(first, 'LIST-SWAP-MARKER').replace(second, first).replace('LIST-SWAP-MARKER', second).encode()
    else:
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        tree = etree.fromstring(blobs['word/document.xml'])
        paragraphs = [p for p in tree.xpath('//w:body/w:p', namespaces=ns)
                      if ''.join(p.xpath('.//w:t/text()', namespaces=ns)) in FIRST + SECOND]
        assert len(paragraphs) == 4
        parent = paragraphs[0].getparent()
        indices = [parent.index(p) for p in paragraphs]
        for p in paragraphs: parent.remove(p)
        for index, paragraph in zip(indices, paragraphs[2:] + paragraphs[:2]):
            parent.insert(index, paragraph)
        blobs['word/document.xml'] = etree.tostring(tree)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, blob in blobs.items(): package.writestr(name, blob)


@pytest.mark.parametrize('fmt', ['html', 'docx', 'md'])
def test_inspection_rejects_reordered_lists_without_changing_text(report, fmt):
    directory, captured = report
    extension = 'zip' if fmt == 'md' else fmt
    original = directory / ('original.' + extension)
    export.export(directory / 'engagement.yaml', fmt, original)
    assert delivery.inspect_export(original, fmt, captured)['structure_units_checked'] >= 4
    altered = directory / ('altered.' + extension)
    swap_lists(original, altered, fmt)
    with pytest.raises(ValueError, match='Lista alterada|List changed'):
        delivery.inspect_export(altered, fmt, captured)


@pytest.mark.parametrize('fmt', ['html', 'docx', 'md'])
def test_inspection_accepts_nested_lists_in_document_order(tmp_path, fmt):
    data = {
        'meta': {'report_title': 'Public synthetic nested list check', 'lang': 'en', 'theme': 'corporativo'},
        'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Nested procedure',
                      'severity': 'info', 'cvss': 0,
                      'description_md': '- Prepare the synthetic check\n'
                                        '    - Read the proposed scope\n'
                                        '    - Record the expected evidence\n'
                                        '- Finish the synthetic check',
                      'impact_md': 'No assessment executed.',
                      'remediation_md': 'Keep the nested procedure intact.'}],
    }
    dump_yaml(data, tmp_path / 'engagement.yaml')
    captured = publication.snapshot(tmp_path, tmp_path / 'reference')
    original = tmp_path / ('original.' + ('zip' if fmt == 'md' else fmt))
    export.export(tmp_path / 'engagement.yaml', fmt, original)
    checks = delivery.inspect_export(original, fmt, captured)
    assert checks['authored_list_items_order_checked'] == 4
