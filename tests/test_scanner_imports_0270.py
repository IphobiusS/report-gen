"""Scanner intake: typed observations, review gating, budgets and atomic API writes."""
from copy import deepcopy
from hashlib import sha256
import base64
import json
from pathlib import Path

import pytest
import app as api
import finding_imports as intake
import scanner_imports
import validate
import workflows
from wizard import dump_yaml
from _support import auth_client

NUCLEI = dict(
    **{'template-id': 'example-header', 'matched-at': 'https://example.test/', 'matcher-name': 'header',
       'template-path': '/never/read/this/path.yaml', 'timestamp': '2026-10-10T10:00:00Z', 'type': 'http'},
    info=dict(name='Header candidate', severity='low', description='Unverified scanner match',
              reference=['https://example.test/advisory'], classification={'cwe-id': ['CWE-200']}),
    request='GET / HTTP/1.1\r\nHost: example.test\r\n\r\n', response='HTTP/1.1 200 OK\r\n\r\n')
HOST = '''<host><status state="up"/><address addr="192.0.2.1" addrtype="ipv4"/>
<hostnames><hostname name="example.test" type="user"/></hostnames><ports>
<extraports state="closed" count="997"/>
<port protocol="tcp" portid="22"><state state="open"/><service name="ssh" product="OpenSSH" version="9.0" method="probed" conf="10"/></port>
<port protocol="tcp" portid="443"><state state="open"/><service name="http" tunnel="ssl"/><script id="ssl-cert" output="omitted"/></port>
<port protocol="udp" portid="53"><state state="open|filtered"/><service name="domain"/></port>
</ports></host>'''
NMAP = '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE nmaprun><nmaprun scanner="nmap" version="7.99" startstr="2026-10-10"><scaninfo type="syn" protocol="tcp" services="1-1000" numservices="1000"/>' + HOST + '<runstats><finished exit="success"/></runstats></nmaprun>'


def basic():
    return workflows.normalize({'meta': {'report_title': 'Test', 'theme': 'serio', 'lang': 'en'},
                                'findings': [], 'report': {'sections': []}})


def payload(kind, value=None, **extra):
    return dict(format=kind, text=value or (json.dumps(NUCLEI) if kind == 'nuclei' else NMAP), **extra)


def test_nuclei_pending_provenance_literal_http_and_no_path_access(monkeypatch):
    monkeypatch.setattr(Path, 'read_bytes', lambda self: pytest.fail('Imported paths must never be read'))
    original = basic()
    out, count = intake.apply(payload('nuclei', selected=[0]), original)
    assert count == 1 and not original['findings']
    finding = out['findings'][0]
    assert finding['verification'] == 'unverified' and finding['status'] == 'open'
    assert finding['walkthrough'][0]['command'] == NUCLEI['request']
    assert finding['import_source']['reviewed'] is False
    assert finding['import_source']['template_id'] == 'example-header'
    assert finding['import_source']['source_line'] == 1
    assert finding['import_source']['record_sha256'] == sha256(json.dumps(NUCLEI).encode()).hexdigest()
    assert not validate.structure_issues(out)
    assert any(i['level'] == 'error' and 'import awaiting review' in i['message'] for i in workflows.review(out, Path('.')))
    finding['import_source']['reviewed'] = True
    assert finding['verification'] == 'unverified'


def test_nuclei_null_optional_fields_and_unicode():
    row = deepcopy(NUCLEI)
    row['info'].update(name='Observación 漢字', reference=None, classification=None)
    result = intake.preview(payload('nuclei', json.dumps(row)), basic())
    assert result['rows'][0]['finding']['title'] == 'Observación 漢字'
    assert not result['rows'][0]['errors']


def test_nuclei_cvss_unknown_severity_and_false_matches():
    row = deepcopy(NUCLEI)
    row['info']['severity'] = 'unknown'
    assert intake.preview(payload('nuclei', json.dumps(row)), basic())['rows'][0]['errors']
    row['matcher-status'] = False
    with pytest.raises(ValueError, match='positive match'):
        intake.apply(payload('nuclei', json.dumps(row), selected=[0]), basic())


