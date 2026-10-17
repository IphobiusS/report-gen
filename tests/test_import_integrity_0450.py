"""Audit regressions: imported text/URLs and strict CVSS metric boundaries."""
import base64
from copy import deepcopy
import json
from io import BytesIO
import unicodedata

import pytest

import app as api
import cvss
import finding_imports
import http_evidence
import workflows
from _support import auth_client
from storage import revision
from wizard import dump_yaml


def project():
    return workflows.normalize({'meta': {'report_title': 'Synthetic intake', 'theme': 'serio', 'lang': 'en'},
                                'findings': [], 'report': {'sections': []}})


def burp(encoding):
    return ('<?xml version="1.0" encoding="' + encoding + '"?><issues><issue>'
            '<name>Sesión de São Paulo</name><severity>Low</severity>'
            '<host>https://example.test</host><path>/sesión</path>'
            '<issueDetail>&lt;p&gt;Revisión autorizada&lt;/p&gt;</issueDetail>'
            '</issue></issues>')


@pytest.mark.parametrize('encoding', ['ISO-8859-1', 'windows-1252', 'UTF-16'])
@pytest.mark.parametrize('original_bytes', [False, True])
def test_burp_refuses_encoding_reinterpretation_atomically(encoding, original_bytes):
    data = project()
    before = deepcopy(data)
    text = burp(encoding)
    body = dict(format='burp', text=text, selected=[0])
    if original_bytes:
        body['bytes_base64'] = base64.b64encode(text.encode('utf-8')).decode('ascii')
    with pytest.raises(ValueError, match='UTF-8'):
        finding_imports.apply(body, data)
    assert data == before


@pytest.mark.parametrize('encoding', ['UTF-8', 'utf8'])
def test_burp_preserves_supported_unicode(encoding):
    out, count = finding_imports.apply(dict(format='burp', text=burp(encoding), selected=[0]), project())
    assert count == 1
    assert out['findings'][0]['title'] == 'Sesión de São Paulo'
    assert out['findings'][0]['affected'] == 'https://example.test/sesión'
    assert out['findings'][0]['description_md'] == 'Revisión autorizada'


@pytest.mark.parametrize('kind', ['json', 'xml'])
def test_zap_reference_urls_are_exact_not_markdown_escaped(kind):
    from xml.sax.saxutils import escape
    first = 'https://example.test/a_b?first=1&second=2#part-3'
    second = 'https://example.test/CVE-2026-1234'
    third = 'https://example.test/plain'
    markup = ('<p><a href="' + first.replace('&', '&amp;') + '">Advisory</a></p>'
              '<p>' + second + '</p><p>' + third + '</p>'
              '<p><a href="javascript:alert(1)">ignored</a></p>'
              '<script>https://example.test/script-must-not-be-a-reference</script>')
    alert = dict(pluginid='1', name='Synthetic ZAP finding', riskcode='1', reference=markup,
                 instances=[{'uri': 'https://example.test/'}])
    if kind == 'json':
        raw = json.dumps({'site': [{'@name': 'https://example.test/', 'alerts': [alert]}]})
    else:
        raw = ('<OWASPZAPReport><site name="https://example.test/"><alerts><alertitem>'
               '<pluginid>1</pluginid><name>Synthetic ZAP finding</name><riskcode>1</riskcode>'
               '<reference>' + escape(markup) + '</reference><instances><instance>'
               '<uri>https://example.test/</uri></instance></instances></alertitem></alerts></site></OWASPZAPReport>')
    data, _ = finding_imports.apply(dict(format='zap', text=raw, selected=[0]), project())
    assert data['findings'][0]['references'] == [first, second, third]


@pytest.mark.parametrize('key,value', [('AV', 'NA'), ('AC', 'LH'), ('PR', 'NL'), ('UI', 'NR'),
                                      ('S', 'UC'), ('C', 'HL'), ('I', 'LN'), ('A', 'HLN')])
def test_cvss_rejects_multicharacter_metric_values_in_library_and_api(key, value):
    metrics = {'AV': 'N', 'AC': 'L', 'PR': 'N', 'UI': 'N', 'S': 'U', 'C': 'H', 'I': 'H', 'A': 'H', key: value}
    with pytest.raises(ValueError):
        cvss.compute(metrics)
    response = auth_client(api.app).post('/api/cvss', json={'version': '3.1', 'metrics': metrics})
    assert response.status_code == 400
    assert 'score' not in (response.get_json() or {})


@pytest.mark.parametrize('declared_form,uploaded_form', [('NFC', 'NFD'), ('NFD', 'NFC')])
def test_annex_upload_matches_declared_unicode_identity(tmp_path, monkeypatch, declared_form, uploaded_form):
    monkeypatch.setattr(api, 'PROJECTS', tmp_path)
    directory = tmp_path / 'case'
    directory.mkdir()
    data = project()
    declared = unicodedata.normalize(declared_form, 'Evaluación.txt')
    uploaded = unicodedata.normalize(uploaded_form, 'Evaluación.txt')
    data['attachments'] = [dict(uid=workflows.new_uid(), name=declared,
                                include=False, reviewed=False, required=True)]
    dump_yaml(data, directory / 'engagement.yaml')
    client = auth_client(api.app)
    response = client.post('/api/projects/case/attachments/upload',
        data={'file': (BytesIO(b'Synthetic annex'), uploaded)},
        headers={'If-Match': revision(directory / 'engagement.yaml')}, content_type='multipart/form-data')
    assert response.status_code == 200, response.get_data(as_text=True)
    row, = response.json['data']['attachments']
    assert row['uid'] == data['attachments'][0]['uid'] and row['name'] == declared and row['required']
    assert row['include'] is row['reviewed'] is False
    before = (directory / 'engagement.yaml').read_bytes()
    duplicate = client.post('/api/projects/case/attachments/upload',
        data={'file': (BytesIO(b'Must not replace'), uploaded)},
        headers={'If-Match': revision(directory / 'engagement.yaml')}, content_type='multipart/form-data')
    assert duplicate.status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert (directory / row['member']).read_bytes() == b'Synthetic annex'


def test_http_automatic_title_respects_utf8_budget_without_truncating_evidence():
    url = 'https://example.test/' + 'evaluación-' * 100
    records = [dict(original=dict(request=dict(method='GET', url=url)))]
    before = deepcopy(records)
    data, _ = http_evidence.add(project(), records)
    row, = data['http_evidence']
    assert records == before and len(row['title'].encode('utf-8')) <= 500
    assert ('GET ' + url).startswith(row['title'])
    assert row['original']['request']['url'] == url
    assert row['sha256'] == http_evidence.digest(row['original'])


@pytest.mark.parametrize('status', [False, 0.0])
def test_har_status_must_be_integer_even_when_response_absent(status):
    value = dict(log=dict(entries=[dict(request=dict(method='GET', url='https://example.test/'),
                                      response=dict(status=status, content={}))]))
    with pytest.raises(ValueError):
        http_evidence.from_har(value)
    value['log']['entries'][0]['response']['status'] = 0
    assert http_evidence.from_har(value)[0]['original']['response'] is None
