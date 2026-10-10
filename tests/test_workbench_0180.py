"""Private capture boundaries, explicit promotion and compatible technical states."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import zipfile

from PIL import Image
import pytest
import app as api
import capture_inbox
import engine
import finding_imports
import project_history
import validate
import workflows
from wizard import dump_yaml
from _support import auth_client


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'PROJECTS', tmp_path)
    d = tmp_path / 'test'; d.mkdir()
    data = workflows.normalize({'meta': {'report_title': 'Review', 'theme': 'serio', 'lang': 'en'},
                                'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'Existing finding', 'severity': 'low',
                                              'description_md': 'Description', 'impact_md': 'Impact', 'remediation_md': 'Fix'}]})
    dump_yaml(data, d / 'engagement.yaml')
    return auth_client(api.app), d, data


def post(c, route, payload, tag=None):
    return c.post('/api/projects/test' + route, json=payload,
                  headers={'If-Match': tag or c.get('/api/projects/test').headers['ETag']})


def note(**extra):
    return dict(kind='command', title='Captured command', raw_text='id\nwhoami', note='Internal context', **extra)


def test_capture_private_until_explicitly_linked(project):
    c, d, before = project
    r = post(c, '/captures', note()); assert r.status_code == 200, r.json
    data = r.json['data']; item = data['capture_inbox'][0]
    assert data['findings'] == before['findings']
    assert item['sha256'] == sha256(b'id\nwhoami').hexdigest()
    assert 'capture_inbox' not in workflows.project_report(data)
    assert not any('Internal context' in i['message'] for i in workflows.review(data, d))
    link = post(c, '/captures/' + item['uid'] + '/link', {'finding_uid': before['findings'][0]['uid']})
    assert link.status_code == 200, link.json
    step = link.json['data']['findings'][0]['walkthrough'][0]
    assert step['command'] == 'id\nwhoami' and step['capture_uid'] == item['uid']
    assert link.json['data']['capture_inbox'][0]['linked_at']
    assert post(c, '/captures/' + item['uid'] + '/link', {'finding_uid': before['findings'][0]['uid']}).status_code == 422


def test_capture_image_original_and_evidence_link(project):
    c, d, before = project
    buf = BytesIO(); Image.new('RGB', (90, 45), '#164255').save(buf, format='PNG'); blob = buf.getvalue()
    r = c.post('/api/projects/test/image', data={'file': (BytesIO(blob), 'proof.png')})
    created = post(c, '/captures', {'kind': 'image', 'title': 'Proof', 'note': 'Caption', 'src': r.json['src']})
    assert created.status_code == 200, created.json
    item = created.json['data']['capture_inbox'][0]
    assert (d / item['original']).read_bytes() == blob
    assert item['sha256'] == sha256(blob).hexdigest()
    linked = post(c, '/captures/' + item['uid'] + '/link', {'finding_uid': before['findings'][0]['uid']})
    assert linked.status_code == 200, linked.json
    evidence = linked.json['data']['evidence'][0]
    assert linked.json['data']['findings'][0]['evidence_uids'] == [evidence['uid']]
    assert evidence['original'] == item['original'] and evidence['caption'] == 'Caption'


@pytest.mark.parametrize('kind', ['command', 'http', 'note'])
def test_raw_capture_preserved_and_plain_note_escaped(project, kind):
    c, _, before = project
    raw = 'GET / HTTP/1.1\r\nX-Token: <private>\r\n\r\n![remote](https://example.test/a.png)'
    r = post(c, '/captures', {'kind': kind, 'title': 'Raw input', 'raw_text': raw})
    assert r.status_code == 200
    item = r.json['data']['capture_inbox'][0]
    assert item['raw_text'] == raw
    linked = post(c, '/captures/' + item['uid'] + '/link', {'finding_uid': before['findings'][0]['uid']})
    assert linked.status_code == 200
    step = linked.json['data']['findings'][0]['walkthrough'][0]
    if kind == 'note':
        from safe_markup import md
        assert '<img' not in str(md(step['text_md']))
    else: assert step['command'] == raw


@pytest.mark.parametrize('payload', [
    {}, {'kind': []}, {'kind': 'script', 'title': 'X'}, {'kind': 'note', 'title': 'X', 'raw_text': {}},
    {'kind': 'note', 'title': 'X', 'raw_text': 'a' * (capture_inbox.MAX_TEXT + 1)},
    {'kind': 'note', 'title': '', 'raw_text': 'x'}, {'kind': 'note', 'title': 'X', 'raw_text': 'x', 'unknown': 1},
    {'kind': 'image', 'title': 'X', 'src': '../private.png'},
    {'kind': 'image', 'title': 'X', 'src': 'https://example.test/p.png'},
])
def test_bad_capture_does_not_mutate(project, payload):
    c, d, _ = project
    before = (d / 'engagement.yaml').read_bytes()
    assert post(c, '/captures', payload).status_code == 422
    assert (d / 'engagement.yaml').read_bytes() == before


def test_capture_revision_and_csrf(project):
    c, d, _ = project
    before = (d / 'engagement.yaml').read_bytes()
    assert post(c, '/captures', note(), 'stale').status_code == 409
    assert c.post('/api/projects/test/captures', json=note()).status_code == 428
    assert api.app.test_client().post('/api/projects/test/captures', json=note()).status_code == 403
    assert (d / 'engagement.yaml').read_bytes() == before


def test_capture_bound_and_integrity_on_link(project):
    c, d, original = project
    made = post(c, '/captures', note()).json['data']; item = made['capture_inbox'][0]
    changed = deepcopy(made); changed['capture_inbox'][0]['raw_text'] = 'tampered'
    dump_yaml(changed, d / 'engagement.yaml')
    assert post(c, '/captures/' + item['uid'] + '/link', {'finding_uid': original['findings'][0]['uid']}).status_code == 422
    assert engine.load_engagement(d / 'engagement.yaml')['findings'] == original['findings']
    with pytest.raises(ValueError): capture_inbox.validate_rows([item] * 501)


def test_bandeja_round_trip_and_private_render(project, tmp_path):
    c, d, _ = project
    data = post(c, '/captures', {'kind': 'note', 'title': 'PRIVATE_TITLE_X', 'raw_text': 'PRIVATE_TEXT_X TODO'}).json['data']
    assert not any('TODO' in i['message'] for i in workflows.review(data, d))
    restored = tmp_path / 'restored'
    project_history.import_bundle(project_history.export_bundle(d), restored)
    assert engine.load_engagement(restored / 'engagement.yaml')['capture_inbox'] == data['capture_inbox']
    markup = engine.render_html(engine.build_env(), data, d, {}, False, engine.load_lang('en'))
    assert 'PRIVATE_TITLE_X' not in markup and 'PRIVATE_TEXT_X' not in markup


def test_capture_link_missing_finding_and_machine(project):
    c, d, data = project
    item = post(c, '/captures', note()).json['data']['capture_inbox'][0]
    assert post(c, '/captures/' + item['uid'] + '/link', {'finding_uid': 'missing'}).status_code == 422
    data = engine.load_engagement(d / 'engagement.yaml'); data['findings'][0]['mode'] = 'machine'
    dump_yaml(data, d / 'engagement.yaml')
    r = post(c, '/captures/' + item['uid'] + '/link', {'finding_uid': data['findings'][0]['uid']})
    assert r.status_code == 200, r.json
    assert r.json['data']['findings'][0]['phases'][0]['steps'][0]['command'] == 'id\nwhoami'


def test_verification_separate_from_import_review_and_legacy(project):
    _, d, data = project
    data['findings'][0]['status'] = 'not_verified'
    normalized = workflows.normalize(deepcopy(data))
    assert normalized['findings'][0] == data['findings'][0]
    out, _ = finding_imports.apply({'format': 'csv', 'text': 'title,severity\nImported,low', 'selected': [0]}, data)
    f = out['findings'][-1]
    assert f['verification'] == 'unverified' and f['status'] == 'open'
    f['import_source']['reviewed'] = True
    assert f['verification'] == 'unverified'
    assert not any(i['level'] == 'error' for i in workflows.review(out, d))
    assert not validate.structure_issues(out)
    f['verification'] = 'automatic_confirmed'
    assert validate.structure_issues(out)


def test_english_review_and_verification_output(project):
    c, _, data = project
    data['findings'][0]['verification'] = 'unverified'
    r = c.put('/api/projects/test', json=data); assert r.status_code == 200
    review = c.get('/api/projects/test/review?lang=en').json['issues']
    assert all('falta' not in i['message'] for i in review)
    sections = workflows.report_sections(data)
    assert 'Unverified' in '\n'.join(s['body'] for s in sections)


def test_capture_not_in_delivery_source(project, tmp_path):
    c, d, _ = project
    post(c, '/captures', {'kind': 'note', 'title': 'Private title', 'raw_text': 'DO_NOT_DELIVER'})
    import delivery
    delivery.capture(d, tmp_path / 'snapshot')
    assert 'capture_inbox' not in engine.load_engagement(tmp_path / 'snapshot/engagement.yaml')
    with zipfile.ZipFile(BytesIO(project_history.export_bundle(d))) as z:
        assert b'DO_NOT_DELIVER' in z.read('engagement.yaml')


def test_private_image_excluded_from_delivery_but_retained_in_backup(project, tmp_path):
    c, d, _ = project
    buf = BytesIO(); Image.new('RGB', (60, 40), '#382610').save(buf, format='PNG')
    image = c.post('/api/projects/test/image', data={'file': (BytesIO(buf.getvalue()), 'private.png')})
    item = post(c, '/captures', {'kind': 'image', 'title': 'PRIVATE_IMAGE', 'src': image.json['src']}).json['data']['capture_inbox'][0]
    import delivery
    captured = delivery.capture(d, tmp_path / 'image-snapshot')
    assert captured['image_placements'] == 0
    assert not (tmp_path / 'image-snapshot' / item['src']).exists()
    assert not (tmp_path / 'image-snapshot' / item['original']).exists()
    restored = tmp_path / 'image-restored'
    project_history.import_bundle(project_history.export_bundle(d), restored)
    assert (restored / item['original']).read_bytes() == buf.getvalue()
    assert (restored / item['src']).read_bytes() == buf.getvalue()
