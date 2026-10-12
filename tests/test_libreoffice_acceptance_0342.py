"""Acceptance guard regressions; synthetic PDFs are not a LibreOffice run."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import fitz
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('libreoffice_acceptance', ROOT / 'scripts/verify-libreoffice.py')
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


@pytest.mark.parametrize(('version', 'stable'), [
    ('LibreOffice 24.2.7.2 420(Build:2)', True),
    ('LibreOffice 26.2.1.1 123456789', True),
    ('LibreOfficeDev 26.8.0.0.alpha0 123456789', False),
    ('LibreOffice 26.2.0.0.beta1', False),
    ('LibreOffice 26.2.0.0.rc1', False),
    ('Microsoft Word 16.0', False),
    ('', False),
])
def test_only_release_version_counts_as_stable(version, stable):
    assert acceptance.stable_version(version) is stable


def pdf_fixture(path, *, blank=False, outside=False):
    with fitz.open() as doc:
        cover = doc.new_page()
        cover.insert_text((60, 100), 'Synthetic cover; not a LibreOffice render')
        body = doc.new_page()
        body.insert_text((60, 25), 'Running header alone does not make a body')
        body.insert_text((60, 810), '2 / 2')
        if not blank:
            body.insert_text((60, 100), 'Body content retained')
        if outside:
            body.insert_text((-8, 200), 'Outside page')
        doc.save(path)


def test_geometry_rejects_page_with_only_running_matter(tmp_path):
    source = tmp_path / 'empty-body.pdf'
    pdf_fixture(source, blank=True)
    with pytest.raises(ValueError, match='Empty body on PDF page 2'):
        acceptance.inspect_geometry(source, tmp_path / 'pages')


def test_geometry_rejects_text_outside_physical_page(tmp_path):
    source = tmp_path / 'clipped.pdf'
    pdf_fixture(source, outside=True)
    with pytest.raises(ValueError, match='outside PDF page 2'):
        acceptance.inspect_geometry(source, tmp_path / 'pages')


def test_geometry_records_real_raster_hashes_without_claiming_visual_approval(tmp_path):
    source = tmp_path / 'valid.pdf'
    pdf_fixture(source)
    result = acceptance.inspect_geometry(source, tmp_path / 'pages')
    assert len(result['pages']) == 2
    assert result['no_empty_body_pages'] is True
    for row in result['pages']:
        assert acceptance.sha256(tmp_path / 'pages' / row['png']) == row['png_sha256']
    assert 'visual_review' not in result


class NoOutputProcess:
    returncode = 0
    pid = 123456789

    def communicate(self, timeout=None):
        return 'Error: source file could not be loaded', ''


def test_zero_exit_without_new_pdf_is_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance.subprocess, 'Popen', lambda *a, **kw: NoOutputProcess())
    with pytest.raises(ValueError, match='did not produce a PDF'):
        acceptance.convert('/fake/soffice', tmp_path / 'input.docx', tmp_path / 'rendered')
    log = json.loads((tmp_path / 'rendered/conversion.json').read_text())
    assert log['returncode'] == 0
    assert 'could not be loaded' in log['stdout']


def test_timeout_kills_process_and_preserves_diagnostics(tmp_path, monkeypatch):
    killed = []

    class TimeoutProcess(NoOutputProcess):
        def communicate(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired('synthetic office', timeout)
            return 'partial output', 'partial diagnostics'

        def kill(self):
            killed.append(self.pid)

    monkeypatch.setattr(acceptance.subprocess, 'Popen', lambda *a, **kw: TimeoutProcess())
    if os.name == 'posix':
        monkeypatch.setattr(acceptance.os, 'killpg', lambda pid, sig: killed.append(pid))
    with pytest.raises(ValueError, match='timed out'):
        acceptance.convert('/fake/soffice', tmp_path / 'input.docx', tmp_path / 'rendered', timeout=.1)
    assert killed == [NoOutputProcess.pid]
    log = json.loads((tmp_path / 'rendered/conversion.json').read_text())
    assert log['status'] == 'timeout'
    assert log['stderr'] == 'partial diagnostics'


def test_existing_evidence_is_preserved(tmp_path):
    marker = tmp_path / 'observed.json'
    marker.write_text('actual previous evidence')
    with pytest.raises(ValueError, match='empty output directory'):
        acceptance.run(tmp_path, '/fake/soffice')
    assert marker.read_text() == 'actual previous evidence'


def test_development_build_cannot_satisfy_stable_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
        a, 0, 'LibreOfficeDev 26.8.0.0.alpha0', ''))
    with pytest.raises(ValueError, match='stable LibreOffice release is required'):
        acceptance.run(tmp_path, '/fake/soffice', require_stable=True)
    receipt = json.loads((tmp_path / 'libreoffice-validation.json').read_text())
    assert receipt['status'] == 'failed'
    assert receipt['distribution_stable'] is False
    assert receipt['visual_review'] == 'pending'
    assert receipt['microsoft_word'] == 'not_run'


def linked_files(tmp_path, pdf_targets):
    target = 'https://example.test/a?return=%2Ftarget%3Fx%3D1&empty=#literal'
    document = Document()
    relationship = document.part.relate_to(target, RT.HYPERLINK, is_external=True)
    for _ in range(2):
        link = OxmlElement('w:hyperlink')
        link.set(qn('r:id'), relationship)
        run, text = OxmlElement('w:r'), OxmlElement('w:t')
        text.text = target
        run.append(text)
        link.append(run)
        document.add_paragraph()._p.append(link)
    source, output = tmp_path / 'links.docx', tmp_path / 'links.pdf'
    document.save(source)
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((60, 100), 'Synthetic link validation, not a native rendering')
        for index, value in enumerate(pdf_targets):
            page.insert_link({'kind': fitz.LINK_URI, 'uri': value or target,
                              'from': fitz.Rect(60, 120 + index * 30, 300, 140 + index * 30)})
        pdf.save(output)
    return source, output


@pytest.mark.parametrize('targets', [[], [''], ['', 'https://example.test/a?return=/target?x=1&empty=#literal']])
def test_native_pdf_missing_or_changed_link_is_rejected(tmp_path, targets):
    source, pdf = linked_files(tmp_path, targets)
    with pytest.raises(ValueError, match='lost an external hyperlink'):
        acceptance.inspect_links(source, pdf, {'internal_links': 0})


def test_native_pdf_wrapped_link_annotations_keep_exact_destinations(tmp_path):
    source, pdf = linked_files(tmp_path, ['', '', ''])
    result = acceptance.inspect_links(source, pdf, {'internal_links': 0})
    assert result['exact_external_targets'] == 1
    assert result['authored_external_placements'] == 2
    assert result['rendered_external_placements'] == 3


def test_native_uri_normalization_never_decodes_reserved_or_double_encoded_separators():
    assert acceptance.normalized_uri('https://example.test/%41%7e?locale=es%2Den&next=%2f%3f%26%3d%23%25%252F') == (
        'https://example.test/A~?locale=es-en&next=%2F%3F%26%3D%23%25%252F')
    assert acceptance.normalized_uri('https://example.test/%C3%A9') == 'https://example.test/%C3%A9'
