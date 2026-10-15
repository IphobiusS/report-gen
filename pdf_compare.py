"""Read-only PDF raster comparison, with bounded disposable worker processes.

Page positions are compared, not document meaning. PDF actions, scripts, links
and embedded files are never opened. Only PNG pixels enter the downloadable HTML.
"""
from base64 import b64encode
from hashlib import sha256
from html import escape
from io import BytesIO
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from error_messages import message as backend_message
from input_guard import ensure_data_tree
from languages import language_tag, normalize_language

MAX_PDF = 16 * 1024 * 1024
MAX_PAGES = 80
MAX_TOTAL_PIXELS = 64_000_000
MAX_PAGE_PIXELS = 1_500_000
MAX_SIDE = 1280
MAX_OUTPUT = 32 * 1024 * 1024
MAX_MEMORY = 768 * 1024 * 1024
TIMEOUT = 45
CPU_SECONDS = 40
_WORKERS = threading.BoundedSemaphore(1)
CSP = ("default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
       "img-src data:; object-src 'none'; base-uri 'none'; form-action 'none'")

_ERRORS = {
    'invalid': lambda lang: backend_message('PDF no válido o mayor que 16 MiB.',
        en='Invalid PDF or file exceeds 16 MiB.', pt='PDF inválido ou arquivo maior que 16 MiB.', language=lang),
    'encrypted': lambda lang: backend_message('No se admiten PDF cifrados, aunque la contraseña esté vacía.',
        en='Encrypted PDFs are not supported, including empty passwords.', pt='PDFs criptografados não são aceitos, mesmo com senha vazia.', language=lang),
    'pages': lambda lang: backend_message('Cada PDF debe tener entre 1 y 80 páginas.',
        en='Each PDF must contain between 1 and 80 pages.', pt='Cada PDF deve conter entre 1 e 80 páginas.', language=lang),
    'geometry': lambda lang: backend_message('El PDF tiene dimensiones no válidas o una escala UserUnit no compatible.',
        en='The PDF has invalid dimensions or an unsupported UserUnit scale.', pt='O PDF tem dimensões inválidas ou uma escala UserUnit incompatível.', language=lang),
    'pixels': lambda lang: backend_message('La comparación supera el límite de 64 millones de píxeles. Divide los PDF.',
        en='The comparison exceeds 64 million pixels. Split the PDFs.', pt='A comparação excede 64 milhões de pixels. Divida os PDFs.', language=lang),
    'output': lambda lang: backend_message('La comparación supera 32 MiB. Divide los PDF.',
        en='The comparison exceeds 32 MiB. Split the PDFs.', pt='A comparação excede 32 MiB. Divida os PDFs.', language=lang),
    'timeout': lambda lang: backend_message('La comparación agotó el límite de 45 segundos. Divide los PDF.',
        en='The comparison exceeded 45 seconds. Split the PDFs.', pt='A comparação excedeu 45 segundos. Divida os PDFs.', language=lang),
    'limits': lambda lang: backend_message('No se pudo comparar el PDF dentro de los límites de memoria y proceso.',
        en='Could not compare the PDFs within memory and process limits.', pt='Não foi possível comparar os PDFs dentro dos limites de memória e processo.', language=lang),
    'busy': lambda lang: backend_message('Ya hay una comparación en curso. Vuelve a intentarlo al terminar.',
        en='A comparison is already running. Try again when it finishes.', pt='Já existe uma comparação em andamento. Tente novamente ao terminar.', language=lang),
    'unavailable': lambda lang: backend_message('Faltan las dependencias de PDF. Reinstala report-gen con sus dependencias.',
        en='PDF dependencies are missing. Reinstall report-gen with its dependencies.', pt='Faltam as dependências de PDF. Reinstale report-gen com suas dependências.', language=lang),
    'language': lambda lang: backend_message('Idiomas admitidos: es, en, pt (pt-BR).',
        en='Supported languages: es, en, pt (pt-BR).', pt='Idiomas disponíveis: es, en, pt (pt-BR).', language=lang),
    'request': lambda lang: backend_message('Sube exactamente dos PDF, antes y después, y un idioma opcional.',
        en='Upload exactly two PDFs, before and after, and an optional language.', pt='Envie exatamente dois PDFs, antes e depois, e um idioma opcional.', language=lang),
}

