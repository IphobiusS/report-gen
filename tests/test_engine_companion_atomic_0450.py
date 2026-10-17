"""A CLI HTML companion must not be published for a failed PDF revision."""
from argparse import Namespace
from pathlib import Path
import os

import pytest

import engine
from wizard import dump_yaml


def _case(tmp_path):
    source = tmp_path / 'engagement.yaml'
    dump_yaml({'meta': {'report_title': 'Fictional companion audit', 'lang': 'en'},
               'findings': []}, source)
    output = tmp_path / 'report.pdf'
    output.write_bytes(b'PREVIOUS_PDF')
    output.with_suffix('.html').write_bytes(b'PREVIOUS_HTML')
    return source, output


def _args(source, output):
    return Namespace(engagement=str(source), out=str(output), only=None,
                     lang=None, theme=None, html=True, backend='weasyprint')


def _renderer(monkeypatch, failure=None):
    calls = []

    def render(_html, target, *_args):
        calls.append(Path(target))
        target.write_bytes(b'FIRST_PASS' if len(calls) == 1 else b'FINAL_PDF')
        if len(calls) == 2 and failure:
            raise failure
        return []

    monkeypatch.setattr(engine, 'do_render', render)
    return calls


def test_final_render_failure_preserves_both_deliverables(tmp_path, monkeypatch):
    source, output = _case(tmp_path)
    before = source.read_bytes()
    calls = _renderer(monkeypatch, ValueError('controlled final-render failure'))
    with pytest.raises(ValueError, match='controlled final-render failure'):
        engine._run(_args(source, output))
    assert len(calls) == 2
    assert output.read_bytes() == b'PREVIOUS_PDF'
    assert output.with_suffix('.html').read_bytes() == b'PREVIOUS_HTML'
    assert source.read_bytes() == before
    assert not list(tmp_path.glob('.export-*'))


def test_html_staging_failure_preserves_previous_outputs(tmp_path, monkeypatch):
    source, output = _case(tmp_path)
    original = Path.write_text

    def refuse_staged_html(path, *args, **kwargs):
        if path.name.startswith('.export-') and path.suffix == '.html':
            raise OSError('controlled HTML write failure')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', refuse_staged_html)
    calls = _renderer(monkeypatch)
    with pytest.raises(OSError, match='controlled HTML write failure'):
        engine._run(_args(source, output))
    assert len(calls) == 1  # Failure precedes the final PDF render.
    assert output.read_bytes() == b'PREVIOUS_PDF'
    assert output.with_suffix('.html').read_bytes() == b'PREVIOUS_HTML'
    assert not list(tmp_path.glob('.export-*'))


@pytest.mark.parametrize('alias', ['same_path', 'symlink', 'hardlink'])
def test_companion_aliases_are_rejected_before_rendering(tmp_path, monkeypatch, alias):
    source, output = _case(tmp_path)
    companion = output.with_suffix('.html')
    companion.unlink()
    if alias == 'same_path':
        output = companion
        output.write_bytes(b'PREVIOUS_PDF')
    elif alias == 'symlink':
        companion.symlink_to(output.name)
    else:
        companion.hardlink_to(output)
    calls = _renderer(monkeypatch)
    with pytest.raises(ValueError, match='PDF y HTML coinciden'):
        engine._run(_args(source, output))
    assert not calls
    assert output.read_bytes() == b'PREVIOUS_PDF'
    assert not list(tmp_path.glob('.export-*'))


def test_success_replaces_both_companions(tmp_path, monkeypatch):
    source, output = _case(tmp_path)
    before = source.read_bytes()
    calls = _renderer(monkeypatch)
    engine._run(_args(source, output))
    assert len(calls) == 2
    assert output.read_bytes() == b'FINAL_PDF'
    assert 'Fictional companion audit' in output.with_suffix('.html').read_text()
    assert source.read_bytes() == before
    assert not list(tmp_path.glob('.export-*'))


@pytest.mark.parametrize('blocked', ['pdf', 'html'])
@pytest.mark.parametrize('previous', [True, False])
def test_publication_failure_rolls_back_completed_companions(tmp_path, monkeypatch, blocked, previous):
    source, output = _case(tmp_path)
    companion = output.with_suffix('.html')
    if not previous:
        output.unlink()
        companion.unlink()
    original = os.replace
    blocked_path = output if blocked == 'pdf' else companion

    def blocked_replace(source, destination):
        if Path(destination) == blocked_path:
            raise PermissionError('controlled locked destination')
        return original(source, destination)

    monkeypatch.setattr(os, 'replace', blocked_replace)
    calls = _renderer(monkeypatch)
    with pytest.raises(PermissionError, match='controlled locked destination'):
        engine._run(_args(source, output))
    assert len(calls) == 2
    if previous:
        assert output.read_bytes() == b'PREVIOUS_PDF'
        assert companion.read_bytes() == b'PREVIOUS_HTML'
    else:
        assert not output.exists() and not companion.exists()
    assert not list(tmp_path.glob('.export-*'))
    assert not list(tmp_path.glob('.report-gen-previous-*'))


def test_failed_rollback_preserves_old_copy_and_reports_recovery(tmp_path, monkeypatch):
    source, output = _case(tmp_path)
    companion = output.with_suffix('.html')
    original = os.replace

    def blocked_replace(source, destination):
        if Path(destination) == companion or Path(source).name.startswith('.report-gen-previous-'):
            raise PermissionError('controlled publish and rollback failure')
        return original(source, destination)

    monkeypatch.setattr(os, 'replace', blocked_replace)
    _renderer(monkeypatch)
    with pytest.raises(ValueError, match='no se pudieron restaurar') as failure:
        engine._run(_args(source, output))
    backups = list(tmp_path.glob('.report-gen-previous-*'))
    assert len(backups) == 1 and backups[0].read_bytes() == b'PREVIOUS_PDF'
    assert str(backups[0]) in str(failure.value)
    assert output.read_bytes() == b'FINAL_PDF'
    assert companion.read_bytes() == b'PREVIOUS_HTML'
    assert not list(tmp_path.glob('.export-*'))
