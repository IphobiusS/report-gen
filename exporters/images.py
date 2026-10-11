"""Fit evidence to Word pages and normalize formats unsupported by OOXML tools."""
from error_messages import message as backend_message
from io import BytesIO
from functools import lru_cache
from math import ceil
from pathlib import Path
from PIL import Image, ImageOps
from docx.shared import Cm, Pt
from docx.oxml.ns import qn
from resources import local_image


def word_image_blob(blob):
    """The exact encoding embedded by Word, shared with delivery verification."""
    with Image.open(BytesIO(blob)) as original:
        if original.width * original.height > 25_000_000:
            raise ValueError(backend_message('Imagen mayor que 25 megapíxeles'))
        image = ImageOps.exif_transpose(original)
        size = image.size
        # Word/python-docx do not accept WebP. Fresh pixels also apply EXIF rotation.
        if original.format == 'WEBP' or image.size != original.size or original.getexif().get(274, 1) != 1:
            output = BytesIO()
            image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(output, 'PNG')
            return output.getvalue(), size
    return blob, size


def word_image(source, root):
    path = local_image(source, root)
    original = path.read_bytes()
    encoded, size = word_image_blob(original)
    return (str(path) if encoded is original else BytesIO(encoded)), size


def align_inline_picture(shape):
    # Omitted DrawingML distances acquire a 9pt side inset in Writer. Be
    # explicit so figures use the paragraph/cell width they were sized for.
    for edge in ('distL', 'distR', 'distT', 'distB'):
        shape._inline.set(edge, '0')
    return shape


@lru_cache(maxsize=1)
def _caption_font():
    from PIL import ImageFont
    return ImageFont.truetype(str(Path(__file__).with_name('fonts') / 'DejaVuSans.ttf'), 100)


def paragraph_width(document, paragraph):
    """The figure's containing text area, including cell padding and indents."""
    section = document.sections[-1]
    width = section.page_width - section.left_margin - section.right_margin
    cell = paragraph._parent
    if cell._element.tag == qn('w:tc'):
        width = cell.width or width
        # Markdown tables use Table Grid, whose inherited left/right cell
        # padding is 108 twips. Respect explicit cell/table overrides too.
        table = cell._tc.getparent().getparent()
        for edge, alias in (('left', 'start'), ('right', 'end')):
            margin = None
            for holder, name in ((cell._tc.tcPr, 'tcMar'), (table.tblPr, 'tblCellMar')):
                if holder is not None:
                    margins = holder.find(qn('w:' + name))
                    if margins is not None:
                        margin = margins.find(qn('w:' + alias))
                        if margin is None:
                            margin = margins.find(qn('w:' + edge))
                        if margin is not None:
                            break
            width -= Pt(int(margin.get(qn('w:w'), '0')) / 20) if margin is not None else Pt(5.4)
    for name in ('left_indent', 'right_indent'):
        value = getattr(paragraph.paragraph_format, name)
        if value is None:
            value = getattr(paragraph.style.paragraph_format, name)
        width -= max(0, value or 0)
    # A positive first-line indent also consumes room on a one-line drawing.
    width -= max(0, paragraph.paragraph_format.first_line_indent or 0)
    return max(1, int(width))


def figure_space(document, caption, font_size=10.5, width=None):
    """Reserve caption lines and preceding labels before sizing a Word figure.

    A fixed two-centimetre allowance fits a short caption but lets a portrait
    push a longer caption onto the next page. Use conservative bundled-font
    metrics; Word may substitute Calibri, and headings/step labels also need
    room in the same keep-with-next chain.
    """
    section = document.sections[-1]
    width = (width or section.page_width - section.left_margin - section.right_margin) / Pt(1)
    font = _caption_font()
    lines = 0
    for paragraph in str(caption or '').split('\n'):
        line = 0
        lines += 1
        for word in paragraph.split():
            length = font.getlength(word + ' ') * font_size / 100
            if line and line + length > width:
                lines += 1
                line = 0
            # Include unusually long unbroken identifiers, which Word wraps.
            extra = max(0, ceil(length / width) - 1)
            lines += extra
            length -= extra * width
            line += length
    return Cm(2) + Pt(lines * font_size * 1.3 + 12)


def fit_width(document, size, preferred, caption_space):
    section = document.sections[-1]
    available = section.page_width - section.left_margin - section.right_margin
    height = section.page_height - section.top_margin - section.bottom_margin - caption_space
    return max(1, min(int(preferred), available, int(height * size[0] / size[1])))
