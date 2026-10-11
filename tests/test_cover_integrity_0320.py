"""Structured exports bind full cover title/subtitle and metadata units."""
from copy import deepcopy
import pytest

import delivery
import export
from wizard import dump_yaml


@pytest.mark.parametrize('fmt', ['html', 'docx', 'md'])
@pytest.mark.parametrize('theme', ['serio', 'corporativo'])
@pytest.mark.parametrize('field,changed', [
    ('report_title', 'NotApproved'),
    ('report_title', 'Approved - rejected'),
    ('report_subtitle', 'NotReviewed'),
    ('client', 'Bank - wrong entity'),
    ('assessor', 'Team Extended'),
    ('report_title', 'Reviewed'),  # The unchanged subtitle cannot replace the title.
])
def test_changed_cover_unit_cannot_be_supplied_by_substring_or_another_field(tmp_path, fmt, theme, field, changed):
    data = {'meta': {'lang': 'en', 'theme': theme, 'report_title': 'Approved',
                     'report_subtitle': 'Reviewed', 'client': 'Bank', 'assessor': 'Team'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F1', 'title': 'Synthetic finding', 'description_md': 'Synthetic body.'}]}
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    output = tmp_path / ('report.' + delivery.get(fmt).extension)
    export.export(source, fmt, output)
    delivery.inspect_export(output, fmt, captured)
    altered = deepcopy(data)
    altered['meta'][field] = changed
    dump_yaml(altered, source)
    export.export(source, fmt, output)
    with pytest.raises(ValueError, match='portada|Cover'):
        delivery.inspect_export(output, fmt, captured)


@pytest.mark.parametrize('theme', ['serio', 'corporativo'])
def test_word_cover_metadata_ignores_separate_long_identity_header(tmp_path, theme):
    from zipfile import ZipFile
    from lxml import etree
    from export_contract import NS

    data = {'meta': {'lang': 'en', 'theme': theme, 'report_title': 'Approved',
                     'report_subtitle': 'Reviewed', 'client': 'Bank', 'assessor': 'Team',
                     'branding': {'wordmark': 'Independent Security Assurance and Technical Review Team',
                                  'confidential_text': 'CONFIDENTIAL - BOARD AND AUTHORIZED RECIPIENTS ONLY'}},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F1', 'title': 'Synthetic finding', 'description_md': 'Synthetic body.'}]}
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    output = tmp_path / 'report.docx'
    export.export(source, 'docx', output)
    with ZipFile(output) as package:
        tree = etree.fromstring(package.read('word/document.xml'))
    assert tree.xpath('./w:body/w:tbl[1]/w:tr[1]/w:tc[last()]/w:tbl', namespaces=NS)
    delivery.inspect_export(output, 'docx', captured)

    # Moving identity to a nested table must not relax metadata integrity.
    data['meta']['client'] = 'Bank - wrong entity'
    dump_yaml(data, source)
    export.export(source, 'docx', output)
    with pytest.raises(ValueError, match='portada|Cover'):
        delivery.inspect_export(output, 'docx', captured)
