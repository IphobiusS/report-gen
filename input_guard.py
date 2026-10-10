"""Bounded project inputs, without ambiguous mappings or exponential aliases."""
from error_messages import message as backend_message
from datetime import date, datetime
import json
import math
import re
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, SequenceNode, ScalarNode

MAX_DOCUMENT_BYTES = 12 * 1024 * 1024
MAX_DEPTH = 64
MAX_NODES = 250_000
MAX_EXPANDED_TEXT = 16 * 1024 * 1024
MAX_PORTABLE_INTEGER = 2**53 - 1
NONPORTABLE_TEXT = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')
_PYTHON_SCANNER_INPUT = re.compile(rb'[\x00\t]|\xef\xbb\xbf|[|>][0-9+-]*#|^%', re.MULTILINE)


def ensure_data_tree(data):
    """Visit expanded values with explicit budgets, including repeated aliases."""
    stack = [(data, 0, False, ())]
    active = set()
    nodes = text_bytes = 0
    while stack:
        value, depth, leaving, path = stack.pop()
        if leaving:
            active.remove(id(value))
            continue
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError(backend_message('Documento demasiado complejo (nodos o profundidad)'))
        if isinstance(value, (dict, list)):
            if id(value) in active:
                raise ValueError(backend_message('El documento contiene una referencia recursiva'))
            active.add(id(value))
            stack.append((value, depth, True, path))
            if isinstance(value, dict):
                if any(not isinstance(k, str) for k in value):
                    raise ValueError(backend_message('Las claves del documento deben ser texto'))
                children = [(key, path) for key in value]
                children += [(item, path + (key,)) for key, item in value.items()]
            else:
                children = [(item, path + (index,)) for index, item in enumerate(value)]
            if nodes + len(children) > MAX_NODES:
                raise ValueError(backend_message('Documento demasiado complejo (nodos)'))
            stack.extend((child, depth + 1, False, child_path) for child, child_path in reversed(children))
        elif isinstance(value, str):
            if NONPORTABLE_TEXT.search(value):
                raise ValueError(backend_message('El texto contiene caracteres de control no compatibles con los informes'))
            text_bytes += len(value.encode('utf-8'))
            if text_bytes > MAX_EXPANDED_TEXT:
                raise ValueError(backend_message('El texto expandido del documento supera 16 MiB'))
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(backend_message('El documento contiene un número no finito'))
        elif type(value) is int:
            # Browser JSON numbers are IEEE-754 doubles. Preserve documentary
            # identifiers as quoted text rather than rounding or coercing them
            # when the editor next saves the project. Never stringify the huge
            # integer itself while reporting this boundary error.
            if not -MAX_PORTABLE_INTEGER <= value <= MAX_PORTABLE_INTEGER:
                location = 'engagement' + ''.join(
                    f'[{part}]' if type(part) is int else '.' + part[:80] + ('…' if len(part) > 80 else '')
                    for part in path)
                raise ValueError(backend_message('{p0}: entero fuera del rango portátil ±9007199254740991; escribe entre comillas los identificadores numéricos mayores / integer outside the portable range; quote larger numeric identifiers', p0=location))
        elif value is not None and not isinstance(value, (int, bool, date, datetime)):
            raise ValueError(backend_message('Tipo de dato no compatible con el proyecto'))
    return data


class PythonProjectLoader(yaml.SafeLoader):
    """Bound composition before PyYAML recursively constructs or merges nodes."""
    def __init__(self, stream):
        super().__init__(stream)
        self.project_depth = 0
        self.project_nodes = 0

    def compose_node(self, parent, index):
        self.project_depth += 1
        self.project_nodes += 1
        try:
            if self.project_nodes > MAX_NODES:
                raise ValueError(backend_message('YAML demasiado complejo (nodos)'))
            if self.project_depth > MAX_DEPTH:
                raise ValueError(backend_message('YAML demasiado profundo'))
            return super().compose_node(parent, index)
        finally:
            self.project_depth -= 1

# Dates entered without quotes retain their ISO text in the browser, rather
# than being converted to an HTTP date by Flask's JSON provider.
PythonProjectLoader.add_constructor('tag:yaml.org,2002:timestamp', PythonProjectLoader.construct_scalar)


class _PythonScannerRequired(Exception):
    """Syntax for which libyaml does not preserve the legacy reader contract."""


def _preflight_yaml_events(blob):
    """Bound C parsing before composing nodes or constructing values.

    libyaml's composer does not call Python's compose_node override. Consume
    its events first, retaining only counters; scalars, aliases and collection
    starts correspond to compose_node calls in the Python implementation.
    The same immutable, byte-bounded input is then composed in a second pass.
    Expanded aliases, merges and duplicate keys still need _check_yaml_graph
    before construction. This pass deliberately does not replace that check.
    """
    parser = yaml.CSafeLoader(blob)
    depth = nodes = documents = 0
    flow_end = None
    try:
        while parser.check_event():
            event = parser.get_event()
            # Empty flow containers are emitted by the production serializer.
            # Nonempty flow syntax has scanner differences between libyaml and
            # the Python reader, including accepted inputs and scalar values.
            if flow_end is not None and not isinstance(event, flow_end):
                raise _PythonScannerRequired
            flow_end = None
            if getattr(event, 'tag', None) == '!':
                raise _PythonScannerRequired
            if isinstance(event, yaml.DocumentStartEvent):
                documents += 1
                if documents > 1:
                    # Match get_single_node: reject a second document before
                    # reading its contents or applying budgets to that content.
                    raise yaml.composer.ComposerError(
                        'expected a single document in the stream', None,
                        'but found another document', event.start_mark)
            if isinstance(event, (yaml.ScalarEvent, yaml.AliasEvent,
                                  yaml.SequenceStartEvent, yaml.MappingStartEvent)):
                nodes += 1
                if nodes > MAX_NODES:
                    raise ValueError(backend_message('YAML demasiado complejo (nodos)'))
                if depth + 1 > MAX_DEPTH:
                    raise ValueError(backend_message('YAML demasiado profundo'))
                if isinstance(event, (yaml.SequenceStartEvent, yaml.MappingStartEvent)):
                    depth += 1
                    if event.flow_style:
                        flow_end = (yaml.SequenceEndEvent if isinstance(event, yaml.SequenceStartEvent)
                                    else yaml.MappingEndEvent)
            elif isinstance(event, (yaml.SequenceEndEvent, yaml.MappingEndEvent)):
                depth -= 1
    finally:
        parser.dispose()


