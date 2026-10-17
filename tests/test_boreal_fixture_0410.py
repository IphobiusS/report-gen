"""Boreal source relationships, translations and long-row contracts are real inputs."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re

import engine
import publication
import pytest
import workflows

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def builder():
    spec = importlib.util.spec_from_file_location('boreal_fixture_test', ROOT/'scripts/build-boreal-case.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def case(builder, tmp_path_factory):
    output = tmp_path_factory.mktemp('boreal')/'case'
    return output, builder.build_case(output)


def test_full_translations_keep_stable_relationships_and_localized_narrative(case):
    root, manifest = case
    docs = {lang:engine.load_engagement(root/'projects'/lang/'engagement.yaml') for lang in ('es','en','pt')}
    for lang, doc in docs.items():
        assert not workflows.structure_errors(doc)
        assert len(doc['findings']) == 78
        assert len(doc['assets']) == 36
        assert len(doc['coverage']) == 216
        assert len(doc['evidence']) == 84
        assert sum(len(f.get('retests', [])) for f in doc['findings']) == 36
        assert len({f['uid'] for f in doc['findings']}) == 78
        for row in doc['findings']:
            assert set(row['asset_uids']) <= {a['uid'] for a in doc['assets']}
            assert set(row['evidence_uids']) <= {e['uid'] for e in doc['evidence']}
        issues = manifest['projects'][lang]['preflight_issues']
        assert not [row for row in issues if row['level']=='error']
        assert len(issues) == 73  # 72 deliberate coverage warnings + private annex.
        assert not manifest['projects'][lang]['validation_warnings']
    for lang in ('en','pt'):
        for source, translated in zip(docs['es']['findings'], docs[lang]['findings']):
            for key in ('id','uid','mode','asset_uids','evidence_uids','root_cause_uid','cvss_vector'):
                assert source.get(key) == translated.get(key)
            assert source['title'] != translated['title']
            if source['mode'] == 'vuln':
                for key in ('description_md','impact_md','remediation_md'):
                    assert source[key] != translated[key]
            else:
                for original, target in zip(source['phases'], translated['phases']):
                    assert original['steps'][0]['text_md'] != target['steps'][0]['text_md']
        assert docs['es']['report']['sections'][3]['summary'] != docs[lang]['report']['sections'][3]['summary']


def test_all_long_tables_have_unique_ordered_rows_in_the_intended_finding_field(case, builder):
    for lang in ('es','en','pt'):
        doc = engine.load_engagement(case[0]/'projects'/lang/'engagement.yaml')
        full = json.dumps(doc, ensure_ascii=False)
        for n,spec in enumerate(builder.LONG_TABLES,1):
            row = next(f for f in doc['findings'] if f['id']==spec['finding'])
            actual = re.findall(fr'BRL-T{n:02d}-R\d{{3}}', json.dumps(row[spec['field']]))
            expected = [f'BRL-T{n:02d}-R{i:03d}' for i in range(1,spec['rows']+1)]
            assert actual == expected
            assert all(full.count(token) == 1 for token in expected)
            assert builder.LONG_URL in json.dumps(row[spec['field']], ensure_ascii=False)
        assert sum(spec['rows'] for spec in builder.LONG_TABLES) == 578


def test_native_publication_removes_control_markers_and_preserves_source(case, builder, tmp_path):
    for lang in ('es','en','pt'):
        source = case[0]/'projects'/lang
        before = {p.relative_to(source).as_posix():sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        output = tmp_path/lang
        receipt = publication.snapshot(source, output)
        public = engine.load_engagement(output/'engagement.yaml')
        assert not public.get('capture_inbox')
        assert not (output/'private').exists()
        assert not (output/'originals').exists()
        for path in output.rglob('*'):
            if path.is_file():
                assert not any(marker.encode() in path.read_bytes() for marker in (builder.PRIVATE_MARKER,builder.REDACTION_MARKER,builder.METADATA_MARKER))
        assert receipt['image_placements']
        assert before == {p.relative_to(source).as_posix():sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}


def test_manifest_binds_sources_without_fabricating_report_outputs(case):
    root, manifest = case
    assert manifest['reports_generated_by_builder'] is False
    assert manifest['network_to_scenario_targets'] is False
    assert manifest['prose_languages'] == ['es','en','pt']
    for name,row in manifest['files'].items():
        data = (root/name).read_bytes()
        assert len(data) == row['bytes'] and sha256(data).hexdigest() == row['sha256']
        assert Path(name).suffix not in ('.pdf','.docx','.html')
    assert {r['format'] for r in manifest['import_previews'].values()} == {'csv','burp','nuclei','nmap','sarif'}
    assert all(r['scope']=='inert_parser_input_not_report_narrative' for r in manifest['import_previews'].values())


def test_incomplete_localization_fails_before_output(builder, monkeypatch, tmp_path):
    content = deepcopy(builder.load_content('en'))
    content['domains'][4].pop('process')
    folder = tmp_path/'content'
    folder.mkdir()
    (folder/'en.json').write_text(json.dumps(content))
    monkeypatch.setattr(builder,'CONTENT',folder)
    target = tmp_path/'source'
    with pytest.raises(ValueError,match='Incomplete Boreal domain'):
        builder.build_case(target,('en',))
    assert not target.exists()


def test_acceptance_rejects_missing_and_duplicate_authored_rows(case):
    spec = importlib.util.spec_from_file_location('boreal_acceptance_test', ROOT/'scripts/audit-boreal-0410.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    doc = engine.load_engagement(case[0]/'projects/en/engagement.yaml')
    assert runner.fixture_contract(doc,'en')['long_table_rows'] == 578
    for replacement in ('', 'BRL-T01-R001 BRL-T01-R001'):
        altered = deepcopy(doc)
        altered['findings'][0]['description_md'] = altered['findings'][0]['description_md'].replace('BRL-T01-R001',replacement)
        with pytest.raises(ValueError,match='lost, reordered or duplicated'):
            runner.fixture_contract(altered,'en')
