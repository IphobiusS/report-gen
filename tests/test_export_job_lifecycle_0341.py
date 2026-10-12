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
        if sys.platform != 'darwin':
            return True
        # macOS has no /proc; a dead orphan can briefly remain a zombie before
        # launchd reaps it. It has already released its files and cannot execute.
        state = subprocess.run(['ps', '-o', 'stat=', '-p', str(self.pid)],
                               capture_output=True, text=True, check=False).stdout.strip()
        return bool(state) and not state.startswith('Z')

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
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(45)'])
    try:
        process, descendants = controlled_tree(mode)
        if mode != 'running':
            eventually(lambda: _exitcode(process) is not None)
            assert _exitcode(process) == int(mode)
            if os.name != 'nt':
                # The live supervisor reserves the group after the actual worker exits.
                assert process.returncode is None
                assert process.poll() is None
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


@pytest.mark.skipif(os.name == 'nt', reason='POSIX group signaling')
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


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows Job Object shutdown barrier')
def test_windows_shutdown_barrier_prevents_new_descendants(tmp_path):
    ready, request, attempted, marker = [tmp_path / name for name in
                                         ('ready', 'request', 'attempted', 'child-ran')]
    code = (
        'import subprocess,sys,time; from pathlib import Path\n'
        'if sys.stdin.buffer.read(1) != b"1": raise SystemExit(99)\n'
        'ready,request,attempted,marker=map(Path,sys.argv[1:])\n'
        'ready.touch()\n'
        'while not request.exists(): time.sleep(.01)\n'
        'try:\n'
        ' subprocess.run([sys.executable,"-c","from pathlib import Path; import sys; '
        'Path(sys.argv[1]).write_text(\\\"ran\\\")",str(marker)],check=True)\n'
        ' attempted.write_text("created")\n'
        'except (OSError, subprocess.CalledProcessError):\n'
        ' attempted.write_text("blocked")\n'
        'while True: time.sleep(1)\n')
    process = _start_process([sys.executable, '-c', code, *map(str, (ready, request, attempted, marker))])
    try:
        eventually(ready.exists)
        process._report_gen_job._block_new_processes()
        request.touch()
        eventually(lambda: attempted.exists() and attempted.read_text() == 'blocked')
        assert not marker.exists()
        assert process.poll() is None
        ExportQueue._stop(process)
        assert process.returncode is not None
    finally:
        ExportQueue._stop(process)


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows handle ownership check')
def test_windows_stale_snapshot_does_not_wait_for_unrelated_process(tmp_path, monkeypatch):
    import ctypes
    from ctypes import wintypes
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(45)'])
    process = _start_process([sys.executable, '-c',
                              'import sys,time; sys.stdin.buffer.read(1); time.sleep(45)'])
    job = process._report_gen_job
    query = job.api.QueryInformationJobObject
    def with_stale_pid(handle, information, buffer, length, returned):
        ok = query(handle, information, buffer, length, returned)
        if ok and information == 3:
            # Model an ID recycled between the job snapshot and OpenProcess. The
            # membership check must reject the real unrelated process handle.
            counts = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD))
            pids = ctypes.cast(ctypes.addressof(buffer._obj) + 8,
                               ctypes.POINTER(ctypes.c_size_t))
            pids[counts[1]] = unrelated.pid
            counts[0] += 1
            counts[1] += 1
        return ok
    monkeypatch.setattr(job.api, 'QueryInformationJobObject', with_stale_pid)
    try:
        ExportQueue._stop(process)
        assert process.returncode is not None
        assert unrelated.poll() is None
        assert not job.process_handles
    finally:
        ExportQueue._stop(process)
        unrelated.kill()
        unrelated.wait(timeout=5)


def test_cleanup_retries_transient_file_lock_and_keeps_only_result(tmp_path, monkeypatch):
    locked = tmp_path / 'held.txt'
    locked.write_text('temporary')
    (tmp_path / 'result').write_text('complete')
    (tmp_path / 'source').mkdir()
    (tmp_path / 'source' / 'private.txt').write_text('private')
    unlink = Path.unlink
    attempts = []
    def briefly_locked(path, *args, **kwargs):
        if path == locked:
            attempts.append(path)
            if len(attempts) <= 2:
                raise PermissionError('controlled transient sharing violation')
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', briefly_locked)
    export_jobs._clean_job_files(tmp_path, keep_result=True)
    assert len(attempts) == 3
    assert [p.name for p in tmp_path.iterdir()] == ['result']
    assert (tmp_path / 'result').read_text() == 'complete'


