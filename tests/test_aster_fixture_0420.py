"""Real Aster inputs retain every relationship and exclude private HTTP originals."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re

import engine
import finding_instances
import http_evidence
import publication
import pytest
import workflows

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def builder():
    spec=importlib.util.spec_from_file_location('aster_fixture_test',ROOT/'scripts/build-aster-case.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.fixture(scope='module')
def case(builder,tmp_path_factory):
    output=tmp_path_factory.mktemp('aster')/'case'
    return output,builder.build_case(output)


def test_trilingual_feature_inventory_and_independent_closure(case):
    root,manifest=case
    docs={lang:engine.load_engagement(root/'projects'/lang/'engagement.yaml') for lang in ('es','en','pt')}
    for lang,doc in docs.items():
        assert not workflows.structure_errors(doc)
        assert len(doc['findings'])==78 and len(doc['assets'])==36 and len(doc['evidence'])==84
        assert len(doc['test_cases'])==114 and len(doc['attack_paths'])==3 and len(doc['http_evidence'])==8
        assert {row['specialty'] for row in doc['test_cases']}=={'api','web','ad','cloud','mobile','ai','custom'}
        assert {row['status'] for row in doc['test_cases']}=={'pending','passed','failed','blocked','not_applicable'}
        summary=finding_instances.summary(doc['findings'][0])
        assert summary['total']==18 and summary['status']=='in_progress'
        assert summary['counts']['verified_fixed']==15 and summary['counts']['open']==2 and summary['counts']['blocked']==1
        assert len(doc['review_exchange']['packages'])==1
        assert doc['client_profile']['delivery']['language']==lang
        assert not [issue for issue in manifest['projects'][lang]['preflight_issues'] if issue['level']=='error']
        assert not manifest['projects'][lang]['validation_warnings']
        for path in doc['attack_paths']:
            assert {edge['state'] for edge in path['edges']}=={'observed','inferred','blocked'}
    for lang in ('en','pt'):
        for key in ('findings','assets','evidence','test_cases','attack_paths','http_evidence'):
            assert [row['uid'] for row in docs['es'][key]]==[row['uid'] for row in docs[lang][key]]
        assert docs['es']['meta']['report_title']!=docs[lang]['meta']['report_title']
        assert docs['es']['findings'][0]['description_md']!=docs[lang]['findings'][0]['description_md']
        assert docs['es']['test_cases'][0]['observed']!=docs[lang]['test_cases'][0]['observed']


def test_authored_rows_and_bank_scope_are_new_and_complete(case,builder):
    for lang in ('es','en','pt'):
        doc=engine.load_engagement(case[0]/'projects'/lang/'engagement.yaml')
        serialized=json.dumps(doc,ensure_ascii=False)
        assert not re.search('boreal|BOREAL|BRL-',serialized)
        assert 'aster.example' in serialized and 'ASTER-FINANCIAL-GROUP' in serialized
        for n,spec in enumerate(builder.LONG_TABLES,1):
            finding=next(row for row in doc['findings'] if row['id']==spec['finding'])
            actual=re.findall(fr'AST-T{n:02d}-R\d{{3}}',json.dumps(finding[spec['field']]))
            expected=[f'AST-T{n:02d}-R{index:03d}' for index in range(1,spec['rows']+1)]
            assert actual==expected
            assert all(serialized.count(token)==1 for token in expected)
        assert sum(spec['rows'] for spec in builder.LONG_TABLES)==578


def test_publication_uses_reviewed_http_and_no_private_canary(case,builder,tmp_path):
    for lang in ('es','en','pt'):
        source=case[0]/'projects'/lang
        original=engine.load_engagement(source/'engagement.yaml')
        before={p.relative_to(source).as_posix():sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        assert builder.HTTP_PRIVATE_MARKER in json.dumps(original['http_evidence'])
        output=tmp_path/lang
        publication.snapshot(source,output)
        public=engine.load_engagement(output/'engagement.yaml')
        assert not public.get('http_evidence') and len(public['http_evidence_refs'])==8
        assert sum(row['published'] for row in public['http_evidence_refs'])==7
        assert not public.get('capture_inbox') and not public.get('review_exchange') and not public.get('client_profile')
        assert not workflows.structure_errors(public)
        for path in output.rglob('*'):
            if path.is_file():
                assert not any(marker.encode() in path.read_bytes() for marker in (builder.PRIVATE_MARKER,builder.HTTP_PRIVATE_MARKER,builder.METADATA_MARKER,builder.REDACTION_MARKER)),path
        assert before=={p.relative_to(source).as_posix():sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}


def test_http_copies_keep_separate_hashes_and_missing_response(case):
    for lang in ('es','en','pt'):
        doc=engine.load_engagement(case[0]/'projects'/lang/'engagement.yaml')
        http_evidence.validate_rows(doc)
        for row in doc['http_evidence']:
            assert row['sha256']==http_evidence.digest(row['original'])
            if row['publication']:
                values={key:row['publication'][key] for key in ('caption','request_text','response_text')}
                assert row['publication']['reviewed_sha256']==http_evidence.digest(dict(original_sha256=row['sha256'],**values))
        assert doc['http_evidence'][5]['original']['response']['body_encoding']=='base64'
        assert doc['http_evidence'][6]['original']['response'] is None
        assert doc['http_evidence'][7]['publication'] is None


def test_manifest_binds_inputs_without_creating_reports(case):
    output,manifest=case
    assert manifest['reports_generated_by_builder'] is False and manifest['network_to_scenario_targets'] is False
    for name,row in manifest['files'].items():
        blob=(output/name).read_bytes()
        assert len(blob)==row['bytes'] and sha256(blob).hexdigest()==row['sha256']
        assert Path(name).suffix not in ('.pdf','.docx','.html')
    assert {row['format'] for row in manifest['import_previews'].values()}=={'csv','burp','nmap','nuclei','sarif'}


def test_builder_factories_do_not_share_mutable_language_state(builder):
    first,_=builder.make_project('es');before=deepcopy(first)
    second,_=builder.make_project('en')
    second['findings'][0]['instances'][0]['owner']='Only this language'
    assert first==before
