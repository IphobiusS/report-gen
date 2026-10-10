from copy import deepcopy
from io import BytesIO
from pathlib import Path
import json
import time
import zipfile

import pytest
from PIL import Image
import app as api
import delivery
import finding_imports as intake
import project_history as history
import report_compare
import validate
import workflows
from export_jobs import ExportQueue
from version import __version__
from wizard import dump_yaml
from _support import auth_client

CSV = 'title,severity,affected,description\nCookie policy,low,https://example.test,Original description\n'
BURP = '''<?xml version="1.0"?><!DOCTYPE issues [<!ELEMENT issues (issue*)>]>
<issues><issue><serialNumber>102</serialNumber><name>Reflected input</name><severity>High</severity>
<confidence>Tentative</confidence><host ip="192.0.2.1">https://example.test</host><path>/query</path>
<issueDetail><![CDATA[<p>First paragraph</p><p>&lt;svg onload=alert(1)&gt;</p>]]></issueDetail>
<requestresponse><request base64="true">R0VUIC8gSFRUUC8xLjENCg0K</request><response>HTTP/1.1 200 OK</response></requestresponse>
</issue></issues>'''


def minimal():
    return workflows.normalize({'meta': {'report_title': 'Prueba / Test', 'theme': 'serio', 'lang': 'en'},
                                'findings': [], 'report': {'sections': []}})