@pytest.mark.parametrize('failure', ['stop', 'unlink'])
def test_cleanup_failure_is_visible_and_queue_runs_next_job(tmp_path, monkeypatch, failure):
    started = []
    def start(command):
        code = ('import sys; from pathlib import Path; '
                'token=sys.stdin.buffer.read(1); '
                'Path(sys.argv[1],"result").write_bytes(b"complete") if token==b"1" else None')
        process = _start_process([sys.executable, '-c', code, command[-1]])
        started.append(process)
        return process
    monkeypatch.setattr(export_jobs, '_start_process', start)
    queue = ExportQueue(timeout=10)
    real_stop, unlink = queue._stop, Path.unlink
    blocked = {'active': True, 'path': None}
    def fail_stop(process):
        if failure == 'stop' and blocked['active']:
            raise OSError('controlled process cleanup failure')
        return real_stop(process)
    def fail_unlink(path, *args, **kwargs):
        if failure == 'unlink' and blocked['active'] and path == blocked['path']:
            raise PermissionError('controlled persistent sharing violation')
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(queue, '_stop', fail_stop)
    monkeypatch.setattr(Path, 'unlink', fail_unlink)
    try:
        def prepare(root):
            root.mkdir()
            if blocked['path'] is None:
                blocked['path'] = root.parent / 'held.txt'
                blocked['path'].write_text('private')
            return {}
        specification = {'label': 'controlled', 'revision': 'test', 'filename': 'x'}
        key = queue.submit('owner', prepare, specification)['id']
        eventually(lambda: queue.status('owner', key)['stage'] in export_jobs.TERMINAL)
        status = queue.status('owner', key)
        assert status['stage'] == 'error' and 'limpieza' in status['error']
        assert not status['verification_available']
        with pytest.raises(ValueError):
            queue.result('owner', key)
        assert not (queue.jobs[key]['root'] / 'result').exists()
        assert not (queue.jobs[key]['root'] / 'source').exists()
        assert queue.thread.is_alive()
        blocked['active'] = False
        for process in started:
            real_stop(process)
        export_jobs._clean_job_files(queue.jobs[key]['root'])
        assert not list(queue.jobs[key]['root'].iterdir())
        next_key = queue.submit('owner', prepare, specification)['id']
        eventually(lambda: queue.status('owner', next_key)['stage'] in export_jobs.TERMINAL)
        assert queue.status('owner', next_key)['stage'] == 'done'
        assert queue.result('owner', next_key)[0] == b'complete'
        assert queue.thread.is_alive()
    finally:
        blocked['active'] = False
        for process in started:
            real_stop(process)
        queue.close()


@pytest.mark.skipif(os.name == 'nt', reason='Portable POSIX supervisor')
@pytest.mark.parametrize('mode', ['0', '7', 'running'])
def test_posix_cleanup_without_waitid_or_wnowait(controlled_tree, monkeypatch, mode):
    monkeypatch.delattr(os, 'waitid', raising=False)
    monkeypatch.delattr(os, 'WNOWAIT', raising=False)
    process, children = controlled_tree(mode)
    if mode != 'running':
        eventually(lambda: _exitcode(process) is not None)
        assert _exitcode(process) == int(mode)
        # Repeated ordinary Popen observation cannot reap the still-live leader.
        for _ in range(10):
            assert process.poll() is None
            assert _exitcode(process) == int(mode)
    ExportQueue._stop(process)
    eventually(lambda: not any(child.alive() for child in children))
    assert process.stdin.closed and process.stdout.closed


@pytest.mark.skipif(os.name == 'nt', reason='POSIX parent-death pipe')
@pytest.mark.parametrize('worker_exit', [False, True])
def test_parent_death_cleans_worker_tree_without_pid_lookup(tmp_path, worker_exit):
    marker = tmp_path / 'pids.json'
    child_code = 'import time; time.sleep(45)'
    worker_code = (
        'import json,os,subprocess,sys,time; from pathlib import Path\n'
        'if sys.stdin.buffer.read(1) != b"1": raise SystemExit(99)\n'
        'child=subprocess.Popen([sys.executable,"-c",sys.argv[2]])\n'
        'Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]))\n'
        + ('raise SystemExit(0)\n' if worker_exit else 'time.sleep(45)\n'))
    parent_code = (
        'import json,os,sys,time; from pathlib import Path\n'
        'from export_jobs import _start_process,_exitcode\n'
        'process=_start_process([sys.executable,"-c",sys.argv[2],sys.argv[1],sys.argv[3]])\n'
        'while not Path(sys.argv[1]).exists(): time.sleep(.01)\n'
        + ('while _exitcode(process) is None: time.sleep(.01)\n' if worker_exit else '') +
        'Path(sys.argv[1]+".supervisor").write_text(str(process.pid))\n'
        'time.sleep(45)\n')
    parent = subprocess.Popen([sys.executable, '-c', parent_code, str(marker),
                               worker_code, child_code], cwd=Path(export_jobs.__file__).parent)
    witnesses = []
    try:
        supervisor = marker.with_suffix('.json.supervisor')
        eventually(supervisor.exists)
        pids = json.loads(marker.read_text())
        witnesses = [Witness(pid) for pid in [int(supervisor.read_text()), *pids]]
        assert witnesses[0].alive() and witnesses[-1].alive()
        # SIGKILL bypasses atexit/finally and proves the parent pipe is not retained
        # by the worker or its descendants. No cleanup request can be sent now.
        parent.kill()
        parent.wait(timeout=5)
        eventually(lambda: not any(witness.alive() for witness in witnesses))
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        for witness in witnesses:
            witness.close()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX supervisor failure')
def test_crashed_supervisor_does_not_publish_success_or_leave_descendants(controlled_tree):
    process, children = controlled_tree('running')
    os.kill(process.pid, signal.SIGKILL)
    with pytest.raises(RuntimeError, match='supervisor closed'):
        eventually(lambda: _exitcode(process) is not None)
    # Observing EOF did not reap the dead leader, so its group remains ours.
    assert process.returncode is None
    ExportQueue._stop(process)
    eventually(lambda: not any(child.alive() for child in children))


@pytest.mark.skipif(os.name == 'nt', reason='POSIX supervisor startup error')
def test_supervisor_reports_worker_launch_failure(tmp_path):
    process = _start_process([str(tmp_path / 'missing-renderer')])
    try:
        eventually(lambda: _exitcode(process) is not None)
        assert _exitcode(process) == 127
        assert process.poll() is None
    finally:
        ExportQueue._stop(process)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX worker signal result')
def test_supervisor_retains_signalled_worker_result():
    process = _start_process([sys.executable, '-c',
        'import os,signal,sys; sys.stdin.buffer.read(1); os.kill(os.getpid(),signal.SIGTERM)'])
    try:
        eventually(lambda: _exitcode(process) is not None)
        assert _exitcode(process) == -signal.SIGTERM
        assert process.poll() is None
    finally:
        ExportQueue._stop(process)
