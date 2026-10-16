"""Read-only PDF raster comparison, with bounded disposable worker processes.

Page positions are compared, not document meaning. PDF actions, scripts, links
and embedded files are never opened. Only PNG pixels enter the downloadable HTML.
"""
from base64 import b64encode
from hashlib import sha256
from html import escape, unescape
from io import BytesIO
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

from error_messages import message as backend_message
from input_guard import ensure_data_tree, load_json
from languages import language_tag, normalize_language

MAX_PDF = 16 * 1024 * 1024
MAX_PAGES = 80
MAX_PAIRS = 2 * MAX_PAGES
MAX_PAIR_JSON = 16 * 1024
MAX_MANIFEST = 256 * 1024
MAX_TOTAL_PIXELS = 64_000_000
MAX_PAGE_PIXELS = 1_500_000
MAX_SIDE = 1280
MAX_OUTPUT = 32 * 1024 * 1024
MAX_MEMORY = 768 * 1024 * 1024
TIMEOUT = 45
CPU_SECONDS = 40
MEMORY_POLL_SECONDS = .05
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
    'pairing': lambda lang: backend_message('El emparejamiento debe incluir cada página exactamente una vez por PDF, sin duplicados, omisiones ni números fuera de rango.',
        en='Pairing must include every page exactly once per PDF, without duplicates, omissions or out-of-range numbers.',
        pt='O pareamento deve incluir cada página exatamente uma vez por PDF, sem duplicatas, omissões ou números fora do intervalo.', language=lang),
    'pairing_json': lambda lang: backend_message('El emparejamiento debe ser una lista JSON de hasta 16 KiB, con entre 1 y 160 pares antes/después; usa números enteros o null.',
        en='Pairing must be a JSON list up to 16 KiB, with between 1 and 160 before/after pairs; use integer page numbers or null.',
        pt='O pareamento deve ser uma lista JSON de até 16 KiB, com entre 1 e 160 pares antes/depois; use números inteiros de página ou null.', language=lang),
    'manifest': lambda lang: backend_message('El recibo de comparación generado no es válido.',
        en='The generated comparison receipt is invalid.', pt='O recibo de comparação gerado é inválido.', language=lang),
    'source_changed': lambda lang: backend_message('Los PDF cambiaron desde la inspección. Vuelve a inspeccionarlos y confirma el emparejamiento.',
        en='The PDFs changed since inspection. Inspect them again and confirm the pairing.',
        pt='Os PDFs mudaram desde a inspeção. Inspecione-os novamente e confirme o pareamento.', language=lang),
}

