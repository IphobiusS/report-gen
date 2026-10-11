"""Reject numbering Word cannot represent instead of silently wrapping to zero."""
from hashlib import sha256
import zipfile

from lxml import etree
import pytest

import export
from wizard import dump_yaml


@pytest.mark.parametrize('start,count', [('2147483648', 1), ('2147483647', 2), ('9' * 5000, 1)],
                         ids=['start-overflow', 'end-overflow', 'huge-input'])
def test_word_rejects_unrepresentable_list_numbering_atomically(tmp_path, start, count):
    data = {'meta': {'report_title': 'Synthetic list boundary', 'lang': 'en'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'List boundary', 'severity': 'info',
                          'description_md': '\n'.join(start + '. Synthetic ordinal ' + str(i) for i in range(count))}]}
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    before = sha256(source.read_bytes()).hexdigest()
    output = tmp_path / 'retained.docx'
    output.write_bytes(b'EXISTING-EXPORT-UNCHANGED')
    with pytest.raises(ValueError, match='Lista:.*2147483647'):
        export.export(source, 'docx', output)
    assert output.read_bytes() == b'EXISTING-EXPORT-UNCHANGED'
    assert sha256(source.read_bytes()).hexdigest() == before
    assert not list(tmp_path.glob('.retained.docx.*'))


@pytest.mark.parametrize('start,count', [('42', 2), ('2147483647', 1), ('0000000000000000000042', 2)])
def test_word_preserves_supported_list_start(tmp_path, start, count):
    data = {'meta': {'report_title': 'Synthetic supported list', 'lang': 'en'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Supported list', 'severity': 'info',
                          'description_md': '\n'.join(start + '. Synthetic ordinal ' + str(i) for i in range(count))}]}
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / 'supported.docx'
    export.export(tmp_path / 'engagement.yaml', 'docx', output)
    with zipfile.ZipFile(output) as package:
        tree = etree.fromstring(package.read('word/numbering.xml'))
        document = etree.fromstring(package.read('word/document.xml'))
    starts = tree.xpath('//*[local-name()="start"]/@*[local-name()="val"]')
    if int(start) <= 65535:
        assert str(int(start)) in starts
    else:
        fields = document.xpath('//*[local-name()="fldSimple"]')
        assert len(fields) == count
        assert fields[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr').endswith(
            f' \\r {int(start)} \\* ARABIC ')
        assert fields[0].xpath('.//*[local-name()="t"]/text()') == [str(int(start))]
