"""Rendering deadlines are explicit, finite, localized, and preserve old output."""
from pathlib import Path
import subprocess

import pytest

from error_messages import language_scope
import exporters.pdf as pdf
from wizard import dump_yaml


def fixture_source(tmp_path):
    source = tmp_path / 'engagement.yaml'
    dump_yaml({'meta':{'lang':'en','report_title':'Bounded rendering'},'findings':[]}, source)
    return source


def configured(monkeypatch, value):
    if value is None:
        monkeypatch.delenv('REPORT_GEN_PDF_TIMEOUT', raising=False)
    else:
        monkeypatch.setenv('REPORT_GEN_PDF_TIMEOUT', value)


@pytest.mark.parametrize('value,seconds', [(None,300),('120',120),('30',30),('600',600),('030',30)])
def test_valid_budget_reaches_child_and_only_complete_output_is_published(tmp_path, monkeypatch, value, seconds):
    configured(monkeypatch,value)
    source = fixture_source(tmp_path)
    target = tmp_path / 'report.pdf'
    calls = []
    def complete(command, **options):
        calls.append(options['timeout'])
        destination=Path(command[command.index('-o')+1])
        destination.write_bytes(b'complete bounded export')
        (destination.parent/'first-pass.pdf').write_bytes(b'private first pass')
        return subprocess.CompletedProcess(command,0)
    monkeypatch.setattr(pdf.subprocess,'run',complete)
    assert pdf.export_pdf(source,target)==target
    assert calls==[seconds]
    assert target.read_bytes()==b'complete bounded export'
    assert {p.name for p in tmp_path.iterdir()}=={'engagement.yaml','report.pdf'}


@pytest.mark.parametrize('language',['es','en'])
@pytest.mark.parametrize('value',['','0','29','601','-1','unlimited','NaN','120.5','True',' 300','+300','٣٠٠','9'*5000])
def test_invalid_budget_is_rejected_before_launch_or_staging(tmp_path, monkeypatch, language, value):
    configured(monkeypatch,value)
    source=fixture_source(tmp_path)
    target=tmp_path/'uncreated'/'report.pdf'
    def forbidden(*args,**kwargs):
        pytest.fail('Invalid rendering budget must not launch a process')
    monkeypatch.setattr(pdf.subprocess,'run',forbidden)
    with language_scope(language),pytest.raises(ValueError) as error:
        pdf.export_pdf(source,target)
    assert 'REPORT_GEN_PDF_TIMEOUT' in str(error.value)
    assert ('entre 30 y 600' if language=='es' else 'between 30 and 600') in str(error.value)
    assert not target.parent.exists()
    assert {p.name for p in tmp_path.iterdir()}=={'engagement.yaml'}


@pytest.mark.parametrize('language',['es','en'])
@pytest.mark.parametrize('value,seconds',[(None,300),('120',120),('600',600)])
def test_timeout_retains_previous_bytes_and_reports_actual_budget(tmp_path, monkeypatch, language, value, seconds):
    configured(monkeypatch,value)
    source=fixture_source(tmp_path)
    target=tmp_path/'report.pdf'
    target.write_bytes(b'previous verified export')
    (tmp_path/'unrelated.pdf').write_bytes(b'unrelated export')
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    def expire(command,**options):
        assert options['timeout']==seconds
        destination=Path(command[command.index('-o')+1])
        destination.write_bytes(b'partial')
        (destination.parent/'first-pass.pdf').write_bytes(b'incomplete pass')
        raise subprocess.TimeoutExpired(command,seconds,output='PRIVATE_CHILD_DETAIL')
    monkeypatch.setattr(pdf.subprocess,'run',expire)
    with language_scope(language),pytest.raises(ValueError) as error:
        pdf.export_pdf(source,target)
    text=str(error.value)
    assert (f'{seconds} segundos' if language=='es' else f'{seconds}-second limit') in text
    assert ('salida anterior se conserva' if language=='es' else 'previous output is preserved') in text
    assert 'PRIVATE_CHILD_DETAIL' not in text and str(tmp_path) not in text
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before
