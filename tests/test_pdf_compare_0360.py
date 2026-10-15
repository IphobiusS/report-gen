"""Actual PDF pixels, positional changes, privacy and worker resource bounds."""
from base64 import b64decode
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, FloatObject, NameObject
import pytest
from werkzeug.datastructures import MultiDict

import app as api
import pdf_compare
from _support import auth_client


def pdf(pages=1, square=None, size=(180, 240), metadata=None):
    stream, writer = BytesIO(), PdfWriter()
    if metadata:
        writer.add_metadata({'/Title': metadata})
    for index in range(pages):
        page = writer.add_blank_page(*size)
        if square is not None:
            content = DecodedStreamObject()
            content.set_data(('q ' + ' '.join(str(value) for value in square) +
                              f' rg {25 + index * 2} 40 35 25 re f Q\n').encode('ascii'))
            page[NameObject('/Contents')] = writer._add_object(content)
    writer.write(stream)
    return stream.getvalue()


def blank(pages=1, size=(180, 240), encrypted=False, unit=None):
    stream, writer = BytesIO(), PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(*size)
        if unit is not None:
            page[NameObject('/UserUnit')] = FloatObject(unit)
    if encrypted is not False:
        writer.encrypt(encrypted)
    writer.write(stream)
    return stream.getvalue()


def manifest(html):
    value = re.search(r'<pre id="comparison-manifest" hidden>(.*?)</pre>', html.decode('utf-8'), re.S)
    assert value, 'comparison must include its machine-readable provenance'
    return json.loads(unescape(value.group(1)))


def images(html):
    values = {}
    for kind, payload in re.findall(r'<img class="([a-z]+)-image"[^>]*src="data:image/png;base64,([A-Za-z0-9+/=]+)"', html.decode()):
        image = Image.open(BytesIO(b64decode(payload)))
        assert image.format == 'PNG'
        values.setdefault(kind, []).append(image.convert('RGB'))
    return values


def test_identical_pdf_reports_hashes_exact_pixels_and_no_semantic_claim():
    raw = pdf(square=(.2, .4, .9))
    output = pdf_compare.compare(raw, raw, 'en')
    value, picture = manifest(output), images(output)
    assert value['before_sha256'] == value['after_sha256'] == sha256(raw).hexdigest()
    assert value['identical_pdf_bytes'] is True and value['semantic_equivalence_verified'] is False
    assert value['rgb_tolerance'] == 0
    assert value['summary'] == dict(unchanged=1, changed=0, added=0, removed=0, dimensions_changed=0, total_pages=1)
    assert value['pages'][0]['changed_pixels'] == 0
    assert picture['before'][0].tobytes() == picture['after'][0].tobytes()
    assert picture['before'][0].size == tuple(value['pages'][0]['canvas_pixels'])


def test_changed_pixels_match_independently_decoded_original_images():
    output = pdf_compare.compare(pdf(square=(0, 0, 0)), pdf(square=(.8, .1, .1)))
    value, rendered = manifest(output), images(output)
    first, second = rendered['before'][0], rendered['after'][0]
    actual = sum(a != b for a, b in zip(first.getdata(), second.getdata()))
    assert 0 < actual < first.width * first.height
    assert value['pages'][0]['changed_pixels'] == actual and value['summary']['changed'] == 1
    assert sum(pixel == (210, 15, 110) for pixel in rendered['difference'][0].getdata()) == actual


def test_metadata_changes_are_not_claimed_as_pixel_changes():
    value = manifest(pdf_compare.compare(pdf(metadata='old'), pdf(metadata='new')))
    assert value['identical_pdf_bytes'] is False and value['summary']['unchanged'] == 1


@pytest.mark.parametrize('counts,status', [((1, 2), 'added'), ((2, 1), 'removed')])
def test_added_removed_pages_retain_position_and_full_surface(counts, status):
    output = pdf_compare.compare(blank(counts[0]), blank(counts[1]))
    value = manifest(output)
    assert value['alignment'] == 'page_position_top_left'
    assert value['summary'][status] == value['summary']['unchanged'] == 1
    row = value['pages'][1]
    assert row['status'] == status and row['changed_pixels'] == row['total_pixels']
    assert images(output)['difference'][1].getextrema() == ((210, 210), (15, 15), (110, 110))


