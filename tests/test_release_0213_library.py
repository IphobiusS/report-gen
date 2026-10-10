"""Reusable findings retain literals and cannot acquire another project's links."""
from copy import deepcopy
from io import BytesIO

from lxml import html
from PIL import Image
import pytest

import app as webapp
import finding_library as library
from safe_markup import md, raw_image_sources
from _support import auth_client


@pytest.mark.parametrize('source', [
    'Before ![Private](img/client.png) after.',
    'Before ![Nested [caption]](img/client(one).png) after.',
    r'Before ![Escaped \[caption\]](img/client\(one\).png) after.',
    'Before ![Private](<img/client space.png>) after.',
    'Before ![Private](img/client.png){width="45%"} after.',
    'Before ![Private][shot] after.\n\n[shot]: img/client.png',
    'Before ![Private][] after.\n\n[private]: img/client.png',
    'Before ![Private] after.\n\n[private]: img/client.png',
    'Before [![Private](img/client.png)](https://example.com/public) after.',
    'Before [![Private](img/client.png)](#F01) after.',
    'Before <img src="img/client.png" alt="Private"> after.',
    '<div>Before ![Private](img/client.png) after.</div>',
])
def test_reusable_template_removes_actual_images_in_every_supported_form(source):
    original = {'title': 'Template', 'description_md': source}
    result = library.sanitize(original)
    assert not raw_image_sources(result['description_md'])
    assert '<img' not in result['description_md']
    assert 'img/client' not in result['description_md']
    assert 'Before' in result['description_md'] and 'after.' in result['description_md']
    assert original['description_md'] == source


@pytest.mark.parametrize('source', [
    '`![literal](img/client.png)` and `[other](#F01)`',
    '```md\n\t![literal](img/client.png)  \n[other](#F01)\n```',
    '    ![literal](img/client.png)  \n    [other](#F01)\n',
    '```html\n<img src="img/client.png">\n<a href="#F01">literal</a>\n```',
    r'\!\[literal\](img/client.png)',
])
def test_reusable_template_keeps_literal_code_and_escaped_image_syntax_exact(source):
    result = library.sanitize({'title': 'Template', 'description_md': source})
    assert result['description_md'] == source


@pytest.mark.parametrize('literal', ['```md\n![literal](img/client.png)  \n```',
                                    '    ![literal](img/client.png)  \n'])
def test_removing_an_image_before_code_preserves_the_literal_block(literal):
    source = '![Private](img/client.png)\n\n' + literal
    result = library.sanitize({'title': 'Template', 'description_md': source})['description_md']
    assert result == '\n\n' + literal


def test_reusable_template_preserves_commands_and_plain_labels_exactly():
    source = {'title': '![plain title](img/client.png)',
              'walkthrough': [{'lead': '![plain lead](img/client.png)',
                               'command': '\tprintf "%s" "![literal](img/client.png) [other](#F01)"  \n'}]}
    assert library.sanitize(source) == source


def test_escaped_bang_leaves_a_real_markdown_link_whose_local_destination_is_removed():
    # Escaping ! alone suppresses the image, but Markdown still parses [label]
    # as a link. Fully escaped brackets above are literal and remain exact.
    source = r'\![literal label](img/client.png)'
    result = library.sanitize({'title': 'Template', 'description_md': source})['description_md']
    tree = html.fragment_fromstring(str(md(result)), create_parent='div')
    assert tree.text_content() == '!literal label'
    assert not tree.xpath('.//a | .//img')


@pytest.mark.parametrize('source,label', [
    ('Before [other finding](#F01) after.', 'other finding'),
    ('Before [**other finding**](#F01) after.', 'other finding'),
    ('Before [other finding][ref] after.\n\n[ref]: #F01', 'other finding'),
    ('Before [other finding][] after.\n\n[other finding]: #F01', 'other finding'),
    ('Before [other finding] after.\n\n[other finding]: #F01', 'other finding'),
    ('Before [appendix](#private-section) after.', 'appendix'),
    ('Before <a href="#F01"><strong>other finding</strong></a> after.', 'other finding'),
    ('Before [local](file:///private/report.html) after.', 'local'),
    (r'Before [local](C:\Clients\Acme\report.pdf) after.', 'local'),
    ('Before [local](C:/Clients/Acme/report.pdf) after.', 'local'),
])
def test_reusable_template_drops_internal_destinations_but_keeps_labels(source, label):
    result = library.sanitize({'title': 'Template', 'description_md': source})['description_md']
    tree = html.fragment_fromstring(str(md(result)), create_parent='div')
    assert not tree.xpath('.//a[@href]')
    assert label in tree.text_content()
    assert '#F01' not in result and '#private-section' not in result and 'file:' not in result
    assert 'C:' not in result  # A renderer stripping the href must not retain the private path in a template.
    assert 'Before' in tree.text_content() and 'after.' in tree.text_content()


def test_shared_external_definition_retains_public_link_after_image_removal():
    source = 'Before ![Private][shared] and [public source][shared].\n\n[shared]: https://example.com/image.png'
    result = library.sanitize({'title': 'Template', 'description_md': source})['description_md']
    tree = html.fragment_fromstring(str(md(result)), create_parent='div')
    assert not tree.xpath('.//img')
    assert tree.xpath('.//a/@href') == ['https://example.com/image.png']
    assert 'public source' in tree.text_content()


def test_https_and_mailto_links_keep_their_destinations():
    source = '[public](https://example.com/path#section) and [mail](mailto:team@example.com) and [ref][public].\n\n[public]: https://example.com/reference'
    assert library.sanitize({'description_md': source})['description_md'] == source


