"""Portrait evidence remains readable and travels with its complete caption."""
from copy import deepcopy
from hashlib import sha256

from lxml import html
import pdfplumber
from PIL import Image, ImageDraw
import pytest

import engine


CAPTIONS = {
    'en': ('Synthetic portrait evidence preserves the full request chronology, comparison identity '
           'and negative-control result. The first rows establish the intended tenant and service, '
           'the middle rows describe the modeled policy decision, and the final rows preserve the '
           'rejection expected for an unrelated tenant. Every identifier belongs to the generated '
           'fixture. The evidence does not represent a live capture, does not contain an operational '
           'credential and does not prove that a production bank has been tested or corrected. '
           'Keep this context attached to the complete portrait when exporting or reviewing the report.'),
    'es': ('La evidencia sintética conserva la cronología completa de la solicitud, la identidad '
           'comparada y el resultado del control negativo. Las primeras filas establecen el ámbito '
           'del servicio y del cliente; las intermedias describen la decisión modelada de la política, '
           'y las últimas conservan el rechazo esperado para un cliente ajeno. Todos los identificadores '
           'pertenecen al caso generado. La evidencia no representa una captura real, no contiene '
           'credenciales operativas y no demuestra que se haya evaluado o corregido un banco en '
           'producción. Este contexto debe permanecer unido a la imagen completa durante su exportación '
           'y revisión.'),
}


def source(tmp_path, language='en', theme='corporativo', size=(800, 1600)):
    picture = Image.new('RGB', size, 'white')
    ImageDraw.Draw(picture).rectangle((1, 1, size[0] - 2, size[1] - 2), outline='black')
    picture.save(tmp_path / 'portrait.png')
    return {'meta': {'lang': language, 'theme': theme, 'report_density': 'compact'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'title': 'Portrait evidence', 'severity': 'medium',
                          'description_md': 'Synthetic observed control.'}]}


def render(data, tmp_path):
    language = data['meta']['lang']
    markup = engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, False,
                                engine.load_lang(language))
    target = tmp_path / 'report.pdf'
    engine.render_pdf_weasyprint(markup, target, tmp_path)
    return markup, target


@pytest.mark.parametrize('theme', ['corporativo', 'ejecutivo', 'laboratorio'])
@pytest.mark.parametrize('language', ['en', 'es'])
def test_portrait_and_long_caption_share_page_in_three_contexts(tmp_path, language, theme):
    data = source(tmp_path, language, theme)
    caption = CAPTIONS[language]
    data['findings'][0]['walkthrough'] = [{'lead': 'STEP_LABEL', 'figure': {
        'src': 'portrait.png', 'caption': 'CAPTION_STEP ' + caption + ' END_STEP'}}]
    data['report']['sections'] += [
        {'key': 'notes', 'title': 'BLOCK_LABEL',
         'body': '![CAPTION_BLOCK ' + caption + ' END_BLOCK](portrait.png)'},
        {'key': 'inline_note', 'title': 'INLINE_LABEL',
         'body': 'Preceding context. ![CAPTION_INLINE ' + caption +
                 ' END_INLINE](portrait.png) Following context.'},
    ]
    original = deepcopy(data)
    image_before = sha256((tmp_path / 'portrait.png').read_bytes()).hexdigest()
    markup, target = render(data, tmp_path)
    with pdfplumber.open(target) as pdf:
        image_pages = [page for page in pdf.pages if page.images]
        assert len(image_pages) == 3
        for page, label in zip(image_pages, ['STEP', 'BLOCK', 'INLINE']):
            assert len(page.images) == 1
            placed = page.images[0]
            height = placed['height'] * 25.4 / 72
            assert 180 <= height <= 200
            assert placed['width'] / placed['height'] == pytest.approx(.5, abs=.001)
            # A source transcript set in 26px is now at least 8.5pt on paper.
            assert placed['height'] / 1600 * 26 >= 8.5
            text = ' '.join((page.extract_text() or '').split())
            assert 'CAPTION_' + label in text and 'END_' + label in text
            assert ' '.join(caption.split()) in text
            assert placed['top'] >= 20 * 72 / 25.4 - 1
            assert placed['bottom'] < page.height - 18 * 72 / 25.4
    tree = html.document_fromstring(markup)
    assert len(tree.xpath('//figure[contains(@class,"rg-tall")]')) == 3
    assert data == original
    assert sha256((tmp_path / 'portrait.png').read_bytes()).hexdigest() == image_before


def test_landscape_walkthrough_keeps_existing_physical_size(tmp_path):
    data = source(tmp_path, size=(1600, 800))
    data['findings'][0]['walkthrough'] = [{'figure': {'src': 'portrait.png', 'caption': 'LANDSCAPE'}}]
    markup, target = render(data, tmp_path)
    assert 'rg-tall' not in markup
    with pdfplumber.open(target) as pdf:
        placed = next(image for page in pdf.pages for image in page.images)
        assert placed['height'] * 25.4 / 72 == pytest.approx(62, abs=.1)
        assert placed['width'] / placed['height'] == pytest.approx(2, abs=.001)