_TEXT = {
    'es': {
        'title': 'Comparación visual de PDF', 'before': 'Antes', 'after': 'Después',
        'difference': 'Diferencias resaltadas', 'page': 'Página', 'pages': 'Páginas comparadas',
        'unchanged': 'Sin cambios de píxeles', 'changed': 'Píxeles diferentes',
        'added': 'Añadida', 'removed': 'Eliminada', 'dimensions_changed': 'Dimensiones diferentes',
        'missing': 'No hay página en este par.', 'pixels': 'píxeles diferentes',
        'size': 'Dimensiones PDF', 'scale': 'Escala de rasterización',
        'method': 'Las páginas se emparejan por posición y se alinean por la esquina superior izquierda. Cada pareja comparte escala, hasta 96 ppp y 1280 píxeles por lado. Se comparan los valores RGB exactos, sin tolerancia. El magenta marca diferencias sobre una vista atenuada.',
        'limits': 'Un cambio de orden o una página insertada puede desplazar todas las comparaciones siguientes. El resultado describe estos píxeles, no equivalencia semántica, accesibilidad, enlaces ni aprobación del informe. Las páginas totalmente blancas pueden conservar los píxeles aunque sus dimensiones cambien.',
        'privacy': 'Procesado en el servidor donde ejecutas report-gen, sin servicios externos. Los PDF temporales se eliminan al terminar. Este HTML contiene imágenes de los documentos; compártelo con el mismo cuidado que los originales.',
        'static': 'Solo se muestran imágenes estáticas: no se ejecutan acciones, formularios ni scripts de los PDF. Una página añadida o eliminada resalta toda su superficie.',
        'hash': 'SHA-256 de los PDF originales', 'renderer': 'Motor', 'same_bytes': 'Los archivos originales tienen el mismo SHA-256.',
        'pair': 'Par', 'pairing_mode': 'Emparejamiento', 'positional': 'Por posición', 'manual': 'Manual',
        'manual_method': 'Las páginas se emparejan según la selección manual indicada en cada par y se alinean por la esquina superior izquierda. Cada pareja comparte escala, hasta 96 ppp y 1280 píxeles por lado. Se comparan valores RGB exactos. El magenta marca diferencias. La elección manual no demuestra equivalencia semántica.',
        'manual_limits': 'El emparejamiento es una selección del usuario, sin correspondencia automática por contenido. Este resultado describe los píxeles de esas parejas, no equivalencia semántica, accesibilidad, enlaces ni aprobación del informe. Las páginas blancas pueden conservar los píxeles aunque cambien sus dimensiones.',
    },
    'en': {
        'title': 'Visual PDF comparison', 'before': 'Before', 'after': 'After',
        'difference': 'Highlighted differences', 'page': 'Page', 'pages': 'Compared page positions',
        'unchanged': 'Unchanged pixels', 'changed': 'Different pixels',
        'added': 'Added', 'removed': 'Removed', 'dimensions_changed': 'Different dimensions',
        'missing': 'No page in this pair.', 'pixels': 'different pixels',
        'size': 'PDF dimensions', 'scale': 'Raster scale',
        'method': 'Pages are paired by position and aligned at the top-left corner. Each pair uses a shared scale, up to 96 dpi and 1280 pixels per side. Exact RGB values are compared without tolerance. Magenta marks differences over a faded view.',
        'limits': 'Reordering or inserting a page can shift every subsequent comparison. This result describes these pixels, not semantic equivalence, accessibility, links or report approval. Entirely white pages may retain identical pixels while their dimensions change.',
        'privacy': 'Processed on the server running report-gen, without external services. Temporary PDFs are deleted when processing finishes. This HTML contains document images; share it as carefully as the originals.',
        'static': 'Only static images are shown: PDF actions, forms and scripts are not executed. Added and removed pages highlight their entire surface.',
        'hash': 'Original PDF SHA-256', 'renderer': 'Renderer', 'same_bytes': 'The original files have the same SHA-256.',
        'pair': 'Pair', 'pairing_mode': 'Pairing', 'positional': 'By position', 'manual': 'Manual',
        'manual_method': 'Pages are paired according to the manual selection shown for each pair and aligned at the top-left corner. Each pair shares a scale, up to 96 dpi and 1280 pixels per side. Exact RGB values are compared. Magenta marks differences. Manual selection does not prove semantic equivalence.',
        'manual_limits': 'Pairing is selected by the user, without automatic content matching. This result describes the pixels of those pairs, not semantic equivalence, accessibility, links or report approval. White pages may retain identical pixels while their dimensions change.',
    },
    'pt': {
        'title': 'Comparação visual de PDF', 'before': 'Antes', 'after': 'Depois',
        'difference': 'Diferenças destacadas', 'page': 'Página', 'pages': 'Posições comparadas',
        'unchanged': 'Pixels sem alterações', 'changed': 'Pixels diferentes',
        'added': 'Adicionada', 'removed': 'Removida', 'dimensions_changed': 'Dimensões diferentes',
        'missing': 'Não há página neste par.', 'pixels': 'pixels diferentes',
        'size': 'Dimensões do PDF', 'scale': 'Escala de renderização',
        'method': 'As páginas são pareadas por posição e alinhadas pelo canto superior esquerdo. Cada par usa a mesma escala, até 96 ppp e 1280 pixels por lado. Os valores RGB exatos são comparados sem tolerância. O magenta marca diferenças sobre uma imagem atenuada.',
        'limits': 'Reordenar ou inserir uma página pode deslocar todas as comparações seguintes. O resultado descreve estes pixels, não equivalência semântica, acessibilidade, links ou aprovação do relatório. Páginas totalmente brancas podem manter pixels iguais mesmo com dimensões diferentes.',
        'privacy': 'Processado no servidor que executa report-gen, sem serviços externos. Os PDFs temporários são excluídos ao terminar. Este HTML contém imagens dos documentos; compartilhe-o com o mesmo cuidado que os originais.',
        'static': 'Somente imagens estáticas são exibidas: ações, formulários e scripts dos PDFs não são executados. Páginas adicionadas e removidas destacam toda a sua superfície.',
        'hash': 'SHA-256 dos PDFs originais', 'renderer': 'Motor', 'same_bytes': 'Os arquivos originais têm o mesmo SHA-256.',
        'pair': 'Par', 'pairing_mode': 'Pareamento', 'positional': 'Por posição', 'manual': 'Manual',
        'manual_method': 'As páginas são pareadas conforme a seleção manual indicada em cada par e alinhadas pelo canto superior esquerdo. Cada par compartilha a escala, até 96 ppp e 1280 pixels por lado. Os valores RGB exatos são comparados. O magenta marca diferenças. A seleção manual não comprova equivalência semântica.',
        'manual_limits': 'O pareamento é uma seleção do usuário, sem correspondência automática por conteúdo. O resultado descreve os pixels desses pares, não equivalência semântica, acessibilidade, links ou aprovação do relatório. Páginas brancas podem manter pixels iguais mesmo com dimensões diferentes.',
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
                timeout_seconds=TIMEOUT, memory_policy=_memory_policy(),
                alignment='page_position_top_left', rgb_tolerance=0, max_dpi=96,
                max_page_pairs=MAX_PAIRS, max_pairing_json_bytes=MAX_PAIR_JSON,
                manual_pairing=True, metadata_inspection=True,
                retention={
                    'content_after_request': {'pdf_bytes': False, 'html_bytes': False, 'raster_images': False},
                    'temporary_receipts': {'metadata_only': True, 'storage': 'process_memory',
                                           'ttl_seconds': 1800, 'expiry_enforcement': 'on_access',
                                           'cleanup': 'lazy_on_store_operation'},
                    'saved_reviews': {'opt_in': True, 'storage': 'private_project_attachment',
                                      'included_in_project_history_and_backups': True},
                }, external_services=False)


def _memory_policy():
    if sys.platform == 'darwin':
        return dict(kind='virtual_growth_ceiling_and_sampled_physical_memory',
                    virtual_growth_limit_bytes=MAX_MEMORY,
                    physical_memory_termination_threshold_bytes=MAX_MEMORY,
                    physical_memory_measure='max(resident_size,physical_footprint)',
                    sampling_interval_ms=round(MEMORY_POLL_SECONDS * 1000),
                    instantaneous_physical_memory_ceiling=False)
    return dict(kind='windows_job_process_commit' if os.name == 'nt' else 'absolute_virtual_address_space',
                hard_limit_bytes=MAX_MEMORY)


class _DarwinMemory:
    """Public libproc ABI from Apple XNU proc_info.h/resource.h (96-byte structs)."""
    def __init__(self):
        import ctypes

        class TaskInfo(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                'virtual_size', 'resident_size', 'total_user', 'total_system',
                'threads_user', 'threads_system')] + [(name, ctypes.c_int32) for name in (
                    'policy', 'faults', 'pageins', 'cow_faults', 'messages_sent', 'messages_received',
                    'syscalls_mach', 'syscalls_unix', 'csw', 'threadnum', 'numrunning', 'priority')]

        class UsageInfo(ctypes.Structure):
            _fields_ = [('uuid', ctypes.c_uint8 * 16)] + [(name, ctypes.c_uint64) for name in (
                'user_time', 'system_time', 'pkg_idle_wkups', 'interrupt_wkups', 'pageins',
                'wired_size', 'resident_size', 'phys_footprint', 'proc_start_abstime', 'proc_exit_abstime')]

        self.ctypes, self.task_type, self.usage_type = ctypes, TaskInfo, UsageInfo
        self.library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        self.library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                             ctypes.c_void_p, ctypes.c_int]
        self.library.proc_pidinfo.restype = ctypes.c_int
        self.library.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        self.library.proc_pid_rusage.restype = ctypes.c_int

    def virtual_size(self, pid):
        value, ctypes = self.task_type(), self.ctypes
        length = self.library.proc_pidinfo(pid, 4, 0, ctypes.byref(value), ctypes.sizeof(value))
        if length != ctypes.sizeof(value) or not 0 < value.virtual_size < 2**63:
            raise OSError(ctypes.get_errno(), 'Darwin virtual memory measurement failed')
        return value.virtual_size

    def physical_size(self, pid):
        value, ctypes = self.usage_type(), self.ctypes
        if self.library.proc_pid_rusage(pid, 0, ctypes.byref(value)) != 0:
            raise OSError(ctypes.get_errno(), 'Darwin physical memory measurement failed')
        return max(value.resident_size, value.phys_footprint)


