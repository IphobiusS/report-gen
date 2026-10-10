"""Explicit local OCR of a publication image, with no text/secrets in results.

Tesseract is optional, never downloaded or contacted. A separate child applies
POSIX resource limits before executing it; input and time limits apply everywhere.
Only single-frame publication derivatives are accepted, never private originals.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile

from PIL import Image, ImageOps, UnidentifiedImageError
from image_integrity import verify_container as _verify_container
from error_messages import message as backend_message

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_OCR_BYTES = 1024 * 1024
MAX_ROWS = 20_000
TIMEOUT = 16


def available():
    return shutil.which('tesseract') is not None


def _result(blob, status):
    return dict(engine='tesseract', image_sha256=sha256(blob).hexdigest(), alerts=[],
                manual_review_required=True, complete=False, status=status)


def preflight(blob):
    """Check dimensions, frames and container integrity before pixel decoding."""
    if not isinstance(blob, bytes) or len(blob) > MAX_IMAGE_BYTES:
        raise ValueError(backend_message('OCR: imagen mayor que 12 MiB. / OCR: image exceeds 12 MiB.'))
    try:
        with Image.open(BytesIO(blob)) as source:
            if source.format not in ('PNG', 'JPEG', 'WEBP', 'GIF'):
                raise ValueError
            if source.width * source.height > MAX_PIXELS:
                return 'image_limit'
            if getattr(source, 'n_frames', 1) != 1:
                return 'animation_unsupported'
            _verify_container(blob, source.format)
            # WeasyPrint permits truncated pixel streams globally in Pillow.
            # Validate the container without changing that shared process flag.
            source.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError, SyntaxError):
        raise ValueError(backend_message('Imagen no válida para OCR. / Invalid image for OCR.')) from None
    return None


def inspect_publication_image(blob):
    # Inspect headers and engine availability before decoding a derivative.
    status = preflight(blob)
    if status:
        return _result(blob, status)
    if not available():
        return _result(blob, 'unavailable')
    import publication
    try:
        return inspect_image(publication.clean_image(blob))
    except (OSError, Image.DecompressionBombError):
        raise ValueError(backend_message('Imagen no válida para OCR. / Invalid image for OCR.')) from None


def inspect_image(blob):
    status = preflight(blob)
    if status:
        return _result(blob, status)
    result = _result(blob, 'unavailable')
    executable = shutil.which('tesseract')
    if not executable:
        return result
    try:
        with Image.open(BytesIO(blob)) as source:
            pixels = ImageOps.exif_transpose(source).convert('RGB')
    except (OSError, Image.DecompressionBombError):
        raise ValueError(backend_message('Imagen no válida para OCR. / Invalid image for OCR.')) from None
    # This directory is private and removed on success, failure or timeout.
    with tempfile.TemporaryDirectory(prefix='rg-ocr-') as folder:
        image = Path(folder) / 'image.png'
        pixels.save(image, format='PNG')
        environment = {**os.environ, 'OMP_THREAD_LIMIT': '1', 'OMP_NUM_THREADS': '1'}
        # Resource setup happens in the child, never preexec_fn in Flask threads.
        with subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker',
                               executable, str(image)], cwd=folder, env=environment,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, start_new_session=os.name == 'posix') as run:
            try:
                stdout, _ = run.communicate(timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    # Kill the OCR grandchild as well, before deleting private
                    # temporary pixels/text and returning from the request.
                    try:
                        os.killpg(run.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    run.kill()
                run.communicate()
                return dict(result, status='timeout')
        if run.returncode != 0 or len(stdout) > MAX_OCR_BYTES:
            return dict(result, status='engine_error')
        try:
            data = json.loads(stdout)
            if not isinstance(data, dict) or data.get('status') not in ('completed', 'engine_error', 'output_limit', 'timeout'):
                raise ValueError
        except (ValueError, UnicodeError):
            return dict(result, status='engine_error')
        return dict(result, **data)


def _scan_tsv(blob):
    import csv
    import re
    from collections import Counter
    import publication
    if len(blob) > MAX_OCR_BYTES:
        return {'status': 'output_limit'}
    rows = csv.DictReader(blob.decode('utf-8', errors='replace').splitlines(), delimiter='\t', quoting=csv.QUOTE_NONE)
    lines = {}
    count = 0
    for row in rows:
        count += 1
        if count > MAX_ROWS:
            return {'status': 'output_limit'}
        if row.get('level') != '5' or not row.get('text', '').strip():
            continue
        try:
            x, y, width, height = (int(row[key]) for key in ('left', 'top', 'width', 'height'))
            if min(x, y, width, height) < 0 or max(x, y, width, height) > MAX_PIXELS:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return {'status': 'engine_error'}
        key = tuple(row.get(k) for k in ('page_num', 'block_num', 'par_num', 'line_num'))
        lines.setdefault(key, []).append((row['text'], x, y, width, height))
    patterns = [*publication.PATTERNS,
                ('possible_email', re.compile(r'[\w.+-]{1,64}@[\w.-]{1,127}\.[A-Za-z]{2,24}')),
                ('possible_rut', re.compile(r'(?<![\w])(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})-[0-9kK](?![\w])'))]
    alerts = []
    words = 0
    for items in lines.values():
        words += len(items)
        text = ' '.join(row[0] for row in items)
        counts = Counter()
        for kind, pattern in patterns:
            counts[kind] += sum(1 for match in pattern.finditer(text)
                                if not re.search(r'(?i)\[(?:redacted|censurado)\]$', match[0]))
        x, y = min(row[1] for row in items), min(row[2] for row in items)
        bounds = [x, y, max(row[1] + row[3] for row in items) - x,
                  max(row[2] + row[4] for row in items) - y]
        for kind, matches in counts.items():
            if matches:
                if len(alerts) >= 200:
                    return {'status': 'output_limit'}
                alerts.append({'kind': kind, 'count': matches, 'bounds': bounds})
    return {'status': 'completed', 'words_recognized': words, 'alerts': alerts}


def _worker(executable, image):
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (12, 13))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * MAX_OCR_BYTES, 2 * MAX_OCR_BYTES))
    output = str(Path(image).with_name('recognized'))
    try:
        proc = subprocess.run([executable, image, output, '-l', 'eng', '--psm', '11', 'tsv'],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=12, check=False)
        path = Path(output + '.tsv')
        if proc.returncode != 0 or not path.is_file():
            result = {'status': 'engine_error'}
        elif path.stat().st_size > MAX_OCR_BYTES:
            result = {'status': 'output_limit'}
        else:
            result = _scan_tsv(path.read_bytes())
    except subprocess.TimeoutExpired:
        result = {'status': 'timeout'}
    except (OSError, ValueError):
        result = {'status': 'engine_error'}
    print(json.dumps(result))


if __name__ == '__main__' and len(sys.argv) == 4 and sys.argv[1] == '--worker':
    _worker(sys.argv[2], sys.argv[3])
