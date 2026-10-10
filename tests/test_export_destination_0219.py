"""Export destinations cannot replace project inputs or their real aliases."""
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import zipfile

from docx import Document
from lxml import html
from PIL import Image
import fitz
import pytest

import engine
import export
from wizard import dump_yaml
from _support import auth_client


CANARY = 'SYNTHETIC_SOURCE_CANARY'


def document():
    return {'meta': {'report_title': 'Synthetic source preservation', 'lang': 'en'},
            'findings': [{'id': 'F01', 'title': 'Synthetic condition', 'severity': 'info',
                          'cvss': 0, 'description_md': CANARY}]}


def create_source(tmp_path, data=None, name='engagement.yaml'):
    source = tmp_path / name
    dump_yaml(data or document(), source)
    return source


def fingerprint(directory):
    return {str(path.relative_to(directory)): sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()}


def alias_path(source, alias):
    if alias == 'direct': return source
    target = source.parent / ('input-alias' + source.suffix)
    if alias == 'symlink': target.symlink_to(source.name)
    else: target.hardlink_to(source)
    return target


@pytest.mark.parametrize('fmt', ['html', 'docx', 'pdf'])
@pytest.mark.parametrize('alias', ['direct', 'symlink', 'hardlink'])
def test_public_export_rejects_source_as_output_before_any_write(tmp_path, fmt, alias):
    source = create_source(tmp_path)
    target = alias_path(source, alias)
    before = fingerprint(tmp_path)
    with pytest.raises(ValueError, match='Output destination matches a project input'):
        export.export(source, fmt, target)
    assert fingerprint(tmp_path) == before
    assert not list(tmp_path.glob('.export-*'))


@pytest.mark.parametrize('alias', ['direct', 'symlink', 'hardlink'])
def test_markdown_checks_effective_zip_destination(tmp_path, alias):
    # The loader accepts documentary YAML independently of its filename.
    source = create_source(tmp_path, name='engagement.zip')
    target = alias_path(source, alias)
    before = fingerprint(tmp_path)
    with pytest.raises(ValueError, match='Output destination matches a project input'):
        export.export(source, 'md', target)
    assert fingerprint(tmp_path) == before
    assert not list(tmp_path.glob('.export-*'))


@pytest.mark.parametrize('fmt', ['html', 'docx', 'pdf'])
@pytest.mark.parametrize('reference', ['figure', 'markdown', 'branding', 'original', 'annex'])
def test_export_rejects_referenced_or_private_input_as_output(tmp_path, fmt, reference):
    data = document()
    image = tmp_path / 'img' / 'evidence space.png'
    image.parent.mkdir()
    Image.new('RGB', (8, 8), 'white').save(image)
    if reference == 'figure':
        data['findings'][0]['walkthrough'] = [{'figure': {'src': 'img/evidence%20space.png'}}]
        target = image
    elif reference == 'markdown':
        data['findings'][0]['description_md'] += '\n\n![Synthetic](img/evidence%20space.png)'
        target = image
    elif reference == 'branding':
        data['meta']['branding'] = {'logo': 'img/evidence%20space.png'}
        target = image
    elif reference == 'original':
        target = tmp_path / 'originals' / 'original.png'
        target.parent.mkdir()
        target.write_bytes(image.read_bytes())
        data['evidence'] = [{'uid': '00000000-0000-0000-0000-000000000001',
                             'title': 'Synthetic', 'src': 'img/evidence%20space.png',
                             'original': 'originals/original.png'}]
    else:
        target = tmp_path / 'attachments' / ('a' * 32 + '.pdf')
        target.parent.mkdir()
        target.write_bytes(b'%PDF-1.7\nSynthetic private input\n')
        data['attachments'] = [{'uid': '00000000-0000-0000-0000-000000000002',
                                'name': 'private.pdf', 'member': 'attachments/' + target.name,
                                'sha256': sha256(target.read_bytes()).hexdigest(),
                                'include': False, 'reviewed': False, 'required': False}]
    source = create_source(tmp_path, data)
    before = fingerprint(tmp_path)
    with pytest.raises(ValueError, match='Output destination matches a project input'):
        export.export(source, fmt, target)
    assert fingerprint(tmp_path) == before


