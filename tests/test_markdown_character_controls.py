"""Decoded Markdown controls fail before export with an actionable field path."""
from copy import deepcopy
from docx import Document
from lxml import html
import pytest

import app as api
import engine
import export
import validate
import workflows
from error_messages import language_scope
from safe_markup import md
from wizard import dump_yaml
from _support import auth_client


def source(text):
    return {'meta': {'lang': 'en', 'report_title': 'Synthetic control fixture'},
            'findings': [{'uid': '11111111-1111-4111-8111-111111111111',
                          'id': 'F01', 'title': 'Synthetic observation', 'severity': 'medium',
                          'description_md': text}]}


def message(language):
    return ('referencia a un carácter no compatible' if language == 'es' else
            'character reference that reports do not support')


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('entity', ['&#x1f;', '&#31;', '&#x1;', '&#8;', '&#0;',
                                   '&#xD800;', '&#65534;', '&#1114112;',
                                   '&#x' + '0' * 5000 + '1f;'])
def test_incompatible_entity_is_rejected_by_field_before_renderer(tmp_path, language, entity):
    data = source('Before' + entity + 'After')
    before = deepcopy(data)
    issues = validate.validate(data, lang=language)
    errors = [text for level, text in issues if level == 'error']
    assert len(errors) == 1
    assert errors[0].startswith('findings[0].description_md: ')
    assert message(language) in errors[0]
    review = workflows.preflight(data, tmp_path, language)
    assert len(review) == 1 and review[0]['level'] == 'error'
    assert review[0]['path'] == 'findings[0].description_md'
    assert review[0]['finding_uid'] == data['findings'][0]['uid']
    assert message(language) in review[0]['message']
    assert data == before


@pytest.mark.parametrize('text', ['> **Before&#31;After**', '1. Before&#31;After',
                                '[Before&#31;After](https://example.test/)',
                                '[link](https://example.test/&#31;)',
                                '![Before&#31;After](evidence.png)'])
def test_control_in_nested_markup_and_attributes_is_not_silently_replaced(text):
    with language_scope('en'), pytest.raises(ValueError, match=message('en')):
        md(text)


@pytest.mark.parametrize('field', ['section', 'retest', 'overview', 'limitations'])
def test_other_authored_markdown_fields_have_exact_paths(field):
    data = source('Ordinary description.')
    text = 'Before&#31;After'
    if field == 'section':
        data['report'] = {'sections': [{'key': 'notes', 'title': 'Notes', 'body': text}]}
        path = 'report.sections[0].body'
    elif field == 'retest':
        data['findings'][0]['retests'] = [{'result': 'open', 'tested_on': '2026-10-13', 'notes_md': text}]
        path = 'findings[0].retests[0].notes_md'
    elif field == 'overview':
        data['meta']['overview'] = {'approach_md': text}
        path = 'meta.overview.approach_md'
    else:
        data['limitations_md'] = text
        path = 'limitations_md'
    assert validate.markdown_control_issues(data, 'en') == [(path,
        'Markdown contains a character reference that reports do not support. '
        'Use code formatting or escape the ampersand to display it literally.')]


@pytest.mark.parametrize('text,expected', [('`Before&#31;After`', 'Before&#31;After'),
                                          ('```\nBefore&#31;After\n```', 'Before&#31;After\n'),
                                          ('Before&amp;#31;After', 'Before&#31;After'),
                                          ('Before&#160;After', 'Before\u00a0After'),
                                          ('Before&#x200b;After', 'Before\u200bAfter'),
                                          ('Before&#x2066;After&#x2069;', 'Before\u2066After\u2069')])
def test_literal_examples_and_valid_unicode_remain_accepted(text, expected):
    data = source(text)
    before = deepcopy(data)
    assert validate.markdown_control_issues(data, 'en') == []
    assert html.fragment_fromstring(str(md(text)), create_parent='div').text_content() == expected
    assert data == before


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('fmt', ['pdf', 'docx', 'html', 'md'])
def test_public_export_rejects_before_staging_and_preserves_files(tmp_path, monkeypatch, language, fmt):
    project = tmp_path / 'source'; project.mkdir()
    yaml = project / 'engagement.yaml'
    dump_yaml(source('Before&#31;After'), yaml)
    output = tmp_path / ('existing.zip' if fmt == 'md' else 'existing.' + fmt)
    output.write_bytes(b'previous verified artifact')
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid decoded controls must be rejected before private staging/rendering')
    monkeypatch.setattr(export, '_export', forbidden)
    with language_scope(language), pytest.raises(ValueError, match=message(language)) as caught:
        export.export(yaml, fmt, output)
    assert 'findings[0].description_md' in str(caught.value)
    assert before == {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


@pytest.mark.parametrize('language', ['es', 'en'])
def test_review_api_returns_field_error_without_rewriting_saved_revision(tmp_path, monkeypatch, language):
    projects = tmp_path / 'projects'; project = projects / 'fixture'; project.mkdir(parents=True)
    yaml = project / 'engagement.yaml'; dump_yaml(workflows.normalize(source('Before&#31;After')), yaml)
    original = yaml.read_bytes()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    client = auth_client(api.app)
    before = client.get('/api/projects/fixture')
    response = client.get('/api/projects/fixture/review?lang=' + language,
                          headers={'X-UI-Language': language})
    assert response.status_code == 200, response.get_json()
    errors = [row for row in response.get_json()['issues'] if row['level'] == 'error']
    assert len(errors) == 1 and errors[0]['path'] == 'findings[0].description_md'
    assert message(language) in errors[0]['message']
    assert errors[0]['finding_uid'] == '11111111-1111-4111-8111-111111111111'
    assert yaml.read_bytes() == original
    assert client.get('/api/projects/fixture').headers['ETag'] == before.headers['ETag']


def test_word_literal_code_example_and_plain_fields_keep_entity_bytes(tmp_path):
    data = source('`Before&#31;After`')
    data['meta']['report_title'] = 'Plain &#31; title'
    data['findings'][0]['walkthrough'] = [{'command': 'echo "&#31;"'}]
    source_path = tmp_path / 'engagement.yaml'; dump_yaml(data, source_path)
    output = tmp_path / 'literal.docx'; export.export(source_path, 'docx', output)
    document = Document(output)
    text = '\n'.join(document.element.xpath('//w:t/text()'))
    assert 'Before&#31;After' in text and 'Plain &#31; title' in text
    assert 'echo "&#31;"' in text
    assert engine.load_engagement(source_path) == data