def test_size_change_preserves_display_scale_and_reports_white_page_geometry():
    output = pdf_compare.compare(blank(size=(180, 240)), blank(size=(240, 240)))
    row, picture = manifest(output)['pages'][0], images(output)
    assert row['status'] == 'dimensions_changed' and row['changed_pixels'] == 0
    assert row['before_points'] == [180, 240] and row['after_points'] == [240, 240]
    assert row['canvas_pixels'] == [320, 320]
    assert picture['before'][0].size == picture['after'][0].size == picture['difference'][0].size == (320, 320)


@pytest.mark.parametrize('language,title', [('es', 'Comparación visual de PDF'), ('en', 'Visual PDF comparison'), ('pt-BR', 'Comparação visual de PDF')])
def test_static_localized_html_excludes_active_pdf_content_and_injection(language, title):
    writer, source = PdfWriter(), BytesIO()
    writer.add_blank_page(width=180, height=240)
    writer.add_metadata({'/Title': '</title><script src="https://hostile.test/x.js">alert(1)</script>'})
    writer.add_js('app.alert("PDF action must never execute");')
    writer.write(source)
    output = pdf_compare.compare(source.getvalue(), blank(), language).decode('utf-8')
    assert title in output and 'hostile.test' not in output and 'alert(' not in output
    assert not any(tag in output for tag in ('<script', '<iframe', '<object'))
    assert 'default-src &#x27;none&#x27;' in output and 'script-src &#x27;none&#x27;' in output
    class CheckResources(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                assert not key.startswith('on')
                if key in ('src', 'href', 'srcset', 'action'):
                    assert tag == 'img' and key == 'src' and value.startswith('data:image/png;base64,')
    CheckResources().feed(output)
    assert manifest(output.encode())['language'] == ('pt' if language == 'pt-BR' else language)


@pytest.mark.parametrize('raw', [b'', b'%PDF-broken', b'<html>pretend PDF</html>'])
def test_malformed_pdf_has_controlled_error(raw):
    with pytest.raises(ValueError, match='Invalid PDF'):
        pdf_compare.compare(raw, blank(), 'en')


@pytest.mark.parametrize('password', ['', 'secret'])
def test_encryption_rejected_even_with_empty_password(password):
    with pytest.raises(ValueError, match='Encrypted PDFs'):
        pdf_compare.compare(blank(encrypted=password), blank(), 'en')


@pytest.mark.parametrize('raw', [blank(0), blank(pdf_compare.MAX_PAGES + 1)])
def test_page_limits_before_rasterization(raw):
    with pytest.raises(ValueError, match='between 1 and 80'):
        pdf_compare.compare(raw, blank(), 'en')


@pytest.mark.parametrize('raw', [blank(size=(15000, 240)), blank(unit=2)])
def test_unsupported_geometry_rejected(raw):
    with pytest.raises(ValueError, match='dimensions|UserUnit'):
        pdf_compare.compare(raw, blank(), 'en')


def test_full_document_pixel_budget_checked_before_rendering():
    with pytest.raises(ValueError, match='64 million pixels'):
        pdf_compare.compare(blank(80, size=(612, 792)), blank(), 'en')


def test_byte_and_language_limits_before_spawn(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('must not start an invalid worker')
    monkeypatch.setattr(pdf_compare, '_execute', forbidden)
    with pytest.raises(ValueError, match='16 MiB'):
        pdf_compare.compare(b'%PDF-' + b'x' * pdf_compare.MAX_PDF, blank(), 'en')
    with pytest.raises(ValueError, match='Idiomas admitidos'):
        pdf_compare.compare(blank(), blank(), 'fr')


def test_busy_worker_rejects_second_comparison():
    assert pdf_compare._WORKERS.acquire(blocking=False)
    try:
        with pytest.raises(ValueError, match='already running'):
            pdf_compare.compare(blank(), blank(), 'en')
    finally:
        pdf_compare._WORKERS.release()


def test_native_worker_can_establish_os_limits_before_parsing():
    # This trusted test-only child exposes an OS setup exception in native CI.
    # The production child continues to return generic, private diagnostics.
    probe = subprocess.run([sys.executable, '-c', '''
import mmap
import sys
import pdf_compare
keeper = pdf_compare._resource_limits()
print("limits-ready", flush=True)
if sys.platform != 'win32':
    # Reserve address space without touching pages or allocating physical GB.
    try:
        region = mmap.mmap(-1, 2 * pdf_compare.MAX_MEMORY)
    except (OSError, ValueError, MemoryError):
        print("reservation-blocked", flush=True)
    else:
        region.close()
        raise AssertionError("Virtual reservation exceeded the enforced budget")
'''],
        cwd=Path(pdf_compare.__file__).parent, capture_output=True, timeout=15, check=False)
    assert probe.returncode == 0, probe.stderr.decode('utf-8', errors='replace')
    assert b'limits-ready' in probe.stdout
    if sys.platform != 'win32':
        assert b'reservation-blocked' in probe.stdout


def test_darwin_virtual_budget_keeps_baseline_and_inherited_stricter_limits():
    class Limits:
        RLIMIT_AS, RLIM_INFINITY = 5, -1
        value = (-1, -1)
        def getrlimit(self, kind):
            assert kind == self.RLIMIT_AS
            return self.value
        def setrlimit(self, kind, value):
            assert kind == self.RLIMIT_AS
            self.value = value
    resource = Limits()
    baseline = 400 * 1024**3  # macOS shared mappings can be very large.
    memory = SimpleNamespace(virtual_size=lambda pid: baseline)
    result = pdf_compare._darwin_virtual_limit(resource, memory)
    assert result['baseline_virtual_bytes'] == baseline
    assert resource.value == (baseline + pdf_compare.MAX_MEMORY,) * 2
    resource.value = (baseline + 1024, baseline + 2048)
    pdf_compare._darwin_virtual_limit(resource, memory)
    assert resource.value == (baseline + 1024,) * 2
    resource.value = (baseline, baseline)
    with pytest.raises(pdf_compare._Rejected, match='limits'):
        pdf_compare._darwin_virtual_limit(resource, memory)


@pytest.mark.parametrize('mode', ['over_budget', 'measurement_error', 'deadline'])
def test_memory_supervisor_kills_and_reaps_actual_child_on_every_failure(mode):
    def read(pid):
        assert pid == process.pid
        if mode == 'measurement_error':
            raise OSError('synthetic native measurement failure')
        return pdf_compare.MAX_MEMORY + 1 if mode == 'over_budget' else 1
    with subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL) as process:
        expected = {'over_budget': pdf_compare._Rejected, 'measurement_error': OSError,
                    'deadline': subprocess.TimeoutExpired}[mode]
        with pytest.raises(expected):
            pdf_compare._supervise_memory(process, .1 if mode == 'deadline' else 2, read)
        assert process.returncode is not None and process.poll() is not None
        if os.name != 'nt':
            with pytest.raises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)  # Already reaped, not a zombie.


