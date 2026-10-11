"""Running header columns retain their text without collisions or body intrusion."""
import re

import pytest
from weasyprint import HTML

import engine


THEMES = ('serio', 'corporativo', 'offsec', 'htb', 'ejecutivo', 'laboratorio')
CASES = (
    ('en', 'Security assessment of settlement and document services',
     'ASTER LAB', 'SIMULATION', '1.0'),
    ('es', 'Evaluación de seguridad de servicios de liquidación y documentales',
     'ASTER LAB', 'SIMULACIÓN', '1.0'),
    ('en', 'Independent technical security assessment of settlement, document processing '
     'and sensitive banking service operations',
     'ASTER INDEPENDENT SECURITY ASSESSMENT AND ASSURANCE LABORATORY',
     'CONFIDENTIAL - AUTHORIZED SECURITY REVIEW RECIPIENTS ONLY', '2026.10.11-final'),
)


def header_document(tmp_path, theme, case):
    language, title, wordmark, classification, version = case
    data = {'meta': {'lang': language, 'theme': theme, 'report_title': title,
                     'version': version, 'date': '2026-10-11',
                     'branding': {'wordmark': wordmark, 'confidential_text': classification}},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'title': 'Synthetic layout observation',
                          'description_md': 'Body content remains inside the original page margins.'}]}
    markup = engine.render_html(engine.build_env(), data, tmp_path, {}, False,
                                engine.load_lang(language))
    return HTML(string=markup, base_url=str(tmp_path)).render()


def compact(text):
    return re.sub(r'\s+', '', text)


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('case', CASES, ids=('aster-en', 'aster-es', 'long-metadata'))
def test_running_headers_have_separate_columns_and_preserve_text(tmp_path, theme, case):
    document = header_document(tmp_path, theme, case)
    assert len(document.pages) == 3
    language, title, wordmark, classification, version = case
    expected = [wordmark, title, f'{classification} | v{version} | 2026-10-11']
    # Physical units are CSS px in WeasyPrint's layout tree.
    mm = 96 / 25.4
    for page in document.pages[1:]:
        page_box = page._page_box
        body = next(box for box in page_box.children if box.element_tag == 'html')
        assert body.position_x == pytest.approx(16 * mm)
        assert body.position_y == pytest.approx(20 * mm)
        assert body.width == pytest.approx(178 * mm)
        boxes = {getattr(box, 'at_keyword', ''): box for box in page_box.children}
        rectangles = []
        for keyword, text in zip(('@top-left', '@top-center', '@top-right'), expected):
            column = boxes[keyword]
            glyphs = [box for box in column.descendants() if type(box).__name__ == 'TextBox']
            assert glyphs
            assert compact(''.join(box.text for box in glyphs)) == compact(text)
            left = min(box.position_x for box in glyphs)
            right = max(box.position_x + box.width for box in glyphs)
            top = min(box.position_y for box in glyphs)
            bottom = max(box.position_y + box.height for box in glyphs)
            assert left >= 16 * mm - .1
            assert right <= 194 * mm + .1
            assert top >= 0
            assert bottom <= body.position_y - 2 * mm
            rectangles.append((left, right))
        # Real text bounds, not merely declared CSS widths, must have a gutter.
        for left, right in zip(rectangles, rectangles[1:]):
            assert right[0] - left[1] >= 2 * mm - .1
    # Cover still has all authored values and no running header duplication.
    cover = document.pages[0]._page_box
    assert not any(getattr(box, 'at_keyword', '').startswith('@top-') for box in cover.children)
    cover_text = ''.join(box.text for box in cover.descendants(placeholders=True) if type(box).__name__ == 'TextBox')
    for value in (title, wordmark, classification, version):
        assert compact(value) in compact(cover_text)
