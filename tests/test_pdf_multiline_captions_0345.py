"""Authored caption lines survive pagination without shrinking evidence."""
from copy import deepcopy
from hashlib import sha256

import fitz
from PIL import Image
import pytest

import engine


@pytest.mark.parametrize('theme', ['corporativo', 'ejecutivo', 'htb', 'laboratorio', 'offsec', 'serio'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_multiline_caption_keeps_lines_and_full_image_across_pages(tmp_path, theme, language):
    picture = tmp_path / 'evidence.png'
    Image.new('RGB', (800, 1600), 'navy').save(picture)
    original_image = sha256(picture.read_bytes()).hexdigest()
    lines = [f'CAPTION_{number:02d}: synthetic annotation.' for number in range(1, 61)]
    caption = '\n'.join(lines)
    data = {'meta': {'lang': language, 'theme': theme},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'title': 'Synthetic documentary fixture', 'severity': 'info',
                          'walkthrough': [{'figure': {'src': picture.name, 'caption': caption}}]}]}
    original = deepcopy(data)
    markup = engine.render_html(engine.build_env(), data, tmp_path, {}, False, engine.load_lang(language))
    output = tmp_path / 'report.pdf'
    engine.render_pdf_weasyprint(markup, output, tmp_path)
    with fitz.open(output) as pdf:
        positions = []
        for text in lines:
            matches = [(page.number, rect) for page in pdf for rect in page.search_for(text)]
            assert len(matches) == 1, text
            positions.append(matches[0])
        # Separate source lines cannot be flattened into one flowing paragraph.
        for (page_a, rect_a), (page_b, rect_b) in zip(positions, positions[1:]):
            assert page_b > page_a or rect_b.y0 > rect_a.y0 + 5
        assert len({page for page, _ in positions}) > 1
        pictures = [(page.number, box) for page in pdf for image in page.get_image_info()
                    for box in [fitz.Rect(image['bbox'])]]
        assert len(pictures) == 1
        page_number, box = pictures[0]
        assert box.height >= 180 * 72 / 25.4
        assert box.width / box.height == pytest.approx(.5, abs=.001)
        assert page_number == positions[0][0]
        assert box.y1 < positions[0][1].y0
        for page_number, rect in positions:
            assert rect.y1 < pdf[page_number].rect.height - 18 * 72 / 25.4 + 2
    assert data == original
    assert sha256(picture.read_bytes()).hexdigest() == original_image
