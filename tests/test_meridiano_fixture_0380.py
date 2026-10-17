"""Contracts of the substantial synthetic case, independent of its report outputs."""
from copy import deepcopy
import csv
from hashlib import sha256
import importlib.util
from io import StringIO
from pathlib import Path

import engine
import finding_imports
import publication
import pytest
import workflows


@pytest.fixture(scope='module')
def builder():
    path = Path(__file__).resolve().parents[1] / 'scripts/build-meridiano-case.py'
    spec = importlib.util.spec_from_file_location('meridiano_fixture_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def case(builder, tmp_path_factory):
    root = tmp_path_factory.mktemp('meridiano') / 'case'
    manifest = builder.build_case(root)
    return root, manifest


def test_case_counts_and_languages_preserve_authored_identity(case):
    root, manifest = case
    assert len(manifest['files']) == 131
    documents = [engine.load_engagement(root / 'projects' / lang / 'engagement.yaml') for lang in ('es', 'en', 'pt')]
    for data in documents:
        assert len(data['findings']) == 34
        assert len(data['assets']) == 16
        assert len(data['evidence']) == 32
        assert len(data['coverage']) == 90
        assert len(data['report']['sections']) == 16
        assert sum(len(row.get('retests', [])) for row in data['findings']) == 10
    for data in documents[1:]:
        assert data['findings'] == documents[0]['findings']
        assert data['report'] == documents[0]['report']
        assert data['evidence'] == documents[0]['evidence']
    for row in manifest['projects'].values():
        assert not row['validation_warnings']
        assert len(row['preflight_issues']) == 31
        assert {issue['level'] for issue in row['preflight_issues']} == {'warning'}


def test_case_manifest_binds_every_input_and_builder_creates_no_report(case):
    root, manifest = case
    assert manifest['reports_generated_by_builder'] is False
    assert manifest['network_to_scenario_targets'] is False
    for name, record in manifest['files'].items():
        blob = (root / name).read_bytes()
        assert len(blob) == record['bytes']
        assert sha256(blob).hexdigest() == record['sha256']
        assert Path(name).suffix not in ('.pdf', '.docx', '.html')
    assert {row['format'] for row in manifest['import_previews'].values()} == {'csv', 'burp', 'nuclei', 'nmap', 'sarif'}
    assert manifest['import_previews']['findings.csv']['counts']['duplicates'] == 1


@pytest.mark.parametrize('changed_field', ['external_id', 'affected'])
def test_csv_duplicate_repeats_source_identity_and_distinct_sources_remain_importable(case, builder, changed_field):
    text = (case[0] / 'inputs/findings.csv').read_text()
    reader = csv.DictReader(StringIO(text))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]['external_id'] == rows[1]['external_id'] == 'GML-CSV-01'
    assert rows[0]['affected'] == rows[1]['affected']
    assert rows[0]['description_md'] != rows[1]['description_md']
    body = {'format': 'csv', 'text': text}
    empty = {'findings': []}
    preview = finding_imports.preview(body, empty)
    fingerprints = [row['finding']['import_source']['fingerprint'] for row in preview['rows']]
    assert fingerprints[0] == fingerprints[1]
    with pytest.raises(ValueError):
        finding_imports.apply({**body, 'selected': [0, 1]}, empty)
    imported, count = finding_imports.apply({**body, 'selected': [0]}, empty)
    assert count == 1
    imported['findings'][0].update(title='Manual title', affected='Manual target grouping')
    repeated = finding_imports.preview(body, imported)
    assert all(row['existing_duplicate'] for row in repeated['rows'])
    rows[1][changed_field] += '-independent'
    distinct_text = builder.csv_bytes(reader.fieldnames, [[row[key] for key in reader.fieldnames] for row in rows]).decode()
    distinct_body = {'format': 'csv', 'text': distinct_text}
    assert finding_imports.preview(distinct_body, empty)['counts']['duplicates'] == 0
    distinct, count = finding_imports.apply({**distinct_body, 'selected': [0, 1]}, empty)
    assert count == 2 and len({row['uid'] for row in distinct['findings']}) == 2


def test_private_inputs_are_removed_by_real_native_snapshot(case, builder, tmp_path):
    source = case[0] / 'projects/es'
    source_before = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    captured = publication.snapshot(source, tmp_path / 'snapshot')
    destination = tmp_path / 'snapshot'
    public = engine.load_engagement(destination / 'engagement.yaml')
    assert public.get('capture_inbox', []) == []
    assert not (destination / 'originals').exists()
    assert not (destination / 'private').exists()
    for path in destination.rglob('*'):
        if path.is_file():
            blob = path.read_bytes()
            for marker in (builder.PRIVATE_MARKER, builder.REDACTION_MARKER, builder.METADATA_MARKER, builder.UNLINKED_MARKER):
                assert marker.encode() not in blob
    assert source_before == {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    assert captured['image_placements']


def test_shared_ids_and_references_remain_valid_after_roundtrip(case, builder):
    data = engine.load_engagement(case[0] / 'projects/es/engagement.yaml')
    assert not workflows.structure_errors(data)
    identities = [row['uid'] for key in ('findings', 'assets', 'evidence', 'coverage', 'root_cause_groups') for row in data[key]]
    assert len(identities) == len(set(identities))
    assert all(row['uid'] == builder.uid(row['id']) for row in data['findings'])
    original = deepcopy(data)
    workflows.normalize(data)
    assert data == original


def test_builder_refuses_to_overwrite_existing_case(case, builder):
    with pytest.raises(FileExistsError):
        builder.build_case(case[0])