if hasattr(yaml, 'CSafeLoader'):
    class ProjectLoader(yaml.CSafeLoader):
        """C composition is reachable only after a bounded event preflight."""
        def __init__(self, stream):
            _preflight_yaml_events(stream)
            super().__init__(stream)

    ProjectLoader.add_constructor('tag:yaml.org,2002:timestamp', ProjectLoader.construct_scalar)
else:
    # PyYAML built without libyaml retains the original bounded composer.
    ProjectLoader = PythonProjectLoader


def _check_yaml_graph(root):
    stack = [(root, 0, False)]
    active = set()
    count = text_bytes = 0
    while stack:
        node, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(node))
            continue
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError(backend_message('YAML demasiado complejo al expandir referencias'))
        if isinstance(node, ScalarNode):
            text_bytes += len(node.value.encode('utf-8'))
            if text_bytes > MAX_EXPANDED_TEXT:
                raise ValueError(backend_message('El YAML expandido supera 16 MiB'))
            continue
        if id(node) in active:
            raise ValueError(backend_message('El YAML contiene una referencia recursiva'))
        if isinstance(node, MappingNode):
            # Check the original mapping, before SafeLoader flattens merges.
            seen = set()
            for key, _ in node.value:
                if not isinstance(key, ScalarNode) or key.tag not in (
                        'tag:yaml.org,2002:str', 'tag:yaml.org,2002:merge'):
                    raise ValueError(backend_message('Las claves YAML deben ser texto'))
                if key.value in seen:
                    raise ValueError(backend_message('Clave YAML duplicada: {p0}', p0=key.value))
                seen.add(key.value)
        active.add(id(node))
        stack.append((node, depth, True))
        children = [x for pair in node.value for x in pair] if isinstance(node, MappingNode) else node.value
        if not isinstance(node, (MappingNode, SequenceNode)) or count + len(children) > MAX_NODES:
            raise ValueError(backend_message('YAML demasiado complejo'))
        stack.extend((child, depth + 1, False) for child in reversed(children))


def _bounded_bytes(blob):
    if isinstance(blob, str):
        blob = blob.encode('utf-8')
    if len(blob) > MAX_DOCUMENT_BYTES:
        raise ValueError(backend_message('El documento supera 12 MiB'))
    return blob


def load_yaml(blob):
    loader = None
    try:
        blob = _bounded_bytes(blob)
        # Keep Python scanning for lexical cases with libyaml differences:
        # literal tabs, BOM/UTF-16, malformed block headers and directives.
        # Valid text matching this conservative filter still loads unchanged.
        loader_type = PythonProjectLoader if _PYTHON_SCANNER_INPUT.search(blob) else ProjectLoader
        try:
            loader = loader_type(blob)
        except (yaml.YAMLError, _PythonScannerRequired):
            if loader_type is PythonProjectLoader:
                raise
            # C scanning is stricter for some legacy-compatible syntax. The
            # fallback still bounds every compose_node before allocation.
            loader = PythonProjectLoader(blob)
        node = loader.get_single_node()
        if node is None:
            return None
        _check_yaml_graph(node)
        try:
            constructed = loader.construct_document(node)
        except (ValueError, KeyError, IndexError, OverflowError) as exc:
            # SafeLoader's explicit scalar constructors can raise ordinary
            # Python errors (empty !!int/!!float, unknown !!bool, overflow).
            # Normalize only construction failures, not graph/storage errors.
            raise ValueError(backend_message('YAML inválido: valor incompatible con su tipo declarado')) from exc
        data = ensure_data_tree(constructed)
        # Aliases describe repeated values, not live shared editor rows. The
        # expanded graph has passed all budgets before containers are detached.
        def detach(value):
            if isinstance(value, dict):
                return {key: detach(item) for key, item in value.items()}
            if isinstance(value, list):
                return [detach(item) for item in value]
            return value
        return detach(data)
    except (yaml.YAMLError, RecursionError, UnicodeError) as exc:
        raise ValueError(backend_message('YAML inválido o demasiado complejo')) from exc
    finally:
        if loader is not None:
            loader.dispose()


def load_yaml_file(path):
    with Path(path).open('rb') as source:
        return load_yaml(source.read(MAX_DOCUMENT_BYTES + 1))


def load_json(blob):
    def unique_mapping(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(backend_message('Clave JSON duplicada: {p0}', p0=key))
            result[key] = value
        return result
    try:
        return ensure_data_tree(json.loads(_bounded_bytes(blob), object_pairs_hook=unique_mapping))
    except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
        raise ValueError(backend_message('JSON inválido o demasiado complejo')) from exc


def load_json_file(path):
    with Path(path).open('rb') as source:
        return load_json(source.read(MAX_DOCUMENT_BYTES + 1))
