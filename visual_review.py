"""Bounded, isolated rasterization of actual PDF bytes and temporary review records."""
from error_messages import message as backend_message
from collections import OrderedDict
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
import math
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import zipfile

MAX_PDF = 16 * 1024 * 1024
MAX_PAGES = 500
TTL = 1800
_WORKERS = threading.BoundedSemaphore(2)


def available():
    return importlib.util.find_spec('pymupdf') is not None


def extract_pdf(payload, filename):
    if filename.lower().endswith('.pdf'):
        if not payload.startswith(b'%PDF-') or len(payload) > MAX_PDF:
            raise ValueError(backend_message('PDF inválido o demasiado grande (16 MB) / Invalid or oversized PDF'))
        return payload
    if not filename.lower().endswith('.zip'):
        raise ValueError(backend_message('El resultado no es PDF ni ZIP / Result is not PDF or ZIP'))
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            # Native delivery has one canonical report; PDF attachments are not
            # alternate reports and must never be mistaken for the generated PDF.
            rows = [row for row in archive.infolist() if row.filename == 'informe.pdf' and not row.is_dir()]
            if len(rows) != 1:
                raise ValueError(backend_message('El paquete necesita un informe.pdf único en la raíz / Package requires one root informe.pdf'))
            row = rows[0]
            if row.file_size > MAX_PDF or row.flag_bits & 1:
                raise ValueError(backend_message('PDF cifrado o demasiado grande / Encrypted or oversized PDF'))
            raw = archive.read(row)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError(backend_message('Paquete PDF inválido / Invalid PDF package')) from exc
    if not raw.startswith(b'%PDF-'):
        raise ValueError(backend_message('PDF inválido / Invalid PDF'))
    return raw


def raster(payload, page=None):
    if not available():
        raise ValueError(backend_message('Instala las dependencias de vistas previas: pip install -e ".[previews]" / Install preview extras'))
    if not payload.startswith(b'%PDF-') or len(payload) > MAX_PDF:
        raise ValueError(backend_message('PDF inválido o demasiado grande / Invalid or oversized PDF'))
    if page is not None and (type(page) is not int or not 1 <= page <= MAX_PAGES):
        raise ValueError(backend_message('Página inválida / Invalid page'))
    if not _WORKERS.acquire(blocking=False):
        raise ValueError(backend_message('Hay dos vistas previas en curso; vuelve a intentar / Two PDF previews are in progress'))
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                                 'metadata' if page is None else str(page)], input=payload,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ValueError(backend_message('La vista previa excedió el límite de tiempo / PDF preview timed out')) from exc
    finally:
        _WORKERS.release()
    if result.returncode:
        raise ValueError(backend_message('No se pudo abrir este PDF dentro de los límites / Could not render this PDF within limits'))
    if page is None:
        value = json.loads(result.stdout)
        if not isinstance(value, list) or not 1 <= len(value) <= MAX_PAGES:
            raise ValueError(backend_message('PDF sin páginas o demasiado extenso / Empty or oversized PDF'))
        return value
    if not result.stdout.startswith(b'\x89PNG\r\n\x1a\n') or len(result.stdout) > 4 * 1024 * 1024:
        raise ValueError(backend_message('Vista previa de página inválida / Invalid page preview'))
    return result.stdout


