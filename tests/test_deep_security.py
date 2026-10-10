"""Adversarial regressions: confidentiality, recoverability and bounded inputs."""
import copy
import hashlib
import io
import json
import zipfile

import pytest
from PIL import Image

import app as webapp
import engine
import export
import project_history as history
import workflows
from _support import auth_client


def data():
    return {'meta': {'report_title': 'Audit', 'lang': 'es', 'theme': 'corporativo'},
            'findings': [], 'report': {'sections': [{'key': 'findings'}]}}


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path)
    monkeypatch.setitem(webapp.app.config, 'TESTING', True)
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path/'library.json'))
    c = auth_client(webapp.app)
    assert c.post('/api/projects', json={'slug': 'audit'}).status_code == 200
    return c, tmp_path/'audit'


@pytest.mark.parametrize('location', ['meta', 'extension'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_json_is_rejected_before_any_save(project, location, value):
    c, directory = project
    before = c.get('/api/projects/audit')
    doc = before.get_json()
    doc.setdefault(location, {})['version'] = value
    files = {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    response = c.put('/api/projects/audit', json=doc, headers={'If-Match': before.headers['ETag']})
    assert response.status_code == 422
    assert {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == files
    assert c.get('/api/projects/audit').headers['ETag'] == before.headers['ETag']


@pytest.mark.parametrize('body', [
    '{"meta": {}, "findings": [{"id":"F1"}], "findings": []}',
    '{"meta": {}, "extension": ' + '['*90 + '0' + ']'*90 + '}',
])
def test_ambiguous_or_deep_json_cannot_replace_data(project, body):
    c, directory = project
    before = (directory/'engagement.yaml').read_bytes()
    r = c.put('/api/projects/audit', data=body, content_type='application/json')
    assert r.status_code == 422
    assert (directory/'engagement.yaml').read_bytes() == before


def archive_with_yaml(blob):
    contents = {'engagement.yaml': blob}
    manifest = {'format': 'report-gen-project', 'version': 1,
                'files': {k: hashlib.sha256(v).hexdigest() for k, v in contents.items()}}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr('manifest.json', json.dumps(manifest))
        for k, v in contents.items(): z.writestr(k, v)
    return out.getvalue()


YAML_CASES = [
    'meta: {}\nfindings: [{id: F1}]\nfindings: []\n',
    'meta: {}\nfindings: []\nextra: &a [*a]\n',
    'meta: {}\nextra: ' + '['*90 + '0' + ']'*90 + '\n',
    'meta: {}\nextra: .nan\n',
    'meta: {}\nextra: !!binary YQ==\n',
    'meta: {}\n1: ambiguous\n',
    'meta: {}\n' + '\n'.join('x'+str(i)+': &a'+str(i)+' [' + ','.join(
        ('leaf' if i == 0 else '*a'+str(i-1)) for _ in range(8)) + ']' for i in range(7)),
]


@pytest.mark.parametrize('source', YAML_CASES)
@pytest.mark.parametrize('route', ['cli', 'import'])
def test_unsafe_yaml_is_rejected_with_a_controlled_error(tmp_path, source, route):
    p = tmp_path/'engagement.yaml'; p.write_text(source)
    with pytest.raises(ValueError):
        if route == 'cli': engine.load_engagement(p)
        else: history.import_bundle(archive_with_yaml(source.encode()), tmp_path/'rejected')
    assert not (tmp_path/'rejected').exists()
    assert not list(tmp_path.glob('.import-*'))


def test_small_yaml_aliases_and_merge_overrides_remain_supported(tmp_path):
    p = tmp_path/'engagement.yaml'
    p.write_text('defaults: &d {report_title: Default, lang: es}\nmeta: {<<: *d, report_title: Chosen}\nfindings: []\n')
    assert engine.load_engagement(p)['meta'] == {'report_title': 'Chosen', 'lang': 'es'}


def test_aliased_legacy_rows_receive_independent_permanent_ids(tmp_path):
    p = tmp_path/'engagement.yaml'
    p.write_text('meta: {}\nassets: [&a {name: Example}, *a]\nfindings: []\n')
    doc = engine.load_engagement(p)
    history.save(tmp_path, doc)
    restored = engine.load_engagement(p)
    assert restored['assets'][0]['uid'] != restored['assets'][1]['uid']
    assert [a['name'] for a in restored['assets']] == ['Example', 'Example']


@pytest.mark.parametrize('header', [{'Origin': 'http://['}, {'X-CSRF-Token': 'ñ'}])
def test_bad_security_headers_are_denied_without_server_error(project, header):
    c, _ = project
    assert c.post('/api/projects', json={'slug': 'unwanted'}, headers=header).status_code == 403


@pytest.mark.parametrize('registered', ['img/proof space.png', 'img/proof%20space.png'])
def test_redaction_updates_all_aliases_and_export_contains_only_masked_pixels(project, registered):
    c, directory = project
    source = directory/'img/proof space.png'
    Image.new('RGB', (40, 40), 'red').save(source)
    uid = workflows.new_uid()
    doc = data()
    doc['evidence'] = [{'uid': uid, 'title': 'Proof', 'src': registered}]
    doc['findings'] = [{'id': 'F1', 'title': 'Example', 'severity': 'info', 'cvss': 0,
        'description_md': '![Encoded](./img/proof%20space.png)',
        'walkthrough': [{'figure': {'src': 'img/proof space.png'}},
                        {'figure': {'src': './img/proof%20space.png'}}]}]
    history.save(directory, doc)
    tag = c.get('/api/projects/audit').headers['ETag']
    response = c.post('/api/projects/audit/evidence/'+uid+'/edit', json={
        'operations': [{'type': 'redact', 'x': 0, 'y': 0, 'w': 1, 'h': 1}]}, headers={'If-Match': tag})
    assert response.status_code == 200, response.get_json()
    current = c.get('/api/projects/audit').get_json()
    new = current['evidence'][0]['src']
    assert not source.exists()
    assert all(s['figure']['src'] == new for s in current['findings'][0]['walkthrough'])
    assert new in current['findings'][0]['description_md']
    out = export.export(directory/'engagement.yaml', 'md', directory.parent/'delivery.zip')
    with zipfile.ZipFile(out) as z:
        images = [n for n in z.namelist() if n.endswith('.png')]
        assert images == [new]
        with Image.open(io.BytesIO(z.read(new))) as rendered:
            assert rendered.getpixel((20, 20)) == (0, 0, 0)


def test_backup_and_history_preserve_referenced_images_outside_img(tmp_path):
    directory = tmp_path/'project'; directory.mkdir()
    nested = directory/'diagrams'; nested.mkdir()
    Image.new('RGB', (20, 20), 'red').save(directory/'cover.png')
    Image.new('RGB', (20, 20), 'blue').save(nested/'network space.png')
    doc = data(); doc['meta']['branding'] = {'logo': 'cover.png'}
    doc['report']['sections'].append({'key': 'custom', 'title': 'Network',
                                    'body': '![Network](diagrams/network%20space.png)'})
    history.save(directory, doc)
    sid = history.checkpoint(directory)['id']
    expected = (directory/'cover.png').read_bytes(), (nested/'network space.png').read_bytes()
    history.import_bundle(history.export_bundle(directory), tmp_path/'imported')
    assert (tmp_path/'imported/cover.png').read_bytes() == expected[0]
    assert (tmp_path/'imported/diagrams/network space.png').read_bytes() == expected[1]
    Image.new('RGB', (20, 20), 'green').save(directory/'cover.png')
    history.restore(directory, sid)
    assert (directory/'cover.png').read_bytes() == expected[0]
    assert (directory/'diagrams/network space.png').read_bytes() == expected[1]


def test_preview_image_route_preserves_paths_but_rejects_private_files(project):
    c, directory = project
    Image.new('RGB', (20, 20), 'red').save(directory/'cover space.png')
    assert c.get('/api/projects/audit/resource/cover%20space.png').status_code == 200
    assert c.get('/api/projects/audit/resource/engagement.yaml').status_code == 404
    assert c.get('/api/projects/audit/resource/../engagement.yaml').status_code == 404
    (directory/'originals').mkdir(exist_ok=True)
    Image.new('RGB', (20, 20), 'red').save(directory/'originals/private.png')
    assert c.get('/api/projects/audit/resource/originals/private.png').status_code == 404
    (directory/'img/link.png').symlink_to(directory/'originals/private.png')
    assert c.get('/api/projects/audit/img/link.png').status_code == 404


def test_history_save_validates_before_writing(tmp_path):
    directory = tmp_path/'project'; directory.mkdir()
    history.save(directory, data())
    before = (directory/'engagement.yaml').read_bytes()
    broken = copy.deepcopy(data()); broken['extension'] = float('inf')
    with pytest.raises(ValueError): history.save(directory, broken)
    assert (directory/'engagement.yaml').read_bytes() == before


def test_literal_percent_filename_is_decoded_once(project):
    c, directory = project
    physical = directory/'img/literal%20name.png'
    Image.new('RGB', (20, 20), 'blue').save(physical)
    doc = data(); doc['meta']['branding'] = {'logo': 'img/literal%2520name.png'}
    history.save(directory, doc)
    markup = engine.render_html(engine.build_env(), doc, directory, {}, False, engine.load_lang('es'))
    assert 'literal%2520name.png' in markup
    response = c.post('/api/projects/audit/export/md', json=doc)
    assert response.status_code == 200, response.get_json()
    with zipfile.ZipFile(io.BytesIO(response.data)) as z:
        assert z.read('img/literal%20name.png') == physical.read_bytes()


def test_dates_keep_iso_text_when_loaded_from_yaml(tmp_path):
    p = tmp_path/'engagement.yaml'
    p.write_text('meta: {date: 2026-10-03}\nfindings: []\n')
    assert engine.load_engagement(p)['meta']['date'] == '2026-10-03'


def test_input_byte_and_expanded_text_limits(monkeypatch):
    import input_guard as guard
    monkeypatch.setattr(guard, 'MAX_DOCUMENT_BYTES', 100)
    with pytest.raises(ValueError): guard.load_json(' ' * 101)
    with pytest.raises(ValueError): guard.load_yaml(' ' * 101)
    monkeypatch.setattr(guard, 'MAX_EXPANDED_TEXT', 10)
    with pytest.raises(ValueError): guard.ensure_data_tree({'value': 'x' * 20})


def test_oversized_library_change_preserves_saved_library(tmp_path, monkeypatch):
    import finding_library as library
    import input_guard as guard
    path = tmp_path/'library.json'
    row = library.put(path, {'name': 'Original', 'content': {'title': 'Initial'}})
    before = path.read_bytes()
    monkeypatch.setattr(guard, 'MAX_DOCUMENT_BYTES', len(before) + 50)
    with pytest.raises(ValueError):
        library.put(path, {'name': 'Changed', 'content': {'title': 'x'*500}}, row['uid'])
    assert path.read_bytes() == before


def test_restore_rolls_back_if_directory_swap_fails(tmp_path, monkeypatch):
    from pathlib import Path
    directory = tmp_path/'project'; directory.mkdir()
    original = data(); history.save(directory, original)
    sid = history.checkpoint(directory)['id']
    changed = copy.deepcopy(original); changed['meta']['report_title'] = 'Current'
    history.save(directory, changed)
    before = (directory/'engagement.yaml').read_bytes()
    rename = Path.rename
    def fail_staging(path, target):
        if path.name.startswith('.restore-'):
            raise OSError('simulated directory swap failure')
        return rename(path, target)
    monkeypatch.setattr(Path, 'rename', fail_staging)
    with pytest.raises(OSError): history.restore(directory, sid)
    assert (directory/'engagement.yaml').read_bytes() == before
    assert not list(tmp_path.glob('.restore-*'))
    assert not list(tmp_path.glob('.previous-*'))


def test_native_server_is_single_process_loopback_with_bounded_body():
    server = webapp.create_local_server(0)
    try:
        assert server.socket.getsockname()[0] == '127.0.0.1'
        assert server.adj.threads == 4
        assert server.adj.max_request_body_size == history.MAX_ARCHIVE + 1024 * 1024
        assert server.adj.clear_untrusted_proxy_headers is True
        assert webapp.app.debug is False
    finally:
        server.close()
