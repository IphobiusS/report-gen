"""Opt-in LibreOffice pagination of immutable, verified export-job DOCX bytes.

No arbitrary upload/path is accepted by the API. Disposable profiles and the
existing process-tree supervisor keep conversion separate from running Office.
The derivative describes LibreOffice's layout, never Microsoft Word acceptance.
"""
import atexit
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import unquote, urlsplit
import uuid
import zipfile

from error_messages import message
from export_jobs import ExportQueue, _exitcode, _start_process
from storage import atomic_write

MAX_DOCX = 16 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_PDF = 32 * 1024 * 1024
MAX_PAGES = 500
MAX_MEMORY = 3 * 1024 * 1024 * 1024
TIMEOUT = 180
TTL = 900
_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
_ERRORS = {
    'unavailable': lambda: message('Instala LibreOffice Writer y vuelve a abrir report-gen para obtener la vista DOCX.',
        en='Install LibreOffice Writer and reopen report-gen to preview DOCX.', pt='Instale o LibreOffice Writer e reabra o report-gen para visualizar DOCX.'),
    'invalid': lambda: message('El DOCX no es válido o supera los límites de la vista previa.',
        en='The DOCX is invalid or exceeds preview limits.', pt='O DOCX é inválido ou excede os limites da visualização.'),
    'active': lambda: message('El DOCX contiene contenido activo, campos o recursos externos no admitidos en la vista previa.',
        en='The DOCX contains active content, fields or external resources unsupported by preview.', pt='O DOCX contém conteúdo ativo, campos ou recursos externos incompatíveis com a visualização.'),
    'source': lambda: message('La comprobación del DOCX no coincide con la exportación. Genera una nueva exportación.',
        en='DOCX verification does not match the export. Generate a new export.', pt='A verificação do DOCX não corresponde à exportação. Gere uma nova exportação.'),
    'missing': lambda: message('Exporta Word o una entrega que incluya Word antes de abrir esta vista.',
        en='Export Word or a delivery containing Word before opening this preview.', pt='Exporte Word ou uma entrega que inclua Word antes de abrir esta visualização.'),
    'busy': lambda: message('Ya hay una conversión DOCX en curso. Espera o cancélala antes de abrir otra.',
        en='A DOCX conversion is already running. Wait or cancel it before opening another.', pt='Já há uma conversão DOCX em andamento. Aguarde ou cancele antes de abrir outra.'),
    'retention': lambda: message('Elimina una vista DOCX temporal antes de abrir otra.',
        en='Remove a temporary DOCX preview before opening another.', pt='Remova uma visualização DOCX temporária antes de abrir outra.'),
    'timeout': lambda: message('LibreOffice superó el límite de 180 segundos. Reduce el informe o revisa la instalación.',
        en='LibreOffice exceeded 180 seconds. Reduce the report or check the installation.', pt='O LibreOffice excedeu 180 segundos. Reduza o relatório ou verifique a instalação.'),
    'conversion': lambda: message('LibreOffice no produjo un PDF válido dentro de los límites. Revisa la instalación de Writer.',
        en='LibreOffice did not produce a valid PDF within limits. Check the Writer installation.', pt='O LibreOffice não produziu um PDF válido dentro dos limites. Verifique a instalação do Writer.'),
    'cleanup': lambda: message('No se pudo limpiar la conversión DOCX; el resultado no está disponible.',
        en='DOCX conversion cleanup failed; the result is unavailable.', pt='A limpeza da conversão DOCX falhou; o resultado está indisponível.'),
    'pending': lambda: message('La vista DOCX todavía no está lista.',
        en='DOCX preview is not ready yet.', pt='A visualização DOCX ainda não está pronta.'),
}


def error(code):
    return _ERRORS.get(code, _ERRORS['conversion'])()


