"""The table error proposes a route that really allows the same content to flow."""
import hashlib

import pytest

import delivery
import export
from error_messages import language_scope
from wizard import dump_yaml


TABLE = ('| Reference | Result |\n| --- | --- |\n' + '\n'.join(
    f'| ROW-{i:03d} | Pending validation of the fictional control. |'
    for i in range(1, 73)))


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_large_table_flows_in_finding_walkthrough_and_section(tmp_path, lang):
    for location in ('description', 'walkthrough', 'section'):
        data = {
            'meta': {'report_title': 'Synthetic table guidance probe', 'lang': lang, 'theme': 'serio'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F-GUIDANCE', 'mode': 'vuln', 'severity': 'info',
                          'title': 'Fictional observation', 'description_md': 'Unverified control.'}],
        }
        if location == 'description':
            data['findings'][0]['description_md'] = TABLE
        elif location == 'walkthrough':
            data['findings'][0]['walkthrough'] = [{'text_md': TABLE}]
        else:
            data['report']['sections'].insert(0, {'key': 'executive_summary', 'summary': TABLE})
        root = tmp_path / location
        root.mkdir()
        source = root / 'engagement.yaml'
        dump_yaml(data, source)
        source_bytes = source.read_bytes()
        previous = b'PREVIOUS_VERIFIED_OUTPUT'
        output = root / 'report.pdf'
        output.write_bytes(previous)
        with language_scope(lang):
            captured = delivery.capture(root, root / 'snapshot')
            export.export(source, 'pdf', output)
            checked = delivery.inspect_export(output, 'pdf', captured)
            assert checked['pdf_table_cells_checked'] >= 146
            assert hashlib.sha256(output.read_bytes()).digest() != hashlib.sha256(previous).digest()
        assert source.read_bytes() == source_bytes
