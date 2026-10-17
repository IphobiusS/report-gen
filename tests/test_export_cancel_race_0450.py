"""An accepted cancellation also owns the final export publication boundary."""
from pathlib import Path
import sys
import threading
import time

import pytest

import export_jobs
from error_messages import language_scope


def terminal(queue, key):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = queue.status('owner', key)
        if state['stage'] in export_jobs.TERMINAL:
            return state
        time.sleep(.01)
    pytest.fail('The export did not finish')


def test_cancellation_during_final_cleanup_cannot_publish_a_result(monkeypatch):
    start = export_jobs._start_process
    clean = export_jobs._clean_job_files
    cleaning, release = threading.Event(), threading.Event()

    def controlled_worker(command):
        code = ('import sys; from pathlib import Path; '
                'assert sys.stdin.buffer.read(1) == b"1"; '
                'Path(sys.argv[1], "result").write_bytes(b"completed export")')
        return start([sys.executable, '-c', code, command[-1]])

    def wait_after_render(root, keep_result=False, timeout=2):
        if keep_result:
            cleaning.set()
            if not release.wait(10):
                raise RuntimeError('The regression did not release cleanup')
        return clean(root, keep_result=keep_result, timeout=timeout)

    monkeypatch.setattr(export_jobs, '_start_process', controlled_worker)
    monkeypatch.setattr(export_jobs, '_clean_job_files', wait_after_render)
    queue = export_jobs.ExportQueue(timeout=10)
    try:
        def prepare(root):
            root.mkdir()
            return {}

        key = queue.submit('owner', prepare, dict(label='Cancellation boundary',
                           revision='saved', filename='result.html'))['id']
        assert cleaning.wait(10), 'Worker did not reach final cleanup'
        assert queue.cancel('owner', key)['stage'] == 'cancelling'
        release.set()
        final = terminal(queue, key)
        assert final['stage'] == 'cancelled'
        assert final['verification_available'] is False
        with pytest.raises(ValueError):
            queue.result('owner', key)
        assert not list(Path(queue.jobs[key]['root']).iterdir())

        # Cancellation does not abandon the queue's worker thread.
        next_key = queue.submit('owner', prepare, dict(label='Next export',
                                revision='saved', filename='result.html'))['id']
        assert terminal(queue, next_key)['stage'] == 'done'
        assert queue.result('owner', next_key)[0] == b'completed export'
    finally:
        release.set()
        queue.close()


@pytest.mark.parametrize('language,notice', [
    ('es', 'Se reintentará la limpieza'),
    ('en', 'Temporary file cleanup will be retried'),
    ('pt', 'A limpeza dos arquivos temporários será repetida'),
])
def test_expired_private_files_are_not_forgotten_after_cleanup_failure(monkeypatch, language, notice):
    queue = export_jobs.ExportQueue(ttl=1)
    remove = export_jobs.shutil.rmtree
    blocked = {'active': True}
    try:
        with queue.lock:
            root = queue.root / 'expired'
            root.mkdir()
            (root / 'private.txt').write_text('Private snapshot retained after a failed cleanup')
            queue.jobs['expired'] = dict(root=root, stage='error', updated=0)

            def sharing_violation(path, *args, **kwargs):
                if Path(path) == root and blocked['active']:
                    if kwargs.get('ignore_errors'):
                        return None
                    raise PermissionError('Controlled persistent file lock')
                return remove(path, *args, **kwargs)

            monkeypatch.setattr(export_jobs.shutil, 'rmtree', sharing_violation)
            with language_scope(language):
                queue._purge()
            assert (root / 'private.txt').exists()
            assert 'expired' in queue.jobs, 'Failed cleanup must remain tracked for a later retry'
            assert queue.jobs['expired']['stage'] == 'error'
            assert queue.jobs['expired']['verification'] is None
            assert notice in queue.jobs['expired']['error']
            blocked['active'] = False
            queue._purge()
            assert 'expired' not in queue.jobs
            assert not root.exists()
    finally:
        blocked['active'] = False
        queue.close()
