"""The public formats must reject counters consumers would silently corrupt."""
from hashlib import sha256
import zipfile

import fitz
from lxml import etree, html
import pytest

import export
from export_numbering import word_markers
from wizard import dump_yaml


FORMATS = ['html', 'pdf', 'md', 'docx']
CASES = {
    'zero': ('0. Zero counter item', ['0'], ['Zero counter item']),
    'maximum-single': ('2147483647. Last supported counter', ['2147483647'], ['Last supported counter']),
    'nested': ('7. Outer first\n    0. Inner zero\n    1. Inner next\n8. Outer second',
               ['7', '0'], ['Outer first', 'Inner zero', 'Inner next', 'Outer second']),
    'literal': ('The identifier is 2147483648, not a list counter.\n\n'
                '```text\n2147483648. Literal code identifier\n```\n\n'
                '<ol start="2147483648"><li>Literal HTML example</li></ol>',
                [], ['2147483648', 'Literal code identifier', 'Literal HTML example']),
}
WORD_ORDINALS = {
    'zero': [0],
    'maximum-single': [2147483647],
    'nested': [7, 0, 1, 8],
    'literal': [],
}


def source_report(directory, markdown):
    source = directory / 'engagement.yaml'
    dump_yaml({'meta': {'report_title': 'Public synthetic counter check', 'lang': 'en'},
               'report': {'sections': [{'key': 'findings'}]},
               'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Synthetic list counter',
                             'severity': 'info', 'description_md': markdown}]}, source)
    return source


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('start,count', [('2147483648', 1), ('2147483647', 2), ('9' * 5000, 1)],
                         ids=['start-overflow', 'last-ordinal-overflow', 'huge-counter'])
def test_all_formats_reject_unrepresentable_counters_atomically(tmp_path, fmt, start, count):
    source = source_report(tmp_path, '\n'.join(start + '. Synthetic item ' + str(i) for i in range(count)))
    original = sha256(source.read_bytes()).hexdigest()
    output = tmp_path / ('retained.' + ('zip' if fmt == 'md' else fmt))
    output.write_bytes(b'EXISTING-EXPORT-UNCHANGED')
    with pytest.raises(ValueError, match='Lista:.*2147483647'):
        export.export(source, fmt, output)
    assert output.read_bytes() == b'EXISTING-EXPORT-UNCHANGED'
    assert sha256(source.read_bytes()).hexdigest() == original
    assert not list(tmp_path.glob('.retained.*'))


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('case', CASES)
def test_supported_counters_and_literal_identifiers_remain_intact(tmp_path, fmt, case):
    markdown, starts, expected_text = CASES[case]
    source = source_report(tmp_path, markdown)
    original = sha256(source.read_bytes()).hexdigest()
    output = tmp_path / ('supported.' + ('zip' if fmt == 'md' else fmt))
    export.export(source, fmt, output)
    if fmt == 'html':
        tree = html.document_fromstring(output.read_text())
        content = tree.text_content()
        observed = tree.xpath('//*[@id="F01"]//ol/@start')
        assert observed == starts
    elif fmt == 'docx':
        with zipfile.ZipFile(output) as package:
            tree = etree.fromstring(package.read('word/document.xml'))
            numbering = etree.fromstring(package.read('word/numbering.xml'))
        content = ' '.join(tree.xpath('//*[local-name()="t"]/text()'))
        # Resolve the visible ordinal, including SEQ compatibility fields. A
        # valid native start alone cannot prove either its use or its sequence.
        observed = list(word_markers(tree, numbering).values())
        assert observed == WORD_ORDINALS[case]
    elif fmt == 'md':
        with zipfile.ZipFile(output) as package:
            content = package.read('report.md').decode()
        assert markdown in content
    else:
        with fitz.open(output) as pdf:
            content = '\n'.join(page.get_text() for page in pdf)
        for start in starts:
            assert start + '.' in content
    for value in expected_text:
        assert value in content
    assert sha256(source.read_bytes()).hexdigest() == original
