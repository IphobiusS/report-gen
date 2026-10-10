"""Incremental YAML serialization and bounded, immutable history compositions.

The interoperable engagement.yaml is always a complete atomically replaced YAML.
Only the local history may compose its bytes from verified content-addressed parts.
Portable backups materialize ordinary YAML objects, compatible with version 1.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re

import yaml
from error_messages import message as backend_message
from input_guard import MAX_DOCUMENT_BYTES, load_yaml
from storage import atomic_write

THRESHOLD = 128 * 1024
MAGIC = b'report-gen-yaml-parts-1\n'
MAX_PARTS = 20000
MAX_RECIPE_BYTES = 2 * 1024 * 1024
MAX_PART_BYTES = MAX_DOCUMENT_BYTES
CACHE_BYTES = 48 * 1024 * 1024
CACHE_PROJECTS = 8
_HASH = re.compile(r'^[0-9a-f]{64}$')
_CACHE = OrderedDict()
_PREPARED = ContextVar('report_gen_incremental_yaml', default=None)


def digest(blob):
    return sha256(blob).hexdigest()


def _error():
    return ValueError(backend_message('Objeto incremental de historial inválido o alterado',
                                    en='Invalid or altered incremental history object'))


def _bounded_file(path, maximum):
    path = Path(path)
    require_unlinked(path)
    if not path.is_file():
        raise _error()
    with path.open('rb') as source:
        blob = source.read(maximum + 1)
    if len(blob) > maximum:
        raise _error()
    return blob


def require_unlinked(path):
    """Check lexical parents before resolving or following any directory link."""
    path = Path(path)
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise _error()


def _equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _dump(value):
    from wizard import _Dumper
    class PartsDumper(_Dumper):
        def ignore_aliases(self, data):
            return True
    blob = yaml.dump(value, Dumper=PartsDumper, allow_unicode=True,
                     sort_keys=False, width=100).encode('utf-8')
    # A keep-chomp scalar can make PyYAML append a root document-end marker.
    # Fragments belong to one complete document. Remove only that complete
    # unindented final line, never a scalar's indented literal "    ...\n".
    return blob[:-4] if blob.endswith(b'\n...\n') else blob


def _portable(value):
    if isinstance(value, dict):
        return {key: _portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_portable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return load_yaml(_dump(value))
    return value


def _sequence_parts(blob, count):
    """Split a newly emitted block sequence at verified root-element offsets.

    Our dumper disables aliases and uses block sequences. A root item's dash is
    the only unindented dash; multiline scalar contents and nested items are
    indented. Validate the boundaries before associating any fragment with a UID.
    Complete YAML parsing and semantic comparison still validate the final state.
    """
    parts, current = [], bytearray()
    for line in blob.splitlines(keepends=True):
        if line.startswith(b'- ') or line in (b'-\n', b'-\r\n'):
            if current:
                parts.append(bytes(current)); current.clear()
        elif not current:
            raise _error()
        current.extend(line)
    if current:
        parts.append(bytes(current))
    if len(parts) != count or b''.join(parts) != blob:
        raise _error()
    return parts


@dataclass
class State:
    data: dict
    parts: list
    entries: dict
    blob: bytes
    revision: str


def _state(data, previous=None):
    parts, entries = [], {}
    stats = dict(serialized_rows=0, reused_rows=0, serialized_top_fields=0)
    old = previous.entries if previous else {}
    for key, value in data.items():
        if isinstance(value, list) and value:
            # Each fragment is its own YAML document-free sequence. No anchors
            # span fragments, so reordering can reuse the identical bytes.
            header_key = ('header', key)
            header = old.get(header_key)
            if header is None:
                header = (None, _dump({key: None}).removesuffix(b' null\n') + b'\n')
                stats['serialized_top_fields'] += 1
            entries[header_key] = header
            parts.append(header[1])
            # A cold save emits the current list once, then obtains reusable
            # row bytes from verified emitter offsets. It never serializes the
            # entire preceding state just to build a cache before the real edit.
            cold_parts = _sequence_parts(_dump(value), len(value)) if previous is None else None
            for index, row in enumerate(value):
                identity = row.get('uid') if isinstance(row, dict) else None
                token = ('row', key, identity if isinstance(identity, str) else index)
                entry = old.get(token)
                if entry is not None and _equal(entry[0], row):
                    stats['reused_rows'] += 1
                else:
                    entry = (deepcopy(row), cold_parts[index] if cold_parts is not None else _dump([row]))
                    stats['serialized_rows'] += 1
                entries[token] = entry
                parts.append(entry[1])
        else:
            token = ('field', key)
            entry = old.get(token)
            if entry is None or not _equal(entry[0], value):
                entry = (deepcopy(value), _dump({key: value}))
                stats['serialized_top_fields'] += 1
            entries[token] = entry
            parts.append(entry[1])
    blob = b''.join(parts)
    # Includes size, graph complexity and expanded text budgets. Reusing parts
    # must never bypass the reader's complete-document validation.
    actual = load_yaml(blob)
    if not _equal(actual, _portable(data)):
        # Dates accepted by the public writer intentionally read back as text;
        # compare the same interoperable scalar semantics, not Python aliases.
        raise _error()
    return State(deepcopy(actual), parts, entries, blob, digest(blob)), stats


@dataclass
class Plan:
    state: State | None
    blob: bytes
    before: bytes | None
    unchanged: bool
    stats: dict
    existing_data: dict | None


def prepare(directory, data):
    key = str(Path(directory).resolve())
    source = Path(directory) / 'engagement.yaml'
    before = _bounded_file(source, MAX_DOCUMENT_BYTES) if source.exists() or source.is_symlink() else None
    old = _CACHE.get(key)
    revision = digest(before) if before is not None else None
    if old is not None and old.revision != revision:
        # Real bytes are checked on every call, even if size/inode/mtime match.
        _CACHE.pop(key, None)
        old = None
    existing = old.data if old is not None else load_yaml(before) if before is not None else None
    stats = dict(cache_hit=old is not None, cold_rows=0, serialized_rows=0,
                 reused_rows=0, serialized_top_fields=0, yaml_bytes=0)
    if before is not None and _equal(existing, data):
        stats['yaml_bytes'] = len(before)
        return Plan(old, before, before, True, stats, existing)
    state, changes = _state(data, old)
    stats.update(changes)
    stats['yaml_bytes'] = len(state.blob)
    return Plan(state, state.blob, before, False, stats, existing)


def remember(directory, plan):
    key = str(Path(directory).resolve())
    if plan.state is None:
        return
    _CACHE.pop(key, None)
    _CACHE[key] = plan.state
    def size(state):
        # Bound serialized copies, with room for the comparable data tree.
        return len(state.blob) + sum(len(entry[1]) for entry in state.entries.values()) * 2
    while len(_CACHE) > CACHE_PROJECTS or sum(size(state) for state in _CACHE.values()) > CACHE_BYTES:
        _CACHE.popitem(last=False)


def clear_cache():
    _CACHE.clear()


@contextmanager
def prepared(data, plan):
    token = _PREPARED.set((id(data), plan.blob, True))
    try:
        yield
    finally:
        _PREPARED.reset(token)


def serialized_yaml(data):
    value = _PREPARED.get()
    if value is not None and value[0] == id(data):
        return value[1]
    from wizard import _Dumper
    return yaml.dump(data, Dumper=_Dumper, allow_unicode=True,
                     sort_keys=False, width=100).encode('utf-8')


def already_validated(data, blob):
    value = _PREPARED.get()
    return value is not None and value[0] == id(data) and value[1] == blob and value[2]


def byte_parts(blob):
    """Content-defined boundaries for externally authored, noncanonical YAML.

    Stable line anchors resynchronize after an edit; no YAML reformatting is
    necessary to preserve an exact legacy or externally authored snapshot.
    """
    result, buffer = [], bytearray()
    for line in blob.splitlines(keepends=True):
        if len(line) > 32768:
            if buffer:
                result.append(bytes(buffer)); buffer.clear()
            result.extend(line[n:n + 32768] for n in range(0, len(line), 32768))
            continue
        buffer.extend(line)
        anchor = int.from_bytes(sha256(line).digest()[:2], 'big') % 128 == 0
        if len(buffer) >= 32768 or (len(buffer) >= 2048 and anchor):
            result.append(bytes(buffer)); buffer.clear()
    if buffer:
        result.append(bytes(buffer))
    return result


def store_object(directory, blob, parts=None):
    """Write only absent immutable fragments and a bounded composition object."""
    directory = Path(directory)
    key = digest(blob)
    target = directory / 'history' / 'objects' / key
    require_unlinked(target)
    if target.exists() or target.is_symlink():
        if read_object(directory, key, document=True) != blob:
            raise _error()
        return dict(object_bytes_written=0, objects_written=0, fragment_bytes_written=0, fragments_written=0)
    stats = dict(object_bytes_written=0, objects_written=1, fragment_bytes_written=0, fragments_written=0)
    if len(blob) < THRESHOLD:
        atomic_write(target, blob)
        stats['object_bytes_written'] = len(blob)
        return stats
    parts = parts if parts and b''.join(parts) == blob else byte_parts(blob)
    # Upper bounds also apply to author lists with many very small rows.
    if len(parts) > MAX_PARTS:
        parts = byte_parts(blob)
    hashes = []
    for part in parts:
        fragment_key = digest(part)
        fragment = directory / 'history' / 'fragments' / fragment_key
        require_unlinked(fragment)
        hashes.append(fragment_key)
        if fragment.exists() or fragment.is_symlink():
            if digest(_bounded_file(fragment, MAX_PART_BYTES)) != fragment_key:
                raise _error()
        else:
            atomic_write(fragment, part)
            stats['fragment_bytes_written'] += len(part)
            stats['fragments_written'] += 1
    recipe = MAGIC + json.dumps(dict(format='report-gen-yaml-parts', version=1,
                    bytes=len(blob), sha256=key, parts=hashes), separators=(',', ':')).encode('ascii')
    if len(recipe) > MAX_RECIPE_BYTES:
        raise _error()
    atomic_write(target, recipe)
    stats['object_bytes_written'] = len(recipe)
    return stats


def read_object(directory, key, *, document=False):
    if not isinstance(key, str) or not _HASH.fullmatch(key):
        raise _error()
    directory = Path(directory)
    target = directory / 'history' / 'objects' / key
    maximum = max(MAX_DOCUMENT_BYTES, MAX_RECIPE_BYTES) if document else 256 * 1024 * 1024
    blob = _bounded_file(target, maximum)
    # The object namespace addresses content, not its role: a valid text annex
    # can contain the very same bytes as a historical YAML. Always return a raw
    # object with its correct hash literally, even if it begins MAGIC. Otherwise
    # a verified composition resolves for every role; callers validate that role.
    if digest(blob) == key:
        return blob
    if not blob.startswith(MAGIC):
        raise _error()
    if len(blob) > MAX_RECIPE_BYTES:
        raise _error()
    try:
        # JSON hooks reject duplicate recipe keys; only this simple schema is
        # accepted. Parts are raw bytes, never recursively resolved recipes.
        def mapping(pairs):
            result = {}
            for name, value in pairs:
                if name in result:
                    raise _error()
                result[name] = value
            return result
        recipe = json.loads(blob[len(MAGIC):], object_pairs_hook=mapping)
        if (not isinstance(recipe, dict) or set(recipe) != {'format', 'version', 'bytes', 'sha256', 'parts'}
                or recipe['format'] != 'report-gen-yaml-parts' or type(recipe['version']) is not int
                or recipe['version'] != 1 or recipe['sha256'] != key
                or type(recipe['bytes']) is not int or not 0 <= recipe['bytes'] <= MAX_DOCUMENT_BYTES
                or not isinstance(recipe['parts'], list) or not 1 <= len(recipe['parts']) <= MAX_PARTS):
            raise _error()
        output = bytearray()
        for fragment_key in recipe['parts']:
            if not isinstance(fragment_key, str) or not _HASH.fullmatch(fragment_key):
                raise _error()
            part = _bounded_file(directory / 'history' / 'fragments' / fragment_key, min(MAX_PART_BYTES, recipe['bytes']))
            if digest(part) != fragment_key or len(output) + len(part) > recipe['bytes']:
                raise _error()
            output.extend(part)
        if len(output) != recipe['bytes'] or digest(output) != key:
            raise _error()
        return bytes(output)
    except (ValueError, UnicodeError, TypeError, KeyError, RecursionError, OSError) as exc:
        raise _error() from exc