@pytest.mark.parametrize('target_kind', ['primary', 'primary-symlink', 'secondary-symlink'])
def test_engine_cli_guards_all_destinations_before_generation(tmp_path, target_kind):
    source = create_source(tmp_path)
    if target_kind == 'primary': target = source
    else:
        target = tmp_path / 'report.pdf'
        alias = target if target_kind == 'primary-symlink' else target.with_suffix('.html')
        alias.symlink_to(source.name)
    before = fingerprint(tmp_path)
    args = [sys.executable, str(Path(engine.__file__)), str(source),
            '--backend', 'weasyprint', '-o', str(target)]
    if target_kind == 'secondary-symlink': args.append('--html')
    result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    assert result.returncode != 0
    assert 'Output destination matches a project input' in result.stderr
    assert fingerprint(tmp_path) == before
    assert not list(tmp_path.glob('.export-*'))


@pytest.mark.parametrize('fmt', ['html', 'docx', 'pdf', 'md'])
def test_distinct_previous_export_can_be_replaced_and_source_retained(tmp_path, fmt):
    source = create_source(tmp_path)
    original = source.read_bytes()
    target = tmp_path / ('report.' + ('zip' if fmt == 'md' else fmt))
    target.write_bytes(b'PREVIOUS_DELIVERABLE')
    result = export.export(source, fmt, target)
    assert result == target
    assert source.read_bytes() == original
    if fmt == 'html': content = html.document_fromstring(result.read_text()).text_content()
    elif fmt == 'docx': content = ' '.join(p.text for p in Document(result).paragraphs)
    elif fmt == 'pdf':
        with fitz.open(result) as pdf: content = ' '.join(page.get_text() for page in pdf)
    else:
        with zipfile.ZipFile(result) as package: content = package.read('report.md').decode()
    assert CANARY in content
    assert not list(tmp_path.glob('.export-*'))


def test_engine_cli_still_replaces_distinct_pdf_and_html(tmp_path):
    source = create_source(tmp_path)
    original = source.read_bytes()
    target = tmp_path / 'report.pdf'
    target.write_bytes(b'OLD_PDF'); target.with_suffix('.html').write_text('OLD_HTML')
    result = subprocess.run([sys.executable, str(Path(engine.__file__)), str(source),
                             '--backend', 'weasyprint', '-o', str(target), '--html'],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert source.read_bytes() == original
    assert CANARY in html.document_fromstring(target.with_suffix('.html').read_text()).text_content()
    with fitz.open(target) as pdf:
        assert CANARY in ' '.join(page.get_text() for page in pdf)


@pytest.mark.parametrize('fmt', ['html', 'docx', 'pdf', 'md'])
def test_editor_api_exports_keep_real_project_inputs_unchanged(tmp_path, monkeypatch, fmt):
    import app as api
    projects = tmp_path / 'projects'
    directory = projects / 'synthetic'
    directory.mkdir(parents=True)
    create_source(directory)
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    before = fingerprint(projects)
    response = auth_client(api.app).post('/api/projects/synthetic/export/' + fmt)
    assert response.status_code == 200, response.get_json()
    assert response.data and response.data != b'PREVIOUS_DELIVERABLE'
    assert fingerprint(projects) == before


@pytest.mark.parametrize('group', ['evidence', 'attachments', 'capture_inbox'])
@pytest.mark.parametrize('invalid', [None, ['invalid row']])
def test_engine_invalid_input_is_rejected_cleanly_before_creating_output(tmp_path, group, invalid):
    data = document(); data[group] = invalid
    source = create_source(tmp_path, data)
    before = fingerprint(tmp_path)
    target = tmp_path / 'new-directory' / 'report.pdf'
    result = subprocess.run([sys.executable, str(Path(engine.__file__)), str(source),
                             '--backend', 'weasyprint', '-o', str(target)],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode != 0
    assert '[!]' in result.stderr and 'Traceback' not in result.stderr
    assert fingerprint(tmp_path) == before
    assert not target.parent.exists()


def test_only_filter_keeps_unselected_input_images_protected(tmp_path):
    data = document()
    image = tmp_path / 'img' / 'other.png'; image.parent.mkdir()
    Image.new('RGB', (8, 8), 'white').save(image)
    data['findings'].append({'id': 'F02', 'title': 'Other synthetic condition',
                             'severity': 'info', 'cvss': 0,
                             'description_md': '![Synthetic](img/other.png)'})
    source = create_source(tmp_path, data)
    before = fingerprint(tmp_path)
    result = subprocess.run([sys.executable, str(Path(engine.__file__)), str(source),
                             '--backend', 'weasyprint', '--only', 'F01', '-o', str(image)],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode != 0
    assert 'Output destination matches a project input' in result.stderr
    assert fingerprint(tmp_path) == before
