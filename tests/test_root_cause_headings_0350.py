"""Generated group labels stay with their content without rewriting author prose."""
from copy import deepcopy

from docx import Document
from lxml import html
import pytest

import engine
import export
from safe_markup import md
import workflows


LABELS = [
    ('es', 'Causa raíz', 'Acción común'),
    ('en', 'Root cause', 'Shared action'),
    ('pt', 'Causa raiz', 'Ação comum'),
]
GROUP_NAME = 'Synthetic shared control'
CAUSE = '**Causa raíz**\n\nAUTHOR_CAUSE: preserve this authored bold label.'
ACTION = '**Acción común**\n\nAUTHOR_ACTION: preserve this authored bold label.'


def document(language):
    group_uid = '00000000-0000-4000-8000-000000000001'
    return {
        'meta': {'lang': language, 'theme': 'ejecutivo', 'report_title': 'Synthetic group audit'},
        'report': {'sections': [{'key': 'findings'}],
                   'workflow': {'include_root_causes': True}},
        'root_cause_groups': [{'uid': group_uid, 'name': GROUP_NAME,
                               'cause_md': CAUSE, 'remediation_md': ACTION}],
        'findings': [{'id': 'F01', 'title': 'Synthetic finding', 'severity': 'info',
                      'root_cause_uid': group_uid}],
    }


@pytest.mark.parametrize('language,cause_label,action_label', LABELS)
def test_localized_group_subheadings_preserve_hierarchy_and_authored_markdown(
        language, cause_label, action_label):
    data = document(language)
    original = deepcopy(data)
    section = next(row for row in workflows.report_sections(data)
                   if row['key'] == 'rg_root_causes')
    body = section['body']
    tree = html.fragment_fromstring(str(md(body)), create_parent='div')

    assert [(node.tag, node.text_content()) for node in tree.xpath('./h3|./h4')] == [
        ('h3', GROUP_NAME), ('h4', cause_label), ('h4', action_label)]
    assert tree.xpath('./p/strong/text()') == ['Causa raíz', 'Acción común']
    assert CAUSE in body and ACTION in body
    assert data == original


@pytest.mark.parametrize('language,cause_label,action_label', LABELS)
def test_docx_group_subheadings_keep_with_following_content(
        tmp_path, language, cause_label, action_label):
    data = document(language)
    original = deepcopy(data)
    target = tmp_path / 'root-causes.docx'
    export.to_docx(data, data['meta'], engine.load_lang(language), tmp_path, target)
    paragraphs = Document(target).paragraphs

    for label, authored_label in ((cause_label, 'Causa raíz'), (action_label, 'Acción común')):
        index = next(i for i, paragraph in enumerate(paragraphs)
                     if paragraph.text == label and paragraph.style.name == 'Heading 4')
        paragraph = paragraphs[index]
        keep_next = paragraph.paragraph_format.keep_with_next
        if keep_next is None:
            keep_next = paragraph.style.paragraph_format.keep_with_next
        assert keep_next is True
        # A user-written bold label remains an ordinary editable paragraph.
        authored = paragraphs[index + 1]
        assert authored.text == authored_label
        assert authored.style.name == 'Normal'
        assert any(run.bold for run in authored.runs)
    assert any(p.text == GROUP_NAME and p.style.name == 'Heading 3' for p in paragraphs)
    assert data == original
