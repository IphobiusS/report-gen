"""Private, read-only PDF annex inspection in the bounded PDF worker.

Only fixed categories, counts and numeric locations leave the worker. The scan
does not render, run actions, open destinations, extract embedded files or OCR
images. A successful bounded inspection is never a privacy certification.
"""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zlib

import pdf_compare

MAX_PDF = 16 * 1024 * 1024
MAX_PAGES = 200
MAX_OBJECTS = 8000
MAX_NODES = 40000
MAX_DEPTH = 32
MAX_TEXT = 2 * 1024 * 1024
MAX_STREAM = 2 * 1024 * 1024
MAX_STREAM_TOTAL = 8 * 1024 * 1024
MAX_LOCATIONS = 200
MAX_OUTPUT = 128 * 1024
TIMEOUT = 20
CATEGORIES = {'page_text', 'metadata', 'link', 'annotation', 'form', 'action', 'embedded_file', 'object'}
PRESENCE = {'pdf_metadata', 'pdf_link', 'pdf_annotation', 'pdf_form', 'pdf_action', 'pdf_embedded_file', 'pdf_image'}
ACTION_TYPES = {'/GoTo', '/GoToR', '/GoToE', '/Launch', '/Thread', '/URI', '/Sound', '/Movie', '/Hide',
                '/Named', '/SubmitForm', '/ResetForm', '/ImportData', '/JavaScript', '/SetOCGState',
                '/Rendition', '/Trans', '/GoTo3DView'}
PATTERN_KINDS = {'private_key', 'credential', 'bearer', 'aws_key', 'possible_email', 'possible_rut'}
LIMITATIONS = {'no_ocr', 'heuristic_detection', 'binary_streams_not_scanned', 'historical_revisions_not_scanned',
               'embedded_files_not_opened', 'actions_not_executed', 'images_present', 'textless_pages',
               'page_limit', 'object_limit', 'node_limit', 'depth_limit', 'text_limit', 'location_limit',
               'stream_limit', 'unsupported_stream_filter', 'unreadable_structure', 'unreadable_text',
               'byte_strings_not_decoded', 'parser_disagreement', 'xml_entities_not_resolved'}
STATUSES = {'inspected', 'partial', 'invalid', 'encrypted', 'timeout', 'limits', 'busy', 'unavailable'}
BASE_LIMITATIONS = {'no_ocr', 'heuristic_detection', 'binary_streams_not_scanned',
                    'historical_revisions_not_scanned', 'actions_not_executed'}


class _Rejected(Exception):
    """Private machine code, never sent to the user as exception prose."""


def _empty(status):
    return {'status': status, 'pages_total': 0, 'pages_inspected': 0, 'objects_total': 0,
            'objects_inspected': 0, 'text_characters_inspected': 0, 'stream_bytes_inspected': 0,
            'limitations': sorted(BASE_LIMITATIONS), 'limits': {
                'pages': MAX_PAGES, 'objects': MAX_OBJECTS, 'nodes': MAX_NODES, 'depth': MAX_DEPTH,
                'text_characters': MAX_TEXT, 'stream_bytes': MAX_STREAM,
                'total_stream_bytes': MAX_STREAM_TOTAL, 'locations': MAX_LOCATIONS,
                'timeout_seconds': TIMEOUT, 'memory': pdf_compare._memory_policy()}}


def inspect_pdf(blob):
    """Return advisory metadata; temporary input and parser output are removed."""
    result = dict(scope='manual', complete=False, manual_review_required=True, bytes_inspected=0,
                  alerts=[], pdf=_empty('invalid'))
    if not isinstance(blob, bytes) or not blob.startswith(b'%PDF-') or len(blob) > MAX_PDF:
        return result
    if not pdf_compare.available():
        result['pdf']['status'] = 'unavailable'
        return result
    # Share the PDF comparator's one-worker budget rather than doubling RAM use.
    if not pdf_compare._WORKERS.acquire(blocking=False):
        result['pdf']['status'] = 'busy'
        return result
    try:
        with tempfile.TemporaryDirectory(prefix='report-gen-annex-scan-') as folder:
            directory = Path(folder)
            (directory / 'input.pdf').write_bytes(blob)
            try:
                process = pdf_compare._execute(
                    [sys.executable, str(Path(__file__).resolve()), '--worker', folder],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=TIMEOUT, check=False)
                if process.returncode:
                    result['pdf']['status'] = 'limits'
                    return result
                with (directory / 'result.json').open('rb') as source:
                    raw = source.read(MAX_OUTPUT + 1)
                if len(raw) > MAX_OUTPUT:
                    raise _Rejected('output')
                receipt = json.loads(raw)
                _validate_receipt(receipt, sha256(blob).hexdigest())
            except subprocess.TimeoutExpired:
                result['pdf']['status'] = 'timeout'
                return result
            except (OSError, ValueError, TypeError, KeyError, _Rejected, pdf_compare._Rejected):
                result['pdf']['status'] = 'limits'
                return result
            result.update(pdf=receipt['pdf'], alerts=receipt['alerts'])
            if result['pdf']['status'] in {'inspected', 'partial'}:
                result['scope'] = 'pdf_structural'
            return result
    finally:
        pdf_compare._WORKERS.release()