def test_explicit_markdown_width_is_not_enlarged(tmp_path):
    data = source(tmp_path)
    data['findings'][0]['description_md'] = '![EXPLICIT_WIDTH](portrait.png){width=35mm}'
    markup, target = render(data, tmp_path)
    image = html.document_fromstring(markup).xpath('//figure/img')[0]
    assert image.get('style') == 'width:35mm'
    with pdfplumber.open(target) as pdf:
        placed = next(image for page in pdf.pages for image in page.images)
        assert placed['width'] * 25.4 / 72 == pytest.approx(35, abs=.1)
        assert placed['height'] * 25.4 / 72 == pytest.approx(70, abs=.1)


def test_machine_and_preview_resource_base_classify_without_source_mutation(tmp_path):
    data = source(tmp_path)
    data['findings'] = [{'id': 'M01', 'mode': 'machine', 'host': {'name': 'Laboratory'},
                         'phases': [{'name': 'Observation', 'steps': [
                             {'figure': {'src': 'portrait.png', 'caption': 'Machine evidence'}}]}]}]
    original = deepcopy(data)
    markup = engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, False,
                                engine.load_lang('en'), img_base='/api/projects/local/resource/')
    tree = html.document_fromstring(markup)
    assert len(tree.xpath('//figure[contains(@class,"rg-tall")]')) == 1
    assert tree.xpath('//figure/img')[0].get('src') == '/api/projects/local/resource/portrait.png'
    assert data == original


@pytest.mark.parametrize('size', [(1200, 946), (1200, 990), (1200, 1122), (900, 1164)])
def test_near_square_and_portrait_transcripts_have_readable_physical_scale(tmp_path, size):
    data = source(tmp_path, size=size)
    data['findings'][0]['walkthrough'] = [{'figure': {
        'src': 'portrait.png', 'caption': CAPTIONS['en'] + ' END_NEAR_SQUARE'}}]
    _, target = render(data, tmp_path)
    with pdfplumber.open(target) as pdf:
        page = next(page for page in pdf.pages if page.images)
        placed = page.images[0]
        # 30px is the source transcript font; this is a geometric check,
        # not a claim that arbitrary raster text has been recognized by OCR.
        assert placed['height'] / size[1] * 30 >= 10
        assert placed['width'] / placed['height'] == pytest.approx(size[0] / size[1], abs=.001)
        assert 'END_NEAR_SQUARE' in (page.extract_text() or '')


def test_layout_hint_bounds_metadata_reads_and_preserves_resource_boundary(tmp_path, monkeypatch):
    data = source(tmp_path)
    data['findings'][0]['walkthrough'] = [{'figure': {'src': 'portrait.png', 'caption': 'Safe local image'}}]
    path = tmp_path / 'portrait.png'
    with path.open('wb') as image:
        image.truncate(12 * 1024 * 1024 + 1)
    monkeypatch.setattr(Image, 'open', lambda *_a, **_kw: pytest.fail('Oversized metadata read'))
    assert engine._tall_figure_image(path) is False

    outside = tmp_path.parent / 'outside-portrait.png'
    outside.write_bytes(b'not an allowed project image')
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ValueError, match='engagement'):
        engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, False, engine.load_lang('en'))


def test_editing_an_image_at_the_same_path_refreshes_the_layout_hint(tmp_path):
    data = source(tmp_path)
    data['findings'][0]['walkthrough'] = [{'figure': {'src': 'portrait.png', 'caption': 'Editable image'}}]
    def markup():
        return engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, False,
                                  engine.load_lang('en'))
    assert 'rg-tall' in markup()
    Image.new('RGB', (1600, 800), 'white').save(tmp_path / 'portrait.png')
    assert 'rg-tall' not in markup()


def test_png_layout_hint_never_decodes_pixels_to_find_missing_exif(tmp_path, monkeypatch):
    from PIL import PngImagePlugin
    source(tmp_path)
    monkeypatch.setattr(PngImagePlugin.PngImageFile, 'load',
                        lambda *_a, **_kw: pytest.fail('Layout hint decoded PNG pixels'))
    assert engine._tall_figure_image(tmp_path / 'portrait.png') is True


def test_jpeg_orientation_is_read_from_available_exif(tmp_path, monkeypatch):
    from PIL import JpegImagePlugin
    picture = Image.new('RGB', (1600, 800), 'white')
    orientation = Image.Exif()
    orientation[274] = 6
    path = tmp_path / 'oriented.jpg'
    picture.save(path, exif=orientation)
    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, 'load',
                        lambda *_a, **_kw: pytest.fail('Layout hint decoded JPEG pixels'))
    assert engine._tall_figure_image(path) is True
