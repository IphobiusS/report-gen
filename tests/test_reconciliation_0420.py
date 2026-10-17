"""Reimport must preserve analyst decisions and retain exact private observations."""
from copy import deepcopy
import json
import pytest
import finding_imports
import import_reconciliation as reconcile
import workflows
from wizard import dump_yaml

ZAP = {'@version': '2.16', 'created': '2026-10-17T10:00:00Z', 'site': [{'@name': 'https://bank.example', 'alerts': [
    {'pluginid': '10020', 'alertRef': '10020-1', 'name': 'Missing header', 'riskcode': '1', 'confidence': '2',
     'desc': '<p>Scanner description</p>', 'solution': '<p>Set the header</p>', 'cweid': '16',
     'reference': '<p>https://example.test/header</p>', 'instances': [
        {'uri': 'https://bank.example/accounts', 'method': 'GET', 'param': 'id', 'evidence': 'Missing',
         'request-header': 'GET /accounts HTTP/1.1\r\nAuthorization: private-token\r\n', 'response-header': 'HTTP/1.1 200 OK\r\n'}]}]}]}
ZAP_XML = '''<OWASPZAPReport version="2.16" created="2026-10-17T10:00:00Z"><site name="https://bank.example"><alerts><alertitem>
<pluginid>10020</pluginid><alertRef>10020-1</alertRef><name>Missing header</name><riskcode>1</riskcode><confidence>2</confidence>
<desc>&lt;p&gt;Scanner description&lt;/p&gt;</desc><solution>Set the header</solution><instances><instance><uri>https://bank.example/accounts</uri><method>GET</method><param>id</param><request-header>GET /accounts HTTP/1.1</request-header></instance></instances>
</alertitem></alerts></site></OWASPZAPReport>'''
NESSUS = '''<NessusClientData_v2><Policy><Credentials><password>never-import-credentials</password></Credentials></Policy><Report name="test"><ReportHost name="192.0.2.1"><HostProperties><tag name="HOST_END">2026-10-17</tag></HostProperties><ReportItem pluginID="10000" pluginName="Service policy" port="443" protocol="tcp" severity="2" svc_name="www" pluginFamily="General"><synopsis>Service detected</synopsis><description>Scanner description</description><solution>Review configuration</solution><plugin_output>Private banner</plugin_output><cvss3_vector>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H</cvss3_vector><cve>CVE-2026-0001</cve></ReportItem></ReportHost></Report></NessusClientData_v2>'''


def basic():
    return workflows.normalize({'meta': {'report_title': 'Review', 'theme': 'serio', 'lang': 'en'}, 'findings': [], 'report': {'sections': []}})


def body(kind='zap', value=None, **extra):
    return dict(format=kind, text=value if value is not None else json.dumps(ZAP) if kind == 'zap' else NESSUS, **extra)


def first(kind='zap'):
    return finding_imports.apply(body(kind, selected=[0]), basic())[0]


def attach(data, payload=None, **extra):
    return reconcile.apply({**(payload or body()), 'decisions': [{'index': 0, 'action': 'attach', 'finding_uid': data['findings'][0]['uid'], **extra}]}, data)


@pytest.mark.parametrize('kind,raw', [('zap', json.dumps(ZAP)), ('zap', ZAP_XML), ('nessus', NESSUS)])
def test_supported_real_report_shapes_unverified_and_literal_evidence(kind, raw):
    result = finding_imports.preview(body(kind, raw), basic())
    assert len(result['rows']) == 1 and not result['rows'][0]['errors']
    saved, _ = finding_imports.apply(body(kind, raw, selected=[0]), basic())
    finding = saved['findings'][0]
    assert finding['verification'] == 'unverified'
    assert finding['status'] == 'open'
    assert finding['import_source']['reviewed'] is False
    assert finding['walkthrough']
    assert 'never-import-credentials' not in json.dumps(saved)
    if kind == 'nessus':
        assert not finding['cvss_vector']
        assert finding['import_source']['reported_cvss3_vector'].startswith('CVSS:3.1')


def test_scanner_identity_survives_manual_title_target_and_vendor_title_changes():
    saved = first()
    saved['findings'][0].update(title='My proof', affected='Author grouping')
    changed = deepcopy(ZAP); changed['site'][0]['alerts'][0]['name'] = 'Renamed scanner rule'
    preview = reconcile.preview(body(value=json.dumps(changed)), saved)
    assert preview['rows'][0]['match'] == 'exact'
    assert preview['rows'][0]['existing_duplicate']
    assert {'title', 'affected'}.issubset({item['field'] for item in preview['rows'][0]['matches'][0]['differences']})