def _darwin_virtual_limit(resource, memory):
    # XNU refuses RLIMIT_AS below the already mapped shared cache/runtime.
    # Limit additional virtual space, preserving any stricter inherited limit.
    baseline = memory.virtual_size(os.getpid())
    ceiling = baseline + MAX_MEMORY
    inherited = resource.getrlimit(resource.RLIMIT_AS)
    for value in inherited:
        if value != resource.RLIM_INFINITY:
            ceiling = min(ceiling, value)
    if ceiling <= baseline:
        raise _Rejected('limits')
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, ceiling))
    if resource.getrlimit(resource.RLIMIT_AS) != (ceiling, ceiling):
        raise _Rejected('limits')
    return dict(baseline_virtual_bytes=baseline, hard_virtual_limit_bytes=ceiling)


def _supervise_memory(process, timeout, read_memory, threshold=MAX_MEMORY):
    """Sample only our unreaped child; every failure kills and reaps it.

    This is a sampled termination threshold, not an instantaneous RAM ceiling.
    Keeping the child unreaped while reading its PID prevents PID reuse.
    """
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            try:
                measured = read_memory(process.pid)
            except OSError:
                if process.poll() is not None:
                    break  # The child exited between poll and the native read.
                raise
            if type(measured) is not int or measured < 0 or measured > threshold:
                raise _Rejected('limits')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            try:
                return process.wait(timeout=min(MEMORY_POLL_SECONDS, remaining))
            except subprocess.TimeoutExpired:
                pass
        return process.returncode
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def _execute(command, **options):
    if sys.platform != 'darwin':
        return subprocess.run(command, **options)
    # Initialize the native reader before starting a child. Failure is closed.
    memory = _DarwinMemory()
    timeout = options.pop('timeout')
    options.pop('check', None)
    with subprocess.Popen(command, **options) as process:
        code = _supervise_memory(process, timeout, memory.physical_size)
    return subprocess.CompletedProcess(command, code)


