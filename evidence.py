"""Flatten annotations and redactions into fresh pixels; originals stay private."""
from error_messages import message as backend_message
from io import BytesIO
import math
from PIL import Image, ImageDraw, ImageOps
from resources import local_image, relative_image
from storage import atomic_write
from workflows import new_uid

MAX_PIXELS = 25_000_000


def edit_image(directory, source, operations):
    if not isinstance(operations, list) or not operations or len(operations) > 100:
        raise ValueError(backend_message('Añade entre 1 y 100 anotaciones o censuras'))
    path = local_image(source, directory)
    if not source.startswith('img/'): raise ValueError(backend_message('Usa una imagen de img/'))
    with Image.open(path) as original:
        if original.width * original.height > MAX_PIXELS: raise ValueError(backend_message('Imagen mayor que 25 megapíxeles'))
        # Copy pixels into a new canvas: no EXIF, comments, extra frames or thumbnails.
        rotated = ImageOps.exif_transpose(original).convert('RGB')
        canvas = Image.new('RGB', rotated.size, 'white'); canvas.paste(rotated)
    draw = ImageDraw.Draw(canvas)
    redactions = []
    for item in operations:
        if not isinstance(item, dict) or item.get('type') not in ('redact', 'box', 'text', 'arrow'):
            raise ValueError(backend_message('Anotación inválida'))
        values = [item.get(k) for k in ('x', 'y', 'w', 'h')]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError(backend_message('Coordenadas inválidas'))
        x, y, w, h = values
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1.000001 or y + h > 1.000001:
            raise ValueError(backend_message('Las coordenadas deben estar dentro de la imagen (0–1)'))
        x1, y1 = math.floor(x * canvas.width), math.floor(y * canvas.height)
        x2, y2 = min(canvas.width - 1, math.ceil((x + w) * canvas.width)), min(canvas.height - 1, math.ceil((y + h) * canvas.height))
        bounds = (x1, y1, x2, y2)
        if item['type'] == 'redact': redactions.append(bounds)
        elif item['type'] == 'box': draw.rectangle(bounds, outline='#e11d48', width=max(2, canvas.width // 300))
        elif item['type'] == 'arrow':
            draw.line(bounds, fill='#e11d48', width=max(2, canvas.width // 300))
            size = max(5, canvas.width // 70); angle = math.atan2(y2-y1, x2-x1)
            draw.polygon([(x2, y2), (x2-size*math.cos(angle-.5), y2-size*math.sin(angle-.5)),
                          (x2-size*math.cos(angle+.5), y2-size*math.sin(angle+.5))], fill='#e11d48')
        else:
            text = item.get('text', '')
            if not isinstance(text, str) or not text or len(text) > 200: raise ValueError(backend_message('Texto de anotación inválido (1–200 caracteres)'))
            draw.rectangle(bounds, fill='#fff7ed')
            draw.text((x1 + 2, y1 + 2), text, fill='#9f1239', font_size=max(12, canvas.width // 60))
    # Redaction wins even if a later annotation overlaps it.
    for bounds in redactions: draw.rectangle(bounds, fill='black')
    output = BytesIO(); canvas.save(output, 'PNG')
    name = 'img/evidence-' + new_uid() + '.png'
    atomic_write(directory / name, output.getvalue())
    return name


def replace_references(value, old, new):
    canonical = relative_image(old)
    from safe_markup import replace_image_destinations
    from resources import markdown_fields
    fields = markdown_fields()
    def same(source):
        try:
            return relative_image(source) == canonical
        except ValueError:
            return False
    def replace(item, key=''):
        if isinstance(item, dict):
            return {k: (v if k in ('original', 'command') else replace(v, k)) for k, v in item.items()}
        if isinstance(item, list):
            return [replace(v) for v in item]
        if isinstance(item, str):
            if key in ('src', 'logo', 'client_logo', 'cover_image') and same(item):
                return new
            return replace_image_destinations(item, old, new) if '[' in item and (key.endswith('_md') or key in fields) else item
        return item
    return replace(value)
