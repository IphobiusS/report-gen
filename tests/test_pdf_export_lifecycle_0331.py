"""PDF child failures retain prior deliverables and remove their own remnants."""
from pathlib import Path
import subprocess

import pytest

import exporters.pdf as pdf
from error_messages import language_scope
from wizard import dump_yaml


@pytest.mark.parametrize('lang', ['es', 'en'])
@pytest.mark.parametrize('failure', ['timeout', 'renderer'])
def test_pdf_failure_preserves_output_and_cleans_only_its_intermediates(tmp_path, monkeypatch, lang, failure):
    source = tmp_path / 'private-project.yaml'
    dump_yaml({'meta': {'lang': lang, 'report_title': 'Lifecycle'}, 'findings': []}, source)
    output = tmp_path / 'existing.pdf'
    output.write_bytes(b'PREVIOUS_VERIFIED_REPORT')
    unrelated = tmp_path / 'another-export.pdf'
    unrelated.write_bytes(b'UNRELATED')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def failed_process(command, **options):
        destination = Path(command[command.index('-o') + 1])
        destination.write_bytes(b'PARTIAL_PDF')
        (destination.parent / 'first-pass.pdf').write_bytes(b'INCOMPLETE_PAGINATION')
        assert command[-2:] == ['--error-language', lang]
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, options['timeout'], output='PRIVATE_CHILD_DETAIL')
        raise subprocess.CalledProcessError(1, command, stderr='Controlled renderer failure')

    monkeypatch.setattr(pdf.subprocess, 'run', failed_process)
    with language_scope(lang), pytest.raises(ValueError) as caught:
        pdf.export_pdf(source, output)
    message = str(caught.value)
    if failure == 'timeout':
        assert ('120 segundos' if lang == 'es' else '120-second limit') in message
        assert ('salida anterior se conserva' if lang == 'es' else 'previous output is preserved') in message
        assert str(tmp_path) not in message and 'PRIVATE_CHILD_DETAIL' not in message
    else:
        assert message == 'Controlled renderer failure'
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_pdf_success_publishes_only_completed_output_and_cleans_passes(tmp_path, monkeypatch):
    source = tmp_path / 'engagement.yaml'
    dump_yaml({'meta': {'lang': 'es', 'report_title': 'Lifecycle'}, 'findings': []}, source)
    source_bytes = source.read_bytes()
    output = tmp_path / 'nested' / 'report.pdf'

    def completed_process(command, **options):
        destination = Path(command[command.index('-o') + 1])
        destination.write_bytes(b'COMPLETE_PDF')
        (destination.parent / 'first-pass.pdf').write_bytes(b'PAGINATION_PASS')
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(pdf.subprocess, 'run', completed_process)
    assert pdf.export_pdf(source, output) == output
    assert output.read_bytes() == b'COMPLETE_PDF'
    assert list(output.parent.iterdir()) == [output]
    assert source.read_bytes() == source_bytes


@pytest.mark.parametrize('destination', ['source', 'symlink', 'hardlink', 'image'])
def test_direct_pdf_writer_rejects_real_input_destinations_before_staging(tmp_path, monkeypatch, destination):
    from PIL import Image
    source = tmp_path / 'engagement.yaml'
    image = tmp_path / 'proof.png'
    Image.new('RGB', (30, 20), '#345678').save(image)
    dump_yaml({'meta': {'lang': 'es', 'report_title': 'Protected input'},
               'findings': [{'id': 'F1', 'mode': 'vuln', 'severity': 'info',
                             'title': 'Synthetic finding', 'description_md': 'Example.',
                             'walkthrough': [{'images': [{'src': 'proof.png', 'caption': 'Example'}]}]}]}, source)
    output = source
    if destination in ('symlink', 'hardlink'):
        output = tmp_path / 'alias.pdf'
        if destination == 'symlink':
            try:
                output.symlink_to(source)
            except OSError:
                pytest.skip('Symlink privilege unavailable')
        else:
            output.hardlink_to(source)
    elif destination == 'image':
        output = image
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def must_not_run(*args, **kwargs):
        pytest.fail('Input overwrite must be rejected before starting the PDF child')

    monkeypatch.setattr(pdf.subprocess, 'run', must_not_run)
    with pytest.raises(ValueError, match='Output destination matches a project input'):
        pdf.export_pdf(source, output)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
