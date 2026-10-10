"""An empty automatic appendix must not leave a title, TOC target or blank sheet."""
from copy import deepcopy
from lxml import html
import pytest

import delivery
import export
import export_contract
import publication
import validate
from wizard import dump_yaml


def document():
    return {'meta': {'lang': 'en', 'theme': 'serio', 'report_title': 'Optional appendix contract'},
            'report': {'sections': [{'key': 'findings'}, {'key': 'appendix'}]},
            'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'MAIN_CONDITION_CANARY',
                          'severity': 'info', 'cvss': 0, 'description_md': 'Synthetic, not executed.'}]}


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_empty_builtin_appendix_omitted_from_export_without_changing_configuration(fmt, tmp_path):
    data = document(); before = deepcopy(data)
    assert not [m for lev, m in validate.validate(data) if lev == 'error']
    dump_yaml(data, tmp_path / 'engagement.yaml'); source = (tmp_path / 'engagement.yaml').read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'captured')
    artifact = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('without-appendix.' + ('zip' if fmt == 'md' else fmt)))
    text = export_contract.profile(artifact, fmt)['text']
    assert 'MAIN_CONDITION_CANARY' in text
    assert 'Appendices' not in text
    assert 'Appendix:' not in text
    delivery.inspect_export(artifact, fmt, captured)
    assert data == before
    assert (tmp_path / 'engagement.yaml').read_bytes() == source
    if fmt == 'html':
        tree = html.document_fromstring(artifact.read_text())
        assert not tree.xpath('//*[@id="appendix"]|//a[@href="#appendix"]')


@pytest.mark.parametrize('content', ['field', 'proof', 'flags', 'custom'])
def test_populated_builtin_or_explicit_custom_appendix_is_preserved(content, tmp_path):
    data = document(); before = deepcopy(data)
    if content == 'field': data['report']['sections'][1]['glossary'] = 'APPENDIX_CONTENT_CANARY'
    elif content in ('proof', 'flags'): data['findings'][0][content] = [{'name': 'APPENDIX_CONTENT_CANARY', 'value': 'Documentary synthetic value'}]
    else: data['report']['sections'][1] = {'key': 'custom_appendix', 'title': 'CUSTOM_TITLE_CANARY', 'body': 'APPENDIX_CONTENT_CANARY'}
    before = deepcopy(data)
    assert not [m for lev, m in validate.validate(data) if lev == 'error']
    tree = publication.render(data, tmp_path)
    assert 'APPENDIX_CONTENT_CANARY' in tree.text_content()
    if content == 'custom': assert 'CUSTOM_TITLE_CANARY' in tree.text_content()
    else: assert tree.xpath('//*[@id="appendix"]')
    assert data == before


def test_an_omitted_optional_anchor_does_not_reserve_a_finding_identity(tmp_path):
    data = document(); data['findings'][0]['id'] = 'appendix'; before = deepcopy(data)
    assert not [m for lev, m in validate.validate(data) if lev == 'error']
    tree = publication.render(data, tmp_path)
    assert len(tree.xpath('//*[@id="appendix"]')) == 1
    assert tree.xpath('//*[@id="appendix"][contains(@class,"finding")]')
    assert data == before
    data['report']['sections'][1]['glossary'] = 'APPENDIX_CONTENT_CANARY'
    assert any(lev == 'error' and 'anchor' in message.lower() for lev, message in validate.validate(data, lang='en'))
