"""A generated verification table flows after prior content, row by row."""
from pathlib import Path

import fitz
from lxml import html
import pytest
from weasyprint import HTML

import engine
from report_layout import prepare_html

THEMES = ('serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio')


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('language', ['es', 'en'])
def test_verification_table_uses_remaining_page_space_without_splitting_rows(theme, language):
    heading = 'Verificación técnica' if language == 'es' else 'Technical verification'
    state = 'Sin verificar' if language == 'es' else 'Unverified'
    rows = ''.join(f'<tr><td>F{i:02d}</td><td>{state}</td></tr>' for i in range(1, 25))
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    source = (f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>'
              '<section class="frontsec sect-rg_retest" id="rg_retest">'
              '<p style="height:420px">PRIOR_CONTENT</p>'
              f'<h3>{heading}</h3><table><thead><tr><th>Finding</th><th>Status</th></tr></thead>'
              f'<tbody>{rows}</tbody></table></section></body></html>')
    prepared = prepare_html(source)
    assert html.document_fromstring(prepared).text_content() == html.document_fromstring(source).text_content()
    document = HTML(string=prepared).render()
    with fitz.open(stream=document.write_pdf(), filetype='pdf') as pdf:
        texts = [page.get_text() for page in pdf]
    assert len(texts) == 2
    assert 'PRIOR_CONTENT' in texts[0] and heading in texts[0] and 'F01' in texts[0]
    assert all('Finding' in text and 'Status' in text for text in texts)
    identifiers = [word for text in texts for word in text.split() if len(word) == 3 and word.startswith('F') and word[1:].isdigit()]
    assert identifiers == [f'F{i:02d}' for i in range(1, 25)]
    assert all(f'F{i:02d}' in texts[-1] for i in (22, 23, 24))
    for page in document.pages:
        root = page._page_box
        top, bottom = root.content_box_y(), root.content_box_y() + root.height
        for box in root.descendants():
            if type(box).__name__ == 'TableRowBox':
                assert top - .1 <= box.position_y <= box.position_y + box.height <= bottom + .1
                text = ''.join(child.text for child in box.descendants() if type(child).__name__ == 'TextBox')
                assert ('FindingStatus' == text or state in text), text


def test_narrative_retest_entry_keeps_original_grouping():
    source = ('<section id="rg_retest"><h3>F01 · 2026-10-13</h3><p>Assessor: Synthetic</p>'
              '<p>Retest notes remain together.</p><h3>Verification</h3>'
              '<table><tr><td>F01</td><td>Unverified</td></tr></table></section>')
    tree = html.document_fromstring(prepare_html(source))
    groups = tree.xpath('//*[@id="rg_retest"]/div')
    assert groups[0].get('class') == 'retest-entry'
    assert len(groups[0].xpath('./h3|./p')) == 3
    assert 'retest-table-group' in groups[1].get('class', '').split()
    assert tree.text_content() == html.document_fromstring(source).text_content()