_TEXT = {
    'es': {
        'title': 'Comparación visual de PDF', 'before': 'Antes', 'after': 'Después',
        'difference': 'Diferencias resaltadas', 'page': 'Página', 'pages': 'Páginas comparadas',
        'unchanged': 'Sin cambios de píxeles', 'changed': 'Píxeles diferentes',
        'added': 'Añadida', 'removed': 'Eliminada', 'dimensions_changed': 'Dimensiones diferentes',
        'missing': 'No hay página en esta posición.', 'pixels': 'píxeles diferentes',
        'size': 'Dimensiones PDF', 'scale': 'Escala de rasterización',
        'method': 'Las páginas se emparejan por posición y se alinean por la esquina superior izquierda. Cada pareja comparte escala, hasta 96 ppp y 1280 píxeles por lado. Se comparan los valores RGB exactos, sin tolerancia. El magenta marca diferencias sobre una vista atenuada.',
        'limits': 'Un cambio de orden o una página insertada puede desplazar todas las comparaciones siguientes. El resultado describe estos píxeles, no equivalencia semántica, accesibilidad, enlaces ni aprobación del informe. Las páginas totalmente blancas pueden conservar los píxeles aunque sus dimensiones cambien.',
        'privacy': 'Procesado en el servidor donde ejecutas report-gen, sin servicios externos. Los PDF temporales se eliminan al terminar. Este HTML contiene imágenes de los documentos; compártelo con el mismo cuidado que los originales.',
        'static': 'Solo se muestran imágenes estáticas: no se ejecutan acciones, formularios ni scripts de los PDF. Una página añadida o eliminada resalta toda su superficie.',
        'hash': 'SHA-256 de los PDF originales', 'renderer': 'Motor', 'same_bytes': 'Los archivos originales tienen el mismo SHA-256.',
    },
    'en': {
        'title': 'Visual PDF comparison', 'before': 'Before', 'after': 'After',
        'difference': 'Highlighted differences', 'page': 'Page', 'pages': 'Compared page positions',
        'unchanged': 'Unchanged pixels', 'changed': 'Different pixels',
        'added': 'Added', 'removed': 'Removed', 'dimensions_changed': 'Different dimensions',
        'missing': 'No page at this position.', 'pixels': 'different pixels',
        'size': 'PDF dimensions', 'scale': 'Raster scale',
        'method': 'Pages are paired by position and aligned at the top-left corner. Each pair uses a shared scale, up to 96 dpi and 1280 pixels per side. Exact RGB values are compared without tolerance. Magenta marks differences over a faded view.',
        'limits': 'Reordering or inserting a page can shift every subsequent comparison. This result describes these pixels, not semantic equivalence, accessibility, links or report approval. Entirely white pages may retain identical pixels while their dimensions change.',
        'privacy': 'Processed on the server running report-gen, without external services. Temporary PDFs are deleted when processing finishes. This HTML contains document images; share it as carefully as the originals.',
        'static': 'Only static images are shown: PDF actions, forms and scripts are not executed. Added and removed pages highlight their entire surface.',
        'hash': 'Original PDF SHA-256', 'renderer': 'Renderer', 'same_bytes': 'The original files have the same SHA-256.',
    },
    'pt': {
        'title': 'Comparação visual de PDF', 'before': 'Antes', 'after': 'Depois',
        'difference': 'Diferenças destacadas', 'page': 'Página', 'pages': 'Posições comparadas',
        'unchanged': 'Pixels sem alterações', 'changed': 'Pixels diferentes',
        'added': 'Adicionada', 'removed': 'Removida', 'dimensions_changed': 'Dimensões diferentes',
        'missing': 'Não há página nesta posição.', 'pixels': 'pixels diferentes',
        'size': 'Dimensões do PDF', 'scale': 'Escala de renderização',
        'method': 'As páginas são pareadas por posição e alinhadas pelo canto superior esquerdo. Cada par usa a mesma escala, até 96 ppp e 1280 pixels por lado. Os valores RGB exatos são comparados sem tolerância. O magenta marca diferenças sobre uma imagem atenuada.',
        'limits': 'Reordenar ou inserir uma página pode deslocar todas as comparações seguintes. O resultado descreve estes pixels, não equivalência semântica, acessibilidade, links ou aprovação do relatório. Páginas totalmente brancas podem manter pixels iguais mesmo com dimensões diferentes.',
        'privacy': 'Processado no servidor que executa report-gen, sem serviços externos. Os PDFs temporários são excluídos ao terminar. Este HTML contém imagens dos documentos; compartilhe-o com o mesmo cuidado que os originais.',
        'static': 'Somente imagens estáticas são exibidas: ações, formulários e scripts dos PDFs não são executados. Páginas adicionadas e removidas destacam toda a sua superfície.',
        'hash': 'SHA-256 dos PDFs originais', 'renderer': 'Motor', 'same_bytes': 'Os arquivos originais têm o mesmo SHA-256.',
    },
}