@pytest.mark.parametrize('raw', ['[]', '{}', '{"info":{}}', '{"a":1,"a":2}', '[', 'null',
                                  json.dumps({**NUCLEI, 'info': []}),
                                  json.dumps({**NUCLEI, 'request': {'path': '/etc/passwd'}}),
                                  json.dumps({**NUCLEI, 'extracted-results': [4]}),
                                  json.dumps({**NUCLEI, 'info': {**NUCLEI['info'], 'reference': ['file:///etc/passwd']}})])
def test_nuclei_invalid(raw):
    with pytest.raises(ValueError):
        intake.preview(payload('nuclei', raw), basic())


@pytest.mark.parametrize('kind', ['nuclei', 'nmap'])
def test_original_bom_hash_and_duplicate_reimport_after_edit(kind):
    body = payload(kind)
    original = b'\xef\xbb\xbf' + body['text'].encode()
    body['bytes_base64'] = base64.b64encode(original).decode()
    first = intake.preview(body, basic())
    assert first['sha256'] == sha256(original).hexdigest()
    assert first['rows'][0]['existing_duplicate'] is False
    out, _ = intake.apply(dict(body, selected=[0]), basic())
    if kind == 'nuclei':
        out['findings'][0]['title'] = 'Edited title'
    else:
        out['assets'][0]['target'] = 'Edited target'
    assert intake.preview(body, out)['rows'][0]['existing_duplicate'] is True
    with pytest.raises(ValueError):
        intake.apply(dict(body, selected=[0]), out)


def test_nmap_creates_only_inventory_and_preserves_open_filtered_distinction():
    data = basic()
    before = deepcopy(data)
    result = intake.preview(payload('nmap'), data)
    assert data == before and result['kind'] == 'inventory'
    assert result['counts'] == dict(rows=1, services=3, valid=1, duplicates=0)
    out, count = intake.apply(payload('nmap', selected=[0]), data)
    assert count == 1 and out['findings'] == [] and data == before
    assert len(out['assets']) == len(out['coverage']) == 1
    asset, coverage = out['assets'][0], out['coverage'][0]
    assert asset['target'] == '192.0.2.1' and coverage['asset_uid'] == asset['uid']
    assert coverage['status'] == 'pending'
    assert '53/udp · open|filtered' in coverage['notes']
    assert 'OpenSSH 9.0' in coverage['notes'] and '1-1000' in coverage['notes']
    assert coverage['import_source']['omitted_scripts'] == 1
    assert not validate.structure_issues(out)


def test_nmap_reuses_existing_asset_without_overwriting_authored_content():
    data = basic()
    data['assets'].append(dict(uid=workflows.new_uid(), name='Customer title', target='192.0.2.1', notes='Author notes', kind='server'))
    out, _ = intake.apply(payload('nmap', selected=[0]), data)
    assert out['assets'] == data['assets']
    assert out['coverage'][0]['asset_uid'] == data['assets'][0]['uid']


def test_nmap_multiple_selected_hosts_and_duplicate_selection_atomic():
    raw = NMAP.replace(HOST, HOST + HOST + HOST.replace('192.0.2.1', '192.0.2.2'))
    rows = intake.preview(payload('nmap', raw), basic())['rows']
    assert [r['duplicate'] for r in rows] == [False, True, False]
    out, count = intake.apply(payload('nmap', raw, selected=[1, 2]), basic())
    assert count == 2 and len(out['assets']) == 2
    data = basic()
    with pytest.raises(ValueError):
        intake.apply(payload('nmap', raw, selected=[0, 1]), data)
    assert not data['assets'] and not data['coverage']


