"""Fit evidence to Word pages and normalize formats unsupported by OOXML tools."""
from error_messages import message as backend_message
from io import BytesIO
from PIL import Image, ImageOps
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


def fit_width(document, size, preferred, caption_space):
    section = document.sections[-1]
    available = section.page_width - section.left_margin - section.right_margin
    height = section.page_height - section.top_margin - section.bottom_margin - caption_space
    return max(1, min(int(preferred), available, int(height * size[0] / size[1])))
