"""The fast reader must keep the bounded Python reader's input contract."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import yaml

import input_guard as guard


@pytest.fixture(params=['default', 'python'])
def reader(request, monkeypatch):
    if request.param == 'python':
        monkeypatch.setattr(guard, 'ProjectLoader', guard.PythonProjectLoader)
    return guard.load_yaml


@pytest.mark.parametrize('source,expected', [
    ('', None), ('# comment\n', None), ('---\n...\n', None),
    ('date: 2026-10-09\ntime: 2026-10-09T12:00:00Z\n',
     {'date': '2026-10-09', 'time': '2026-10-09T12:00:00Z'}),
    ('v: !!timestamp not-a-date\n', {'v': 'not-a-date'}),
    ('v: [!!int "1_000", !!float "2:30.0", !!bool YES, null]\n',
     {'v': [1000, 150.0, True, None]}),
    ('defaults: &d {title: Original, language: es}\n'
     'meta: {<<: *d, title: Chosen}\n',
     {'defaults': {'title': 'Original', 'language': 'es'},
      'meta': {'title': 'Chosen', 'language': 'es'}}),
    ('a: &a {x: first, y: one}\nb: &b {x: second, z: two}\n'
     'c: {<<: [*a, *b], y: override}\n',
     {'a': {'x': 'first', 'y': 'one'}, 'b': {'x': 'second', 'z': 'two'},
      'c': {'x': 'first', 'y': 'override', 'z': 'two'}}),
    ('v: |+\n  uno\n  ...\n\n', {'v': 'uno\n...\n\n'}),
    ('v: "x\ty"\n', {'v': 'x\ty'}),
    ('v: |\n  x\ty\n', {'v': 'x\ty\n'}),
    ('v: "Prometeo · Evaristo 🐾"\n', {'v': 'Prometeo · Evaristo 🐾'}),
    ('a: &a [\r\ufeffx,y]\nb: *a', {'a': ['\ufeffx', 'y'], 'b': ['\ufeffx', 'y']}),
    ('a: {<<:{x: y}, x: z}\n', {'a': {'x': 'z'}}),
    ('a: [ax, y:, z]\n', {'a': ['ax', {'y': None}, 'z']}),
    ('%AML 1.1\n---\na: x\n', {'a': 'x'}),
    ('a: x\nb: !\n', {'a': 'x', 'b': None}),
    ('! \n# comentario\n', None),
])
def test_readers_preserve_values(reader, source, expected):
    assert reader(source) == expected


@pytest.mark.parametrize('source', [
    'a: 1\na: 2\n', 'a: 1\n"a": 2\n',
    'd: &d {a: x}\nv: {<<: *d, <<: *d}\n',
    '{[x]: y}', '{1: y}', '{true: y}',
    'a: &a [*a]\n', 'a: &a {<<: *a}\n',
    'a: *missing\n', 'a: &same x\nb: &same y\n',
    '---\na: x\n---\nb: y\n',
    'a: !!python/object/apply:os.system [echo]\n',
    'a: !!int ""\n', 'a: !!float ""\n', 'a: !!bool unknown\n',
    'a: .nan\n', 'a: .inf\n', 'a: 9007199254740992\n',
    'a: "\\u0000"\n', 'a: "\\uD800"\n',
    'a: x\ty\n', 'a:\n\t- y\n', 'a: [x,\n',
    'a: |#comment\n', 'a: >#comment\n', 'a: |1-#comment\n',
    'a: [x, y?, z]\n', 'a: &a [!,y]\nb: *a\n',
    b'a: \xff\n',
])
def test_readers_reject_ambiguous_or_unsafe_inputs(reader, source):
    with pytest.raises(ValueError):
        reader(source)


def test_alias_containers_are_detached(reader):
    value = reader('original: &a {rows: [{title: first}]}\ncopy: *a\n')
    value['copy']['rows'][0]['title'] = 'modified'
    assert value['original']['rows'][0]['title'] == 'first'


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-16-le', 'utf-16-be'])
def test_unicode_encoding_and_dates(reader, encoding):
    text = 'v: Prometeo · Evaristo\ndate: 2026-10-09\n'
    bom = {'utf-16-le': b'\xff\xfe', 'utf-16-be': b'\xfe\xff'}.get(encoding, b'')
    assert reader(bom + text.encode(encoding)) == {'v': 'Prometeo · Evaristo', 'date': '2026-10-09'}


@pytest.mark.parametrize('budget,amount,source', [
    ('MAX_DOCUMENT_BYTES', 24, 'a: ' + 'x' * 30),
    ('MAX_DEPTH', 4, '[' * 5 + 'x' + ']' * 5),
    ('MAX_NODES', 6, 'a: [x, y, z, q]'),
    ('MAX_NODES', 20, 'a: &a [x, y, z]\nb: [*a, *a, *a, *a, *a]'),
    ('MAX_EXPANDED_TEXT', 20, 'a: &a abcdefghij\nb: [*a, *a]'),
])
def test_budgets_apply_to_both_readers(reader, monkeypatch, budget, amount, source):
    monkeypatch.setattr(guard, budget, amount)
    with pytest.raises(ValueError):
        reader(source)


def test_depth_boundary_includes_scalar(reader, monkeypatch):
    monkeypatch.setattr(guard, 'MAX_DEPTH', 4)
    assert reader('[[[x]]]') == [[['x']]]
    with pytest.raises(ValueError, match='profundo'):
        reader('[[[[x]]]]')


@pytest.mark.skipif(not hasattr(yaml, 'CSafeLoader'), reason='libyaml is not installed')
@pytest.mark.parametrize('budget,amount,source', [
    ('MAX_DEPTH', 4, '\n'.join(' ' * n + 'a:' for n in range(100)) + '\n'),
    ('MAX_NODES', 5, 'values:\n' + '  - word\n' * 10000),
])
def test_c_preflight_rejects_before_composition(monkeypatch, budget, amount, source):
    reached = []
    def forbidden(*args):
        reached.append(True)
        raise AssertionError('composition must not start')
    monkeypatch.setattr(guard.ProjectLoader, 'get_single_node', forbidden)
    monkeypatch.setattr(guard, budget, amount)
    with pytest.raises(ValueError):
        guard.load_yaml(source)
    assert not reached


@pytest.mark.skipif(not hasattr(yaml, 'CSafeLoader'), reason='libyaml is not installed')
def test_c_preflight_does_not_construct_documents(monkeypatch):
    reached = []
    def forbidden(*args):
        reached.append(True)
        raise AssertionError('preflight must not construct')
    monkeypatch.setattr(yaml.CSafeLoader, 'get_single_node', forbidden)
    monkeypatch.setattr(yaml.CSafeLoader, 'construct_document', forbidden)
    guard._preflight_yaml_events(b'a: &a\n  - 1\n  - 2\nb: *a\n')
    assert not reached


@pytest.mark.parametrize('source', [
    'a: &a [*a]\n', 'a: 1\na: 2\n',
    'a: &a [x, y, z]\nb: [*a, *a, *a, *a, *a]',
    'a: &a\n  self: *a\n',
    'a: &a\n  - x\n  - y\n  - z\nb:\n' + '  - *a\n' * 5,
])
def test_graph_rejections_happen_before_construction(reader, monkeypatch, source):
    reached = []
    def forbidden(*args):
        reached.append(True)
        raise AssertionError('unsafe graph must not be constructed')
    monkeypatch.setattr(guard.ProjectLoader, 'construct_document', forbidden)
    monkeypatch.setattr(guard.PythonProjectLoader, 'construct_document', forbidden)
    monkeypatch.setattr(guard, 'MAX_NODES', 20)
    with pytest.raises(ValueError):
        reader(source)
    assert not reached


def test_python_fallback_when_libyaml_is_unavailable(monkeypatch):
    monkeypatch.delattr(yaml, 'CSafeLoader', raising=False)
    spec = spec_from_file_location('guard_without_libyaml', Path(guard.__file__))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ProjectLoader is module.PythonProjectLoader
    assert module.load_yaml('date: 2026-10-09\n') == {'date': '2026-10-09'}
    with pytest.raises(ValueError):
        module.load_yaml('a: &a [*a]')
    monkeypatch.setattr(module, 'MAX_DEPTH', 3)
    with pytest.raises(ValueError):
        module.load_yaml('[[[x]]]')


@pytest.mark.parametrize('second_document', ['[' * 100 + 'x' + ']' * 100,
                                            '[' + ','.join(['x'] * 100) + ']'])
def test_multiple_documents_rejected_before_second_document_budget(reader, monkeypatch, second_document):
    monkeypatch.setattr(guard, 'MAX_DEPTH', 4)
    monkeypatch.setattr(guard, 'MAX_NODES', 8)
    with pytest.raises(ValueError, match='^YAML inválido o demasiado complejo$'):
        reader('first: document\n---\n' + second_document)


@pytest.mark.skipif(not hasattr(yaml, 'CSafeLoader'), reason='libyaml is not installed')
def test_production_block_yaml_and_empty_containers_use_c_composition(monkeypatch):
    reached = []
    original = guard.ProjectLoader.get_single_node
    def counted(self):
        reached.append(True)
        return original(self)
    monkeypatch.setattr(guard.ProjectLoader, 'get_single_node', counted)
    actual = guard.load_yaml('meta:\n  date: 2026-10-09\nfindings:\n  - id: F1\n'
                             '    tags: []\n    details: {}\n')
    assert actual == {'meta': {'date': '2026-10-09'},
                      'findings': [{'id': 'F1', 'tags': [], 'details': {}}]}
    assert reached == [True]


@pytest.mark.skipif(not hasattr(yaml, 'CSafeLoader'), reason='libyaml is not installed')
@pytest.mark.parametrize('source,budget', [('a:\n  b:\n    c: x', 2),
                                          ('a: [x, y]', 64),
                                          ('a: [', 64)])
def test_preflight_disposes_parser_when_budget_syntax_or_fallback_stops_it(monkeypatch, source, budget):
    disposed = []
    original = yaml.CSafeLoader
    class Tracked(original):
        def dispose(self):
            disposed.append(True)
            return super().dispose()
    monkeypatch.setattr(yaml, 'CSafeLoader', Tracked)
    monkeypatch.setattr(guard, 'MAX_DEPTH', budget)
    with pytest.raises((ValueError, yaml.YAMLError, guard._PythonScannerRequired)):
        guard._preflight_yaml_events(source.encode())
    assert disposed == [True]
