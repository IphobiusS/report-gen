"""Local assistant protocol/consent guards; no installed LLM is asserted here."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import threading
import time

import pytest

import app as api
import editorial_assistant as assistant
import insights
from storage import revision
import workflows
from wizard import dump_yaml
from _support import auth_client


def document():
    return workflows.normalize(dict(meta=dict(report_title='Caso sintético', lang='es', theme='serio',
                                              client='PRIVATE_CLIENT_CANARY'),
        findings=[dict(id='F1', title='PRIVATE_TITLE_CANARY', severity='info', mode='vuln', cvss=0,
                       description_md='Una cuenta leyó un documento ajeno',
                       impact_md='PRIVATE_IMPACT_CANARY', remediation_md='Validar autorización',
                       proof=[{'name': 'PRIVATE_PROOF_CANARY', 'value': 'PRIVATE_PROOF_VALUE_CANARY'}])]))


def body(data, **extra):
    value = dict(finding_uid=data['findings'][0]['uid'], fields=['description_md'],
                 model='writer:local', confirmed_local=True, task='improve_clarity')
    value.update(extra)
    return value


@pytest.fixture
def client(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'assistant'
    directory.mkdir(parents=True)
    data = document()
    dump_yaml(data, directory / 'engagement.yaml')
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    return auth_client(api.app), directory, data


def request_proposal(client, payload=None, tag=None):
    c, directory, data = client
    return c.post('/api/projects/assistant/assistant', json=payload or body(data),
                  headers={'If-Match': tag or '"' + revision(directory / 'engagement.yaml') + '"'})


@pytest.fixture
def protocol(monkeypatch):
    calls = []
    returned = {
        '/api/tags': {'models': [{'name': 'writer:local', 'size': 4 * 1024 * 1024,
                                 'details': {'format': 'gguf'}, 'digest': 'test-model'}]},
        '/api/show': {'details': {'format': 'gguf'}},
        '/api/chat': {'message': {'content': json.dumps({'proposals': [
            {'field': 'description_md', 'after': 'Se documentó la lectura de un documento de otra cuenta.'}]})}},
    }

    def call(path, payload=None, **options):
        calls.append((path, deepcopy(payload), options))
        return deepcopy(returned[path])

    monkeypatch.setattr(assistant, '_call', call)
    return calls, returned


def test_exact_selected_fields_only_are_sent_and_never_auto_saved(client, protocol):
    _, directory, data = client
    before = (directory / 'engagement.yaml').read_bytes()
    result = request_proposal(client)
    assert result.status_code == 200, result.get_json()
    calls, _ = protocol
    assert [path for path, _, _ in calls] == ['/api/tags', '/api/show', '/api/chat']
    payload = calls[-1][1]
    selected = json.loads(payload['messages'][1]['content'])
    assert selected == {'task': 'improve_clarity', 'fields': {'description_md': data['findings'][0]['description_md']}}
    assert 'PRIVATE_' not in json.dumps(payload)
    assert payload['stream'] is False and payload['options']['temperature'] == 0
    assert result.get_json()['sources'][0]['sha256'] == assistant.digest(data['findings'][0]['description_md'])
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert not (directory / 'history').exists()
    assert len({options['deadline'] for _, _, options in calls}) == 1


def test_proposal_requires_explicit_confirmation_and_revision_before_network(client, protocol):
    c, directory, data = client
    calls, _ = protocol
    plain = api.app.test_client()
    assert plain.post('/api/projects/assistant/assistant', json=body(data),
                      headers={'If-Match': revision(directory / 'engagement.yaml')}).status_code == 403
    assert c.post('/api/projects/assistant/assistant', json=body(data)).status_code == 428
    assert request_proposal(client, body(data, confirmed_local=False)).status_code == 422
    assert request_proposal(client, tag='"' + 'a' * 64 + '"').status_code == 409
    assert not calls


@pytest.mark.parametrize('changes', [
    {'fields': ['proof']}, {'fields': ['cvss']}, {'fields': ['description_md', 'description_md']},
    {'fields': []}, {'fields': [{}]}, {'fields': 'description_md'},
    {'model': 'remote:cloud'}, {'model': 'https://external.example/model'},
    {'url': 'http://external.example'}, {'task': 'verify_pentest'}, {'task': []},
    {'finding_uid': 'absent'}, {'confirmed_local': 'true'},
])
def test_disallowed_requests_do_not_contact_any_model(client, protocol, changes):
    calls, _ = protocol
    assert request_proposal(client, body(client[2], **changes)).status_code == 422
    assert not calls


def test_explicit_accept_applies_only_selected_proposal_and_invalidates_review(client, protocol):
    c, directory, data = client
    approved = insights.mutate(data, dict(action='review', decision='approved', author='Nombre local'),
                               revision(directory / 'engagement.yaml'), directory)
    dump_yaml(approved, directory / 'engagement.yaml')
    proposed = request_proposal(client).get_json()
    response = c.post('/api/projects/assistant/assistant/apply',
                      json={'proposal_id': proposed['proposal_id'], 'fields': ['description_md']},
                      headers={'If-Match': proposed['revision']})
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()['data']
    assert saved['findings'][0]['description_md'] == proposed['proposals'][0]['after']
    assert saved['findings'][0]['impact_md'] == data['findings'][0]['impact_md']
    assert saved['findings'][0]['cvss'] == 0 and saved['findings'][0]['proof'] == data['findings'][0]['proof']
    assert insights.view(saved, directory)['review_status']['state'] == 'stale'
    assert c.post('/api/projects/assistant/assistant/apply',
                  json={'proposal_id': proposed['proposal_id'], 'fields': ['description_md']},
                  headers={'If-Match': response.headers['ETag']}).status_code == 404


def test_accept_cannot_change_unproposed_fields(client, protocol):
    c, directory, _ = client
    proposed = request_proposal(client).get_json()
    before = (directory / 'engagement.yaml').read_bytes()
    response = c.post('/api/projects/assistant/assistant/apply',
        json={'proposal_id': proposed['proposal_id'], 'fields': ['impact_md']},
        headers={'If-Match': proposed['revision']})
    assert response.status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_changed_source_blocks_earlier_proposal_even_if_text_selection_unchanged(client, protocol):
    c, directory, data = client
    proposed = request_proposal(client).get_json()
    data['meta']['client'] = 'Cambio documental'
    dump_yaml(data, directory / 'engagement.yaml')
    response = c.post('/api/projects/assistant/assistant/apply',
        json={'proposal_id': proposed['proposal_id'], 'fields': ['description_md']},
        headers={'If-Match': revision(directory / 'engagement.yaml')})
    assert response.status_code == 409
    assert c.get('/api/projects/assistant').get_json()['findings'][0]['description_md'] == data['findings'][0]['description_md']


def test_proposal_cannot_be_accepted_by_another_local_session(client, protocol):
    _, directory, _ = client
    proposed = request_proposal(client).get_json()
    other = auth_client(api.app)
    assert other.post('/api/projects/assistant/assistant/apply',
        json={'proposal_id': proposed['proposal_id'], 'fields': ['description_md']},
        headers={'If-Match': revision(directory / 'engagement.yaml')}).status_code == 404


@pytest.mark.parametrize('model', [
    {'name': 'writer:cloud', 'size': 4 * 1024 * 1024, 'details': {'format': 'gguf'}},
    {'name': 'writer:local', 'size': 4 * 1024 * 1024, 'details': {'format': 'gguf'}, 'remote_host': 'cloud.example'},
    {'name': 'writer:local', 'size': 4 * 1024 * 1024, 'details': {'format': 'onnx'}},
    {'name': 'writer:local', 'size': True, 'details': {'format': 'gguf'}},
    {'name': 'writer:local', 'size': 1, 'details': {'format': 'gguf'}},
    None,
])
def test_cloud_or_nonlocal_metadata_is_rejected_before_chat(client, protocol, model):
    calls, responses = protocol
    responses['/api/tags']['models'] = [model]
    assert request_proposal(client).status_code == 422
    assert not any(path == '/api/chat' for path, _, _ in calls)


def test_changed_remote_model_metadata_is_rejected(client, protocol):
    calls, responses = protocol
    responses['/api/show']['remote_model'] = 'cloud:model'
    assert request_proposal(client).status_code == 422
    assert not any(path == '/api/chat' for path, _, _ in calls)


@pytest.mark.parametrize('output', [
    'not json', '{}', '{"proposals":[]}',
    '{"proposals":[{"field":"cvss","after":"9.8"}]}',
    '{"proposals":[{"field":"description_md","after":"x","hidden":"secret"}]}',
    '{"proposals":[{"field":"description_md","after":""}]}',
])
def test_malformed_or_field_inventing_model_output_does_not_write(client, protocol, output):
    _, directory, _ = client
    _, responses = protocol
    responses['/api/chat']['message']['content'] = output
    before = (directory / 'engagement.yaml').read_bytes()
    assert request_proposal(client).status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_proposal_quota_is_checked_before_model_inference(client, protocol):
    calls, _ = protocol
    for _ in range(8):
        assert request_proposal(client).status_code == 200
    count = len(calls)
    assert request_proposal(client).status_code == 429
    assert len(calls) == count


def test_discard_is_owned_and_reclaims_capacity_without_changing_source(client, protocol):
    c, directory, _ = client
    before = (directory / 'engagement.yaml').read_bytes()
    proposed = request_proposal(client).get_json()
    other = auth_client(api.app)
    payload = {'proposal_id': proposed['proposal_id']}
    assert other.post('/api/projects/assistant/assistant/discard', json=payload).status_code == 404
    assert c.post('/api/projects/other/assistant/discard', json=payload).status_code == 404
    assert c.post('/api/projects/assistant/assistant/discard', json=payload).status_code == 200
    assert c.post('/api/projects/assistant/assistant/discard', json=payload).status_code == 404
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert request_proposal(client).status_code == 200


def test_only_one_inference_runs_and_editor_reads_remain_available(client, monkeypatch):
    c, directory, data = client
    entered, release = threading.Event(), threading.Event()
    responses = []

    def slow(source, selected):
        entered.set()
        assert release.wait(5)
        return dict(finding_uid=selected['finding_uid'], proposals=[dict(field='description_md',
            before=source['findings'][0]['description_md'], after='Texto propuesto')], sources=[], warnings=[])

    monkeypatch.setattr(assistant, 'propose', slow)
    thread = threading.Thread(target=lambda: responses.append(request_proposal(client)), daemon=True)
    thread.start()
    assert entered.wait(2)
    try:
        second = auth_client(api.app)
        response = second.post('/api/projects/assistant/assistant', json=body(data),
                               headers={'If-Match': revision(directory / 'engagement.yaml')})
        assert response.status_code == 429
        assert second.get('/api/projects/assistant').status_code == 200
    finally:
        release.set()
        thread.join(5)
    assert responses[0].status_code == 200
    assert c.get('/api/projects/assistant').status_code == 200


class FakeResponse:
    def __init__(self, blob=b'{}', status=200):
        self.status, self.blob, self.offset = status, blob, 0

    def read1(self, size):
        chunk = self.blob[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


@pytest.fixture
def transport(monkeypatch):
    calls, settings = [], {'blob': b'{}', 'status': 200}

    class Connection:
        sock = None

        def __init__(self, host, port, timeout):
            calls.append(('connect', host, port, timeout))

        def request(self, method, path, body=None, headers=None):
            calls.append(('request', method, path, body, headers))

        def getresponse(self):
            return FakeResponse(settings['blob'], settings['status'])

        def close(self):
            calls.append(('close',))

    monkeypatch.setattr(assistant.http.client, 'HTTPConnection', Connection)
    return calls, settings


def test_adapter_is_fixed_to_numeric_loopback_and_ignores_proxy_environment(transport, monkeypatch):
    calls, _ = transport
    monkeypatch.setenv('HTTP_PROXY', 'http://proxy.example:8080')
    assert assistant._call('/api/show', {'model': 'writer:local'}) == {}
    assert calls[0][1:3] == ('127.0.0.1', 11434)
    assert calls[1][1:3] == ('POST', '/api/show')


@pytest.mark.parametrize('status', [301, 302, 307, 403, 500])
def test_adapter_does_not_follow_redirects_or_other_http_status(transport, status):
    calls, settings = transport
    settings['status'] = status
    with pytest.raises(ValueError, match='Local Ollama rejected'):
        assistant._call('/api/tags')
    assert len([call for call in calls if call[0] == 'connect']) == 1


@pytest.mark.parametrize('blob', [b'x' * (assistant.MAX_RESPONSE + 1), b'[]', b'not json'])
def test_adapter_limits_response_bytes_and_structure(transport, blob):
    _, settings = transport
    settings['blob'] = blob
    with pytest.raises(ValueError):
        assistant._call('/api/tags')


def test_expired_deadline_does_not_open_any_socket(transport):
    calls, _ = transport
    with pytest.raises(ValueError, match='deadline exceeded'):
        assistant._call('/api/tags', deadline=time.monotonic() - 1)
    assert calls == []


def test_overall_deadline_interrupts_actual_slow_local_http_headers(monkeypatch):
    # This is a real local HTTP transport, with a synthetic server instead of
    # a model. Port substitution is test-only; the production target is fixed.
    seen = []

    class Slow(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Slow: ')
                self.wfile.flush()
                for _ in range(20):
                    time.sleep(0.025)
                    self.wfile.write(b'a')
                    self.wfile.flush()
                self.wfile.write(b'\r\nContent-Length: 2\r\n\r\n{}')
                self.wfile.flush()
            except OSError:
                pass

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Slow)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = http.client.HTTPConnection

    def connect(host, port, timeout):
        seen.append((host, port))
        return original(host, server.server_port, timeout=timeout)

    monkeypatch.setattr(assistant.http.client, 'HTTPConnection', connect)
    started = time.monotonic()
    try:
        with pytest.raises(ValueError, match='deadline exceeded'):
            assistant._call('/api/tags', deadline=started + 0.15)
        assert time.monotonic() - started < 0.4
        assert seen == [('127.0.0.1', 11434)]
    finally:
        server.shutdown()
        server.server_close()


def test_readonly_capabilities_never_connect_and_models_require_csrf(client, transport):
    c, _, _ = client
    calls, _ = transport
    assert c.get('/api/assistant/capabilities').get_json()['connected'] is False
    assert calls == []
    plain = api.app.test_client()
    assert plain.post('/api/assistant/models', json={}).status_code == 403
    assert c.post('/api/assistant/models', json={'url': 'http://external.example'}).status_code == 422
    assert calls == []