def test_html_code_tag_does_not_hide_an_active_markdown_image_from_the_report_parser():
    # This application's raw HTML tags display as prose; use Markdown backticks
    # to write a literal example. Unsupported ambiguous forms fail before save.
    with pytest.raises(ValueError, match='No se puede retirar'):
        library.sanitize({'description_md': '<code>![Private](img/client.png)</code>'})


def test_structured_internal_references_are_removed_and_https_references_retained():
    source = {'title': 'Template', 'references': ['#F01', '#private-section', 'img/private.png',
                                               'file:///private/report.html', 'https://example.com/public#section']}
    result = library.sanitize(source)
    assert result['references'] == ['https://example.com/public#section']
    assert source['references'][0] == '#F01'


def test_references_preserve_bibliography_prose_during_validation_save_and_instantiation(tmp_path):
    citations = ['OWASP ASVS 4.0.3, V5: Validation, Sanitization and Encoding',
                 'NIST SP 800-115', 'SANS/GIAC Report Writing', 'RFC9110/HTTP Semantics',
                 'history/Research methodology notes', '# Retest methodology note', 'https://owasp.org/Top10/']
    source = {'title': 'Reusable', 'references': citations + ['#F01', 'img/private space.png',
              './private-report.pdf', '../old-report', '/private/report', r'C:\private\report.pdf',
              'screenshots/private.png', 'private-report.html', 'private-report.html?token=old', 'file:///private/report.html']}
    assert library.sanitize(source)['references'] == citations
    entry = library.validate_entry({'name': 'Bibliography', 'content': source})
    assert entry['content']['references'] == citations
    saved = library.put(tmp_path / 'findings.json', {'name': 'Bibliography', 'content': source})
    assert saved['content']['references'] == citations
    assert library.instantiate(saved, {})['references'] == citations
    assert source['references'][0] == citations[0]


@pytest.mark.parametrize('destination,expected', [('https://example.com/new#public', True),
                                                ('#F01', False), ('img/old-client.png', False)])
def test_url_variables_remain_editable_and_instantiation_checks_the_filled_destination(destination, expected):
    original = {'title': 'Template', 'description_md': '[public source](https://client.example/old)',
                'references': ['https://client.example/old']}
    cleaned = library.sanitize(original, {'url': 'https://client.example/old'})
    assert cleaned['description_md'] == '[public source]({{url}})'
    assert cleaned['references'] == ['{{url}}']
    entry = library.validate_entry({'name': 'Template', 'content': cleaned})
    result = library.instantiate(entry, {'url': destination})
    tree = html.fragment_fromstring(str(md(result['description_md'])), create_parent='div')
    assert tree.xpath('.//a/@href') == ([destination] if expected else [])
    assert result['references'] == ([destination] if expected else [])
    assert 'public source' in tree.text_content()


def test_library_save_and_instantiation_cannot_retarget_a_previous_project_link(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path / 'projects')
    webapp.PROJECTS.mkdir()
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path / 'library' / 'findings.json'))
    monkeypatch.setitem(webapp.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'library' / 'designs.json'))
    client = auth_client(webapp.app)
    assert client.post('/api/projects', json={'slug': 'first', 'title': 'First project'}).status_code == 200
    image = BytesIO(); Image.new('RGB', (20, 20), 'red').save(image, 'PNG'); image.seek(0)
    uploaded = client.post('/api/projects/first/image', data={'file': (image, 'private.png')}).get_json()['src']
    source = client.get('/api/projects/first').get_json()
    source['findings'] = [{'id': 'F01', 'title': 'Original destination'},
                          {'id': 'F02', 'title': 'Reusable', 'description_md':
                           'Relationship [original finding](#F01).\n\n![Private][shot]\n\n[shot]: ' + uploaded,
                           'references': ['#F01', 'https://example.com/public'],
                           'walkthrough': [{'command': 'printf "![literal](img/private.png)"\n'}]}]
    assert client.put('/api/projects/first', json=source).status_code == 200
    source_before = deepcopy(client.get('/api/projects/first').get_json())
    tag = client.get('/api/library').headers['ETag']
    saved = client.post('/api/library', json={'name': 'Reusable', 'content': source_before['findings'][1]}, headers={'If-Match': tag})
    assert saved.status_code == 200, saved.get_json()
    entry = saved.get_json()
    assert client.post('/api/projects', json={'slug': 'second', 'title': 'Second project'}).status_code == 200
    instance = client.post('/api/library/' + entry['uid'] + '/instantiate', json={'values': {}})
    assert instance.status_code == 200, instance.get_json()
    finding = instance.get_json(); finding['id'] = 'F02'
    destination = client.get('/api/projects/second').get_json()
    destination['findings'] = [{'id': 'F01', 'title': 'Different and unrelated destination'}, finding]
    assert client.put('/api/projects/second', json=destination).status_code == 200
    assert '#F01' not in finding['description_md']
    assert not raw_image_sources(finding['description_md'])
    assert finding['references'] == ['https://example.com/public']
    assert finding['walkthrough'][0]['command'] == source_before['findings'][1]['walkthrough'][0]['command']
    preview = client.post('/api/projects/second/preview', json=destination)
    assert preview.status_code == 200, preview.get_json()
    tree = html.fromstring(preview.data).get_element_by_id('F02')
    assert not tree.xpath('.//a[@href="#F01"] | .//img')
    assert 'original finding' in tree.text_content()
    assert client.get('/api/projects/first').get_json() == source_before
    assert (webapp.PROJECTS / 'first' / uploaded).is_file()
