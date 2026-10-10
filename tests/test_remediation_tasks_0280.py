"""Privacy, spreadsheet safety and exact saved-revision task exports."""
from copy import deepcopy
import csv
from io import BytesIO, StringIO
import zipfile

import pytest

import app as webapp
import remediation_tasks as tasks
import workflows
from _support import auth_client


def document():
    asset, group, first, second = [workflows.new_uid() for _ in range(4)]
    return {'meta': {'lang': 'es', 'report_title': 'SECRET CLIENT'}, 'assets': [
        {'uid': asset, 'name': 'Private system', 'target': 'https://internal.example', 'notes': 'OMITTED ASSET NOTES'}],
        'root_cause_groups': [{'uid': group, 'name': 'Shared policy', 'cause_md': 'OMITTED CAUSE',
                               'remediation_md': 'Deny unauthorized access.'}],
        'findings': [{'uid': first, 'id': 'F1', 'title': '<img src=x onerror=alert(1)>', 'mode': 'vuln',
            'severity': 'high', 'asset_uids': [asset], 'root_cause_uid': group, 'remediation_md': '=CMD("secret")',
            'owner': 'Private owner', 'due_date': '2026-11-20', 'status': 'reported_fixed',
            'closure_criteria_md': 'Unauthorized user receives 403; authorized access still works.',
            'description_md': 'OMITTED DESCRIPTION', 'impact_md': 'OMITTED IMPACT', 'retests': []},
            {'uid': second, 'id': 'F2', 'title': 'Second finding', 'mode': 'vuln', 'severity': 'low',
             'root_cause_uid': group, 'remediation_md': ''}]}


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path)
    client = auth_client(webapp.app)
    assert client.post('/api/projects', json={'slug': 'tasks', 'title': 'Tasks'}).status_code == 200
    data = document()
    assert client.put('/api/projects/tasks', json=data).status_code == 200
    return client, tmp_path / 'tasks', data


def preview(client, fields=None, ack=False):
    tag = client.get('/api/projects/tasks').headers['ETag']
    body = {'fields': fields or ['id', 'finding_uid'], 'lang': 'es', 'ack_private': ack}
    response = client.post('/api/projects/tasks/remediation-tasks/preview', json=body, headers={'If-Match': tag})
    return response, tag, body


def export(client, body, tag, token, kind='csv'):
    return client.post('/api/projects/tasks/remediation-tasks/export',
                       json={**body, 'format': kind, 'preview_token': token}, headers={'If-Match': tag})


def test_projection_preserves_ids_private_opt_in_and_shared_action():
    data = document()
    before = deepcopy(data)
    fields = list(tasks.FIELDS)
    rows = tasks.rows(data, fields)
    assert data == before
    assert [row['finding_uid'] for row in rows] == [finding['uid'] for finding in data['findings']]
    assert rows[0]['action'] == '=CMD("secret")'
    assert rows[1]['action'] == 'Deny unauthorized access.'
    assert rows[0]['shared_action'] == rows[1]['shared_action'] == 'Deny unauthorized access.'
    assert rows[0]['group_uid'] == rows[1]['group_uid'] == data['root_cause_groups'][0]['uid']
    assert rows[1]['closure_criteria'] == ''
    assert 'Private system · https://internal.example' == rows[0]['assets']
    assert 'OMITTED' not in str(rows)
    assert tasks.rows(data, ['id', 'finding_uid']) == [
        {key: row[key] for key in ('id', 'finding_uid')} for row in rows]


@pytest.mark.parametrize('fields', [None, [], ['title'], ['id', 'finding_uid', 'owner', 'owner'],
                                   ['id', 'finding_uid', 'description_md'], ['id', 'finding_uid', {}]])
def test_reject_implicit_unknown_duplicate_and_missing_identity_fields(fields):
    with pytest.raises(ValueError):
        tasks.options({'fields': fields, 'ack_private': True})


@pytest.mark.parametrize('value', ['=1+1', ' +CMD()', '-1+CMD()', '@SUM(A1)', '\t=CMD()',
                                   '\r=CMD()', '\n=CMD()', '\ufeff=CMD()', '\x00=CMD()', '\u200b=CMD()'])
def test_csv_formula_prefixes_are_neutralized(value):
    rows = [{'id': 'F1', 'finding_uid': workflows.new_uid(), 'action': value}]
    blob = tasks.csv_bytes(rows, ['id', 'finding_uid', 'action'])
    parsed = list(csv.reader(StringIO(blob.decode('utf-8-sig'))))
    assert parsed[1][-1] == "'" + value
    assert blob.startswith(b'\xef\xbb\xbf')


def test_csv_quotes_unicode_commas_and_multiline_without_losing_fields():
    row = {'id': 'F1', 'finding_uid': workflows.new_uid(), 'action': 'Aplicar "política", luego\nverificar autorización.'}
    parsed = list(csv.reader(StringIO(tasks.csv_bytes([row], list(row)).decode('utf-8-sig'))))
    assert parsed[1] == list(row.values())