def compare(before, after, language='es', page_pairs=None):
    """Return a self-contained HTML byte string; retain no server-side record."""
    if page_pairs is not None:
        validate_page_pairs(page_pairs, language=language)
    return _run_operation(before, after, language, 'compare', page_pairs)


def metadata(before, after, language='es'):
    """Inspect hashes and page geometry only, within the same worker limits."""
    raw = _run_operation(before, after, language, 'metadata')
    try:
        value = load_json(raw)
        _validate_metadata(value, before, after)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError(error('manifest', language)) from exc
    return value


def validate_page_pairs(page_pairs, before_count=None, after_count=None, language=None):
    """Validate explicit input without filling, sorting or repairing any pair."""
    if not isinstance(page_pairs, list) or not 1 <= len(page_pairs) <= MAX_PAIRS:
        raise ValueError(error('pairing_json', language))
    seen = {'before': set(), 'after': set()}
    for pair in page_pairs:
        if not isinstance(pair, dict) or set(pair) != {'before', 'after'}:
            raise ValueError(error('pairing_json', language))
        if pair['before'] is None and pair['after'] is None:
            raise ValueError(error('pairing_json', language))
        for key in seen:
            number = pair[key]
            if number is not None:
                if type(number) is not int or not 1 <= number <= MAX_PAGES:
                    raise ValueError(error('pairing_json', language))
                if number in seen[key]:
                    raise ValueError(error('pairing', language))
                seen[key].add(number)
    if len(json.dumps(page_pairs, separators=(',', ':')).encode('utf-8')) > MAX_PAIR_JSON:
        raise ValueError(error('pairing_json', language))
    for key, count in (('before', before_count), ('after', after_count)):
        if count is not None and seen[key] != set(range(1, count + 1)):
            raise ValueError(error('pairing', language))
    return page_pairs


