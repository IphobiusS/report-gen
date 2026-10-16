"""PowerShell provenance guards execute before any optional licensed Word COM."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('fault,expected', [
    ('hash', 'DOCX source hash does not match'),
    ('multiple', 'A source receipt binds exactly one DOCX'),
    ('receipt', 'Invalid report-gen native DOCX preview receipt'),
])
def test_opt_in_word_receipt_rejects_unbound_sources_before_com(tmp_path, fault, expected):
    powershell = shutil.which('pwsh') or shutil.which('powershell')
    if not powershell:
        pytest.skip('PowerShell is optional here; Windows CI executes this source-binding guard')
    source = tmp_path / 'input'
    source.mkdir()
    raw = b'synthetic guard fixture; never opened by Word'
    (source / 'report.docx').write_bytes(raw)
    value = dict(format='report-gen-docx-native-preview', version=1, source_docx_sha256=sha256(raw).hexdigest(),
                 source_revision='frozen-source-revision', job_id='own-job', word_verified=False)
    if fault == 'hash':
        value['source_docx_sha256'] = '0' * 64
    elif fault == 'multiple':
        (source / 'second.docx').write_bytes(raw)
    else:
        value['format'] = 'unrelated-receipt'
    receipt = tmp_path / 'expected.json'
    receipt.write_text(json.dumps(value), encoding='utf-8')
    result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-File',
                             str(ROOT / 'scripts/verify-microsoft-word.ps1'), '-InputDirectory', str(source),
                             '-OutputDirectory', str(tmp_path / 'output'), '-ExpectedSourceReceipt', str(receipt)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0 and expected in result.stdout + result.stderr
    assert (source / 'report.docx').read_bytes() == raw
    assert not (tmp_path / 'output/word-validation.json').exists()