class _Rejected(Exception):
    """Worker-only bounded error code; never expose third-party parser details."""


def error(code, language=None):
    return _ERRORS.get(code, _ERRORS['limits'])(language)


def available():
    return all(importlib.util.find_spec(name) is not None for name in ('pypdfium2', 'pypdf', 'PIL'))


def capabilities():
    return dict(available=available(), max_pdf_bytes=MAX_PDF, max_pages_per_pdf=MAX_PAGES,
                max_total_pixels=MAX_TOTAL_PIXELS, max_output_bytes=MAX_OUTPUT,
                timeout_seconds=TIMEOUT, memory_limit_bytes=MAX_MEMORY,
                alignment='page_position_top_left', rgb_tolerance=0, max_dpi=96,
                server_retention=False, external_services=False)


def compare(before, after, language='es'):
    """Return a self-contained HTML byte string; retain no server-side record."""
    language = normalize_language(language, None)
    if language is None:
        raise ValueError(error('language'))
    for raw in (before, after):
        if not isinstance(raw, bytes) or not raw.startswith(b'%PDF-') or len(raw) > MAX_PDF:
            raise ValueError(error('invalid', language))
    if not available():
        raise ValueError(error('unavailable', language))
    if not _WORKERS.acquire(blocking=False):
        raise ValueError(error('busy', language))
    try:
        # TemporaryDirectory is private, random and removed on every exit path.
        # The child writes to files instead of an unbounded subprocess PIPE.
        with tempfile.TemporaryDirectory(prefix='report-gen-pdf-compare-') as folder:
            directory = Path(folder)
            (directory / 'before.pdf').write_bytes(before)
            (directory / 'after.pdf').write_bytes(after)
            try:
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), '--worker', folder, language],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=TIMEOUT, check=False)
            except subprocess.TimeoutExpired as exc:
                raise ValueError(error('timeout', language)) from exc
            except OSError as exc:
                raise ValueError(error('limits', language)) from exc
            if result.returncode:
                code = 'limits'
                status = directory / 'status'
                if status.exists():
                    with status.open('rb') as stream:
                        candidate = stream.read(32).decode('ascii', errors='ignore')
                    if candidate in _ERRORS:
                        code = candidate
                raise ValueError(error(code, language))
            try:
                with (directory / 'comparison.html').open('rb') as stream:
                    result = stream.read(MAX_OUTPUT + 1)
            except OSError as exc:
                raise ValueError(error('limits', language)) from exc
            if len(result) > MAX_OUTPUT or not result.startswith(b'<!doctype html>'):
                raise ValueError(error('output', language))
            return result
    finally:
        _WORKERS.release()