def _run_operation(before, after, language, operation, page_pairs=None):
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
            options = dict(operation=operation, page_pairs=page_pairs)
            (directory / 'request.json').write_text(json.dumps(options, separators=(',', ':')), encoding='utf-8')
            try:
                result = _execute(
                    [sys.executable, str(Path(__file__).resolve()), '--worker', folder, language],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=TIMEOUT, check=False)
            except subprocess.TimeoutExpired as exc:
                raise ValueError(error('timeout', language)) from exc
            except (OSError, _Rejected) as exc:
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
                output_name = 'comparison.html' if operation == 'compare' else 'metadata.json'
                output_limit = MAX_OUTPUT if operation == 'compare' else MAX_MANIFEST
                with (directory / output_name).open('rb') as stream:
                    result = stream.read(output_limit + 1)
            except OSError as exc:
                raise ValueError(error('limits', language)) from exc
            if len(result) > output_limit or (operation == 'compare' and not result.startswith(b'<!doctype html>')):
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
    if sys.platform == 'darwin':
        memory_limit = _darwin_virtual_limit(resource, _DarwinMemory())
    else:
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY, MAX_MEMORY))
        memory_limit = None
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT, MAX_OUTPUT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return memory_limit


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


def _metadata(before, after):
    value = {'schema': 'report-gen-pdf-metadata/1'}
    for key, raw in (('before', before), ('after', after)):
        with _validated_document(raw) as document:
            dimensions = _geometry(document)
        value[key] = dict(sha256=sha256(raw).hexdigest(), bytes=len(raw),
                          pages=[dict(number=index + 1, width=size[0], height=size[1])
                                 for index, size in enumerate(dimensions)])
    return value


def _require_manifest(condition):
    if not condition:
        raise ValueError(error('manifest'))


def _number(value, low, high, integer=False):
    return (type(value) in ((int,) if integer else (int, float))
            and math.isfinite(value) and low <= value <= high)


def _validate_metadata(value, before, after):
    _require_manifest(isinstance(value, dict) and set(value) == {'schema', 'before', 'after'}
                      and value['schema'] == 'report-gen-pdf-metadata/1')
    for key, raw in (('before', before), ('after', after)):
        row = value[key]
        _require_manifest(isinstance(row, dict) and set(row) == {'sha256', 'bytes', 'pages'})
        _require_manifest(row['sha256'] == sha256(raw).hexdigest()
                          and type(row['bytes']) is int and row['bytes'] == len(raw))
        _require_manifest(isinstance(row['pages'], list) and 1 <= len(row['pages']) <= MAX_PAGES)
        for index, page in enumerate(row['pages']):
            _require_manifest(isinstance(page, dict) and set(page) == {'number', 'width', 'height'})
            _require_manifest(type(page['number']) is int and page['number'] == index + 1
                              and _number(page['width'], 0, 14400) and page['width'] > 0
                              and _number(page['height'], 0, 14400) and page['height'] > 0)


def comparison_manifest(content):
    """Read only the bounded terminal PRE from server-generated comparison HTML.

    This helper does not import HTML, execute a parser/browser or open resources.
    It verifies the receipt's shape, coverage, geometry and count consistency;
    it cannot authenticate HTML submitted by another source and is not an
    endpoint for accepting arbitrary uploaded comparison documents.
    """
    marker, ending = b'<pre id="comparison-manifest" hidden>', b'</pre></body></html>'
    try:
        _require_manifest(isinstance(content, bytes) and len(content) <= MAX_OUTPUT
                          and content.startswith(b'<!doctype html>') and content.endswith(ending))
        tail = content[-(MAX_MANIFEST + len(marker) + len(ending)):]
        position = tail.find(marker)
        _require_manifest(position >= 0 and content.count(marker) == 1)
        encoded = tail[position + len(marker):-len(ending)]
        _require_manifest(len(encoded) <= MAX_MANIFEST)
        value = load_json(unescape(encoded.decode('utf-8')))
        _verify_comparison_manifest(value)
        return value
    except (ValueError, KeyError, TypeError, OverflowError, _Rejected) as exc:
        raise ValueError(error('manifest')) from exc


