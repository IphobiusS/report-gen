"""Independent failure-injection and cross-format contract tests."""
import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from docx import Document
from lxml import html

import app as webapp
import engine
import export
import input_guard
import project_history as history
import validate
from safe_markup import md


def document():
    return {'meta': {'report_title': 'Independent audit', 'lang': 'es', 'theme': 'corporativo'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F1', 'title': 'Proof', 'severity': 'info', 'cvss': 0,
                          'description_md': 'Evidence', 'walkthrough': []}]}


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path)
    monkeypatch.setitem(webapp.app.config, 'TESTING', True)
    c = webapp.app.test_client()
    token = c.get('/api/session').get_json()['csrf']
    c.environ_base['HTTP_X_CSRF_TOKEN'] = token
    assert c.post('/api/projects', json={'slug': 'audit'}).status_code == 200
    return c, tmp_path/'audit'


def test_save_cannot_commit_a_document_its_reader_rejects(api, monkeypatch):
    client, root = api
    response = client.get('/api/projects/audit')
    value = response.get_json(); value['extra'] = {'text': 'a\n'*1000}
    # Scaling the real documented limit keeps the regression quick. The audit
    # also reproduces this case at the actual 12 MiB limit outside pytest.
    assert len(json.dumps(value).encode()) < 7000
    before = files(root)
    monkeypatch.setattr(input_guard, 'MAX_DOCUMENT_BYTES', 7000)
    value['extra']['text'] *= 2
    with pytest.raises(ValueError): history.save(root, value)
    assert files(root) == before
    assert engine.load_engagement(root/'engagement.yaml')