def test_nmap_partial_scan_and_version_updates_are_distinct_observations():
    raw = NMAP.replace('<runstats><finished exit="success"/></runstats>', '')
    out, _ = intake.apply(payload('nmap', raw, selected=[0]), basic())
    assert not out['coverage'][0]['import_source']['scan_complete']
    assert 'partial coverage' in out['coverage'][0]['notes']
    out, _ = intake.apply(payload('nmap', NMAP.replace('version="9.0"', 'version="9.1"'), selected=[0]), out)
    assert len(out['assets']) == 1 and len(out['coverage']) == 2


@pytest.mark.parametrize('raw', [
    '<issues/>', '<nmaprun/>', NMAP.replace('192.0.2.1', 'invalid'),
    NMAP.replace('portid="22"', 'portid="99999"'), NMAP.replace('protocol="tcp"', 'protocol="shell"'),
    NMAP.replace('<state state="open"/>', ''),
    NMAP.replace('encoding="UTF-8"', 'encoding="ISO-8859-1"'),
    '<!DOCTYPE nmaprun SYSTEM "file:///etc/passwd"><nmaprun/>',
    '<!DOCTYPE nmaprun [<!ENTITY x SYSTEM "file:///etc/passwd">]><nmaprun>&x;</nmaprun>',
    '<!DOCTYPE nmaprun [<!ENTITY a "123"><!ENTITY b "&a;&a;">]><nmaprun>&b;</nmaprun>',
])
def test_nmap_rejects_malformed_unbounded_entities_and_external_dtd(raw):
    with pytest.raises(ValueError):
        intake.preview(payload('nmap', raw), basic())


@pytest.mark.parametrize('selected', [[], [True], [-1], [1], [0, 0], '0', None])
@pytest.mark.parametrize('kind', ['nmap', 'nuclei'])
def test_invalid_selection(kind, selected):
    with pytest.raises(ValueError):
        intake.apply(payload(kind, selected=selected), basic())


def test_import_budgets(monkeypatch):
    with pytest.raises(ValueError):
        intake.preview(payload('nuclei', '\n'.join([json.dumps(NUCLEI)] * 501)), basic())
    with pytest.raises(ValueError):
        intake.preview(payload('nmap', NMAP.replace(HOST, HOST * 501)), basic())
    with pytest.raises(ValueError):
        intake.preview(payload('nuclei', 'x' * (intake.MAX_BYTES + 1)), basic())
    monkeypatch.setattr(scanner_imports, 'MAX_PORTS', 2)
    with pytest.raises(ValueError, match='10000'):
        intake.preview(payload('nmap'), basic())


@pytest.fixture
def client(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'
    projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    directory = projects / 'test'
    directory.mkdir()
    dump_yaml(basic(), directory / 'engagement.yaml')
    return auth_client(api.app), directory


@pytest.mark.parametrize('kind', ['nmap', 'nuclei'])
def test_api_preview_revision_guard_atomic_apply_and_restore(client, kind):
    c, directory = client
    before = (directory / 'engagement.yaml').read_bytes()
    tag = c.get('/api/projects/test').headers['ETag']
    body = payload(kind, selected=[0])
    result = c.post('/api/projects/test/intake/preview', json=body, headers={'If-Match': tag})
    assert result.status_code == 200
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert c.post('/api/projects/test/intake/apply', json=body).status_code == 428
    assert c.post('/api/projects/test/intake/apply', json=body, headers={'If-Match': 'stale'}).status_code == 409
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert c.post('/api/projects/test/intake/apply', json=dict(body, selected=[0, 999]), headers={'If-Match': tag}).status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before
    result = c.post('/api/projects/test/intake/apply', json=body, headers={'If-Match': tag})
    assert result.status_code == 200, result.json
    assert result.json['import_kind'] == ('inventory' if kind == 'nmap' else 'findings')
    saved = c.get('/api/projects/test')
    assert saved.status_code == 200 and len(saved.json['coverage' if kind == 'nmap' else 'findings']) == 1
    assert len(c.get('/api/projects/test/history').json) >= 2
    assert c.post('/api/projects/test/intake/apply', json=body, headers={'If-Match': result.headers['ETag']}).status_code == 422
