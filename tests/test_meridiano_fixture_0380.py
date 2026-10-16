"""Contracts of the substantial synthetic case, independent of its report outputs."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path

import engine
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