@pytest.mark.parametrize('failure', ['history', 'yaml', 'rename'])
def test_failed_save_preserves_every_prior_project_file(api, monkeypatch, failure):
    _, root = api
    before = files(root); value = engine.load_engagement(root/'engagement.yaml')
    value['meta']['report_title'] = 'Must not partially commit'
    if failure == 'history':
        original = history.checkpoint; calls = 0
        def fail(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('injected post-save history failure')
            return original(*args, **kwargs)
        monkeypatch.setattr(history, 'checkpoint', fail)
    elif failure == 'yaml':
        import storage
        original = storage.os.replace
        def fail(source, target):
            if Path(target).name == 'engagement.yaml': raise OSError('injected YAML commit failure')
            return original(source, target)
        monkeypatch.setattr(storage.os, 'replace', fail)
    else:
        original = Path.rename
        def fail(source, target):
            if source.name.startswith('.transaction-'): raise OSError('injected activation failure')
            return original(source, target)
        monkeypatch.setattr(Path, 'rename', fail)
    with pytest.raises(OSError): history.save(root, value)
    assert files(root) == before
    assert not list(root.parent.glob('.transaction-*'))
    assert not list(root.parent.glob('.previous-*'))


@pytest.mark.parametrize('action', ['register', 'edit'])
def test_evidence_failure_does_not_leave_orphan_files_or_partial_data(api, monkeypatch, action):
    c, root = api; Image.new('RGB', (12, 12), 'red').save(root/'img/shot.png')
    value = document(); uid = '00000000-0000-4000-8000-000000000001'
    if action == 'edit': value['evidence'] = [{'uid': uid, 'src': 'img/shot.png', 'title': 'Proof'}]
    history.save(root, value)
    tag = c.get('/api/projects/audit').headers['ETag']; before = files(root)
    def fail(*args, **kwargs): raise OSError('injected history storage failure')
    monkeypatch.setattr(history, 'save', fail)
    path = '/api/projects/audit/evidence' + ('/'+uid+'/edit' if action == 'edit' else '')
    body = {'operations': [{'type': 'redact', 'x': 0, 'y': 0, 'w': 1, 'h': 1}]} if action == 'edit' else {'src': 'img/shot.png'}
    try:
        response = c.post(path, headers={'If-Match': tag}, json=body)
        assert response.status_code >= 400
    except OSError:
        pass
    assert files(root) == before


SOURCES = [
    '![Proof](./img/%73hot.png)',
    '![Proof][ref]\n\n[ref]: ./img/%73hot.png',
    '![Proof][]\n\n[Proof]: ./img/%73hot.png',
    '![Proof]\n\n[Proof]: ./img/%73hot.png',
]


@pytest.mark.parametrize('source', SOURCES)
def test_all_markdown_image_forms_use_the_project_resource_base(source):
    tree = html.fragment_fromstring(str(md(source, img_base='/api/projects/a/resource/')), create_parent='div')
    assert tree.xpath('.//img/@src') == ['/api/projects/a/resource/img/shot.png']


@pytest.mark.parametrize('source', SOURCES)
def test_redaction_preserves_exportability_and_removes_original_pixels(api, source):
    c, root = api; Image.new('RGB', (12, 12), 'red').save(root/'img/shot.png')
    value = document(); uid = '00000000-0000-4000-8000-000000000001'
    value['evidence'] = [{'uid': uid, 'src': 'img/shot.png', 'title': 'Proof'}]
    value['findings'][0]['description_md'] = source
    value['findings'][0]['walkthrough'] = [{'command': 'cat img/shot.png'}]
    history.save(root, value)
    # Prove the input is a working report before testing the redaction.
    initial = export.export(root/'engagement.yaml', 'md', root.parent/'before.zip')
    with zipfile.ZipFile(initial) as archive: assert archive.read('img/shot.png')
    tag = c.get('/api/projects/audit').headers['ETag']
    response = c.post('/api/projects/audit/evidence/'+uid+'/edit', headers={'If-Match': tag},
                      json={'operations': [{'type': 'redact', 'x': 0, 'y': 0, 'w': 1, 'h': 1}]})
    assert response.status_code == 200
    current = c.get('/api/projects/audit').get_json()
    assert current['findings'][0]['walkthrough'][0]['command'] == 'cat img/shot.png'
    output = c.post('/api/projects/audit/export/md', json=current)
    assert output.status_code == 200, output.get_json()
    with zipfile.ZipFile(io.BytesIO(output.data)) as archive:
        images = [n for n in archive.namelist() if n.endswith('.png')]
        assert len(images) == 1
        with Image.open(io.BytesIO(archive.read(images[0]))) as im:
            assert im.convert('RGB').getextrema() == ((0, 0),)*3


@pytest.mark.parametrize('source,expected', [
    ('    ![Proof](img/shot.png)', '![Proof](img/shot.png)\n'),
    ('``some\n![Proof](img/shot.png)\ncode``', 'some\n![Proof](img/shot.png)\ncode'),
    ('```\n![Proof](img/shot.png)\n```', '![Proof](img/shot.png)\n'),
])
def test_image_examples_in_code_remain_literal(source, expected):
    tree = html.fragment_fromstring(str(md(source)), create_parent='div')
    assert not tree.xpath('.//img')
    assert tree.xpath('.//code')[0].text_content() == expected


@pytest.mark.parametrize('codepoint', [0, 0x1b, 0xb, 0xfffe, 0xffff])
def test_nonportable_text_is_rejected_before_saving(api, codepoint):
    c, root = api; value = c.get('/api/projects/audit'); before = files(root)
    data = value.get_json(); data['meta']['report_title'] = 'before'+chr(codepoint)+'after'
    response = c.put('/api/projects/audit', headers={'If-Match': value.headers['ETag']}, json=data)
    assert response.status_code == 422
    assert files(root) == before


@pytest.mark.parametrize('sections', [True, False])
def test_absent_cvss_vector_is_portable_to_word(tmp_path, sections):
    value = document(); value['findings'][0]['cvss_vector'] = None
    if not sections: value.pop('report')
    assert not any(level == 'error' for level, _ in validate.validate(value))
    history.save(tmp_path, value)
    output = export.export(tmp_path/'engagement.yaml', 'docx', tmp_path.parent/'null-vector.docx')
    doc = Document(output)
    assert 'Proof' in '\n'.join(p.text for p in doc.paragraphs)


def test_yaml_budget_applies_while_nodes_are_being_created(monkeypatch):
    import yaml.composer
    original = yaml.composer.ScalarNode; created = []
    class Counted(original):
        def __init__(self, *args, **kwargs):
            created.append(1); super().__init__(*args, **kwargs)
    monkeypatch.setattr(yaml.composer, 'ScalarNode', Counted)
    monkeypatch.setattr(input_guard, 'MAX_NODES', 40)
    with pytest.raises(ValueError): input_guard.load_yaml('values: ['+', '.join('word' for _ in range(1000))+']')
    assert len(created) <= 40


@pytest.mark.parametrize('literal', [
    '`img/shot.png`',
    '```\n![Example](img/shot.png)\n```',
    '~~~\n![Example](img/shot.png)\n~~~',
    '    ![Example](img/shot.png)',
])
def test_redaction_does_not_rewrite_nearby_code_examples(literal):
    import evidence
    text = '![Real](img/shot.png)\n\n'+literal
    result = evidence.replace_references({'body': text}, 'img/shot.png', 'img/masked.png')['body']
    assert result == '![Real](img/masked.png)\n\n'+literal


def test_failed_project_creation_does_not_reserve_the_name(api, monkeypatch):
    c, root = api
    def fail(*args, **kwargs): raise OSError('injected initial save failure')
    with monkeypatch.context() as context:
        context.setattr(history, 'save', fail)
        assert c.post('/api/projects', json={'slug': 'new-project'}).status_code == 503
    assert not (root.parent/'new-project').exists()
    assert c.post('/api/projects', json={'slug': 'new-project'}).status_code == 200


def test_cleanup_failure_is_not_reported_as_a_failed_commit(api, monkeypatch, caplog):
    c, root = api; response = c.get('/api/projects/audit')
    value = response.get_json(); value['meta']['report_title'] = 'Successfully committed'
    original = history.shutil.rmtree
    def fail(path, *args, **kwargs):
        if Path(path).name.startswith('.previous-'): raise OSError('injected cleanup failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(history.shutil, 'rmtree', fail)
    result = c.put('/api/projects/audit', json=value, headers={'If-Match': response.headers['ETag']})
    assert result.status_code == 200
    assert engine.load_engagement(root/'engagement.yaml')['meta']['report_title'] == 'Successfully committed'
    assert 'pendiente de limpieza' in caplog.text


def test_staging_copy_fallback_preserves_resources(api, monkeypatch):
    _, root = api; Image.new('RGB', (12, 12), 'blue').save(root/'img/shot.png')
    image = (root/'img/shot.png').read_bytes()
    def unsupported(*args, **kwargs): raise OSError('hard links unavailable')
    monkeypatch.setattr(history.os, 'link', unsupported)
    data = engine.load_engagement(root/'engagement.yaml'); data['meta']['report_title'] = 'Copy fallback'
    history.save(root, data)
    assert (root/'img/shot.png').read_bytes() == image


def test_backup_budget_includes_manifest_bytes(api, monkeypatch):
    _, root = api
    blob = history.export_bundle(root)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        total = sum(entry.file_size for entry in archive.infolist())
    monkeypatch.setattr(history, 'MAX_EXPANDED', total - 10)
    with pytest.raises(ValueError): history.export_bundle(root)


def test_backup_refuses_case_collisions_its_importer_cannot_accept(api):
    _, root = api
    for name in ['a.png', 'A.png']: Image.new('RGB', (8, 8), 'blue').save(root/'img'/name)
    with pytest.raises(ValueError, match='mayúsculas'): history.export_bundle(root)


def test_backup_refuses_corrupt_historical_objects(api):
    _, root = api
    record = history.history(root)[0]
    path = root/'history/objects'/record['files']['engagement.yaml']
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='alterado'): history.export_bundle(root)
