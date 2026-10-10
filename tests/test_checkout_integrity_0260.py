"""A Windows-style Git checkout must preserve content-addressed history bytes."""
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import project_history

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which('git') is None, reason='Git is required to exercise checkout filters')
def test_autocrlf_checkout_keeps_hashed_history_exportable_and_restorable(tmp_path):
    repository = tmp_path / 'repository'
    repository.mkdir()
    environment = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    def git(*arguments, **kwargs):
        return subprocess.run(['git', *arguments], cwd=repository, env=environment,
                              check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    git('init', '--quiet')
    shutil.copyfile(ROOT / '.gitattributes', repository / '.gitattributes')
    shutil.copytree(ROOT / 'examples/quality-lab', repository / 'examples/quality-lab')
    fragment = b'first synthetic line\nsecond synthetic line\n'
    key = sha256(fragment).hexdigest()
    fragments = repository / 'contract/history/fragments'
    fragments.mkdir(parents=True)
    (fragments / key).write_bytes(fragment)
    (repository / 'ordinary-text.txt').write_bytes(b'first\nsecond\n')
    git('-c', 'core.autocrlf=false', 'add', '--', '.gitattributes', 'examples', 'contract', 'ordinary-text.txt')
    checkout = tmp_path / 'windows-checkout'
    checkout.mkdir()
    git('-c', 'core.autocrlf=true', 'checkout-index', '--all', '--prefix=' + checkout.as_posix() + '/')
    assert (checkout / 'ordinary-text.txt').read_bytes() == b'first\r\nsecond\r\n', 'Checkout filter was not exercised'
    assert (checkout / 'contract/history/fragments' / key).read_bytes() == fragment
    project = checkout / 'examples/quality-lab'
    for path in (project / 'history/objects').iterdir():
        assert sha256(path.read_bytes()).hexdigest() == path.name
    payload = project_history.export_bundle(project)
    restored = tmp_path / 'restored-project'
    project_history.import_bundle(payload, restored)
    original_records = project_history.history(ROOT / 'examples/quality-lab')
    restored_records = project_history.history(restored)
    assert {row['id'] for row in original_records} <= {row['id'] for row in restored_records}
    assert (restored / 'img/evidence.png').read_bytes() == (ROOT / 'examples/quality-lab/img/evidence.png').read_bytes()
    assert project_history.export_bundle(restored)
