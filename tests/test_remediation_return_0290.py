"""Return templates are explicit assignments, never evidence of a verified fix."""
from copy import deepcopy
import csv
from io import StringIO
import json

import pytest

import app as webapp
import remediation_return as returns
import remediation_tasks as tasks
import workflows
from _support import auth_client


def document():
    return {'meta': {'lang': 'es', 'report_title': 'SYNTHETIC'}, 'findings': [
        {'uid': workflows.new_uid(), 'id': 'F1', 'title': 'First', 'mode': 'vuln', 'severity': 'high',
         'owner': 'Original owner', 'due_date': '2026-11-20', 'status': 'open', 'verification': 'confirmed',
         'description_md': 'Original description', 'retests': [{'uid': workflows.new_uid(), 'tested_on': '2026-10-01',
         'assessor': 'Evaluator', 'result': 'open', 'notes_md': 'Still reproducible'}]},
        {'uid': workflows.new_uid(), 'id': 'F2', 'title': 'Second', 'mode': 'vuln', 'severity': 'low', 'owner': 'Other'}]}


def edit(blob, updates=None, transform=None):
    rows = list(csv.reader(StringIO(blob.decode('utf-8-sig'), newline='')))
    for key, value in (updates or {}).items():
        rows[1][rows[0].index(key)] = value
    if transform:
        transform(rows)
    stream = StringIO(newline='')
    csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator='\r\n').writerows(rows)
    return '\ufeff' + stream.getvalue()


def issued(data=None, both=False):
    data = data or document()
    return returns.issue(data, 'tasks', [finding['uid'] for finding in data['findings'][:2 if both else 1]])


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path)
    client = auth_client(webapp.app)
    assert client.post('/api/projects', json={'slug': 'tasks', 'title': 'Tasks'}).status_code == 200
    data = document()
    assert client.put('/api/projects/tasks', json=data).status_code == 200
    return client, tmp_path / 'tasks', data


def call(client, operation, payload, tag=None, **headers):
    tag = tag or client.get('/api/projects/tasks').headers['ETag']
    return client.post('/api/projects/tasks/remediation-tasks/'+operation, json=payload, headers={'If-Match': tag, **headers})


def issue_api(client, data):
    response = call(client, 'return-template', {'finding_uids': [data['findings'][0]['uid']],
                                              'ack_private': True, 'ack_retention': True})
    assert response.status_code == 200, response.json
    return response


def propose_api(client, text):
    response = call(client, 'return-preview', {'text': text})
    assert response.status_code == 200, response.json
    return response


def apply_api(client, text, proposal, selected=None, **kwargs):
    return call(client, 'return-apply', {'text': text, 'preview_token': proposal.json['preview_token'],
                                       'selected': selected if selected is not None else [c['key'] for c in proposal.json['changes']],
                                       'ack_reviewed': True, **kwargs})


def test_template_roundtrip_is_lossless_and_preview_is_read_only():
    data = document()
    data['findings'][0]['owner'] = "'=not a formula"
    data['findings'][0]['reported_remediation'] = '=SUM(1,2)\n"Quote", último'
    before = deepcopy(data)
    updated, blob = issued(data)
    assert data == before
    assert returns.plan(updated, 'tasks', blob.decode('utf-8-sig'))['changes'] == []
    assert len(updated['remediation_exchanges']) == 1
    parsed = list(csv.reader(StringIO(blob.decode('utf-8-sig'))))
    assert parsed[1][4] == "''=not a formula"
    assert parsed[1][6].startswith("'=SUM")
    assert updated['findings'] == data['findings']


@pytest.mark.parametrize('text', ['=1+1', '+CALL()', '-1+CMD()', '@SUM(A1)', "'literal", "''literal", 'Español, "texto"'])
def test_formula_protection_removes_exactly_one_required_marker(text):
    data = document()
    data['findings'][0]['owner'] = text
    result, blob = issued(data)
    assert returns.plan(result, 'tasks', blob.decode('utf-8'))['changes'] == []
    changed = edit(blob, {'reported_remediation': "'" + text})
    plan = returns.plan(result, 'tasks', changed)
    assert plan['changes'][0]['after'] == text
    assert tasks.csv_cell(plan['changes'][0]['after']).startswith("'") or text.startswith("'") or text.startswith('Español')


