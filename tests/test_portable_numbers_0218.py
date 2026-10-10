"""Global numeric boundary: source IDs must survive a real browser JSON save."""
from copy import deepcopy
import json
import math
import shutil
import subprocess

import pytest

from input_guard import ensure_data_tree, load_json, load_yaml
import validate


SAFE = 2**53 - 1


@pytest.mark.parametrize('value', [SAFE + 1, -(SAFE + 1), 10**400, -(10**400)])
@pytest.mark.parametrize('container', ['proof', 'meta', 'extension'])
def test_nonportable_integer_rejected_globally_with_its_path_before_mutation(value, container):
    data = {'meta': {'report_title': 'Synthetic numeric audit'}, 'findings': [{'id': 'F1'}]}
    if container == 'proof':
        data['findings'][0]['proof'] = [{'name': 'Synthetic numeric identifier', 'value': value}]
        expected = 'findings[0].proof[0].value'
    elif container == 'meta':
        data['meta']['version'] = value; expected = 'meta.version'
    else:
        data['extension'] = {'documentary_id': value}; expected = 'extension.documentary_id'
    before = deepcopy(data)
    with pytest.raises(ValueError, match=expected.replace('[', r'\[').replace(']', r'\]')) as exc:
        ensure_data_tree(data)
    assert 'entre comillas' in str(exc.value) and 'quote' in str(exc.value)
    errors = [message for level, message in validate.structure_issues(data) if level == 'error']
    assert len(errors) == 1 and expected in errors[0]
    assert data == before


def test_error_does_not_stringify_arbitrarily_large_integer():
    data = {'extension': {'documentary_id': 1 << 20000}}
    with pytest.raises(ValueError, match='extension.documentary_id') as exc:
        ensure_data_tree(data)
    assert len(str(exc.value)) < 300


@pytest.mark.parametrize('loader', [load_json, load_yaml])
@pytest.mark.parametrize('literal', ['9007199254740992', '-9007199254740992', '1' + '0' * 400])
def test_serialized_number_rejected_by_both_bounded_input_formats(loader, literal):
    source = ('{"extension":{"documentary_id":' + literal + '}}') if loader is load_json else ('extension:\n  documentary_id: ' + literal + '\n')
    with pytest.raises(ValueError, match='extension.documentary_id'):
        loader(source)


@pytest.mark.parametrize('loader', [load_json, load_yaml])
@pytest.mark.parametrize('value', [str(SAFE + 1), str(-(SAFE + 1)), '1' + '0' * 400])
def test_quoted_numeric_identifier_preserves_all_documentary_digits(loader, value):
    data = {'meta': {'version': value}, 'findings': [{'id': 'F1', 'proof': [{'value': value}]}]}
    source = json.dumps(data) if loader is load_json else __import__('yaml').safe_dump(data)
    assert loader(source) == data
    assert not validate.structure_issues(data)


@pytest.mark.parametrize('value', [-SAFE, -1, 0, 1, SAFE, True, False])
def test_safe_numbers_and_structural_booleans_keep_their_values_and_types(value):
    data = {'extension': {'value': value}}
    assert ensure_data_tree(data) is data
    for loader in (load_json, load_yaml):
        parsed = loader(json.dumps(data))
        assert parsed == data and type(parsed['extension']['value']) is type(value)


@pytest.mark.parametrize('literal', ['NaN', 'Infinity', '-Infinity', '1e400'])
def test_nonfinite_json_numbers_stay_rejected(literal):
    with pytest.raises(ValueError, match='no finito'):
        load_json('{"extension":{"value":' + literal + '}}')


def test_finite_floats_safe_integer_limits_and_unicode_survive_real_node_json_roundtrip():
    node = shutil.which('node')
    if not node: pytest.skip('Node.js is required for the real browser-number round-trip contract.')
    values = [-SAFE, SAFE, 0, True, False, None, 0.1, 1.7976931348623157e308,
              math.nextafter(0, 1), -1.7976931348623157e308, str(SAFE + 1), 'á / 序列 / 🔒']
    data = {'Unicode_序列': {'values': values}}
    for _ in range(40): data = {'level': data}
    ensure_data_tree(data)
    source = json.dumps(data, ensure_ascii=False, allow_nan=False)
    result = subprocess.run([node, '-e', "process.stdout.write(JSON.stringify(JSON.parse(require('fs').readFileSync(0,'utf8'))));"],
                             input=source, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert load_json(result.stdout) == data


def test_unicode_deep_location_identifies_nonportable_integer_without_rewriting():
    data = {'序列': [{'documentary_id': SAFE + 1}]}
    for _ in range(40): data = {'level': data}
    before = deepcopy(data)
    with pytest.raises(ValueError, match=r'序列\[0\]\.documentary_id'):
        ensure_data_tree(data)
    assert data == before