def _validate_receipt(receipt, digest):
    """Allow no parser-controlled text or fields into the API response."""
    if not isinstance(receipt, dict) or set(receipt) != {'sha256', 'pdf', 'alerts'} or receipt['sha256'] != digest:
        raise _Rejected('receipt')
    pdf = receipt['pdf']
    template = _empty('invalid')
    if not isinstance(pdf, dict) or set(pdf) != set(template) or pdf['status'] not in STATUSES:
        raise _Rejected('receipt')
    if pdf['limits'] != template['limits']:
        raise _Rejected('receipt')
    for key in ('pages_total', 'pages_inspected', 'objects_total', 'objects_inspected',
                'text_characters_inspected', 'stream_bytes_inspected'):
        if type(pdf[key]) is not int or not 0 <= pdf[key] <= 2**31:
            raise _Rejected('receipt')
    if not isinstance(pdf['limitations'], list) or len(pdf['limitations']) > len(LIMITATIONS):
        raise _Rejected('receipt')
    if any(code not in LIMITATIONS for code in pdf['limitations']):
        raise _Rejected('receipt')
    alerts = receipt['alerts']
    if not isinstance(alerts, list) or len(alerts) > len(PRESENCE | PATTERN_KINDS):
        raise _Rejected('receipt')
    count = 0
    for alert in alerts:
        if not isinstance(alert, dict) or set(alert) != {'kind', 'count', 'locations'}:
            raise _Rejected('receipt')
        if alert['kind'] not in PRESENCE | PATTERN_KINDS or type(alert['count']) is not int or not 0 < alert['count'] <= 2**31:
            raise _Rejected('receipt')
        if not isinstance(alert['locations'], list):
            raise _Rejected('receipt')
        for location in alert['locations']:
            if not isinstance(location, dict) or not {'category'} <= set(location) <= {'category', 'page', 'object', 'generation'}:
                raise _Rejected('receipt')
            if location['category'] not in CATEGORIES:
                raise _Rejected('receipt')
            for key, value in location.items():
                if key != 'category' and (type(value) is not int or not 0 <= value <= 2**31):
                    raise _Rejected('receipt')
            count += 1
    if count > MAX_LOCATIONS:
        raise _Rejected('receipt')