def test_apply_only_selected_fields_preserves_all_technical_information():
    data, blob = issued()
    text = edit(blob, {'owner': "'New owner", 'due_date': '', 'reported_remediation': "'Client says fixed"})
    plan = returns.plan(data, 'tasks', text)
    assert len(plan['changes']) == 3
    updated = returns.apply(data, plan, [plan['changes'][2]['key']])
    expected = deepcopy(data)
    expected['findings'][0]['reported_remediation'] = 'Client says fixed'
    assert updated == expected
    assert data['findings'][0]['status'] == 'open'
    assert data['findings'][0]['verification'] == 'confirmed'
    assert data['findings'][0]['retests'][0]['result'] == 'open'


def test_changed_since_issue_is_explicit_and_partial_rows_never_delete():
    data, blob = issued(both=True)
    data['findings'][0]['owner'] = 'Changed internally'
    text = edit(blob, {'owner': "'Client proposal"}, lambda rows: rows.pop())
    plan = returns.plan(data, 'tasks', text)
    assert plan['rows'] == 1
    assert plan['changes'][0]['changed_since_issue'] is True
    assert plan['changes'][0]['issued'] == 'Original owner'
    assert plan['changes'][0]['before'] == 'Changed internally'
    updated = returns.apply(data, plan, [plan['changes'][0]['key']])
    assert updated['findings'][1] == data['findings'][1]


@pytest.mark.parametrize('case', ['unknown_uid', 'unassigned_uid', 'duplicate', 'wrong_slug', 'wrong_batch', 'extra_column',
                                  'duplicate_header', 'no_text_marker', 'invalid_date', 'empty_owner', 'control', 'bidi',
                                  'wrong_format', 'empty', 'blank_line', 'ambiguous_delimiter', 'overlong', 'deleted'])
def test_rejects_ambiguous_unassigned_or_invalid_returns(case):
    data, blob = issued()
    changes = {'unknown_uid': {'finding_uid': workflows.new_uid()},
               'unassigned_uid': {'finding_uid': data['findings'][1]['uid']},
               'wrong_slug': {'project_slug': 'other'}, 'wrong_batch': {'batch_uid': workflows.new_uid()},
               'no_text_marker': {'owner': '=Formula'}, 'invalid_date': {'due_date': '2026-02-30'},
               'empty_owner': {'owner': "'  "}, 'control': {'owner': "'a\x00b"},
               'bidi': {'reported_remediation': "'x\u202ey"}, 'wrong_format': {'format': 'untrusted'},
               'overlong': {'reported_remediation': "'" + 'a'*8001}}
    def transform(rows):
        if case == 'duplicate': rows.append(rows[1][:])
        if case == 'extra_column':
            rows[0].append('verified_fixed');rows[1].append('true')
        if case == 'duplicate_header': rows[0][-1] = rows[0][-2]
        if case == 'empty': rows.pop()
        if case == 'blank_line': rows.append([])
    text = edit(blob, changes.get(case), transform)
    if case == 'ambiguous_delimiter': text = text.replace(',', ';')
    if case == 'deleted': data['findings'].pop(0)
    with pytest.raises(ValueError): returns.plan(data, 'tasks', text)


@pytest.mark.parametrize('selected', [[], ['bad'], ['verified_fixed'], [None]])
def test_selection_must_reference_actual_changes(selected):
    data, blob = issued()
    plan = returns.plan(data, 'tasks', edit(blob, {'owner': "'Updated"}))
    with pytest.raises(ValueError): returns.apply(data, plan, selected)


def test_rejects_mix_of_batches_and_limit_overflow():
    data, first = issued()
    data, second = issued(data, both=True)
    first_rows = list(csv.reader(StringIO(first.decode('utf-8-sig'))))
    text = edit(second, transform=lambda rows: rows.append(first_rows[1]))
    with pytest.raises(ValueError): returns.plan(data, 'tasks', text)
    with pytest.raises(ValueError): returns.plan(data, 'tasks', 'a'*(returns.MAX_BYTES+1))
    with pytest.raises(ValueError): returns.plan(data, 'tasks', '\ud800')
    with pytest.raises(ValueError): returns.issue(data, 'tasks', [data['findings'][0]['uid']]*501)


def test_limited_retention_and_restart_have_no_session_dependency():
    data, first = issued()
    for _ in range(returns.MAX_BATCHES): data, latest = issued(data)
    assert len(data['remediation_exchanges']) == returns.MAX_BATCHES
    with pytest.raises(ValueError): returns.plan(data, 'tasks', first.decode('utf-8'))
    restored = json.loads(json.dumps(data))
    assert returns.plan(restored, 'tasks', latest.decode('utf-8'))['changes'] == []


def test_batches_validated_in_normal_project_saves():
    data, _ = issued()
    assert workflows.structure_errors(data) == []
    data['remediation_exchanges'][0]['rows'][0]['base']['owner'] = ''
    assert any('remediation_exchanges' in text for _, text in workflows.structure_errors(data))


