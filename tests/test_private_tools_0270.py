"""Authenticated backups and explicit bounded local OCR, including real Tesseract."""
from io import BytesIO
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont
import pytest
import app as api
import private_backup as encrypted
import privacy_ocr as ocr
import project_history
import workspace_backup
from storage import revision
from _support import auth_client

PASSWORD = 'test-only strong passphrase 0270'


def paths(root):
    return root/'projects', root/'library/findings.json', root/'library/designs.json'


def project(root):
    locations = paths(root)
    project_history.save(locations[0]/'example', {'meta': {'report_title': 'PRIVATE_BACKUP_SENTINEL', 'lang': 'es'}, 'findings': []})
    return locations


def configure(monkeypatch, locations):
    monkeypatch.setattr(api, 'PROJECTS', locations[0])
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(locations[1]))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(locations[2]))
    return auth_client(api.app)


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def image_blob(text='api_key=TESTONLYSECRET0123456789'):
    image = Image.new('RGB', (1500, 160), 'white')
    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
    if font.exists():
        font = ImageFont.truetype(str(font), 42)
    else:
        font = ImageFont.load_default(size=42)
    ImageDraw.Draw(image).text((30, 45), text, font=font, fill='black')
    out = BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def test_encrypted_roundtrip_randomized_and_no_source_mutation(tmp_path):
    source = project(tmp_path/'source')
    before = tree(tmp_path/'source')
    first = encrypted.export_encrypted(*source, PASSWORD)
    second = encrypted.export_encrypted(*source, PASSWORD)
    assert first != second and first.startswith(encrypted.MAGIC)
    assert b'PRIVATE_BACKUP_SENTINEL' not in first and not first.startswith(b'PK')
    assert tree(tmp_path/'source') == before
    target = paths(tmp_path/'target')
    assert encrypted.restore_encrypted(first, *target, PASSWORD)['projects'] == 1
    assert b'PRIVATE_BACKUP_SENTINEL' in (target[0]/'example/engagement.yaml').read_bytes()
    with pytest.raises(ValueError, match='vacía'):
        encrypted.restore_encrypted(second, *target, PASSWORD)


@pytest.mark.parametrize('change', ['password', 'salt', 'nonce', 'ciphertext', 'tag', 'truncated', 'version'])
def test_bad_encrypted_input_never_touches_destination(tmp_path, change):
    payload = encrypted.export_encrypted(*project(tmp_path/'source'), PASSWORD)
    password = PASSWORD
    if change == 'password':
        password += 'incorrect'
    elif change == 'truncated':
        payload = payload[:-1]
    else:
        offset = {'salt': len(encrypted.MAGIC), 'nonce': encrypted.HEADER_BYTES - 1,
                  'ciphertext': encrypted.HEADER_BYTES, 'tag': len(payload)-1,
                  'version': len(encrypted.MAGIC)-1}[change]
        payload = payload[:offset] + bytes([payload[offset] ^ 1]) + payload[offset+1:]
    target = paths(tmp_path/'target')
    with pytest.raises(ValueError):
        encrypted.restore_encrypted(payload, *target, password)
    assert not target[0].parent.exists()


def test_authenticated_non_archive_still_rejected_without_activation(tmp_path):
    payload = encrypted.encrypt(b'not a workspace', PASSWORD)
    target = paths(tmp_path/'target')
    with pytest.raises(ValueError):
        encrypted.restore_encrypted(payload, *target, PASSWORD)
    assert not target[0].parent.exists()


def test_invalid_envelope_and_oversize_reject_before_kdf(monkeypatch):
    monkeypatch.setattr(encrypted, '_crypto', lambda: pytest.fail('must reject before crypto'))
    with pytest.raises(ValueError):
        encrypted.decrypt(b'bad', PASSWORD)
    with pytest.raises(ValueError):
        encrypted.encrypt(b'x', 'short')
    monkeypatch.setattr(workspace_backup, 'MAX_ARCHIVE', 4)
    with pytest.raises(ValueError):
        encrypted.encrypt(b'12345', PASSWORD)


