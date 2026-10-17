"""Acceptance-runner contracts without launching the expensive export matrix."""
from copy import deepcopy
from io import BytesIO
import importlib.util
from pathlib import Path
import zipfile

import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('aster_acceptance_contract_test',ROOT/'scripts/audit-aster-0420.py')
AUDIT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(AUDIT)


@pytest.fixture(scope='module')
def source():
    return AUDIT.BUILDER.make_project('es')[0]


def test_complete_synthetic_contract_and_old_boreal_default_preserved(source):
    value=AUDIT.fixture_contract(source,'es')
    assert value['long_table_rows']==578 and value['test_cases']==114 and value['instances']['total']==18
    assert len(value['specialties'])==7 and value['reviewed_http_pairs']==7
    assert AUDIT.RUNNER.inspect_long_tables.__kwdefaults__['token_prefix']=='BRL'
    assert AUDIT.RUNNER.inspect_long_tables.__kwdefaults__['builder'].CASE!=AUDIT.BUILDER.CASE


@pytest.mark.parametrize('change',[
    lambda d:d['findings'][0]['instances'].pop(),
    lambda d:d['test_cases'][1].update(test_id=d['test_cases'][0]['test_id']),
    lambda d:d['test_cases'][-1].update(specialty='api'),
    lambda d:d['attack_paths'][0]['edges'][1].update(state='observed'),
    lambda d:d['http_evidence'][-1].update(publication={}),
    lambda d:d.pop('client_profile'),
    lambda d:d['review_exchange'].update(accepted=[]),
])
def test_runner_rejects_weakened_fixture_contract(source,change):
    data=deepcopy(source);change(data)
    with pytest.raises(ValueError):AUDIT.fixture_contract(data,'es')


def archive(name,blob):
    output=BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(name,blob)
    return output.getvalue()


def test_recursive_archive_inspection_detects_private_canary_and_source_paths():
    nested=archive('informe.docx',archive('word/document.xml',b'PRIVATE_CANARY'))
    with pytest.raises(ValueError,match='Private fixture'):AUDIT.inspect_archive(nested,['PRIVATE_CANARY'],'delivery.zip')
    with pytest.raises(ValueError,match='Private project'):AUDIT.inspect_archive(archive('originals/proof.png',b'pixels'),[],'delivery.zip')
    with pytest.raises(ValueError,match='Unexpected archive'):AUDIT.inspect_archive(archive('../escape',b'text'),[],'delivery.zip')
    result=AUDIT.inspect_archive(archive('markdown.zip',archive('report.md',b'Allowed reviewed text')),['PRIVATE_CANARY'],'delivery.zip')
    assert result['recursive_members']==2


def test_image_fingerprint_ignores_container_metadata_but_not_pixels():
    from PIL import PngImagePlugin
    image=Image.new('RGB',(4,4),'white');a=BytesIO();b=BytesIO();meta=PngImagePlugin.PngInfo();meta.add_text('private','PRIVATE_CANARY')
    image.save(a,format='PNG');image.save(b,format='PNG',pnginfo=meta)
    assert AUDIT.image_fingerprint(a.getvalue())==AUDIT.image_fingerprint(b.getvalue())
    with pytest.raises(ValueError):AUDIT.reject_private(b.getvalue(),['PRIVATE_CANARY'],'image')
    image.putpixel((0,0),(0,0,0));c=BytesIO();image.save(c,format='PNG')
    assert AUDIT.image_fingerprint(a.getvalue())!=AUDIT.image_fingerprint(c.getvalue())


def test_private_markers_cover_review_profile_and_encoded_http(source):
    tokens=AUDIT.private_tokens(source)
    assert source['client_profile']['uid'] in tokens
    assert source['review_exchange']['packages'][0]['uid'] in tokens
    import base64
    assert base64.b64encode(AUDIT.BUILDER.HTTP_PRIVATE_MARKER.encode()).decode() in tokens
    with pytest.raises(ValueError):AUDIT.reject_private(AUDIT.BUILDER.HTTP_PRIVATE_MARKER.encode('utf-16-le'),tokens,'encoded')


def test_semantic_markdown_checks_decode_generated_escapes():
    from exporters.markdown import parse_exported
    from workflows import md_text
    value='ASTER-TC-001 / https://api.aster.example/v2/accounts/SYNTH-001'
    escaped=md_text(value)
    assert 'ASTER-TC-001' not in escaped
    assert AUDIT.compact(parse_exported(escaped).text_content())==AUDIT.compact(value)
