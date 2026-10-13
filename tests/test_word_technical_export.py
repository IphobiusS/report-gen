"""Real DOCX export adds only technical-language metadata in both save paths."""
from copy import deepcopy
from hashlib import sha256
from zipfile import ZipFile
import subprocess

from docx import Document
from docx.oxml.ns import qn
from lxml import etree
from PIL import Image
import pytest

import engine
import export
import exporters.docx as word_export
from exporters.technical_text import TECHNICAL_LOCALE, mark_technical_text


TOKEN = 'ALBOR_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
URL = 'https://bank.example.test/' + '0123456789abcdef' * 5 + '?locale=es%2Den&next=%252F#control'
NATURAL = 'pneumonoultramicroscopicsilicovolcanoconiosis'
HEADER = 'HEADER_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
FOOTER = 'FOOTER_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def _run_style(run):
    properties = deepcopy(run.find(qn('w:rPr')))
    if properties is None:
        return None
    language = properties.find(qn('w:lang'))
    if language is not None and language.get(qn('w:val')) == TECHNICAL_LOCALE:
        language.attrib.pop(qn('w:val'))
        if not language.attrib and not len(language):
            properties.remove(language)
    return etree.tostring(properties) if len(properties) or properties.attrib else None


def _events(root):
    """Compare actual source characters/styles and all non-run XML structure.

    Run splitting and xml:space on new text fragments are allowed; everything
    else, including paragraph controls, fields and hyperlink ancestry, must
    stay identical. A global text-only assertion could miss moved content.
    """
    result = []
    def visit(node, style=None):
        if node.tag == qn('w:rPr'):
            return
        if node.tag == qn('w:r'):
            current = _run_style(node)
            for child in node:
                visit(child, current)
            return
        if node.tag == qn('w:t'):
            result.extend(('character', character, style) for character in node.text or '')
            return
        result.append(('open', node.tag, tuple(sorted(node.attrib.items())), node.text, style))
        for child in node:
            visit(child, style)
        result.append(('close', node.tag, node.tail))
    visit(root)
    return result


def _package(path):
    with ZipFile(path) as package:
        return {name: package.read(name) for name in package.namelist()}


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('context', ['sections', 'legacy', 'machine'])
def test_export_marks_technical_literals_without_addon_or_content_changes(tmp_path, monkeypatch, language, context):
    Image.new('RGB', (80, 160), '#327391').save(tmp_path / 'evidence.png')
    source_hash = sha256((tmp_path / 'evidence.png').read_bytes()).hexdigest()
    body = ('🧪 café 東京 Δ: ' + NATURAL + '\n\n'
            'Styled literal: **' + TOKEN[:16] + '**' + TOKEN[16:] + '\n\n'
            '[' + URL + '](' + URL + ')\n\n'
            '- List: ' + TOKEN + '\n\n'
            '| Context | Literal |\n|---|---|\n| Table | ' + TOKEN + ' |\n\n'
            'Before  \nAfter\n\n```text\n' + TOKEN + '\tvalue\n```')
    figure = {'figure': {'src': 'evidence.png', 'caption': 'café ' + TOKEN}}
    finding = {'id': 'F01', 'title': 'Audit ' + TOKEN, 'severity': 'info',
               'description_md': body, 'walkthrough': [figure]}
    if context == 'machine':
        finding.update(mode='machine', host={'name': 'Host ' + TOKEN}, summary_md=body,
                       phases=[{'name': 'Evidence', 'steps': [figure]}])
        finding.pop('walkthrough')
    data = {'meta': {'lang': language, 'theme': 'corporativo', 'report_title': 'Literal audit',
                     'branding': {'wordmark': HEADER, 'byline': FOOTER}},
            'report': {'sections': [{'key': 'findings'}]}, 'findings': [finding]}
    if context == 'legacy':
        data.pop('report')
    before = deepcopy(data)
    calls = []
    def mark(document):
        changed = mark_technical_text(document)
        calls.append(changed)
        return changed
    monkeypatch.setattr(word_export, 'mark_technical_text', mark)
    def external_process_forbidden(*args, **kwargs):
        raise AssertionError('DOCX export must not require an external renderer or addon')
    monkeypatch.setattr(subprocess, 'Popen', external_process_forbidden)
    candidate = tmp_path / 'candidate.docx'
    export.to_docx(data, data['meta'], engine.load_lang(language), tmp_path, candidate)
    assert len(calls) == 1 and calls[0] > 0
    monkeypatch.setattr(word_export, 'mark_technical_text', lambda document: 0)
    control = tmp_path / 'control.docx'
    export.to_docx(data, data['meta'], engine.load_lang(language), tmp_path, control)
    assert data == before
    assert sha256((tmp_path / 'evidence.png').read_bytes()).hexdigest() == source_hash

    actual, expected = _package(candidate), _package(control)
    assert actual.keys() == expected.keys()
    marked_stories = {}
    for name, blob in actual.items():
        story = name == 'word/document.xml' or name.startswith(('word/header', 'word/footer'))
        if not story or not name.endswith('.xml'):
            assert blob == expected[name], name
            continue
        root, baseline = etree.fromstring(blob), etree.fromstring(expected[name])
        assert _events(root) == _events(baseline), name
        assert root.xpath('.//w:t/text()', namespaces=NS) != []
        marked_stories[name] = ''.join(root.xpath(
            './/w:r[w:rPr/w:lang[@w:val="' + TECHNICAL_LOCALE + '"]]/w:t/text()', namespaces=NS))
    marked = ''.join(marked_stories.values())
    assert TOKEN in marked and URL in marked and HEADER in marked and FOOTER in marked
    assert any(HEADER in text for name, text in marked_stories.items() if name.startswith('word/header'))
    assert any(FOOTER in text for name, text in marked_stories.items() if name.startswith('word/footer'))
    assert NATURAL not in marked and 'café' not in marked and '東京' not in marked
    assert not any(character in marked for character in ('\u200b', '\u00ad', '\ufffc'))

    main = etree.fromstring(actual['word/document.xml'])
    assert len(main.xpath('.//w:tbl', namespaces=NS)) >= 2
    assert main.xpath('.//w:drawing', namespaces=NS)
    assert main.xpath('.//w:instrText[contains(., "PAGEREF")]', namespaces=NS)
    assert main.xpath('.//w:hyperlink[@w:anchor]', namespaces=NS)
    relationships = etree.fromstring(actual['word/_rels/document.xml.rels'])
    assert URL in [r.get('Target') for r in relationships if r.get('TargetMode') == 'External']
    document = Document(candidate)
    serialized = etree.tostring(document.element)
    assert mark_technical_text(document) == 0
    assert etree.tostring(document.element) == serialized