def _resource_limits():
    """Fail closed if the OS cannot establish the worker's memory/time limits."""
    if os.name == 'nt':
        import ctypes
        from types import SimpleNamespace
        from export_jobs import _WindowsJob
        job = _WindowsJob()
        limits = job.limits_type()
        # Per-process memory and CPU, one process, no breakaway, kill on close.
        limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x100 | 0x2 | 0x8
        limits.BasicLimitInformation.PerProcessUserTimeLimit = CPU_SECONDS * 10_000_000
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        limits.ProcessMemoryLimit = MAX_MEMORY
        if not job.api.SetInformationJobObject(job.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        job.assign(SimpleNamespace(_handle=-1))  # GetCurrentProcess pseudo handle.
        return job  # Keep the job handle alive until the worker exits.
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY, MAX_MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT, MAX_OUTPUT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return None


def _validated_document(raw):
    from pypdf import PdfReader
    import pypdfium2
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise _Rejected('encrypted')
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise _Rejected('pages')
        # PDFium does not account for UserUnit. Refuse a misleading size/scale.
        for page in reader.pages:
            unit = page.get('/UserUnit', 1)
            if isinstance(unit, bool) or not isinstance(unit, (int, float)) or unit != 1:
                raise _Rejected('geometry')
        document = pypdfium2.PdfDocument(raw)
        if len(document) != len(reader.pages):
            document.close()
            raise _Rejected('invalid')
        # No init_forms(), action dispatch or text/attachment extraction.
        return document
    except _Rejected:
        raise
    except Exception as exc:
        raise _Rejected('invalid') from exc


def _geometry(document):
    dimensions = []
    for index in range(len(document)):
        page = document[index]
        try:
            width, height = page.get_size()
        finally:
            page.close()
        if not all(math.isfinite(v) and 0 < v <= 14400 for v in (width, height)):
            raise _Rejected('geometry')
        dimensions.append((width, height))
    return dimensions


def _plans(left, right):
    rows, total = [], 0
    for index in range(max(len(left), len(right))):
        first = left[index] if index < len(left) else None
        second = right[index] if index < len(right) else None
        width = max(size[0] for size in (first, second) if size)
        height = max(size[1] for size in (first, second) if size)
        scale = min(96 / 72, MAX_SIDE / width, MAX_SIDE / height,
                    math.sqrt((MAX_PAGE_PIXELS - 2 * MAX_SIDE) / (width * height)))
        canvas = (math.ceil(width * scale), math.ceil(height * scale))
        pixels = canvas[0] * canvas[1]
        total += pixels
        if pixels > MAX_PAGE_PIXELS or total > MAX_TOTAL_PIXELS:
            raise _Rejected('pixels')
        rows.append(dict(number=index + 1, before_points=list(first) if first else None,
                         after_points=list(second) if second else None,
                         scale=scale, canvas_pixels=list(canvas), total_pixels=pixels))
    return rows


def _raster(document, index, scale):
    if index >= len(document):
        return None
    page, bitmap = document[index], None
    try:
        bitmap = page.render(scale=scale, may_draw_forms=False, draw_annots=True,
                             fill_color=(255, 255, 255, 255))
        try:
            return bitmap.to_pil().convert('RGB')
        finally:
            bitmap.close()
    finally:
        page.close()


def _png(image):
    stream = BytesIO()
    image.save(stream, format='PNG')
    return b64encode(stream.getvalue()).decode('ascii')


def _page_html(row, before, after, highlight, text):
    columns = []
    for key, image in (('before', before), ('after', after), ('difference', highlight)):
        content = ('<p class="missing">' + escape(text['missing']) + '</p>' if image is None else
                   f'<img class="{key}-image" width="{image.width}" height="{image.height}" '
                   f'alt="{escape(text[key])} · {row["number"]}" src="data:image/png;base64,{_png(image)}">')
        columns.append(f'<figure><figcaption>{escape(text[key])}</figcaption>{content}</figure>')
    dimensions = ' → '.join('—' if size is None else f'{size[0]:g} × {size[1]:g} pt'
                            for size in (row['before_points'], row['after_points']))
    return (f'<section class="comparison-page" data-status="{row["status"]}" id="page-{row["number"]}">'
            f'<h2>{escape(text["page"])} {row["number"]} <span>{escape(text[row["status"]])}</span></h2>'
            f'<p>{row["changed_pixels"]:,} / {row["total_pixels"]:,} {escape(text["pixels"])} '
            f'({row["changed_percent"]:.3f}%) · {escape(text["size"])}: {dimensions} · '
            f'{escape(text["scale"])}: {row["scale"]:.6f}</p><div class="images">' + ''.join(columns) + '</div></section>')


def _comparison(before, after, language):
    from PIL import Image, ImageChops, ImageOps
    import pypdfium2
    text = _TEXT[language]
    with _validated_document(before) as left, _validated_document(after) as right:
        rows = _plans(_geometry(left), _geometry(right))
        manifest = dict(schema='report-gen-pdf-comparison/1', language=language,
                        before_sha256=sha256(before).hexdigest(), after_sha256=sha256(after).hexdigest(),
                        before_bytes=len(before), after_bytes=len(after),
                        before_pages=len(left), after_pages=len(right),
                        renderer='PDFium ' + str(pypdfium2.PDFIUM_INFO), alignment='page_position_top_left',
                        max_dpi=96, rgb_tolerance=0, semantic_equivalence_verified=False,
                        summary={key: 0 for key in ('unchanged', 'changed', 'added', 'removed', 'dimensions_changed')},
                        pages=rows)
        parts, output_size = [], 0
        for index, row in enumerate(rows):
            first = _raster(left, index, row['scale'])
            second = _raster(right, index, row['scale'])
            canvas = tuple(row['canvas_pixels'])
            old, new = Image.new('RGB', canvas, 'white'), Image.new('RGB', canvas, 'white')
            if first is not None:
                old.paste(first, (0, 0))
            if second is not None:
                new.paste(second, (0, 0))
            if first is None or second is None:
                mask = Image.new('L', canvas, 255)
                row['status'] = 'added' if first is None else 'removed'
            else:
                channels = ImageChops.difference(old, new).split()
                mask = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2]).point(lambda value: 255 if value else 0)
                row['status'] = ('dimensions_changed' if row['before_points'] != row['after_points'] else
                                 'changed' if mask.getbbox() else 'unchanged')
            row['changed_pixels'] = mask.histogram()[255]
            row['changed_percent'] = row['changed_pixels'] / row['total_pixels'] * 100
            bounds = mask.getbbox()
            row['changed_bounds'] = list(bounds) if bounds else None
            base = new if second is not None else old
            highlight = Image.blend(ImageOps.grayscale(base).convert('RGB'), Image.new('RGB', canvas, 'white'), .65)
            highlight.paste((210, 15, 110), mask=mask)
            manifest['summary'][row['status']] += 1
            part = _page_html(row, old if first is not None else None,
                              new if second is not None else None, highlight, text)
            output_size += len(part.encode('utf-8'))
            if output_size > MAX_OUTPUT - 256 * 1024:
                raise _Rejected('output')
            parts.append(part)
        manifest['summary']['total_pages'] = len(rows)
        manifest['identical_pdf_bytes'] = manifest['before_sha256'] == manifest['after_sha256']
        ensure_data_tree(manifest)
        badges = ''.join(f'<div><strong>{value}</strong><span>{escape(text[key])}</span></div>'
                         for key, value in manifest['summary'].items() if key != 'total_pages')
        header = f'''<!doctype html><html lang="{language_tag(language)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="{escape(CSP, quote=True)}">
<title>{escape(text['title'])}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f4f8;color:#18283c;font:15px/1.5 system-ui,sans-serif}}
header,main,footer{{max-width:1800px;margin:auto;padding:28px 32px}}header{{background:#12263d;color:#f7fafc;border-bottom:5px solid #27b3a6}}h1{{margin:0 0 12px;font-size:32px}}h2{{font-size:20px;margin:0}}h2 span{{font-weight:500;font-size:14px;background:#e7edf3;padding:5px 9px;border-radius:6px}}p{{margin:12px 0}}header p{{max-width:1150px}}.summary{{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}}.summary div{{background:#fff;color:#18283c;padding:12px 18px;border-radius:9px;min-width:155px}}.summary strong{{font-size:26px;display:block}}.summary span{{display:block;font-size:13px}}.hashes{{overflow-wrap:anywhere;font-size:12px}}.hashes code{{font-family:monospace}}.comparison-page{{background:white;border:1px solid #d8e1eb;border-radius:10px;padding:20px;margin:0 0 24px;break-inside:avoid}}.comparison-page>p{{font-size:12px;color:#42546a}}.images{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;align-items:start}}figure{{margin:0;min-width:0}}figcaption{{font-weight:650;margin:0 0 8px}}img{{display:block;width:100%;height:auto;border:1px solid #ced8e5;background:white}}.missing{{padding:30px;background:#f1f4f8;color:#65748a}}footer{{padding-top:0;color:#42546a}}@media(max-width:760px){{header,main,footer{{padding:20px 14px}}.images{{grid-template-columns:1fr}}h1{{font-size:26px}}}}@media print{{header{{background:white;color:#18283c}}body{{background:white}}main{{padding:0}}.comparison-page{{break-before:page}}}}
</style></head><body><header><h1>{escape(text['title'])}</h1><p>{escape(text['method'])}</p>
<div id="comparison-summary" class="summary">{badges}</div><p>{escape(text['pages'])}: {len(rows)} · {escape(text['renderer'])}: {escape(manifest['renderer'])}</p>
<div class="hashes"><strong>{escape(text['hash'])}</strong><p>{escape(text['before'])}: <code>{manifest['before_sha256']}</code><br>{escape(text['after'])}: <code>{manifest['after_sha256']}</code></p></div>
<p>{escape(text['same_bytes']) if manifest['identical_pdf_bytes'] else ''}</p></header><main>'''
        end = ('</main><footer><p>' + escape(text['limits']) + '</p><p>' + escape(text['static']) +
               '</p><p>' + escape(text['privacy']) + '</p></footer><pre id="comparison-manifest" hidden>' +
               escape(json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))) + '</pre></body></html>')
        result = (header + ''.join(parts) + end).encode('utf-8')
        if len(result) > MAX_OUTPUT:
            raise _Rejected('output')
        return result


def _worker(directory, language):
    keeper = _resource_limits()
    # Keep the Windows job alive. Do not close it before the process exits.
    _ = keeper
    raws = []
    for name in ('before.pdf', 'after.pdf'):
        with (directory / name).open('rb') as stream:
            raw = stream.read(MAX_PDF + 1)
        if not raw.startswith(b'%PDF-') or len(raw) > MAX_PDF:
            raise _Rejected('invalid')
        raws.append(raw)
    result = _comparison(*raws, language)
    (directory / 'comparison.html').write_bytes(result)


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] != '--worker' or sys.argv[3] not in _TEXT:
        raise SystemExit(2)
    destination = Path(sys.argv[2])
    try:
        _worker(destination, sys.argv[3])
    except Exception as failure:
        code = failure.args[0] if isinstance(failure, _Rejected) and failure.args else 'limits'
        try:
            (destination / 'status').write_text(code if code in _ERRORS else 'limits', encoding='ascii')
        except OSError:
            pass
        raise SystemExit(3) from None
