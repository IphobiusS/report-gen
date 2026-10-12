"""Real rendering trees must stop even when their worker has already exited."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

import export_jobs
from export_jobs import ExportQueue, _exitcode, _start_process


def eventually(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.02)
    pytest.fail('Controlled process did not reach the expected state')


class Witness:
    """A retained Windows handle or POSIX PID; zombies are no longer running."""
    def __init__(self, pid):
        self.pid = pid
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.api = ctypes.WinDLL('kernel32', use_last_error=True)
            for name, args, result in (
                ('OpenProcess', [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
                ('WaitForSingleObject', [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
                ('TerminateProcess', [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
                ('CloseHandle', [wintypes.HANDLE], wintypes.BOOL),
            ):
                function = getattr(self.api, name)
                function.argtypes, function.restype = args, result
            self.handle = self.api.OpenProcess(0x00100001, False, pid)  # synchronize + terminate
            assert self.handle, ctypes.WinError(ctypes.get_last_error())

    def alive(self):
        if os.name == 'nt':
            return self.api.WaitForSingleObject(self.handle, 0) == 258  # WAIT_TIMEOUT
        try:
            os.kill(self.pid, 0)
        except ProcessLookupError:
            return False
        status = Path('/proc') / str(self.pid) / 'stat'
        if status.exists():
            try:
                return status.read_text().rsplit(')', 1)[1].split()[0] != 'Z'
            except FileNotFoundError:
                return False
        return True

    def close(self):
        if os.name == 'nt':
            if self.alive():
                self.api.TerminateProcess(self.handle, 1)
                self.api.WaitForSingleObject(self.handle, 5000)
            self.api.CloseHandle(self.handle)
        elif self.alive():
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.fixture
def controlled_tree(tmp_path):
    child = tmp_path / 'child.py'
    child.write_text(
        'import json, os, subprocess, sys, time\n'
        'from pathlib import Path\n'
        'held = (Path(sys.argv[2]) / "child-held.txt").open("w")\n'
        'grandchild = subprocess.Popen([sys.executable, "-c", '
        '"import sys,time; from pathlib import Path; held=Path(sys.argv[1]).open(\\\"w\\\"); '
        'held.write(\\\"held\\\"); held.flush(); time.sleep(45)", '
        'str(Path(sys.argv[2]) / "grandchild-held.txt")])\n'
        'while not (Path(sys.argv[2]) / "grandchild-held.txt").exists(): time.sleep(.01)\n'
        'Path(sys.argv[1]).write_text(json.dumps([os.getpid(), grandchild.pid]))\n'
        'time.sleep(45)\n', encoding='utf-8')
    worker = tmp_path / 'worker.py'
    worker.write_text(
        'import subprocess, sys, time\n'
        'from pathlib import Path\n'
        'if sys.stdin.buffer.read(1) != b"1": raise SystemExit(99)\n'
        'subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2], sys.argv[4]])\n'
        'while not Path(sys.argv[2]).exists(): time.sleep(.01)\n'
        'if sys.argv[3] == "running": time.sleep(45)\n'
        'raise SystemExit(int(sys.argv[3]))\n', encoding='utf-8')
    processes, witnesses = [], []

    def start(mode='0', hold_root=None):
        ready = tmp_path / ('pids-' + str(len(processes)) + '.json')
        held_directory = hold_root or tmp_path
        process = _start_process([sys.executable, str(worker), str(child), str(ready), mode,
                                  str(held_directory)])
        processes.append(process)
        eventually(ready.exists)
        # read_text can race the file creation, so wait for the complete tiny record.
        def read_pids():
            try:
                return json.loads(ready.read_text())
            except json.JSONDecodeError:
                return None
        children = [Witness(pid) for pid in eventually(read_pids)]
        witnesses.extend(children)
        return process, children

    yield start
    for process in processes:
        ExportQueue._stop(process)
    for witness in witnesses:
        witness.close()


@pytest.mark.parametrize('mode', ['0', '7', 'running'])
def test_stop_terminates_real_descendants_and_preserves_unrelated_process(controlled_tree, mode):
    if mode != 'running' and os.name != 'nt' and not hasattr(os, 'WNOWAIT'):
        pytest.skip('Older POSIX Python lacks non-reaping exit observation')
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(45)'])
    try:
        process, descendants = controlled_tree(mode)
        if mode != 'running':
            eventually(lambda: _exitcode(process) is not None)
            assert _exitcode(process) == int(mode)
            if os.name != 'nt' and hasattr(os, 'WNOWAIT'):
                # Observing exit must not reap the leader and release its process-group ID.
                assert process.returncode is None
                assert os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT).si_pid == process.pid
        assert all(child.alive() for child in descendants)
        ExportQueue._stop(process)
        if os.name == 'nt':
            # Stop must await descendants, not just initiate termination of an exited root.
            assert not any(child.alive() for child in descendants)
        eventually(lambda: not any(child.alive() for child in descendants))
        assert process.returncode is not None
        assert unrelated.poll() is None
        ExportQueue._stop(process)
        ExportQueue._stop(None)
        assert unrelated.poll() is None
        if os.name == 'nt':
            assert process._report_gen_job.handle is None
    finally:
        unrelated.kill()
        unrelated.wait(timeout=5)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX group signaling')
def test_stop_never_signals_a_group_after_its_leader_was_reaped():
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(45)'],
                                 start_new_session=True)
    try:
        # Model a stale worker PID which now belongs to this unrelated process group.
        stale = SimpleNamespace(pid=unrelated.pid, returncode=0, wait=lambda timeout: 0)
        ExportQueue._stop(stale)
        ExportQueue._stop(stale)
        assert unrelated.poll() is None
    finally:
        unrelated.kill()
        unrelated.wait(timeout=5)


@pytest.mark.skipif(os.name == 'nt' or not hasattr(os, 'WNOWAIT'), reason='POSIX non-reaping group signaling')
def test_stop_can_retry_failed_group_cleanup(controlled_tree, monkeypatch):
    process, descendants = controlled_tree('0')
    eventually(lambda: _exitcode(process) is not None)
    real_killpg = os.killpg
    def denied(*args):
        raise PermissionError('controlled cleanup failure')
    monkeypatch.setattr(os, 'killpg', denied)
    with pytest.raises(PermissionError):
        ExportQueue._stop(process)
    assert not getattr(process, '_report_gen_stopped', False)
    assert all(child.alive() for child in descendants)
    monkeypatch.setattr(os, 'killpg', real_killpg)
    ExportQueue._stop(process)
    eventually(lambda: not any(child.alive() for child in descendants))


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows Job Object assignment')
def test_failed_windows_assignment_never_releases_worker(tmp_path, monkeypatch):
    marker = tmp_path / 'released.txt'
    captured = []
    real_close = export_jobs._WindowsJob.close
    closed = []
    def reject_assignment(job, process):
        captured.append(process)
        raise OSError('controlled assignment failure')
    def close(job):
        real_close(job)
        closed.append(job.handle is None)
    monkeypatch.setattr(export_jobs._WindowsJob, 'assign', reject_assignment)
    monkeypatch.setattr(export_jobs._WindowsJob, 'close', close)
    code = ('import sys; from pathlib import Path; '
            'token=sys.stdin.buffer.read(1); '
            'Path(sys.argv[1]).write_text("released") if token == b"1" else None')
    with pytest.raises(OSError, match='controlled assignment failure'):
        _start_process([sys.executable, '-c', code, str(marker)])
    assert len(captured) == 1 and captured[0].poll() is not None
    assert captured[0].stdin.closed
    assert closed == [True]
    assert not marker.exists()


@pytest.mark.parametrize('returncode,stage', [(0, 'done'), (7, 'error')])
def test_queue_finally_stops_descendants_after_worker_exit(controlled_tree, monkeypatch, returncode, stage):
    if os.name != 'nt' and not hasattr(os, 'WNOWAIT'):
        pytest.skip('Older POSIX Python lacks non-reaping exit observation')
    captured = []
    def start(_command):
        process, children = controlled_tree(str(returncode), hold_root=Path(_command[-1]))
        captured.extend(children)
        return process
    monkeypatch.setattr(export_jobs, '_start_process', start)
    queue = ExportQueue(timeout=10)
    try:
        def prepare(root):
            root.mkdir()
            return {}
        status = queue.submit('owner', prepare, {'label': 'controlled', 'revision': 'test', 'filename': 'x'})
        key = status['id']
        eventually(lambda: queue.status('owner', key)['stage'] in export_jobs.TERMINAL)
        assert queue.status('owner', key)['stage'] == stage
        assert len(captured) == 2
        eventually(lambda: not any(child.alive() for child in captured))
        assert not list(queue.jobs[key]['root'].iterdir())
    finally:
        queue.close()