def test_rule_variants_methods_and_parameters_remain_distinct():
    doc = deepcopy(ZAP)
    alert = doc['site'][0]['alerts'][0]
    alert['instances'] += [{**alert['instances'][0], 'method': 'POST'}, {**alert['instances'][0], 'param': 'other'}]
    doc['site'][0]['alerts'].append({**alert, 'alertRef': '10020-2'})
    result = finding_imports.preview(body(value=json.dumps(doc)), basic())
    keys = [row['finding']['import_source']['fingerprint'] for row in result['rows']]
    assert len(set(keys)) == len(keys) == 6
    assert not any(row['duplicate'] for row in result['rows'])


def test_attach_preserves_authored_fields_cvss_status_and_retests():
    saved = first(); f = saved['findings'][0]
    f.update(title='Manual title', description_md='Analyst description', cvss=9.8, cvss_vector='analyst vector',
             status='verified_fixed', verification='confirmed', retests=[{'uid': workflows.new_uid(), 'notes': 'Human result'}])
    before = deepcopy(saved)
    out, count = attach(saved)
    assert count == 1 and saved == before
    actual = out['findings'][0]
    assert {key: value for key, value in actual.items() if key != 'import_observations'} == f
    obs = actual['import_observations'][0]
    assert 'private-token' in json.dumps(obs['snapshot'])
    assert obs['selected_fields'] == []
    assert not reconcile.structure_errors(out)


def test_explicit_copy_only_replaces_selected_fields_and_appends_steps():
    saved = first(); f = saved['findings'][0]
    f['description_md'] = 'Author description'; f['walkthrough'] = [{'lead': 'Author steps', 'command': 'manual'}]
    out, _ = attach(saved, fields=['description_md', 'walkthrough'])
    result = out['findings'][0]
    assert result['description_md'] == 'Scanner description'
    assert result['walkthrough'][0]['command'] == 'manual'
    assert len(result['walkthrough']) > 1
    assert result['import_observations'][0]['selected_fields'] == ['description_md', 'walkthrough']


def test_attach_to_instance_does_not_change_instance_state():
    saved = first(); uid = workflows.new_uid()
    saved['findings'][0]['instances'] = [{'uid': uid, 'endpoint': '/accounts', 'status': 'verified_fixed'}]
    out, _ = attach(saved, instance_uid=uid)
    assert out['findings'][0]['instances'] == saved['findings'][0]['instances']
    assert out['findings'][0]['import_observations'][0]['instance_uid'] == uid
    with pytest.raises(ValueError): attach(saved, instance_uid=workflows.new_uid())


def test_repeated_observation_rejected_and_new_scan_stored_without_mutation():
    saved, _ = attach(first())
    with pytest.raises(ValueError, match='already attached|ya está adjunta'): attach(saved)
    changed = deepcopy(ZAP); changed['created'] = '2026-10-18T10:00:00Z'
    out, _ = attach(saved, body(value=json.dumps(changed)))
    assert len(out['findings'][0]['import_observations']) == 2
    assert out['findings'][0]['status'] == saved['findings'][0]['status']


def test_absent_from_report_does_not_close_or_remove_anything():
    saved = first(); saved['findings'][0]['description_md'] = 'Manual'
    changed = deepcopy(ZAP); changed['site'][0]['alerts'][0]['alertRef'] = 'other'; changed['site'][0]['alerts'][0]['name'] = 'Other observation'
    out, _ = reconcile.apply(body(value=json.dumps(changed), decisions=[{'index': 0, 'action': 'create'}]), saved)
    assert out['findings'][0] == saved['findings'][0]
    assert len(out['findings']) == 2
    empty = deepcopy(ZAP); empty['site'][0]['alerts'] = []
    assert reconcile.preview(body(value=json.dumps(empty)), saved)['rows'] == []
    assert saved['findings'][0]['status'] == 'open'


@pytest.mark.parametrize('fields', [['cvss_vector'], ['severity'], ['status'], ['verification'], ['retests'], ['uid'], ['title', 'title'], [1], 'description_md'])
def test_technical_fields_and_malformed_selection_never_copy(fields):
    saved = first(); before = deepcopy(saved)
    with pytest.raises(ValueError): attach(saved, fields=fields)
    assert saved == before


@pytest.mark.parametrize('kind,root', [('zap', 'OWASPZAPReport'), ('nessus', 'NessusClientData_v2')])
@pytest.mark.parametrize('declaration', ['<!DOCTYPE ROOT SYSTEM "file:///etc/passwd">', '<!DOCTYPE ROOT [<!ENTITY x SYSTEM "http://example.test/">]>', '<!DOCTYPE ROOT [<!ENTITY a "123"><!ENTITY b "&a;&a;">]>'])
def test_xml_entities_dtd_network_never_expanded(kind, root, declaration):
    with pytest.raises(ValueError): finding_imports.preview(body(kind, declaration.replace('ROOT', root) + '<'+root+'/>'), basic())


@pytest.mark.parametrize('raw', ['{}', '[]', '{"site":null}', '{"site":[{"alerts":"x"}]}', '{"site":[],"site":[]}'])
def test_zap_malformed_json_rejected(raw):
    with pytest.raises(ValueError): finding_imports.preview(body(value=raw), basic())