def _verify_comparison_manifest(value):
    keys = {'schema', 'language', 'pairing_mode', 'before_sha256', 'after_sha256',
            'before_bytes', 'after_bytes', 'before_pages', 'after_pages', 'renderer',
            'alignment', 'max_dpi', 'rgb_tolerance', 'semantic_equivalence_verified',
            'memory_policy', 'summary', 'pages', 'identical_pdf_bytes'}
    _require_manifest(isinstance(value, dict) and set(value) == keys
                      and value['schema'] == 'report-gen-pdf-comparison/2')
    _require_manifest(value['language'] in _TEXT and value['pairing_mode'] in ('positional', 'manual'))
    _require_manifest(value['max_dpi'] == 96 and type(value['max_dpi']) is int
                      and value['rgb_tolerance'] == 0 and type(value['rgb_tolerance']) is int
                      and value['semantic_equivalence_verified'] is False)
    _require_manifest(value['alignment'] == ('page_position_top_left' if value['pairing_mode'] == 'positional'
                                             else 'page_pairs_top_left'))
    _require_manifest(isinstance(value['renderer'], str) and value['renderer'].startswith('PDFium ')
                      and len(value['renderer']) <= 100 and value['memory_policy'] == _memory_policy())
    for side in ('before', 'after'):
        _require_manifest(isinstance(value[side + '_sha256'], str)
                          and re.fullmatch('[0-9a-f]{64}', value[side + '_sha256']) is not None
                          and _number(value[side + '_bytes'], 5, MAX_PDF, True)
                          and _number(value[side + '_pages'], 1, MAX_PAGES, True))
    _require_manifest(type(value['identical_pdf_bytes']) is bool
                      and value['identical_pdf_bytes'] == (value['before_sha256'] == value['after_sha256']))
    if value['identical_pdf_bytes']:
        _require_manifest(value['before_bytes'] == value['after_bytes']
                          and value['before_pages'] == value['after_pages'])
    rows = value['pages']
    _require_manifest(isinstance(rows, list) and 1 <= len(rows) <= MAX_PAIRS)
    pairs, left, right = [], [None] * value['before_pages'], [None] * value['after_pages']
    row_keys = {'number', 'before_page', 'after_page', 'before_points', 'after_points',
                'scale', 'canvas_pixels', 'total_pixels', 'status', 'changed_pixels',
                'changed_percent', 'changed_bounds'}
    for index, row in enumerate(rows):
        _require_manifest(isinstance(row, dict) and set(row) == row_keys
                          and type(row['number']) is int and row['number'] == index + 1)
        pair = {side: row[side + '_page'] for side in ('before', 'after')}
        pairs.append(pair)
        for side, dimensions in (('before', left), ('after', right)):
            number, points = pair[side], row[side + '_points']
            if number is None:
                _require_manifest(points is None)
            else:
                _require_manifest(_number(number, 1, len(dimensions), True)
                                  and isinstance(points, list) and len(points) == 2
                                  and all(_number(v, 0, 14400) and v > 0 for v in points))
                dimensions[number - 1] = points
    validate_page_pairs(pairs, len(left), len(right))
    if value['identical_pdf_bytes']:
        _require_manifest(left == right)
    if value['pairing_mode'] == 'positional':
        _require_manifest(pairs == _pairing(len(left), len(right), None))
    expected = _plans(left, right, pairs)
    counts = dict.fromkeys(('unchanged', 'changed', 'added', 'removed', 'dimensions_changed'), 0)
    for row, plan in zip(rows, expected):
        _require_manifest(_number(row['scale'], 0, 96 / 72) and row['scale'] > 0
                          and isinstance(row['canvas_pixels'], list) and len(row['canvas_pixels']) == 2
                          and all(_number(v, 1, MAX_SIDE, True) for v in row['canvas_pixels'])
                          and _number(row['total_pixels'], 1, MAX_PAGE_PIXELS, True))
        _require_manifest(all(row[key] == result for key, result in plan.items()))
        _require_manifest(_number(row['changed_pixels'], 0, row['total_pixels'], True)
                          and _number(row['changed_percent'], 0, 100)
                          and math.isclose(row['changed_percent'], row['changed_pixels'] / row['total_pixels'] * 100,
                                           rel_tol=0, abs_tol=1e-9))
        status = ('added' if row['before_page'] is None else 'removed' if row['after_page'] is None else
                  'dimensions_changed' if row['before_points'] != row['after_points'] else
                  'changed' if row['changed_pixels'] else 'unchanged')
        _require_manifest(row['status'] == status)
        bounds = row['changed_bounds']
        if row['changed_pixels']:
            _require_manifest(isinstance(bounds, list) and len(bounds) == 4
                              and all(type(v) is int for v in bounds)
                              and 0 <= bounds[0] < bounds[2] <= row['canvas_pixels'][0]
                              and 0 <= bounds[1] < bounds[3] <= row['canvas_pixels'][1])
            _require_manifest(row['changed_pixels'] <= (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]))
        else:
            _require_manifest(bounds is None)
        if status in ('added', 'removed'):
            _require_manifest(row['changed_pixels'] == row['total_pixels']
                              and bounds == [0, 0, *row['canvas_pixels']])
        counts[status] += 1
    counts['total_pages'] = len(rows)
    _require_manifest(isinstance(value['summary'], dict) and value['summary'] == counts
                      and all(type(v) is int for v in value['summary'].values()))