class Store:
    """Session-owned transient bytes. No PDF, identity or review is written to projects."""
    def __init__(self):
        self.lock, self.records = threading.RLock(), {}

    def _prune(self):
        now = time.monotonic()
        for key in list(self.records):
            if self.records[key]['expires'] < now:
                del self.records[key]

    def add(self, owner, payload, revision, filename, origin, job_id=None):
        digest = sha256(payload).hexdigest()
        with self.lock:
            self._prune()
            for key, record in self.records.items():
                if (record['owner'], record['pdf_sha256'], record['revision'], record['origin'], record['job_id']) == (owner, digest, revision, origin, job_id):
                    return key
            if (len(self.records) >= 8 or sum(row['owner'] == owner for row in self.records.values()) >= 4
                    or sum(len(row['payload']) for row in self.records.values()) + len(payload) > 64 * 1024 * 1024):
                raise ValueError(backend_message('Borra una vista previa temporal antes de abrir otra / Clear a temporary preview first'))
        pages = raster(payload)
        with self.lock:
            self._prune()
            if (len(self.records) >= 8 or sum(row['owner'] == owner for row in self.records.values()) >= 4
                    or sum(len(row['payload']) for row in self.records.values()) + len(payload) > 64 * 1024 * 1024):
                raise ValueError(backend_message('Límite de vistas temporales / Temporary preview limit reached'))
            key = secrets.token_urlsafe(24)
            self.records[key] = dict(id=key, owner=owner, payload=payload, revision=revision,
                                     filename=filename, origin=origin, job_id=job_id, pdf_sha256=digest,
                                     pages=pages, review=None, thumbnails=OrderedDict(),
                                     expires=time.monotonic() + TTL)
            return key

    def get(self, owner, key):
        with self.lock:
            self._prune()
            record = self.records.get(key)
            if not record or record['owner'] != owner:
                raise KeyError(key)
            return record

    def metadata(self, owner, key, prefix):
        record = self.get(owner, key)
        return {field: record[field] for field in ('id', 'revision', 'filename', 'origin', 'job_id', 'pdf_sha256', 'review')} | dict(
            pages=[dict(row, image_url=f'{prefix}/page/{row["number"]}') for row in record['pages']],
            retention_seconds=TTL, original_word_verified=False, manually_verified=False,
            rasterized_pages=list(record['thumbnails']))

    def page(self, owner, key, number):
        record = self.get(owner, key)
        if not 1 <= number <= len(record['pages']):
            raise KeyError(number)
        with self.lock:
            if number in record['thumbnails']:
                value = record['thumbnails'].pop(number)
                record['thumbnails'][number] = value
                return value
        payload = raster(record['payload'], number)
        with self.lock:
            record['thumbnails'][number] = payload
            while len(record['thumbnails']) > 4:
                record['thumbnails'].popitem(last=False)
        return payload

    def review(self, owner, key, body):
        record = self.get(owner, key)
        if not isinstance(body, dict) or set(body) != {'revision', 'pdf_sha256', 'author', 'decision', 'pages', 'note'}:
            raise ValueError(backend_message('Registro visual inválido / Invalid visual review'))
        if body['revision'] != record['revision'] or body['pdf_sha256'] != record['pdf_sha256']:
            raise ValueError(backend_message('El registro no corresponde a este PDF / Review does not match this PDF'))
        for field, maximum in (('author', 120), ('note', 4000)):
            if not isinstance(body[field], str) or len(body[field]) > maximum:
                raise ValueError(backend_message('Texto de revisión inválido / Invalid review text'))
        if not body['author'].strip() or body['decision'] not in ('accepted', 'issues'):
            raise ValueError(backend_message('Indica autor y decisión / Provide author and decision'))
        pages = body['pages']
        if not isinstance(pages, list) or len(pages) > MAX_PAGES:
            raise ValueError(backend_message('Observaciones inválidas / Invalid observations'))
        if body['decision'] == 'accepted' and pages:
            raise ValueError(backend_message('No marques aceptado un PDF con problemas registrados / Cannot accept a PDF with recorded issues'))
        if body['decision'] == 'issues' and not pages and not body['note'].strip():
            raise ValueError(backend_message('Describe el problema observado / Describe the observed issue'))
        for row in pages:
            if (not isinstance(row, dict) or set(row) != {'number', 'issue', 'note'}
                    or type(row['number']) is not int or not 1 <= row['number'] <= len(record['pages'])
                    or row['issue'] not in ('table_cut', 'orphan_title', 'unreadable_image', 'other')
                    or not isinstance(row['note'], str) or not row['note'].strip() or len(row['note']) > 4000):
                raise ValueError(backend_message('Observación de página inválida / Invalid page observation'))
        value = dict(body, created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                     author_identity='local_self_declaration', origin=record['origin'],
                     original_word_verified=False, automated_layout_verification=False,
                     statement='Human review of this exact PDF; not a pentest or publication authorization.')
        with self.lock:
            record['review'] = value
        return value

    def discard(self, owner, key):
        self.get(owner, key)
        with self.lock:
            self.records.pop(key, None)


def _worker(command):
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
    except (ImportError, ValueError, OSError):
        pass  # Windows still has the external timeout and size/page bounds.
    import pymupdf
    raw = sys.stdin.buffer.read(MAX_PDF + 1)
    if not raw.startswith(b'%PDF-') or len(raw) > MAX_PDF:
        raise ValueError(backend_message('invalid PDF'))
    with pymupdf.open(stream=raw, filetype='pdf') as document:
        if document.needs_pass or not 1 <= len(document) <= MAX_PAGES:
            raise ValueError(backend_message('password or page limit'))
        rows = []
        for index in range(len(document)):
            rect = document[index].rect
            if not all(math.isfinite(v) and 0 < v <= 14400 for v in (rect.width, rect.height)):
                raise ValueError(backend_message('invalid page geometry'))
            scale = min(720 / rect.width, 1000 / rect.height)
            rows.append(dict(number=index + 1, width=max(1, round(rect.width * scale)),
                             height=max(1, round(rect.height * scale))))
        if command == 'metadata':
            sys.stdout.buffer.write(json.dumps(rows).encode('utf-8'))
        else:
            number = int(command)
            if not 1 <= number <= len(document):
                raise ValueError(backend_message('invalid page'))
            page = document[number - 1]
            scale = min(720 / page.rect.width, 1000 / page.rect.height)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
            sys.stdout.buffer.write(pixmap.tobytes('png'))


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--worker':
        raise SystemExit(2)
    try:
        _worker(sys.argv[2])
    except Exception:
        raise SystemExit(3) from None
