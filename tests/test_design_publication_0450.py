"""Rendered design prose follows explicit publication redactions in every locale."""
from copy import deepcopy
from zipfile import ZipFile

import fitz
import pytest
from lxml import etree, html

import design_library
import export
import publication
import validate
from wizard import dump_yaml


SECRET = 'PRIVATE_CERTIFICATE_0450'
REPLACEMENT = 'REVIEWED_CERTIFICATE_0450'


def document(lang='en'):
    data = design_library.apply({'meta': {'lang': lang, 'report_title': 'Synthetic design audit'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [{'id': 'F1', 'title': 'Synthetic finding', 'mode': 'vuln',
            'severity': 'info', 'description_md': 'Controlled observation.',
            'impact_md': 'Synthetic impact.', 'remediation_md': 'Check the boundary.'}]},
        design_library.profile('htb-cpts'))
    data['meta']['design']['certificate'] = SECRET
    data['publication'] = {'redactions': [{'needle': SECRET, 'replacement': REPLACEMENT},
        {'needle': 'htb-cpts', 'replacement': 'must-not-change-identity'}]}
    validate.require_valid(data, final=True)
    return data


def test_certificate_redaction_preserves_design_configuration_and_original():
    data = document(); before = deepcopy(data)
    result = publication.project(data)
    expected = deepcopy(data['meta']['design']); expected['certificate'] = REPLACEMENT
    assert result['meta']['design'] == expected
    assert result['meta']['design']['id'] == 'htb-cpts'
    assert result['meta']['design']['guidance_id'] == 'htb-cpts'
    assert data == before
    # Historical arbitrary config dictionaries remain untouched, including
    # fields named original; only this rendered meta.design field is content.
    config = {'design': {'original': SECRET, 'certificate': SECRET},
              'workflow': {'original': SECRET}, 'publication': data['publication']}
    projected = publication.project(config)
    assert projected['design'] == config['design']
    assert projected['workflow'] == config['workflow']


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
@pytest.mark.parametrize('fmt', ['html', 'docx', 'pdf'])
def test_real_exports_redact_certificate_without_changing_source(tmp_path, lang, fmt):
    data = document(lang)
    source = tmp_path / 'engagement.yaml'; dump_yaml(data, source)
    before = source.read_bytes()
    target = export.export(source, fmt, tmp_path / ('report.' + fmt))
    if fmt == 'html':
        text = html.fromstring(target.read_bytes()).text_content()
    elif fmt == 'docx':
        with ZipFile(target) as archive:
            text = '\n'.join(''.join(etree.fromstring(archive.read(name)).itertext())
                for name in archive.namelist() if name.endswith('.xml'))
    else:
        with fitz.open(target) as pdf:
            text = '\n'.join(page.get_text() for page in pdf)
    assert SECRET not in text
    assert REPLACEMENT in text
    assert source.read_bytes() == before


def test_invalid_empty_redacted_design_stops_export_without_public_file(tmp_path):
    data = document(); data['publication']['redactions'][0]['replacement'] = ''
    source = tmp_path / 'engagement.yaml'; dump_yaml(data, source)
    before = source.read_bytes(); target = tmp_path / 'report.html'
    with pytest.raises(ValueError):
        export.export(source, 'html', target)
    assert not target.exists()
    assert source.read_bytes() == before