def test_xml_wrong_encoding_and_shape_rejected():
    for kind in ('zap', 'nessus'):
        with pytest.raises(ValueError): finding_imports.preview(body(kind, '<other/>'), basic())
        with pytest.raises(ValueError): finding_imports.preview(body(kind, '<?xml version="1.0" encoding="utf-16"?><other/>'), basic())


def test_row_and_byte_budgets_and_atomic_observation_budget(monkeypatch):
    doc = deepcopy(ZAP); doc['site'][0]['alerts'][0]['instances'] *= 501
    with pytest.raises(ValueError): finding_imports.preview(body(value=json.dumps(doc)), basic())
    with pytest.raises(ValueError): finding_imports.preview(body('nessus', NESSUS.replace('</ReportHost>', NESSUS.split('<ReportItem')[1].split('</ReportItem>')[0].join(['<ReportItem', '</ReportItem>']) * 500 + '</ReportHost>')), basic())
    with pytest.raises(ValueError): finding_imports.preview(body(value='a'*(finding_imports.MAX_BYTES+1)), basic())
    monkeypatch.setattr(reconcile, 'MAX_PER_FINDING', 0)
    saved = first(); before = deepcopy(saved)
    with pytest.raises(ValueError): attach(saved)
    assert saved == before


def test_probable_matches_are_not_auto_applied():
    saved = first()
    changed = deepcopy(ZAP); changed['site'][0]['alerts'][0]['instances'][0]['uri'] = 'https://bank.example/new'
    preview = reconcile.preview(body(value=json.dumps(changed)), saved)
    assert preview['rows'][0]['match'] == 'probable'
    assert preview['rows'][0]['suggested_action'] == 'skip'


def test_api_preview_token_revision_and_explicit_ack(tmp_path, monkeypatch):
    import app as api
    from _support import auth_client
    projects = tmp_path/'projects'; projects.mkdir(); directory=projects/'review'; directory.mkdir()
    monkeypatch.setattr(api,'PROJECTS',projects)
    dump_yaml(first(),directory/'engagement.yaml')
    client=auth_client(api.app)
    route='/api/projects/review/imports/reconcile/'
    tag=client.get('/api/projects/review').headers['ETag']
    preview=client.post(route+'preview',json=body(),headers={'If-Match':tag})
    assert preview.status_code==200,preview.get_json()
    uid=client.get('/api/projects/review').json['findings'][0]['uid']
    payload=body(decisions=[{'index':0,'action':'attach','finding_uid':uid}],preview_token=preview.json['preview_token'],ack_reviewed=True)
    original=(directory/'engagement.yaml').read_bytes()
    assert client.post(route+'apply',json=payload).status_code==428
    assert client.post(route+'apply',json=payload,headers={'If-Match':'stale'}).status_code==409
    assert client.post(route+'apply',json={**payload,'ack_reviewed':False},headers={'If-Match':tag}).status_code==422
    assert client.post(route+'apply',json={**payload,'text':payload['text']+' '},headers={'If-Match':tag}).status_code==409
    assert (directory/'engagement.yaml').read_bytes()==original
    saved=client.post(route+'apply',json=payload,headers={'If-Match':tag})
    assert saved.status_code==200,saved.get_json()
    assert saved.json['data']['findings'][0]['import_observations']
    assert client.post(route+'apply',json=payload,headers={'If-Match':tag}).status_code==409


@pytest.mark.parametrize('uid', [None, [], {}, 1, True])
def test_malformed_destination_is_validation_error(uid):
    with pytest.raises(ValueError):
        reconcile.apply(body(decisions=[{'index': 0, 'action': 'attach', 'finding_uid': uid}]), first())


def test_burp_rule_type_identity_survives_scan_serial_and_title_changes():
    raw = '<issues><issue><serialNumber>1</serialNumber><type>1048832</type><name>Original rule</name><severity>Low</severity><host>https://example.test</host><path>/account</path></issue></issues>'
    saved, _ = finding_imports.apply(body('burp', raw, selected=[0]), basic())
    changed = raw.replace('<serialNumber>1', '<serialNumber>2').replace('Original rule', 'Revised rule name')
    assert reconcile.preview(body('burp', changed), saved)['rows'][0]['match'] == 'exact'


def test_machine_evidence_is_added_as_phase_without_destroying_existing_steps():
    saved=first();f=saved['findings'][0];f['mode']='machine';f['phases']=[{'name':'Manual phase','steps':[{'command':'manual proof'}]}]
    f.pop('walkthrough',None)
    out,_=attach(saved,fields=['walkthrough'])
    assert out['findings'][0]['phases'][0]==f['phases'][0]
    assert len(out['findings'][0]['phases'])==2
    assert out['findings'][0]['phases'][1]['steps']
    assert 'walkthrough' not in out['findings'][0]
    with pytest.raises(ValueError):attach(saved,fields=['description_md'])