def test_encrypted_api_restore_and_plain_zip_compatibility(tmp_path, monkeypatch):
    source = project(tmp_path/'source')
    client = configure(monkeypatch, source)
    response = client.post('/api/workspace/backup/encrypted', json={'password': PASSWORD})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert '.rgbackup' in response.headers['Content-Disposition']
    assert client.post('/api/workspace/backup/encrypted', json={}).status_code == 422
    target = paths(tmp_path/'target')
    client = configure(monkeypatch, target)
    bad = client.post('/api/workspace/restore', data={'file': (BytesIO(response.data), 'private.rgbackup'), 'password': PASSWORD+'no'})
    assert bad.status_code == 422 and not target[0].parent.exists()
    ok = client.post('/api/workspace/restore', data={'file': (BytesIO(response.data), 'private.rgbackup'), 'password': PASSWORD})
    assert ok.status_code == 200 and ok.get_json()['authenticated'] is True
    target2 = paths(tmp_path/'plain')
    client = configure(monkeypatch, target2)
    plain = workspace_backup.export_workspace(*source)
    assert client.post('/api/workspace/restore', data={'file': (BytesIO(plain), 'plain.zip')}).status_code == 200
    assert PASSWORD not in json.dumps(ok.get_json())


def test_ocr_unavailable_and_image_limits_are_not_clean_results(monkeypatch):
    monkeypatch.setattr(ocr.shutil, 'which', lambda _: None)
    result = ocr.inspect_image(image_blob())
    assert result['status'] == 'unavailable' and not result['complete'] and result['manual_review_required']
    monkeypatch.setattr(ocr.shutil, 'which', lambda _: '/usr/bin/tesseract')
    monkeypatch.setattr(ocr, 'MAX_PIXELS', 10)
    assert ocr.inspect_image(image_blob())['status'] == 'image_limit'
    with pytest.raises(ValueError):
        ocr.inspect_image(b'not an image')


def test_ocr_tsv_flags_locations_without_returning_secrets():
    blob = b'level\tpage_num\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t10\t20\t800\t40\t90\tpassword=TEST_ONLY_SECRET_0270\n'
    result = ocr._scan_tsv(blob)
    assert result['status'] == 'completed'
    assert result['alerts'] == [{'kind': 'credential', 'count': 1, 'bounds': [10, 20, 800, 40]}]
    assert 'TEST_ONLY_SECRET' not in json.dumps(result) and 'password=' not in json.dumps(result)


def test_ocr_limits_output_and_does_not_treat_no_words_as_no_secrets(monkeypatch):
    assert ocr._scan_tsv(b'level\ttext\n')['words_recognized'] == 0
    monkeypatch.setattr(ocr, 'MAX_OCR_BYTES', 10)
    assert ocr._scan_tsv(b'x'*11)['status'] == 'output_limit'


def test_real_tesseract_uses_local_image_and_redacts_response(tmp_path):
    if not shutil.which('tesseract'):
        pytest.skip('Optional system Tesseract is absent')
    result = ocr.inspect_image(image_blob())
    assert result['status'] == 'completed', result
    assert result['words_recognized'] > 0 and any(a['kind'] == 'credential' for a in result['alerts'])
    assert 'TESTONLYSECRET' not in json.dumps(result) and 'api_key' not in json.dumps(result)
    assert result['manual_review_required'] and result['complete'] is False


def test_ocr_api_only_published_images_and_current_revision(tmp_path, monkeypatch):
    locations = project(tmp_path)
    directory = locations[0]/'example'
    (directory/'img').mkdir()
    (directory/'img/proof.png').write_bytes(image_blob())
    data = {'meta': {'report_title': 'Example', 'lang': 'es'},
            'report': {'sections': [{'key': 'custom', 'title': 'Evidence', 'body': '![Proof](img/proof.png)'}]}, 'findings': []}
    project_history.save(directory, data)
    client = configure(monkeypatch, locations)
    before = tree(directory)
    monkeypatch.setattr(ocr, 'inspect_image', lambda _: {'status': 'completed', 'alerts': [], 'words_recognized': 1, 'complete': False})
    response = client.post('/api/projects/example/privacy/ocr', json={'name': 'img/proof.png'}, headers={'If-Match': revision(directory/'engagement.yaml')})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['language'] == 'eng'
    assert response.headers['Cache-Control'] == 'no-store'
    assert tree(directory) == before
    assert client.post('/api/projects/example/privacy/ocr', json={'name': '../secret'}, headers={'If-Match': revision(directory/'engagement.yaml')}).status_code == 404
    assert client.post('/api/projects/example/privacy/ocr', json={'name': 'img/proof.png'}, headers={'If-Match': 'stale'}).status_code == 409
    assert client.post('/api/projects/example/privacy/ocr', json={'name': 'img/proof.png'}).status_code == 428