def test_api_issue_persists_but_preview_does_not_and_apply_is_selective(project):
    client, directory, data = project
    issued_response = issue_api(client, data)
    blob = issued_response.data
    text = edit(blob, {'owner': "'External owner", 'reported_remediation': "'Says done"})
    before = {p.relative_to(directory):p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    proposal = propose_api(client, text)
    assert proposal.headers['ETag'] == issued_response.headers['ETag']
    assert {p.relative_to(directory):p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
    selected = [c['key'] for c in proposal.json['changes'] if c['field'] == 'reported_remediation']
    response = apply_api(client, text, proposal, selected)
    assert response.status_code == 200, response.json
    current = response.json['data']['findings'][0]
    assert current['reported_remediation'] == 'Says done'
    for key in ('owner', 'status', 'verification', 'retests', 'description_md'):
        assert current[key] == data['findings'][0][key]
    assert response.headers['ETag'] != issued_response.headers['ETag']


def test_api_stale_or_modified_preview_is_not_applicable(project):
    client, _, data = project
    blob = issue_api(client, data).data
    text = edit(blob, {'owner': "'External owner"})
    proposal = propose_api(client, text)
    assert apply_api(client, edit(blob, {'owner': "'Changed again"}), proposal).status_code == 409
    assert apply_api(client, text, proposal, preview_token='invalid').status_code == 409
    current = client.get('/api/projects/tasks').json
    current['findings'][0]['description_md'] = 'Concurrent edit'
    assert client.put('/api/projects/tasks', json=current).status_code == 200
    assert apply_api(client, text, proposal).status_code == 409
    assert call(client, 'return-preview', {'text': text}, proposal.headers['ETag']).status_code == 409


def test_api_csrf_options_ack_and_no_cross_project_template(project):
    client, _, data = project
    blob = issue_api(client, data).data
    text = edit(blob, {'owner': "'External owner"})
    proposal = propose_api(client, text)
    assert apply_api(client, text, proposal, ack_reviewed=False).status_code == 422
    assert call(client, 'return-preview', {'text': text}, **{'X-CSRF-Token': ''}).status_code == 403
    assert call(client, 'return-preview', {'text': text}, Origin='https://evil.invalid').status_code == 403
    assert call(client, 'return-preview', {'text': text, 'status': 'verified_fixed'}).status_code == 422
    assert client.post('/api/projects', json={'slug': 'other', 'title': 'Other'}).status_code == 200
    assert client.put('/api/projects/other', json=client.get('/api/projects/tasks').json).status_code == 200
    tag = client.get('/api/projects/other').headers['ETag']
    response = client.post('/api/projects/other/remediation-tasks/return-preview',json={'text':text},headers={'If-Match':tag})
    assert response.status_code == 422
    missing = client.post('/api/projects/tasks/remediation-tasks/return-preview',json={'text':text})
    assert missing.status_code == 428


def test_api_errors_follow_language(project):
    client, _, _ = project
    response = call(client, 'return-preview', {'text': 'wrong'}, **{'X-UI-Language':'en'})
    assert response.status_code == 422
    assert response.json['error'].startswith('Invalid return template.')


@pytest.mark.parametrize('slug', ['-1-2', 'clínica', 'ordinary'])
def test_project_reference_is_explicitly_text_and_roundtrips(slug):
    data = document()
    issued_data, blob = returns.issue(data, slug, [data['findings'][0]['uid']])
    parsed = list(csv.reader(StringIO(blob.decode('utf-8-sig'))))
    assert parsed[1][1] == "'" + slug
    assert returns.plan(issued_data, slug, blob.decode('utf-8'))['changes'] == []


def test_partial_acceptance_replay_is_a_new_comparison_not_automatic_acceptance():
    data, blob = issued()
    text = edit(blob, {'owner': "'New owner", 'due_date': ''})
    first = returns.plan(data, 'tasks', text)
    updated = returns.apply(data, first, [first['changes'][0]['key']])
    second = returns.plan(updated, 'tasks', text)
    assert [change['field'] for change in second['changes']] == ['due_date']


def test_csv_forging_technical_fields_and_duplicate_selection_are_rejected():
    data, blob = issued()
    plan = returns.plan(data, 'tasks', edit(blob, {'owner': "'New owner"}))
    key = plan['changes'][0]['key']
    with pytest.raises(ValueError): returns.apply(data, plan, [key, key])
    for field in ('status', 'verification', 'retests', 'evidence_uids', 'description_md'):
        text = edit(blob, transform=lambda rows: rows[0].__setitem__(4, field))
        with pytest.raises(ValueError): returns.plan(data, 'tasks', text)