def _pairing(before_count, after_count, page_pairs):
    if page_pairs is None:
        return [dict(before=number if number <= before_count else None,
                     after=number if number <= after_count else None)
                for number in range(1, max(before_count, after_count) + 1)]
    try:
        return validate_page_pairs(page_pairs, before_count, after_count)
    except ValueError as exc:
        raise _Rejected('pairing') from exc


def _plans(left, right, page_pairs=None):
    rows, total = [], 0
    for index, pair in enumerate(_pairing(len(left), len(right), page_pairs)):
        first = left[pair['before'] - 1] if pair['before'] is not None else None
        second = right[pair['after'] - 1] if pair['after'] is not None else None
        width = max(size[0] for size in (first, second) if size)
        height = max(size[1] for size in (first, second) if size)
        scale = min(96 / 72, MAX_SIDE / width, MAX_SIDE / height,
                    math.sqrt((MAX_PAGE_PIXELS - 2 * MAX_SIDE) / (width * height)))
        canvas = (math.ceil(width * scale), math.ceil(height * scale))
        pixels = canvas[0] * canvas[1]
        total += pixels
        if pixels > MAX_PAGE_PIXELS or total > MAX_TOTAL_PIXELS:
            raise _Rejected('pixels')
        rows.append(dict(number=index + 1, before_page=pair['before'], after_page=pair['after'],
                         before_points=list(first) if first else None,
                         after_points=list(second) if second else None,
                         scale=scale, canvas_pixels=list(canvas), total_pixels=pixels))
    return rows


def _raster(document, index, scale):
    if index is None or index >= len(document):
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
    mapping = (f'{text["before"]} {row["before_page"] if row["before_page"] is not None else "—"} → '
               f'{text["after"]} {row["after_page"] if row["after_page"] is not None else "—"}')
    for key, image in (('before', before), ('after', after), ('difference', highlight)):
        number = row.get(key + '_page')
        label = text[key] + (' · ' + text['page'] + ' ' + str(number) if number is not None else '')
        if key == 'difference':
            label += ' · ' + mapping
        content = ('<p class="missing">' + escape(text['missing']) + '</p>' if image is None else
                   f'<img class="{key}-image" width="{image.width}" height="{image.height}" '
                   f'alt="{escape(label)}" src="data:image/png;base64,{_png(image)}">')
        columns.append(f'<figure><figcaption>{escape(label)}</figcaption>{content}</figure>')
    dimensions = ' → '.join('—' if size is None else f'{size[0]:g} × {size[1]:g} pt'
                            for size in (row['before_points'], row['after_points']))
    return (f'<section class="comparison-page" data-status="{row["status"]}" id="page-{row["number"]}">'
            f'<h2>{escape(text["pair"])} {row["number"]} · {escape(mapping)} <span>{escape(text[row["status"]])}</span></h2>'
            f'<p>{row["changed_pixels"]:,} / {row["total_pixels"]:,} {escape(text["pixels"])} '
            f'({row["changed_percent"]:.3f}%) · {escape(text["size"])}: {dimensions} · '
            f'{escape(text["scale"])}: {row["scale"]:.6f}</p><div class="images">' + ''.join(columns) + '</div></section>')