def test_memory_supervisor_reaps_normal_exit_without_a_false_limit_failure():
    with subprocess.Popen([sys.executable, '-c', 'pass'], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL) as process:
        assert pdf_compare._supervise_memory(process, 5, lambda pid: 1) == 0
        assert process.returncode == 0


def test_native_darwin_physical_sampler_and_honest_capabilities():
    policy = pdf_compare.capabilities()['memory_policy']
    if sys.platform == 'darwin':
        memory = pdf_compare._DarwinMemory()
        assert memory.virtual_size(os.getpid()) > 0
        assert memory.physical_size(os.getpid()) > 0
        assert policy['instantaneous_physical_memory_ceiling'] is False
        assert policy['sampling_interval_ms'] == 50
        # A one-byte threshold proves native measurement and kill/reap without
        # stressing the host: an ordinary Python process already exceeds it.
        with subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            with pytest.raises(pdf_compare._Rejected, match='limits'):
                pdf_compare._supervise_memory(process, 5, memory.physical_size, threshold=1)
            assert process.returncode is not None
    else:
        assert policy['hard_limit_bytes'] == pdf_compare.MAX_MEMORY


def test_timeout_deletes_inputs_releases_capacity_and_uses_no_pipes(monkeypatch):
    directories = []
    def timeout(command, **kwargs):
        path = Path(command[-2]); directories.append(path)
        assert (path / 'before.pdf').read_bytes().startswith(b'%PDF-')
        assert kwargs['timeout'] == pdf_compare.TIMEOUT
        assert kwargs['stdout'] == kwargs['stderr'] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
    monkeypatch.setattr(pdf_compare, '_execute', timeout)
    with pytest.raises(ValueError, match='exceeded 45 seconds'):
        pdf_compare.compare(blank(), blank(), 'en')
    assert directories and all(not directory.exists() for directory in directories)
    assert pdf_compare._WORKERS.acquire(blocking=False)
    pdf_compare._WORKERS.release()