def test_cards_escape_active_markup_preserve_text_and_zip_is_reproducible():
    data = document()
    fields = list(tasks.FIELDS)
    rows = tasks.rows(data, fields)
    blob = tasks.cards_zip(rows, fields)
    assert blob == tasks.cards_zip(rows, fields)
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        assert archive.namelist() == ['task-' + finding['uid'] + '.html' for finding in data['findings']]
        html = archive.read(archive.namelist()[0]).decode()
    assert '<img src=' not in html and '&lt;img src=x onerror=alert(1)&gt;' in html
    assert 'Content-Security-Policy' in html and 'default-src &#39;none&#39;' in html
    assert 'OMITTED' not in html and 'SECRET CLIENT' not in html


def test_preview_export_match_without_mutating_saved_files(project):
    client, directory, _ = project
    before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    response, tag, body = preview(client, list(tasks.FIELDS), True)
    assert response.status_code == 200, response.json
    result = response.json
    assert response.headers['ETag'] == tag
    assert result['revision'] == tag.strip('"')
    csv_response = export(client, body, tag, result['preview_token'])
    assert csv_response.status_code == 200
    expected = [[tasks.csv_cell(row[key]) for key in result['fields']] for row in result['rows']]
    parsed = list(csv.reader(StringIO(csv_response.data.decode('utf-8-sig'))))
    assert parsed[0] == list(result['labels'][key] for key in result['fields'])
    assert parsed[1:] == expected
    cards = export(client, body, tag, result['preview_token'], 'cards')
    assert cards.status_code == 200 and cards.headers['Cache-Control'] == 'no-store'
    assert {path.relative_to(directory): path.read_bytes() for path in directory.rglob('*') if path.is_file()} == before


def test_sensitive_fields_are_opt_in_and_unselected_fields_absent(project):
    client, _, _ = project
    response, _, _ = preview(client, ['id', 'finding_uid', 'owner'])
    assert response.status_code == 422
    response, _, _ = preview(client)
    assert response.status_code == 200
    assert 'Private owner' not in response.get_data(as_text=True)
    assert 'SECRET CLIENT' not in response.get_data(as_text=True)
    assert all(set(row) == {'id', 'finding_uid'} for row in response.json['rows'])


def test_export_cannot_expand_preview_fields_or_acknowledgement(project):
    client, _, _ = project
    response, tag, body = preview(client)
    token = response.json['preview_token']
    assert export(client, {**body, 'fields': body['fields'] + ['owner'], 'ack_private': True}, tag, token).status_code == 409
    assert export(client, {**body, 'lang': 'en'}, tag, token).status_code == 409
    assert export(client, body, tag, 'incorrect').status_code == 409
    assert export(client, body, tag, 'no-válido').status_code == 409


def test_preview_and_export_reject_stale_saved_revision(project):
    client, _, data = project
    response, tag, body = preview(client)
    data['findings'][0]['owner'] = 'Changed owner'
    assert client.put('/api/projects/tasks', json=data).status_code == 200
    assert export(client, body, tag, response.json['preview_token']).status_code == 409
    current = client.get('/api/projects/tasks').headers['ETag']
    assert export(client, body, current, response.json['preview_token']).status_code == 409


def test_preview_tokens_cannot_cross_projects(project):
    client, _, data = project
    response, _, body = preview(client)
    assert client.post('/api/projects', json={'slug': 'other', 'title': 'Other'}).status_code == 200
    assert client.put('/api/projects/other', json=data).status_code == 200
    tag = client.get('/api/projects/other').headers['ETag']
    result = client.post('/api/projects/other/remediation-tasks/export', json={**body, 'format': 'csv',
                         'preview_token': response.json['preview_token']}, headers={'If-Match': tag})
    assert result.status_code == 409


def test_api_uses_csrf_origin_revision_and_strict_options(project):
    client, _, _ = project
    response, tag, body = preview(client)
    endpoint = '/api/projects/tasks/remediation-tasks/preview'
    assert client.post(endpoint, json=body).status_code == 428
    assert client.post(endpoint, json=body, headers={'If-Match': tag, 'X-CSRF-Token': ''}).status_code == 403
    assert client.post(endpoint, json=body, headers={'If-Match': tag, 'Origin': 'https://evil.example'}).status_code == 403
    assert client.post(endpoint, json={**body, 'include_private': True}, headers={'If-Match': tag}).status_code == 422
    assert client.post(endpoint+'?fields=owner', json=body, headers={'If-Match': tag}).status_code == 422


def test_missing_and_duplicate_identities_do_not_produce_untraceable_tasks():
    for kind in ('missing', 'duplicate', 'missing_asset'):
        data = document()
        if kind == 'missing':
            del data['findings'][0]['uid']
        elif kind == 'duplicate':
            data['findings'][1]['uid'] = data['findings'][0]['uid']
        else:
            data['assets'] = []
        with pytest.raises(ValueError):
            tasks.rows(data, ['id', 'finding_uid', 'assets'])


@pytest.mark.parametrize('lang,expected', [
    ('en', 'Confirm review of fields that may contain private data'),
    ('es', 'Confirma que revisaste los campos que pueden contener datos privados'),
])
def test_api_errors_follow_ui_language_without_bilingual_text(project, lang, expected):
    client, _, _ = project
    tag = client.get('/api/projects/tasks').headers['ETag']
    response = client.post('/api/projects/tasks/remediation-tasks/preview',
                           json={'fields': ['id', 'finding_uid', 'owner'], 'lang': lang},
                           headers={'If-Match': tag, 'X-UI-Language': lang})
    assert response.status_code == 422
    assert response.json == {'error': expected}
    assert response.headers['Content-Language'] == lang