def _comparison(before, after, language, page_pairs=None):
    from PIL import Image, ImageChops, ImageOps
    import pypdfium2
    text = _TEXT[language]
    with _validated_document(before) as left, _validated_document(after) as right:
        rows = _plans(_geometry(left), _geometry(right), page_pairs)
        mode = 'positional' if page_pairs is None else 'manual'
        manifest = dict(schema='report-gen-pdf-comparison/2', language=language, pairing_mode=mode,
                        before_sha256=sha256(before).hexdigest(), after_sha256=sha256(after).hexdigest(),
                        before_bytes=len(before), after_bytes=len(after),
                        before_pages=len(left), after_pages=len(right),
                        renderer='PDFium ' + str(pypdfium2.PDFIUM_INFO),
                        alignment='page_position_top_left' if mode == 'positional' else 'page_pairs_top_left',
                        max_dpi=96, rgb_tolerance=0, semantic_equivalence_verified=False,
                        memory_policy=_memory_policy(),
                        summary={key: 0 for key in ('unchanged', 'changed', 'added', 'removed', 'dimensions_changed')},
                        pages=rows)
        parts, output_size = [], 0
        for row in rows:
            first = _raster(left, row['before_page'] - 1 if row['before_page'] is not None else None, row['scale'])
            second = _raster(right, row['after_page'] - 1 if row['after_page'] is not None else None, row['scale'])
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
</style></head><body><header><h1>{escape(text['title'])}</h1><p id="pairing-mode">{escape(text['pairing_mode'])}: {escape(text[mode])}</p><p>{escape(text['method'] if mode == 'positional' else text['manual_method'])}</p>
<div id="comparison-summary" class="summary">{badges}</div><p>{escape(text['pages'])}: {len(rows)} · {escape(text['renderer'])}: {escape(manifest['renderer'])}</p>
<div class="hashes"><strong>{escape(text['hash'])}</strong><p>{escape(text['before'])}: <code>{manifest['before_sha256']}</code><br>{escape(text['after'])}: <code>{manifest['after_sha256']}</code></p></div>
<p>{escape(text['same_bytes']) if manifest['identical_pdf_bytes'] else ''}</p></header><main>'''
        manifest_text = escape(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
        if len(manifest_text.encode('utf-8')) > MAX_MANIFEST:
            raise _Rejected('output')
        end = ('</main><footer><p>' + escape(text['limits'] if mode == 'positional' else text['manual_limits']) + '</p><p>' + escape(text['static']) +
               '</p><p>' + escape(text['privacy']) + '</p></footer><pre id="comparison-manifest" hidden>' +
               manifest_text + '</pre></body></html>')
        result = (header + ''.join(parts) + end).encode('utf-8')
        if len(result) > MAX_OUTPUT:
            raise _Rejected('output')
        return result


def _worker(directory, language):
    keeper = _resource_limits()
    # Keep the Windows job alive. Do not close it before the process exits.
    _ = keeper
    with (directory / 'request.json').open('rb') as stream:
        options_raw = stream.read(MAX_PAIR_JSON + 129)
    if len(options_raw) > MAX_PAIR_JSON + 128:
        raise _Rejected('pairing_json')
    options = load_json(options_raw)
    if (not isinstance(options, dict) or set(options) != {'operation', 'page_pairs'}
            or options['operation'] not in ('compare', 'metadata')
            or (options['operation'] == 'metadata' and options['page_pairs'] is not None)):
        raise _Rejected('pairing_json')
    raws = []
    for name in ('before.pdf', 'after.pdf'):
        with (directory / name).open('rb') as stream:
            raw = stream.read(MAX_PDF + 1)
        if not raw.startswith(b'%PDF-') or len(raw) > MAX_PDF:
            raise _Rejected('invalid')
        raws.append(raw)
    if options['operation'] == 'metadata':
        result = json.dumps(_metadata(*raws), separators=(',', ':')).encode('utf-8')
        if len(result) > MAX_MANIFEST:
            raise _Rejected('output')
        (directory / 'metadata.json').write_bytes(result)
    else:
        result = _comparison(*raws, language, options['page_pairs'])
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