@pytest.fixture
def client(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    d = projects / 'test'; d.mkdir(); dump_yaml(minimal(), d / 'engagement.yaml')
    q = ExportQueue(timeout=90)
    monkeypatch.setitem(api.app.extensions, 'export_queue', q)
    yield auth_client(api.app), d, q
    q.close()


def wait_job(queue, owner, key):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        status = queue.status(owner, key)
        if status['stage'] in ('done', 'error', 'cancelled'): return status
        time.sleep(.05)
    pytest.fail('Export did not terminate')


def test_version_is_shared(client):
    c, _, _ = client
    assert c.get('/api/session').json['version'] == delivery.VERSION == __version__
    assert 'version = "0.16.0"' not in (Path(__file__).parents[1] / 'pyproject.toml').read_text()


@pytest.mark.parametrize('delimiter', [',', ';', '\t'])
def test_csv_delimiters_multiline_and_bom(delimiter):
    raw = '\ufefftitle,severity,description\n"A",high,"line1\nline2"'.replace(',', delimiter)
    preview = intake.preview(dict(format='csv', text=raw), minimal())
    assert preview['rows'][0]['finding']['description_md'] == 'line1\nline2'
    assert not preview['rows'][0]['errors']


def test_mapping_and_pending_origin():
    data = minimal()
    body = dict(format='csv', text='Mi título;Riesgo\nA;Alta', mapping={'title': 'Mi título', 'severity': 'Riesgo'}, selected=[0])
    out, count = intake.apply(body, data)
    assert count == 1 and not data['findings']
    f = out['findings'][0]
    assert f['severity'] == 'high' and f['status'] == 'open' and f['verification'] == 'unverified'
    assert f['import_source']['reviewed'] is False
    assert len(f['import_source']['file_sha256']) == 64
    assert not validate.structure_issues(out)
    assert any(i['level'] == 'error' and 'importación' in i['message'] for i in workflows.review(out, Path('.')))
    f['import_source']['reviewed'] = True
    assert not any(i['level'] == 'error' for i in workflows.review(out, Path('.')))


def test_dedup_same_file_and_edited_import():
    body = dict(format='csv', text=CSV, selected=[0])
    data, _ = intake.apply(body, minimal())
    data['findings'][0]['title'] = 'Manually edited'
    assert intake.preview(body, data)['rows'][0]['duplicate']
    with pytest.raises(ValueError, match='duplicadas'): intake.apply(body, data)
    raw = CSV + CSV.splitlines()[1]
    rows = intake.preview(dict(format='csv', text=raw), minimal())['rows']
    assert not rows[0]['duplicate'] and rows[1]['duplicate']


def test_burp_dtd_http_and_html_payload():
    rows = intake.preview(dict(format='burp', text=BURP), minimal())['rows']
    f = rows[0]['finding']
    assert f['affected'] == 'https://example.test/query'
    assert f['import_source']['external_id'] == '102'
    assert f['import_source']['confidence'] == 'Tentative'
    assert f['walkthrough'][0]['command'] == 'GET / HTTP/1.1\r\n\r\n'
    assert 'svg onload' in f['description_md'] and '<svg' not in f['description_md']
    assert '\n' in f['description_md']


@pytest.mark.parametrize('raw', [
    '<!DOCTYPE issues SYSTEM "file:///etc/passwd"><issues/>',
    '<!DOCTYPE issues [<!ENTITY x SYSTEM "file:///etc/passwd">]><issues>&x;</issues>',
    '<!DOCTYPE issues [<!ENTITY % x "expansion">]><issues/>', '<items/>', '<issues>',
    '<issues><issue><requestresponse><request base64="true">%%%%</request></requestresponse></issue></issues>',
])
def test_burp_rejects_unsafe_or_invalid_xml(raw):
    with pytest.raises(ValueError): intake.preview(dict(format='burp', text=raw), minimal())


@pytest.mark.parametrize('body', [
    {'format': []}, {'format': 'csv', 'text': 'title,title\na,b'},
    {'format': 'csv', 'text': 'title,severity\na,high,extra'},
    {'format': 'csv', 'text': CSV, 'mapping': {'title': 'missing'}},
    {'format': 'csv', 'text': CSV, 'mapping': {'title': 'title', 'severity': 'title'}},
    {'format': 'csv', 'text': CSV, 'mapping': []},
    {'format': 'csv', 'text': 'title,severity\n' + 'a,high\n' * 501},
    {'format': 'csv', 'text': 'a' * (intake.MAX_BYTES + 1)},
])
def test_bad_imports_are_bounded(body):
    with pytest.raises(ValueError): intake.preview(body, minimal())


@pytest.mark.parametrize('selected', [[], [True], [-1], [100], [0, 0], '0'])
def test_bad_selections(selected):
    with pytest.raises(ValueError): intake.apply(dict(format='csv', text=CSV, selected=selected), minimal())


def test_unknown_severity_and_cvss_are_not_silently_fixed():
    body = dict(format='csv', text='title,severity,cvss_vector\nA,urgent,bad\nB,low,CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H')
    rows = intake.preview(body, minimal())['rows']
    assert len(rows[0]['errors']) == 2 and len(rows[1]['errors']) == 1


def test_preview_no_mutation_apply_atomic_conflict(client):
    c, d, _ = client
    before = (d / 'engagement.yaml').read_bytes()
    body = dict(format='csv', text=CSV, selected=[0])
    tag = c.get('/api/projects/test').headers['ETag']
    assert c.post('/api/projects/test/intake/preview', json=body, headers={'If-Match': tag}).status_code == 200
    assert (d / 'engagement.yaml').read_bytes() == before
    assert c.post('/api/projects/test/intake/apply', json=body).status_code == 428
    assert c.post('/api/projects/test/intake/apply', json=body, headers={'If-Match': 'stale'}).status_code == 409
    r = c.post('/api/projects/test/intake/apply', json=body, headers={'If-Match': tag})
    assert r.status_code == 200 and r.json['imported'] == 1
    assert len(c.get('/api/projects/test/history').json) >= 2
    tag = r.headers['ETag']
    r = c.post('/api/projects/test/jobs', json=dict(kind='export', formats=['md'], label='x'), headers={'If-Match': tag})
    assert r.status_code == 422 and 'import awaiting review' in r.json['error']


def test_real_queue_snapshot_delivery_and_owner(client):
    c, d, q = client
    tag = c.get('/api/projects/test').headers['ETag']
    body = dict(kind='delivery', formats=['docx', 'md'], label='Release', acknowledge_warnings=True)
    r = c.post('/api/projects/test/jobs', json=body, headers={'If-Match': tag})
    assert r.status_code == 202
    key = r.json['id']; token = c.get('/api/session').json['csrf']
    edited = minimal(); edited['meta']['report_title'] = 'Changed after queueing'; dump_yaml(edited, d / 'engagement.yaml')
    assert wait_job(q, token, key)['stage'] == 'done'
    other = auth_client(api.app)
    assert other.get('/api/jobs/' + key).status_code == 404
    assert other.get('/api/jobs/' + key + '/verification').status_code == 404
    verification=c.get('/api/jobs/' + key + '/verification')
    assert verification.status_code==200
    assert verification.json['source_revision']==tag.strip('"')
    result = c.get('/api/jobs/' + key + '/download')
    with zipfile.ZipFile(BytesIO(result.data)) as z:
        manifest = json.loads(z.read('verificacion.json'))
        assert manifest['tool_version'] == __version__ and manifest['source_revision'] == tag.strip('"')
        with zipfile.ZipFile(BytesIO(z.read('markdown.zip'))) as md:
            assert b'Changed after queueing' not in md.read('report.md')
            assert 'Prueba / Test' in md.read('report.md').decode()
    # Private snapshot cleanup has completed by the time the worker lock is available.
    assert list((q.root / key).iterdir()) == [q.root / key / 'result']
    assert c.delete('/api/jobs/' + key).status_code == 200
    assert not (q.root / key).exists()


def test_real_running_cancel_and_cleanup(client):
    c, _, q = client
    tag = c.get('/api/projects/test').headers['ETag']
    r = c.post('/api/projects/test/jobs', json=dict(kind='export', formats=['pdf'], label='Cancel'), headers={'If-Match': tag})
    key, token = r.json['id'], c.get('/api/session').json['csrf']
    deadline = time.monotonic() + 10
    while q.jobs[key]['process'] is None and time.monotonic() < deadline: time.sleep(.02)
    process = q.jobs[key]['process']; assert process is not None
    assert c.post('/api/jobs/' + key + '/cancel', json={}).status_code == 200
    assert wait_job(q, token, key)['stage'] == 'cancelled'
    assert process.poll() is not None
    assert c.get('/api/jobs/' + key + '/download').status_code == 422
    assert not list((q.root / key).iterdir())


@pytest.mark.parametrize('body', [dict(kind=[], formats=['pdf'], label='x'), dict(kind='export', formats=[{}], label='x'),
    dict(kind='export', formats=['pdf', 'docx'], label='x'), dict(kind='delivery', formats=['pdf', 'pdf'], label='x'),
    dict(kind='export', formats=['md'], label=[]), dict(kind='export', formats=['md'], label='x', acknowledge_warnings=1)])
def test_invalid_jobs(client, body):
    c, _, _ = client
    tag = c.get('/api/projects/test').headers['ETag']
    assert c.post('/api/projects/test/jobs', json=body, headers={'If-Match': tag}).status_code == 422


def test_visual_diff_escapes_and_keeps_images(client):
    c, d, _ = client
    data = minimal(); data['findings'] = [dict(uid=workflows.new_uid(), id='F1', title='A', severity='high', mode='vuln', walkthrough=[{'figure':{'src':'img/proof.png','caption':'Proof'}}])]
    dump_yaml(data, d / 'engagement.yaml')
    (d / 'img').mkdir()
    image = d / 'img/proof.png'; Image.new('RGB', (10, 10), 'red').save(image)
    old = history.checkpoint(d, 'First', 'delivered', True)
    data['findings'][0].update(severity='low', description_md='<script>alert(1)</script>')
    dump_yaml(data, d / 'engagement.yaml'); Image.new('RGB', (10, 10), 'blue').save(image)
    new = history.checkpoint(d, 'Second', 'retest', True)
    r = c.get('/api/projects/test/history/' + old['id'] + '/visual?to=' + new['id'] + '&lang=en&download=1')
    text = r.data.decode()
    assert r.status_code == 200 and 'attachment;' in r.headers['Content-Disposition']
    assert '<script>' not in text and '&lt;script&gt;' in text
    assert '<del>High</del>' in text and '<ins>Low</ins>' in text
    assert text.count('src="data:image/png;') == 1 and 'SHA-256' in text
    assert '1 modified' in text and 'font-src data:' in r.headers['Content-Security-Policy']
    assert 'Retirado significa' not in text


def test_long_diff_bounded_and_full():
    a, b = report_compare.diff('old ' * 20000, 'new ' * 20000)
    assert a.count('old ') == b.count('new ') == 20000


def test_reordering_is_not_delete():
    data = minimal(); data['findings'] = [dict(uid=workflows.new_uid(), id='F1', title='First'), dict(uid=workflows.new_uid(), id='F2', title='Second')]
    other = deepcopy(data); other['findings'].reverse()
    markup = report_compare.render(data, other, {}, {}, 'old', 'new', 'en')
    assert '0 added · 0 removed · 0 modified' in markup
