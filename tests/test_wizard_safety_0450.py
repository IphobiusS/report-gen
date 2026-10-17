"""The terminal wizard preserves identifiers, evidence and existing reports."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from input_guard import load_yaml_file
import wizard
from workflows import MAX_SEQUENCE


@pytest.mark.parametrize('counter,reference,expected', [(0, '', 'F4'), (20, '', 'F21'), (0, '#F30', 'F31')])
def test_add_finding_uses_document_identifier_allocation(tmp_path, monkeypatch, counter, reference, expected):
    source = tmp_path / 'engagement.yaml'
    data = {'meta': {'lang': 'es', 'report_title': 'Retained'}, 'finding_sequence': counter,
            'findings': [{'id': 'F1', 'title': 'First'}, {'id': 'F3', 'title': 'Third'}],
            'report': {'sections': [{'key': 'custom', 'title': 'References', 'body': reference}]}}
    wizard.dump_yaml(data, source)
    monkeypatch.setattr(wizard, 'ask_finding', lambda identity, _images: {'id': identity, 'title': 'Added'})
    monkeypatch.setattr(wizard, 'ask_yesno', lambda *args, **kwargs: False)
    wizard.cmd_add_finding(SimpleNamespace(engagement=source))
    saved = load_yaml_file(source)
    assert [row['id'] for row in saved['findings']] == ['F1', 'F3', expected]
    assert saved['finding_sequence'] == int(expected[1:])
    assert saved['report'] == data['report']


def test_exhausted_id_fails_before_prompt_or_write(tmp_path, monkeypatch):
    source = tmp_path / 'engagement.yaml'
    wizard.dump_yaml({'meta': {'lang': 'es'}, 'findings': [], 'finding_sequence': MAX_SEQUENCE}, source)
    before = source.read_bytes()
    monkeypatch.setattr(wizard, 'ask_finding', lambda *_args: pytest.fail('Cannot ask for an exhausted ID'))
    with pytest.raises(ValueError):
        wizard.cmd_add_finding(SimpleNamespace(engagement=source))
    assert source.read_bytes() == before


def test_next_identifier_preview_does_not_mutate_findings():
    findings = [{'id': 'F1'}, {'id': 'F3'}]
    before = deepcopy(findings)
    assert wizard.next_fid(findings) == 'F4'
    assert findings == before


@pytest.mark.parametrize('same_file,filename', [(False, 'proof.png'), (True, 'proof.png'),
                                              (False, 'proof %2f #.png')])
def test_figure_copy_preserves_existing_evidence(tmp_path, monkeypatch, same_file, filename):
    images = tmp_path / 'project' / 'img'; images.mkdir(parents=True)
    previous = images / 'proof.png'; Image.new('RGB', (8, 8), 'red').save(previous)
    before = previous.read_bytes()
    source = previous if same_file else tmp_path / filename
    if not same_file:
        Image.new('RGB', (8, 8), 'blue').save(source)
    selected = source.read_bytes()
    answers = iter([str(source), 'New caption'])
    monkeypatch.setattr(wizard, 'ask', lambda *_args: next(answers))
    figure = wizard.ask_figure(images)
    assert previous.read_bytes() == before
    copied = images.parent / figure['src']
    assert copied != previous
    assert copied.read_bytes() == selected
    assert figure['caption'] == 'New caption'
    assert copied.name.isascii() and '%' not in copied.name and '#' not in copied.name


def test_new_report_never_replaces_an_existing_project(tmp_path, monkeypatch):
    root = tmp_path / 'reports' / 'existing'; root.mkdir(parents=True)
    document = root / 'engagement.yaml'; document.write_bytes(b'Existing report must remain intact\n')
    image = root / 'proof.png'; image.write_bytes(b'Existing evidence')
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    monkeypatch.setattr(wizard, 'ROOT', tmp_path)
    monkeypatch.setattr(wizard, 'ask', lambda _prompt, default='': default)
    monkeypatch.setattr(wizard, 'ask_yesno', lambda *_args, **_kwargs: False)
    with pytest.raises(ValueError):
        wizard.cmd_new(SimpleNamespace(model='corporativo-es', slug='existing'))
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


@pytest.mark.parametrize('language,notice', [('es', b'Captura interrumpida.'), ('en', b'Data entry interrupted.'),
                                           ('pt', b'Preenchimento interrompido.')])
def test_terminal_eof_exits_instead_of_repeating_the_choice_prompt(language, notice):
    run = subprocess.run([sys.executable, str(Path(wizard.__file__)), 'new', '--ui-language', language],
                         stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    assert run.returncode == 1
    assert len(run.stdout) + len(run.stderr) < 10000
    assert b'Traceback' not in run.stderr
    assert notice in run.stderr


@pytest.mark.parametrize('prompt', ['ask', 'ask_block'])
def test_terminal_input_eof_does_not_become_valid_empty_authored_content(monkeypatch, prompt):
    def closed_input(*_args):
        raise EOFError
    monkeypatch.setattr('builtins.input', closed_input)
    with pytest.raises(wizard.InputCancelled):
        getattr(wizard, prompt)('Titulo del informe')