class _Scan:
    def __init__(self):
        from publication import PATTERNS
        self.patterns = [*PATTERNS,
            ('possible_email', re.compile(r'[\w.+-]{1,64}@[\w.-]{1,127}\.[A-Za-z]{2,24}')),
            ('possible_rut', re.compile(r'(?<![\w])(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})-[0-9kK](?![\w])'))]
        self.pdf = _empty('inspected')
        self.limitations = set(BASE_LIMITATIONS)
        self.counts, self.locations = Counter(), {}
        self.location_count, self.nodes = 0, 0
        self.partial = False
        self.streams = {}

    def limit(self, code):
        self.limitations.add(code)
        self.partial = True

    def alert(self, kind, location, count=1):
        self.counts[kind] += count
        locations = self.locations.setdefault(kind, [])
        if location in locations:
            return
        if self.location_count == MAX_LOCATIONS:
            self.limit('location_limit')
            return
        locations.append(location.copy())
        self.location_count += 1

    def text(self, value, location):
        remaining = MAX_TEXT - self.pdf['text_characters_inspected']
        if len(value) > remaining:
            self.limit('text_limit')
        value = value[:remaining]
        self.pdf['text_characters_inspected'] += len(value)
        for kind, pattern in self.patterns:
            count = sum(not re.search(r'(?i)\[(?:redacted|censurado)\]$', match[0])
                        for match in pattern.finditer(value))
            if count:
                self.alert(kind, location, count)

    def walk(self, obj, location, depth=0):
        from pypdf.generic import (ArrayObject, ByteStringObject, DictionaryObject,
                                   IndirectObject, NameObject, TextStringObject)
        self.nodes += 1
        if self.nodes > MAX_NODES:
            self.limit('node_limit')
            return
        if depth > MAX_DEPTH:
            self.limit('depth_limit')
            return
        if isinstance(obj, IndirectObject):
            return  # Enumerated once from the current xref, never recurse cycles.
        if isinstance(obj, DictionaryObject):
            kind, subtype = obj.get('/Type'), obj.get('/Subtype')
            category = location['category']
            if kind == '/Metadata':
                category = 'metadata'
                self.streams[location['object']] = (obj, category, location)
                self.alert('pdf_metadata', dict(location, category=category))
            elif kind == '/EmbeddedFile':
                category = 'embedded_file'
                self.alert('pdf_embedded_file', dict(location, category=category))
                self.limitations.add('embedded_files_not_opened')
            elif kind == '/Annot' or subtype in {'/Text', '/Link', '/Widget', '/FileAttachment', '/FreeText'}:
                category = 'annotation'
                self.alert('pdf_annotation', dict(location, category=category))
            if subtype == '/Image':
                self.alert('pdf_image', location)
                self.limitations.add('images_present')
            if '/FT' in obj or subtype == '/Widget':
                category = 'form'
                self.alert('pdf_form', dict(location, category=category))
            action = obj.get('/S')
            if (isinstance(action, str) and action in ACTION_TYPES) or any(key in obj for key in ('/OpenAction', '/AA', '/JS')):
                category = 'action'
                self.alert('pdf_action', dict(location, category=category))
            for key, value in obj.items():
                if self.nodes >= MAX_NODES:
                    self.limit('node_limit')
                    break
                child = dict(location, category='link' if key == '/URI' else category)
                self.text(key, child)
                if key == '/URI':
                    self.alert('pdf_link', child)
                if key == '/JS' and isinstance(value, IndirectObject):
                    self.streams[value.idnum] = (value, 'action', dict(location, object=value.idnum, generation=value.generation, category='action'))
                if key == '/Metadata' and isinstance(value, IndirectObject):
                    self.streams[value.idnum] = (value, 'metadata', dict(location, object=value.idnum, generation=value.generation, category='metadata'))
                self.walk(value, child, depth + 1)
        elif isinstance(obj, ArrayObject):
            for value in obj:
                if self.nodes >= MAX_NODES:
                    self.limit('node_limit')
                    break
                self.walk(value, location, depth + 1)
        elif isinstance(obj, (TextStringObject, NameObject)):
            self.text(obj, location)
        elif isinstance(obj, ByteStringObject):
            self.limitations.add('byte_strings_not_decoded')

    def receipt(self, blob):
        self.pdf['status'] = 'partial' if self.partial else self.pdf['status']
        self.pdf['limitations'] = sorted(self.limitations)
        return dict(sha256=sha256(blob).hexdigest(), pdf=self.pdf,
                    alerts=[dict(kind=kind, count=count, locations=self.locations[kind])
                            for kind, count in sorted(self.counts.items())])


def _text_stream(stream):
    """Decode only small unfiltered or simple Flate text; never parse XML/JS."""
    from pypdf.generic import IndirectObject, StreamObject
    if isinstance(stream, IndirectObject):
        stream = stream.get_object()
    if not isinstance(stream, StreamObject):
        raise _Rejected('unreadable_structure')
    raw = stream._data
    if len(raw) > MAX_STREAM:
        raise _Rejected('stream_limit')
    filters = stream.get('/Filter')
    if filters and filters != '/FlateDecode' and filters != ['/FlateDecode']:
        raise _Rejected('unsupported_stream_filter')
    if stream.get('/DecodeParms'):
        raise _Rejected('unsupported_stream_filter')
    if filters:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(raw, MAX_STREAM + 1)
        if len(raw) > MAX_STREAM or not decoder.eof:
            raise _Rejected('stream_limit')
        if decoder.unused_data:
            raise _Rejected('unreadable_structure')
    return raw