def test_parent_bounds_output_and_cleans_up(monkeypatch):
    directories = []
    monkeypatch.setattr(pdf_compare, 'MAX_OUTPUT', 100)
    def output(command, **kwargs):
        path = Path(command[-2]); directories.append(path)
        (path / 'comparison.html').write_bytes(b'<!doctype html>' + b'x' * 101)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(pdf_compare, '_execute', output)
    with pytest.raises(ValueError, match='32 MiB'):
        pdf_compare.compare(blank(), blank(), 'en')
    assert all(not path.exists() for path in directories)


def test_child_output_budget_before_unbounded_html(monkeypatch):
    monkeypatch.setattr(pdf_compare, 'MAX_OUTPUT', 1024)
    with pytest.raises(pdf_compare._Rejected, match='output'):
        pdf_compare._comparison(blank(), blank(), 'en')


def test_unknown_worker_failure_is_generic_and_cleanup_complete(monkeypatch):
    directories = []
    def failure(command, **kwargs):
        path = Path(command[-2]); directories.append(path)
        (path / 'status').write_text('secret-third-party-error', encoding='ascii')
        return SimpleNamespace(returncode=3)
    monkeypatch.setattr(pdf_compare, '_execute', failure)
    with pytest.raises(ValueError, match='memory and process limits') as error:
        pdf_compare.compare(blank(), blank(), 'en')
    assert 'secret' not in str(error.value) and all(not path.exists() for path in directories)


@pytest.fixture
def client():
    return auth_client(api.app)


def upload(client, before=None, after=None, language='en', **kwargs):
    return client.post('/api/pdf-compare', data={
        'before': (BytesIO(blank() if before is None else before), '../../sensitive-before.pdf'),
        'after': (BytesIO(blank() if after is None else after), '<script>after.pdf'),
        'language': language,
    }, **kwargs)


def test_endpoint_read_only_private_download_and_strict_csp(client, tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    result = upload(client, language='pt')
    assert result.status_code == 200, result.get_json(silent=True)
    assert result.mimetype == 'text/html' and result.headers['Content-Disposition'].startswith('attachment;')
    assert result.headers['Content-Language'] == 'pt-BR' and result.headers['Cache-Control'] == 'no-store'
    assert "default-src 'none'" in result.headers['Content-Security-Policy']
    assert "script-src 'none'" in result.headers['Content-Security-Policy']
    assert manifest(result.data)['language'] == 'pt'
    assert b'sensitive-before' not in result.data and b'<script>after' not in result.data
    assert list(projects.iterdir()) == []
    caps = client.get('/api/pdf-compare/capabilities').json
    assert caps['available'] and caps['max_pages_per_pdf'] == 80
    assert caps['external_services'] is False and caps['server_retention'] is False


def test_endpoint_csrf_origin_content_type_and_duplicate_fields(client):
    assert upload(api.app.test_client()).status_code == 403
    assert upload(client, headers={'Origin': 'https://hostile.test'}).status_code == 403
    assert client.post('/api/pdf-compare', json={}).status_code == 415
    data = MultiDict([('before', (BytesIO(blank()), 'a.pdf')),
                      ('before', (BytesIO(blank()), 'again.pdf')), ('after', (BytesIO(blank()), 'b.pdf'))])
    assert client.post('/api/pdf-compare', data=data).status_code == 415
    duplicate = MultiDict([('before', (BytesIO(blank()), 'a.pdf')), ('after', (BytesIO(blank()), 'b.pdf')),
                           ('language', 'es'), ('language', 'pt')])
    assert client.post('/api/pdf-compare', data=duplicate).status_code == 415
    assert upload(client, language='fr').status_code == 422


def test_endpoint_error_language_and_request_body_limit(client):
    response = upload(client, before=b'broken', language='pt', headers={'X-UI-Language': 'pt'})
    assert response.status_code == 422 and 'PDF inválido' in response.json['error']
    assert response.headers['Content-Language'] == 'pt-BR'
    response = client.post('/api/pdf-compare', data=b'x', content_type='multipart/form-data',
                           environ_overrides={'CONTENT_LENGTH': str(2 * pdf_compare.MAX_PDF + 1024 * 1024 + 1)})
    assert response.status_code == 413


def test_complete_explicit_language_parity():
    assert set(pdf_compare._TEXT['es']) == set(pdf_compare._TEXT['en']) == set(pdf_compare._TEXT['pt'])
    assert all(pdf_compare.error(code, lang) for code in pdf_compare._ERRORS for lang in ('es', 'en', 'pt'))
