"""Optional, private comparison reviews; never copy source PDF/HTML/image data.

Temporary receipts are session-bound RAM metadata, pruned on store access.
Saved records also contain the reviewer's explicit author and note text, and are
ordinary private project attachments, so project history and backups retain them. A
record is a local self-declaration, including when imported from a backup;
hash validation detects file changes, not authorship or authenticity.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
import threading
import time
import unicodedata
import uuid

import attachments
from error_messages import message as backend_message
from input_guard import load_json
import pdf_compare

SCHEMA = 'report-gen-pdf-comparison-review/1'
TTL = 30 * 60
MAX_OWNER = 8
MAX_RECEIPTS = 64
MAX_METADATA = 64 * 1024
_HASH = re.compile(r'^[a-f0-9]{64}$')
_ID = re.compile(r'^[A-Za-z0-9_-]{43}$')
_SUMMARY = {'unchanged', 'changed', 'added', 'removed', 'dimensions_changed', 'total_pages'}
_COMPARISON = {'before_sha256', 'after_sha256', 'before_pages', 'after_pages',
               'pairing_mode', 'page_pairs', 'summary'}
_RECORD = _COMPARISON | {'schema', 'uid', 'created', 'html_sha256', 'author',
                        'decision', 'note', 'author_identity',
                        'semantic_equivalence_verified', 'original_word_verified'}


def invalid():
    return backend_message('Registro de revisión de comparación no válido.',
                           en='Invalid comparison review record.',
                           pt='Registro de revisão da comparação inválido.')


def missing():
    return backend_message('Recibo temporal inexistente o caducado; vuelve a comparar los PDF.',
                           en='Temporary receipt missing or expired; compare the PDFs again.',
                           pt='Recibo temporário inexistente ou expirado; compare os PDFs novamente.')


class ReceiptLimitError(ValueError):
    """The comparison remains usable when optional metadata cannot be retained."""


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _text(value, maximum, *, required=False, multiline=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        return False
    return all(unicodedata.category(char) not in {'Cc', 'Cf', 'Cs', 'Zl', 'Zp'}
               or (multiline and char in '\n\r\t') for char in value)


def validate_decision(author, decision, note):
    if not _text(author, 120, required=True):
        raise ValueError(backend_message('Indica un autor de 1 a 120 caracteres, sin caracteres de control.',
                                        en='Enter an author of 1 to 120 characters without control characters.',
                                        pt='Informe um autor de 1 a 120 caracteres, sem caracteres de controle.'))
    if not isinstance(decision, str) or decision not in {'accepted', 'issues'}:
        raise ValueError(backend_message('La decisión debe ser accepted o issues.',
                                        en='Decision must be accepted or issues.',
                                        pt='A decisão deve ser accepted ou issues.'))
    if not _text(note, 4000, required=decision == 'issues', multiline=True):
        raise ValueError(backend_message('La nota admite hasta 4000 caracteres y es obligatoria si hay problemas.',
                                        en='The note allows up to 4000 characters and is required for issues.',
                                        pt='A nota permite até 4000 caracteres e é obrigatória se houver problemas.'))
    return author.strip(), decision, note.strip()


def validate_comparison(value):
    """Validate the compact, non-content subset also accepted from backups."""
    if not isinstance(value, dict) or set(value) != _COMPARISON:
        raise ValueError(invalid())
    if any(not isinstance(value[key], str) or not _HASH.fullmatch(value[key])
           for key in ('before_sha256', 'after_sha256')):
        raise ValueError(invalid())
    if any(not _integer(value[key], 1, pdf_compare.MAX_PAGES)
           for key in ('before_pages', 'after_pages')):
        raise ValueError(invalid())
    if value['before_sha256'] == value['after_sha256'] and value['before_pages'] != value['after_pages']:
        raise ValueError(invalid())
    if not isinstance(value['pairing_mode'], str) or value['pairing_mode'] not in {'positional', 'manual'}:
        raise ValueError(invalid())
    pairs = value['page_pairs']
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 2 * pdf_compare.MAX_PAGES:
        raise ValueError(invalid())
    seen = {'before': set(), 'after': set()}
    added = removed = 0
    for index, pair in enumerate(pairs, 1):
        if not isinstance(pair, dict) or set(pair) != {'before_page', 'after_page'}:
            raise ValueError(invalid())
        if pair['before_page'] is None and pair['after_page'] is None:
            raise ValueError(invalid())
        for side in seen:
            number = pair[side + '_page']
            if number is not None:
                if not _integer(number, 1, value[side + '_pages']) or number in seen[side]:
                    raise ValueError(invalid())
                seen[side].add(number)
            if value['pairing_mode'] == 'positional' and number != (index if index <= value[side + '_pages'] else None):
                raise ValueError(invalid())
        added += pair['before_page'] is None
        removed += pair['after_page'] is None
    if any(seen[side] != set(range(1, value[side + '_pages'] + 1)) for side in seen):
        raise ValueError(invalid())
    summary = value['summary']
    if (not isinstance(summary, dict) or set(summary) != _SUMMARY
            or any(not _integer(count, 0, len(pairs)) for count in summary.values())
            or summary['total_pages'] != len(pairs)
            or sum(count for key, count in summary.items() if key != 'total_pages') != len(pairs)
            or summary['added'] != added or summary['removed'] != removed):
        raise ValueError(invalid())
    return value


def _summary(content):
    manifest = pdf_compare.comparison_manifest(content)
    value = {key: deepcopy(manifest[key]) for key in _COMPARISON - {'page_pairs'}}
    value['page_pairs'] = [{key: row[key] for key in ('before_page', 'after_page')}
                           for row in manifest['pages']]
    validate_comparison(value)
    result = dict(value, schema='report-gen-pdf-comparison/2')
    if len(dumps(result)) > MAX_METADATA:
        raise ReceiptLimitError(backend_message('El recibo temporal supera 64 KiB.',
                                               en='The temporary receipt exceeds 64 KiB.',
                                               pt='O recibo temporário excede 64 KiB.'))
    return result


class ReceiptStore:
    """Bounded metadata only, rotating oldest entries within the same session."""

    def __init__(self, *, clock=None):
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._records = {}

    def _prune(self, now):
        for key, item in list(self._records.items()):
            if now >= item['deadline']:
                del self._records[key]

    def add(self, owner, html_bytes):
        if not isinstance(owner, str) or not owner:
            raise ValueError(invalid())
        manifest = _summary(html_bytes)
        html_hash = sha256(html_bytes).hexdigest()
        with self._lock:
            now = self._clock()
            self._prune(now)
            owned = [key for key, item in self._records.items() if item['owner'] == owner]
            if len(owned) < MAX_OWNER and len(self._records) >= MAX_RECEIPTS:
                raise ReceiptLimitError(backend_message('Hay demasiados recibos temporales; vuelve a intentarlo más tarde.',
                                                       en='Too many temporary receipts; try again later.',
                                                       pt='Há muitos recibos temporários; tente novamente mais tarde.'))
            if len(owned) >= MAX_OWNER:
                del self._records[owned[0]]
            key = secrets.token_urlsafe(32)
            while key in self._records:
                key = secrets.token_urlsafe(32)
            created = datetime.now(timezone.utc)
            value = dict(comparison_id=key, manifest=manifest, html_sha256=html_hash,
                         created_at=created.isoformat(timespec='microseconds'),
                         expires_at=(created + timedelta(seconds=TTL)).isoformat(timespec='microseconds'))
            self._records[key] = dict(owner=owner, deadline=now + TTL, value=value)
            return key

    def get(self, owner, key):
        with self._lock:
            self._prune(self._clock())
            if not isinstance(key, str) or not _ID.fullmatch(key):
                raise KeyError(key)
            item = self._records.get(key)
            if item is None or item['owner'] != owner:
                raise KeyError(key)
            return deepcopy(item['value'])

    def discard(self, owner, key):
        with self._lock:
            try:
                self.get(owner, key)
            except KeyError:
                return False
            del self._records[key]
            return True


def make_record(receipt, author, decision, note):
    author, decision, note = validate_decision(author, decision, note)
    record = {key: deepcopy(receipt['manifest'][key]) for key in _COMPARISON}
    record.update(schema=SCHEMA, uid=str(uuid.uuid4()), created=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                  html_sha256=receipt['html_sha256'], author=author, decision=decision, note=note,
                  author_identity='local_self_declaration', semantic_equivalence_verified=False,
                  original_word_verified=False)
    validate_record(record)
    return record


def validate_record(record):
    if not isinstance(record, dict) or set(record) != _RECORD or record['schema'] != SCHEMA:
        raise ValueError(invalid())
    try:
        uid = uuid.UUID(record['uid'])
        created = datetime.fromisoformat(record['created'])
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(invalid()) from exc
    if (str(uid) != record['uid'] or uid.version != 4 or created.utcoffset() != timedelta(0)
            or not isinstance(record['html_sha256'], str) or not _HASH.fullmatch(record['html_sha256'])
            or record['author_identity'] != 'local_self_declaration'
            or record['semantic_equivalence_verified'] is not False
            or record['original_word_verified'] is not False):
        raise ValueError(invalid())
    validate_decision(record['author'], record['decision'], record['note'])
    validate_comparison({key: record[key] for key in _COMPARISON})
    if len(dumps(record)) > MAX_METADATA:
        raise ValueError(invalid())
    return record


def attachment_row(record, blob):
    validate_record(record)
    return dict(uid=record['uid'], name='pdf-comparison-review-' + record['uid'] + '.json',
                member='attachments/' + uuid.UUID(record['uid']).hex + '.json',
                sha256=sha256(blob).hexdigest(), include=False, reviewed=False, required=False)


def read_record(directory, row):
    """Read only an explicitly declared receipt whose content/hash/identity agree."""
    attachments.validate_rows([row])
    if (not row['name'].startswith('pdf-comparison-review-')
            or row['name'] != 'pdf-comparison-review-' + row['uid'] + '.json'
            or row.get('member') != 'attachments/' + row['uid'].replace('-', '') + '.json'):
        raise ValueError(invalid())
    path = Path(directory) / row['member']
    if path.is_symlink() or (Path(directory) / 'attachments').is_symlink() or path.stat().st_size > MAX_METADATA:
        raise ValueError(invalid())
    blob = attachments.read(directory, row)
    record = validate_record(load_json(blob))
    if record['uid'] != row['uid']:
        raise ValueError(invalid())
    return record, blob


def records(data, directory):
    rows = data.get('attachments', [])
    attachments.validate_rows(rows)
    result = []
    for row in rows:
        if row['name'].startswith('pdf-comparison-review-'):
            try:
                record, _ = read_record(directory, row)
            except (ValueError, OSError):
                continue  # Unrelated, missing, modified or imported-invalid attachments are not reviews.
            result.append(record)
    return sorted(result, key=lambda item: (item['created'], item['uid']), reverse=True)
