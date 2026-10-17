"""Legacy synthetic duplicate rows must repeat the actual scanner identity."""
import csv
import importlib.util
from io import StringIO
from pathlib import Path

import pytest

import finding_imports


@pytest.mark.parametrize('script,entry', [
    ('build-horizonte-case.py', 'write_import_inputs'),
    ('build-meridiano-case.py', 'import_inputs'),
    ('build-atlas-case.py', 'import_inputs'),
    ('build-boreal-case.py', 'import_inputs'),
    ('build-aster-case.py', 'BASE.import_inputs'),
])
def test_synthetic_duplicate_inputs_repeat_external_id_and_target(tmp_path, script, entry):
    spec = importlib.util.spec_from_file_location('scanner_identity_' + script.replace('-', '_'),
                                                Path(__file__).resolve().parents[1] / 'scripts' / script)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    create = builder
    for name in entry.split('.'):
        create = getattr(create, name)
    directory = tmp_path / 'inputs'
    manifests = create(directory)
    raw = (directory / 'findings.csv').read_text()
    rows = list(csv.DictReader(StringIO(raw)))
    assert len(rows) == 2 and rows[0]['external_id']
    assert (rows[0]['external_id'], rows[0]['affected']) == (rows[1]['external_id'], rows[1]['affected'])
    assert rows[0]['description_md'] != rows[1]['description_md']
    result = finding_imports.preview({'format': 'csv', 'text': raw}, {'findings': []})
    assert result['counts'] == manifests['findings.csv']['counts'] == {'rows': 2, 'valid': 2, 'duplicates': 1}
    assert [row['duplicate'] for row in result['rows']] == [False, True]
    assert result['rows'][0]['finding']['import_source']['fingerprint'] == result['rows'][1]['finding']['import_source']['fingerprint']
    with pytest.raises(ValueError):
        finding_imports.apply({'format': 'csv', 'text': raw, 'selected': [0, 1]}, {'findings': []})