@pytest.mark.parametrize('kind', ['image_limit', 'animation_unsupported'])
def test_publication_ocr_rejects_headers_before_cleaning_or_decoding(tmp_path, monkeypatch, kind):
    import publication
    if kind == 'image_limit':
        blob = image_blob()
        monkeypatch.setattr(ocr, 'MAX_PIXELS', 10)
    else:
        out = BytesIO()
        Image.new('RGB', (10, 10), 'red').save(out, format='GIF', save_all=True,
                  append_images=[Image.new('RGB', (10, 10), 'blue')], duration=100)
        blob = out.getvalue()
    monkeypatch.setattr(publication, 'clean_image', lambda _: pytest.fail('must reject before cleaning'))
    monkeypatch.setattr(ocr, 'inspect_image', lambda _: pytest.fail('must reject before decoding'))
    locations = project(tmp_path)
    directory = locations[0]/'example'
    (directory/'img').mkdir()
    name = 'img/proof.' + ('gif' if kind == 'animation_unsupported' else 'png')
    (directory/name).write_bytes(blob)
    project_history.save(directory, {'meta': {'lang': 'es'}, 'report': {'sections': [
        {'key': 'custom', 'title': 'Evidence', 'body': f'![Proof]({name})'}]}, 'findings': []})
    client = configure(monkeypatch, locations)
    response = client.post('/api/projects/example/privacy/ocr', json={'name': name},
                           headers={'If-Match': revision(directory/'engagement.yaml')})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['status'] == kind
    assert response.get_json()['manual_review_required'] is True


def test_unavailable_ocr_never_decodes_publication_derivative(monkeypatch):
    import publication
    monkeypatch.setattr(ocr, 'available', lambda: False)
    monkeypatch.setattr(publication, 'clean_image', lambda _: pytest.fail('no need to decode without engine'))
    assert ocr.inspect_publication_image(image_blob())['status'] == 'unavailable'


def test_truncated_pixels_raise_input_error_not_storage_failure(monkeypatch):
    from PIL import ImageFile
    from error_messages import language_scope
    import publication
    monkeypatch.setattr(ocr.shutil, 'which', lambda _: '/usr/bin/tesseract')
    monkeypatch.setattr(ocr, 'available', lambda: True)
    # WeasyPrint sets this process-wide flag to True. Integrity guards must not
    # depend on import order or temporarily mutate Pillow shared by other work.
    for allow_truncated in (False, True):
        with monkeypatch.context() as state, language_scope('es'):
            state.setattr(ImageFile, 'LOAD_TRUNCATED_IMAGES', allow_truncated)
            for image_format in ('PNG', 'JPEG', 'WEBP', 'GIF'):
                stream = BytesIO()
                Image.new('RGB', (12, 9), 'white').save(stream, format=image_format)
                valid = stream.getvalue()
                assert ocr.preflight(valid) is None
                assert ImageFile.LOAD_TRUNCATED_IMAGES is allow_truncated
                # Missing terminal bytes plus a deeper truncation exercise the
                # container closure and payload boundary, not just its header.
                for damaged in (valid[:-2], valid[:len(valid)//2]):
                    with monkeypatch.context() as guard:
                        guard.setattr(publication, 'clean_image', lambda _: pytest.fail('reject before cleaning'))
                        for inspect in (ocr.preflight, ocr.inspect_image, ocr.inspect_publication_image):
                            with pytest.raises(ValueError, match='Imagen no válida'):
                                inspect(damaged)
                            assert ImageFile.LOAD_TRUNCATED_IMAGES is allow_truncated