class Rejected(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(error(code))


def executable():
    # This is a server operator setting, never taken from browser input.
    configured = os.environ.get('REPORT_GEN_LIBREOFFICE')
    if configured:
        path = Path(configured).expanduser()
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    for name in ('libreoffice', 'soffice'):
        found = shutil.which(name)
        if found:
            return found
    candidates = [Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')]
    for variable in ('PROGRAMFILES', 'PROGRAMFILES(X86)'):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / 'LibreOffice/program/soffice.exe')
    return next((str(p) for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)


def capabilities():
    return dict(available=bool(executable()), engine='LibreOffice', max_docx_bytes=MAX_DOCX,
                max_pdf_bytes=MAX_PDF, max_pages=MAX_PAGES, timeout_seconds=TIMEOUT,
                retention_seconds=TTL, source='completed_verified_export_job',
                original_word_verified=False, external_services=False,
                memory_policy=memory_policy(),
                unavailable_message=error('unavailable'))


def memory_policy():
    if os.name == 'nt':
        return dict(kind='windows_job_aggregate_commit', hard_limit_bytes=MAX_MEMORY)
    if sys.platform == 'darwin':
        return dict(kind='virtual_growth_ceiling', growth_limit_bytes=MAX_MEMORY,
                    instantaneous_physical_memory_ceiling=False)
    return dict(kind='per_process_absolute_virtual_address_space', hard_limit_bytes=MAX_MEMORY)


def extract_docx(payload, filename, verification, revision):
    """Extract only the generated root member and bind it to the queue receipt."""
    name = filename
    if filename.lower().endswith('.zip'):
        name = 'informe.docx'
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                rows = [row for row in archive.infolist() if row.filename == name and not row.is_dir()]
                if len(rows) != 1:
                    raise Rejected('missing')
                if rows[0].file_size > MAX_DOCX or rows[0].flag_bits & 1:
                    raise Rejected('invalid')
                payload = archive.read(rows[0])
        except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise Rejected('invalid') from exc
    elif not filename.lower().endswith('.docx'):
        raise Rejected('missing')
    if not payload or len(payload) > MAX_DOCX:
        raise Rejected('invalid')
    record = verification.get('files', {}).get(name, {})
    if (verification.get('source_revision') != revision or record.get('bytes') != len(payload)
            or record.get('sha256') != sha256(payload).hexdigest()):
        raise Rejected('source')
    return payload


def validate_docx(raw):
    """Reject native active/external resources before starting a document engine."""
    from lxml import etree
    if not raw or len(raw) > MAX_DOCX:
        raise Rejected('invalid')
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            rows = archive.infolist()
            names = [row.filename for row in rows]
            if (len(rows) > 2000 or len(set(names)) != len(names)
                    or sum(row.file_size for row in rows) > MAX_EXPANDED
                    or not {'[Content_Types].xml', 'word/document.xml'}.issubset(names)):
                raise Rejected('invalid')
            for row in rows:
                name = row.filename
                if (row.flag_bits & 1 or name.startswith('/') or '\\' in name
                        or any(part in ('..', '.') for part in PurePosixPath(name).parts)
                        or row.file_size > MAX_DOCX):
                    raise Rejected('invalid')
                if re.search(r'(?i)vba|activex|embeddings/|customui/|\.bin$', name):
                    raise Rejected('active')
                if not name.endswith(('.xml', '.rels')):
                    continue
                data = archive.read(row)
                if re.search(br'<!\s*(?:DOCTYPE|ENTITY)', data, re.I):
                    raise Rejected('active')
                parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
                tree = etree.fromstring(data, parser)
                if tree.getroottree().docinfo.doctype:
                    raise Rejected('active')
                for node in tree.iter():
                    local = etree.QName(node).localname
                    if local in ('altChunk', 'object', 'OLEObject', 'attachedTemplate'):
                        raise Rejected('active')
                    if local in ('Default', 'Override'):
                        content_type = node.get('ContentType', '').lower()
                        if any(term in content_type for term in ('macroenabled', 'vbaproject', 'oleobject', 'activex')):
                            raise Rejected('active')
                    if node.tag == '{' + _REL + '}Relationship':
                        target = node.get('Target', '')
                        if node.get('TargetMode', '').lower() == 'external':
                            if (not node.get('Type', '').endswith('/hyperlink')
                                    or (not target.startswith('#') and urlsplit(target).scheme.lower()
                                        not in ('http', 'https', 'mailto'))):
                                raise Rejected('active')
                        else:
                            # Internal OOXML resources must stay inside the ZIP;
                            # a missing TargetMode cannot disguise a local/remote URL.
                            target = unquote(target)
                            base = str(PurePosixPath(name).parent.parent)
                            member = posixpath.normpath(posixpath.join(base, target))
                            if (not target or target.startswith('/') or '\\' in target or urlsplit(target).scheme
                                    or member.startswith('../') or member not in names):
                                raise Rejected('active')
                    instruction = (node.text if node.tag == '{' + _W + '}instrText' else
                                   node.get('{' + _W + '}instr') if node.tag == '{' + _W + '}fldSimple' else None)
                    if instruction is not None and not re.fullmatch(
                            r'\s*(?:(?:PAGE|NUMPAGES)|PAGEREF [A-Za-z_][A-Za-z0-9_]* \\h|'
                            r'SEQ RGList[1-9][0-9]{0,9} (?:\\r [1-9][0-9]{0,9}|\\n) \\\* ARABIC)\s*', instruction):
                        raise Rejected('active')
    except (zipfile.BadZipFile, RuntimeError, OSError, etree.XMLSyntaxError, ValueError) as exc:
        if isinstance(exc, Rejected):
            raise
        raise Rejected('invalid') from exc


def _profile(root):
    directory = root / 'profile'
    (directory / 'user').mkdir(parents=True)
    (directory / 'user/registrymodifications.xcu').write_text(
        '<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
        '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>'
        '<item oor:path="/org.openoffice.Office.Writer/Content/Update">'
        '<prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item></oor:items>', encoding='utf-8')
    return directory


def _worker_limits():
    if os.name == 'nt':
        import ctypes
        from types import SimpleNamespace
        from export_jobs import _WindowsJob
        keeper = _WindowsJob()
        limits = keeper.limits_type()
        limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x200 | 0x4 | 0x8
        limits.BasicLimitInformation.PerJobUserTimeLimit = TIMEOUT * 10_000_000
        limits.BasicLimitInformation.ActiveProcessLimit = 8
        limits.JobMemoryLimit = MAX_MEMORY
        if not keeper.api.SetInformationJobObject(keeper.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        keeper.assign(SimpleNamespace(_handle=-1))
        return keeper  # Native descendants inherit this nested, aggregate limit.
    if os.name == 'posix':
        import resource
        memory = MAX_MEMORY
        if sys.platform == 'darwin':
            # Shared-cache mappings can already exceed a fixed address-space
            # ceiling. Bound additional virtual growth; do not call this RSS.
            from pdf_compare import _DarwinMemory
            memory += _DarwinMemory().virtual_size(os.getpid())
        for inherited in resource.getrlimit(resource.RLIMIT_AS):
            if inherited != resource.RLIM_INFINITY:
                memory = min(memory, inherited)
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_PDF, MAX_PDF))
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT, TIMEOUT))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def worker(root):
    """Executed only below the gated, owned process-tree supervisor."""
    root = Path(root)
    try:
        keeper = _worker_limits()
        config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
        raw = (root / 'source.docx').read_bytes()
        if sha256(raw).hexdigest() != config['source_docx_sha256']:
            raise Rejected('source')
        validate_docx(raw)
        profile = _profile(root)
        command = [config['executable'], '-env:UserInstallation=' + profile.as_uri(),
                   '--headless', '--nologo', '--nodefault', '--norestore']
        version = subprocess.run(command + ['--version'], capture_output=True, timeout=15, check=False)
        label = version.stdout.decode('utf-8', 'replace').strip()[:300]
        if version.returncode or not re.match(r'^LibreOffice(?:Dev)?\s+\d', label):
            raise Rejected('conversion')
        output = root / 'rendered'
        output.mkdir()
        result = subprocess.run(command + ['--convert-to', 'pdf:writer_pdf_Export', '--outdir',
                                str(output), str(root / 'source.docx')],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env={**os.environ, 'SAL_USE_VCLPLUGIN': 'svp'}, check=False)
        path = output / 'source.pdf'
        if result.returncode or path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_PDF:
            raise Rejected('conversion')
        from pypdf import PdfReader
        pdf = path.read_bytes()
        reader = PdfReader(BytesIO(pdf), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
            raise Rejected('conversion')
        if sha256((root / 'source.docx').read_bytes()).hexdigest() != config['source_docx_sha256']:
            raise Rejected('source')
        receipt = dict(format='report-gen-docx-native-preview', version=1,
                       engine=dict(name='LibreOffice', version=label), source_docx_sha256=config['source_docx_sha256'],
                       source_revision=config['revision'], job_id=config['job_id'], pdf_sha256=sha256(pdf).hexdigest(),
                       pdf_bytes=len(pdf), pages=len(reader.pages), word_verified=False,
                       pagination='derived_from_docx_by_libreoffice', source_unchanged=True,
                       memory_policy=memory_policy(), visual_acceptance='not_assessed')
        atomic_write(root / 'preview.pdf', pdf)
        atomic_write(root / 'receipt.json', json.dumps(receipt).encode())
        # Keep the Windows job object alive until all document work finishes.
        _ = keeper
        return 0
    except Exception as exc:
        atomic_write(root / 'error.json', json.dumps({'code': exc.code if isinstance(exc, Rejected) else 'conversion'}).encode())
        return 1


class Store:
    """One bounded conversion; eight session-owned results with lazy TTL expiry."""
    def __init__(self, timeout=TIMEOUT, ttl=TTL):
        self.root = Path(tempfile.mkdtemp(prefix='report-gen-docx-preview-'))
        self.lock, self.records = threading.RLock(), {}
        self.timeout, self.ttl, self.closed = timeout, ttl, False
        atexit.register(self.close)

    def _prune(self):
        for key, row in list(self.records.items()):
            if row['stage'] in ('done', 'error', 'cancelled') and time.monotonic() > row['expires']:
                shutil.rmtree(row['root'])
                del self.records[key]

    def _get(self, owner, key):
        self._prune()
        row = self.records.get(key)
        if row is None or row['owner'] != owner:
            raise KeyError(key)
        return row

    def start(self, owner, raw, revision, job_id):
        with self.lock:
            self._prune()
            if self.closed or any(r['stage'] in ('rendering', 'cancelling') for r in self.records.values()):
                raise Rejected('busy')
            if len(self.records) >= 8:
                raise Rejected('retention')
            program = executable()
            if program is None:
                raise Rejected('unavailable')
            if not raw or len(raw) > MAX_DOCX:
                raise Rejected('invalid')
            key = uuid.uuid4().hex
            directory = self.root / key
            directory.mkdir()
            digest = sha256(raw).hexdigest()
            try:
                atomic_write(directory / 'source.docx', raw)
                atomic_write(directory / 'config.json', json.dumps(dict(executable=program,
                             source_docx_sha256=digest, revision=revision, job_id=job_id)).encode())
                row = dict(id=key, owner=owner, root=directory, stage='rendering', revision=revision,
                           job_id=job_id, source_docx_sha256=digest, receipt=None, error_code=None,
                           cancel=threading.Event(), expires=time.monotonic() + self.ttl)
                self.records[key] = row
                thread = threading.Thread(target=self._run, args=(row,), daemon=True, name='report-gen-docx-preview')
                row['thread'] = thread
                thread.start()
            except BaseException:
                self.records.pop(key, None)
                shutil.rmtree(directory, ignore_errors=True)
                raise
            return self.status(owner, key)

    def _run(self, row):
        process, outcome, error_code, receipt = None, 'error', 'conversion', None
        try:
            process = _start_process([sys.executable, str(Path(__file__).resolve()), '--worker-gated', str(row['root'])])
            started = time.monotonic()
            while (code := _exitcode(process)) is None:
                if row['cancel'].is_set() or self.closed:
                    outcome, error_code = 'cancelled', None
                    break
                if time.monotonic() - started > self.timeout:
                    error_code = 'timeout'
                    break
                # Bound retained temporary data on every platform, including
                # engines which return success while failing to emit a PDF.
                sizes = []
                for path in row['root'].rglob('*'):
                    try:
                        if path.is_file():
                            sizes.append(path.stat().st_size)
                    except FileNotFoundError:
                        pass  # Office atomically replaces transient profile files.
                if sum(sizes) > 256 * 1024 * 1024 or any(size > MAX_PDF for size in sizes):
                    error_code = 'conversion'
                    break
                time.sleep(.05)
            else:
                if code == 0:
                    receipt = json.loads((row['root'] / 'receipt.json').read_text(encoding='utf-8'))
                    pdf = (row['root'] / 'preview.pdf').read_bytes()
                    if (receipt['source_docx_sha256'] != row['source_docx_sha256']
                            or receipt['source_revision'] != row['revision']
                            or receipt['pdf_sha256'] != sha256(pdf).hexdigest() or len(pdf) > MAX_PDF):
                        raise Rejected('source')
                    outcome, error_code = 'done', None
                elif (row['root'] / 'error.json').is_file():
                    error_code = json.loads((row['root'] / 'error.json').read_text(encoding='utf-8')).get('code', 'conversion')
        except Exception as exc:
            error_code = exc.code if isinstance(exc, Rejected) else 'conversion'
        finally:
            try:
                ExportQueue._stop(process)
                # A cancellation racing successful output still discards its data.
                if row['cancel'].is_set() or self.closed:
                    outcome, error_code = 'cancelled', None
                for path in row['root'].iterdir():
                    if outcome == 'done' and path.name in ('preview.pdf', 'receipt.json'):
                        continue
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
            except Exception:
                outcome, error_code = 'error', 'cleanup'
            with self.lock:
                row.update(stage=outcome, error_code=error_code,
                           receipt=receipt if outcome == 'done' else None, expires=time.monotonic() + self.ttl)

    def status(self, owner, key):
        with self.lock:
            row = self._get(owner, key)
            result = {k: row[k] for k in ('id', 'stage', 'revision', 'job_id', 'source_docx_sha256')}
            result.update(error=error(row['error_code']) if row['error_code'] else None,
                          error_code=row['error_code'], receipt=deepcopy(row['receipt']))
            return result

    def cancel(self, owner, key):
        with self.lock:
            row = self._get(owner, key)
            if row['stage'] in ('rendering', 'cancelling'):
                row['cancel'].set()
                row['stage'] = 'cancelling'
            return self.status(owner, key)

    def result(self, owner, key):
        with self.lock:
            row = self._get(owner, key)
            if row['stage'] != 'done':
                raise Rejected('pending')
            return (row['root'] / 'preview.pdf').read_bytes()

    def discard(self, owner, key):
        with self.lock:
            row = self._get(owner, key)
            if row['stage'] in ('rendering', 'cancelling'):
                raise Rejected('pending')
            shutil.rmtree(row['root'])
            del self.records[key]

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            rows = list(self.records.values())
            for row in rows:
                row['cancel'].set()
        for row in rows:
            row['thread'].join(timeout=20)
        if all(not row['thread'].is_alive() for row in rows):
            shutil.rmtree(self.root, ignore_errors=True)


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--worker-gated' or sys.stdin.buffer.read(1) != b'1':
        raise SystemExit('Use the local report-gen DOCX preview API')
    raise SystemExit(worker(sys.argv[2]))