def _inspect(blob):
    import pypdf
    from pypdf.generic import IndirectObject
    scan = _Scan()
    # Newer pypdf versions expose pre-allocation decoder and page-tree limits.
    # Older supported versions remain behind the same hard worker memory limit.
    if hasattr(pypdf, 'overwrite_configuration'):
        current = pypdf.get_configuration()
        options = {key: value for key, value in {
            'zlib_maximum_output_length': MAX_STREAM_TOTAL,
            'lzw_maximum_output_length': MAX_STREAM_TOTAL,
            'run_length_maximum_output_length': MAX_STREAM_TOTAL,
            'array_based_stream_maximum_output_length': MAX_STREAM_TOTAL,
            'page_tree_maximum_entries': MAX_OBJECTS,
            'page_tree_maximum_depth': MAX_DEPTH}.items() if hasattr(current, key)}
        pypdf.overwrite_configuration(**options)
    try:
        reader = pypdf.PdfReader(BytesIO(blob), strict=True)
        if reader.is_encrypted:
            scan.pdf['status'] = 'encrypted'
            return scan.receipt(blob)
        scan.pdf['pages_total'] = len(reader.pages)
        if not scan.pdf['pages_total']:
            scan.pdf['status'] = 'invalid'
            return scan.receipt(blob)
    except Exception:
        scan.pdf['status'] = 'invalid'
        return scan.receipt(blob)
    if scan.pdf['pages_total'] > MAX_PAGES:
        scan.limit('page_limit')
    pages = {}
    annotation_count = 0
    for index, page in enumerate(reader.pages[:MAX_PAGES]):
        ref = page.indirect_reference
        if ref:
            pages[(ref.idnum, ref.generation)] = index + 1
        annotations = page.get('/Annots', [])
        if isinstance(annotations, IndirectObject):
            annotations = annotations.get_object()
        if not isinstance(annotations, list):
            scan.limit('unreadable_structure')
            continue
        for annotation in annotations:
            annotation_count += 1
            if annotation_count > MAX_NODES:
                scan.limit('node_limit')
                break
            if isinstance(annotation, IndirectObject):
                pages[(annotation.idnum, annotation.generation)] = index + 1
    info = reader.trailer.get('/Info')
    info_ref = (info.idnum, info.generation) if isinstance(info, IndirectObject) else None
    references = {(number, generation) for generation, objects in reader.xref.items()
                  for number in objects if number > 0 and generation < 65535}
    references.update((number, 0) for number in reader.xref_objStm)
    scan.pdf['objects_total'] = len(references)
    if len(references) > MAX_OBJECTS:
        scan.limit('object_limit')
    for number, generation in sorted(references)[:MAX_OBJECTS]:
        location = {'category': 'metadata' if (number, generation) == info_ref else 'object',
                    'object': number, 'generation': generation}
        if (number, generation) in pages:
            location['page'] = pages[(number, generation)]
        try:
            obj = reader.get_object(IndirectObject(number, generation, reader))
            if location['category'] == 'metadata':
                scan.alert('pdf_metadata', location)
            scan.walk(obj, location)
            scan.pdf['objects_inspected'] += 1
        except Exception:
            scan.limit('unreadable_structure')
        if scan.nodes >= MAX_NODES:
            break
    for stream, category, location in scan.streams.values():
        try:
            raw = _text_stream(stream)
            if scan.pdf['stream_bytes_inspected'] + len(raw) > MAX_STREAM_TOTAL:
                scan.limit('stream_limit')
                break
            scan.pdf['stream_bytes_inspected'] += len(raw)
            encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
            scan.text(raw.decode(encoding), dict(location, category=category))
            if category == 'metadata':
                scan.limitations.add('xml_entities_not_resolved')
        except (_Rejected, ValueError, UnicodeError, zlib.error) as exc:
            code = exc.args[0] if exc.args and exc.args[0] in LIMITATIONS else 'unreadable_structure'
            scan.limit(code)
        except Exception:
            scan.limit('unreadable_structure')
    try:
        import pypdfium2
        with pypdfium2.PdfDocument(blob) as document:
            if len(document) != scan.pdf['pages_total']:
                scan.limit('parser_disagreement')
            for index in range(min(len(document), MAX_PAGES)):
                page = document[index]
                textpage = None
                try:
                    textpage = page.get_textpage()
                    count = textpage.count_chars()
                    remaining = MAX_TEXT - scan.pdf['text_characters_inspected']
                    if count > remaining:
                        scan.limit('text_limit')
                    if not count:
                        scan.limitations.add('textless_pages')
                    elif remaining:
                        scan.text(textpage.get_text_range(0, min(count, remaining)),
                                  {'category': 'page_text', 'page': index + 1})
                    scan.pdf['pages_inspected'] += 1
                    if count > remaining:
                        break
                finally:
                    if textpage is not None:
                        textpage.close()
                    page.close()
    except Exception:
        scan.limit('unreadable_text')
    reader.close()
    return scan.receipt(blob)


def _worker(directory):
    keeper = pdf_compare._resource_limits()
    _ = keeper  # Keep the Windows Job alive through process exit.
    with (directory / 'input.pdf').open('rb') as source:
        blob = source.read(MAX_PDF + 1)
    if not blob.startswith(b'%PDF-') or len(blob) > MAX_PDF:
        raise _Rejected('input')
    result = _inspect(blob)
    _validate_receipt(result, sha256(blob).hexdigest())
    raw = json.dumps(result, separators=(',', ':')).encode()
    if len(raw) > MAX_OUTPUT:
        raise _Rejected('output')
    (directory / 'result.json').write_bytes(raw)


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--worker':
        raise SystemExit(2)
    try:
        _worker(Path(sys.argv[2]))
    except Exception:
        raise SystemExit(3) from None
