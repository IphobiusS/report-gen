"""Bounded local export queue; each immutable job runs in its own process tree."""
from error_messages import message as backend_message
from error_messages import current_language, set_language, reset_language
from collections import deque
from pathlib import Path
import atexit
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from hashlib import sha256

from storage import atomic_write
from diagnostic_locations import DiagnosticError, error_diagnostics, sanitize_diagnostics

TERMINAL = {'done', 'error', 'cancelled'}


class _WindowsJob:
    """Keep rendering descendants attached after their immediate parent exits."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                        ('PerJobUserTimeLimit', ctypes.c_int64),
                        ('LimitFlags', wintypes.DWORD),
                        ('MinimumWorkingSetSize', ctypes.c_size_t),
                        ('MaximumWorkingSetSize', ctypes.c_size_t),
                        ('ActiveProcessLimit', wintypes.DWORD),
                        ('Affinity', ctypes.c_size_t),
                        ('PriorityClass', wintypes.DWORD),
                        ('SchedulingClass', wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IoCounters),
                        ('ProcessMemoryLimit', ctypes.c_size_t),
                        ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t),
                        ('PeakJobMemoryUsed', ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in (
                'TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime',
                'ThisPeriodTotalKernelTime')] + [(name, wintypes.DWORD) for name in (
                    'TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses',
                    'TotalTerminatedProcesses')]

        self.accounting_type = Accounting
        self.limits_type = ExtendedLimits
        self.process_handles = {}
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            'SetInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                         wintypes.DWORD], wintypes.BOOL),
            'AssignProcessToJobObject': ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            'TerminateJobObject': ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            'QueryInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'IsProcessInJob': ([wintypes.HANDLE, wintypes.HANDLE,
                                ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
            'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.api.CloseHandle(self.handle)
            self.handle = None
            raise error

    def assign(self, process):
        import ctypes
        # Popen's Windows handle identifies this process even if its PID is reused.
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def _block_new_processes(self):
        import ctypes
        limits = self.limits_type()
        # A zero active-process limit rejects new associations (including children)
        # before they execute. Existing members remain ours and can be snapshotted.
        limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x8
        limits.BasicLimitInformation.ActiveProcessLimit = 0
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())

    def _capture_process_handles(self, deadline):
        import ctypes
        from ctypes import wintypes
        capacity = 16
        while True:
            class ProcessIds(ctypes.Structure):
                _fields_ = [('assigned', wintypes.DWORD), ('count', wintypes.DWORD),
                            ('ids', ctypes.c_size_t * capacity)]
            members = ProcessIds()
            ok = self.api.QueryInformationJobObject(self.handle, 3, ctypes.byref(members),
                                                     ctypes.sizeof(members), None)
            error = ctypes.get_last_error() if not ok else 0
            if ok and members.count <= capacity and members.count == members.assigned:
                break
            if error not in (0, 234):  # ERROR_MORE_DATA: retry with the required buffer
                raise ctypes.WinError(error)
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired('export process tree cleanup', 15)
            capacity = max(capacity * 2, members.assigned)
        for pid in members.ids[:members.count]:
            if pid in self.process_handles:
                continue
            # Retain identity through termination; never act on a subsequently reused PID.
            handle = self.api.OpenProcess(0x00101000, False, pid)  # synchronize + query limited
            if not handle:
                error = ctypes.get_last_error()
                if error == 87:  # ERROR_INVALID_PARAMETER: the process is already gone
                    continue
                raise ctypes.WinError(error)
            member = wintypes.BOOL()
            if not self.api.IsProcessInJob(handle, self.handle, ctypes.byref(member)):
                error = ctypes.WinError(ctypes.get_last_error())
                self.api.CloseHandle(handle)
                raise error
            if member.value:
                self.process_handles[pid] = handle
            else:
                self.api.CloseHandle(handle)

    def close(self):
        if self.handle is not None:
            import ctypes
            deadline = time.monotonic() + 15
            try:
                self._block_new_processes()
                self._capture_process_handles(deadline)
            finally:
                # Even a snapshot error must initiate tree termination. Retain the
                # job and captured handles on failure so a caller can retry safely.
                if not self.api.TerminateJobObject(self.handle, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
            for handle in self.process_handles.values():
                milliseconds = max(0, int((deadline - time.monotonic()) * 1000))
                status = self.api.WaitForSingleObject(handle, milliseconds)
                if status == 258:  # WAIT_TIMEOUT
                    raise subprocess.TimeoutExpired('export process tree cleanup', 15)
                if status != 0:  # WAIT_OBJECT_0 is actual process completion, not accounting
                    raise ctypes.WinError(ctypes.get_last_error())
            while True:
                accounting = self.accounting_type()
                if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting),
                                                           ctypes.sizeof(accounting), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if accounting.ActiveProcesses == 0:
                    break
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired('export process tree cleanup', 15)
                time.sleep(.02)
            if not self.api.CloseHandle(self.handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None
            for handle in self.process_handles.values():
                self.api.CloseHandle(handle)
            self.process_handles.clear()


def _clean_job_files(root, keep_result=False, timeout=2):
    """Bound transient sharing violations without abandoning the queue thread."""
    deadline = time.monotonic() + timeout
    while True:
        errors = []
        try:
            if root.exists():
                for path in root.iterdir():
                    if keep_result and path.name == 'result':
                        continue
                    try:
                        if path.is_dir() and not path.is_symlink():
                            shutil.rmtree(path)
                        else:
                            path.unlink(missing_ok=True)
                    except OSError as exc:
                        errors.append(exc)
        except OSError as exc:
            errors.append(exc)
        if not errors:
            return
        if time.monotonic() >= deadline:
            raise errors[0]
        time.sleep(.02)


def _start_process(command):
    """Internal only: command must wait for byte '1' on stdin before doing work."""
    job = _WindowsJob() if os.name == 'nt' else None
    process = None
    try:
        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                   if os.name == 'nt' else {'start_new_session': True})
        if os.name != 'nt':
            # Keep a live session leader until cleanup, including on Python builds
            # without waitid/WNOWAIT. The worker's result travels on a separate pipe;
            # observing it never reaps the process that reserves our private PGID.
            command = [sys.executable, str(Path(__file__).resolve()),
                       '--supervisor-gated', json.dumps(command)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE if os.name != 'nt' else subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, **options)
        if job is not None:
            # Assignment must precede releasing the worker: rendering children inherit this job.
            job.assign(process)
            process._report_gen_job = job
        process.stdin.write(b'1')
        process.stdin.flush()
        if os.name == 'nt':
            process.stdin.close()
        else:
            process._report_gen_status = b''
            os.set_blocking(process.stdout.fileno(), False)
        return process
    except BaseException:
        # The gate is still closed if assignment failed. Kill before closing its pipe.
        try:
            if process is not None:
                try:
                    if os.name == 'nt':
                        process.kill()
                    else:
                        # Do not call Popen.kill first: it can reap the leader before
                        # group cleanup and allow the private PGID to be recycled.
                        os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        finally:
            try:
                if job is not None:
                    job.close()
            finally:
                if process is not None:
                    try:
                        process.wait(timeout=15)
                    finally:
                        if not process.stdin.closed:
                            process.stdin.close()
                        if process.stdout is not None:
                            process.stdout.close()
        raise


def _exitcode(process):
    if os.name == 'nt':
        return process.poll()
    if hasattr(process, '_report_gen_worker_exitcode'):
        return process._report_gen_worker_exitcode
    try:
        status = os.read(process.stdout.fileno(), 32)
    except BlockingIOError:
        return None
    if not status:
        raise RuntimeError(backend_message(
            'El supervisor de exportación terminó sin recibir el resultado del trabajador',
            en='Export supervisor closed without a worker result'))
    process._report_gen_status += status
    if len(process._report_gen_status) > 16:
        raise RuntimeError(backend_message(
            'Resultado del supervisor de exportación inválido',
            en='Invalid export supervisor result'))
    if not process._report_gen_status.endswith(b'\n'):
        return None
    process._report_gen_worker_exitcode = int(process._report_gen_status)
    return process._report_gen_worker_exitcode


def _supervise(command):
    """Reserve the POSIX group while its worker finishes; parent EOF cancels all."""
    if os.name == 'nt' or os.getpgrp() != os.getpid():
        raise SystemExit('Export supervisor requires its own POSIX session')
    if sys.stdin.buffer.read(1) != b'1':
        return 1

    def parent_closed():
        # This descriptor is not inherited by workers. Parent death therefore
        # causes EOF even while the renderer is running or after it has exited.
        sys.stdin.buffer.read()
        os.killpg(os.getpgrp(), signal.SIGKILL)

    threading.Thread(target=parent_closed, daemon=True).start()
    try:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        try:
            child.stdin.write(b'1')
            child.stdin.close()
        except BrokenPipeError:
            pass
        code = child.wait()
    except OSError:
        code = 127
    sys.stdout.write(str(code) + '\n')
    sys.stdout.flush()
    # The supervisor stays alive, reserving the PGID, until its parent cleans up.
    # Do not use waitid, waitpid, or poll here to observe any other process.
    threading.Event().wait()


class ExportQueue:
    def __init__(self, limit=8, ttl=3600, timeout=1800):
        self.root = Path(tempfile.mkdtemp(prefix='report-gen-jobs-'))
        self.limit, self.ttl, self.timeout = limit, ttl, timeout
        self.lock = threading.RLock()
        self.jobs, self.pending = {}, deque()
        self.wake = threading.Event()
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True, name='report-gen-exports')
        self.thread.start()
        atexit.register(self.close)

    def _purge(self):
        for key, job in list(self.jobs.items()):
            if job['stage'] in TERMINAL and time.time() - job['updated'] > self.ttl:
                try:
                    shutil.rmtree(job['root'])
                except OSError:
                    try:
                        removed = not job['root'].exists()
                    except OSError:
                        removed = False
                    if not removed:
                        # A sharing violation must not orphan a private source
                        # snapshot. Keep ownership for the next purge attempt,
                        # and do not advertise a partially removed deliverable.
                        job.update(stage='error', verification=None, diagnostics=[],
                                   error=backend_message(
                                       'No se pudo completar la limpieza de la exportación: {detail}',
                                       en='Export cleanup could not be completed: {detail}',
                                       detail=backend_message('Se reintentará la limpieza de los archivos temporales.',
                                                              en='Temporary file cleanup will be retried.',
                                                              pt='A limpeza dos arquivos temporários será repetida.')))
                        continue
                del self.jobs[key]

    def submit(self, owner, prepare, specification):
        # reserve and capture before publishing the job; never accept partial snapshots
        with self.lock:
            self._purge()
            if self.closed or sum(j['stage'] not in TERMINAL for j in self.jobs.values()) >= self.limit:
                raise ValueError(backend_message('La cola está llena; espera a que termine una exportación'))
            if len(self.jobs) >= 100:
                raise ValueError(backend_message('Demasiados resultados retenidos; elimina los que ya descargaste'))
            key = uuid.uuid4().hex
            root = self.root / key
            root.mkdir()
            try:
                captured = prepare(root / 'source')
                config = dict(specification, captured=captured, error_language=current_language())
                atomic_write(root / 'job.json', json.dumps(config).encode())
            except BaseException:
                shutil.rmtree(root, ignore_errors=True)
                raise
            self.jobs[key] = dict(id=key, owner=owner, root=root, stage='queued', updated=time.time(),
                                  label=specification['label'], revision=specification['revision'],
                                  error=None, cancelled=False, process=None, filename=specification['filename'], verification=None,
                                  formats=list(specification.get('formats', [])), diagnostics=[],
                                  error_language=current_language())
            self.pending.append(key)
            self.wake.set()
            return self.status(owner, key)

    def _get(self, owner, key):
        job = self.jobs.get(key)
        if not job or job['owner'] != owner:
            raise KeyError(key)
        return job

    def status(self, owner, key):
        with self.lock:
            self._purge()
            return self._status_record(self._get(owner, key))

    def _status_record(self, job):
        """Serialize under the caller's lock without expiring other records."""
        result = {k: job[k] for k in ('id', 'stage', 'label', 'revision', 'error', 'filename')}
        result['formats'] = list(job.get('formats', []))
        result['diagnostics'] = sanitize_diagnostics(job.get('diagnostics'))
        result['verification_available'] = bool(job.get('verification')) and job['stage'] == 'done'
        result['position'] = list(self.pending).index(job['id']) + 1 if job['id'] in self.pending else 0
        return result

    def list(self, owner):
        with self.lock:
            self._purge()
            return [self._status_record(job) for job in self.jobs.values() if job['owner'] == owner]

    def cancel(self, owner, key):
        with self.lock:
            job = self._get(owner, key)
            if key in self.pending:
                self.pending.remove(key)
                job.update(cancelled=True, stage='cancelled', updated=time.time())
                shutil.rmtree(job['root'])
                job['root'].mkdir()
            elif job['stage'] not in TERMINAL:
                job['cancelled'] = True
                job['stage'] = 'cancelling'
                self.wake.set()
            return self.status(owner, key)

    def result(self, owner, key):
        with self.lock:
            job = self._get(owner, key)
            if job['stage'] != 'done':
                raise ValueError(backend_message('La exportación aún no está disponible'))
            return (job['root'] / 'result').read_bytes(), job['filename']

    def verification(self, owner, key):
        with self.lock:
            self._purge()
            job = self._get(owner, key)
            if job['stage'] != 'done' or not job.get('verification'):
                raise ValueError(backend_message('Comprobaciones aún no disponibles / Checks not available yet'))
            from copy import deepcopy
            return deepcopy(job['verification'])

    def discard(self, owner, key):
        with self.lock:
            job = self._get(owner, key)
            if job['stage'] not in TERMINAL:
                raise ValueError(backend_message('Cancela la exportación antes de eliminarla'))
            shutil.rmtree(job['root'])
            del self.jobs[key]

    @staticmethod
    def _stop(process):
        if process is None:
            return
        if not getattr(process, '_report_gen_stopped', False):
            if os.name == 'nt':
                process._report_gen_job.close()
            elif process.returncode is not None:
                # Defensive guard for an externally reaped/unowned process handle.
                return process.wait(timeout=15)
            else:
                # The supervisor is still alive (or our unreaped child if it crashed).
                # Never poll it before signaling: its PID reserves this private group.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            # Mark only successful cleanup; never signal a stale group on a repeated call.
            process._report_gen_stopped = True
        process.wait(timeout=15)
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if process.stdout is not None and not process.stdout.closed:
            process.stdout.close()

    def _run(self):
        while not self.closed:
            self.wake.wait(.2)
            self.wake.clear()
            with self.lock:
                self._purge()
                if not self.pending:
                    continue
                key = self.pending.popleft()
                job = self.jobs[key]
                job['stage'] = 'cancelling' if job['cancelled'] else 'validating'
            process = None
            outcome = 'error'
            language_token = set_language(job['error_language'])
            try:
                if not job['cancelled']:
                    process = _start_process([sys.executable, str(Path(__file__).resolve()),
                                              '--worker-gated', str(job['root'])])
                    job['process'] = process
                    started = time.monotonic()
                    while (returncode := _exitcode(process)) is None:
                        if self.closed or job['cancelled'] or time.monotonic() - started > self.timeout:
                            self._stop(process)
                            if not self.closed and not job['cancelled']:
                                raise ValueError(backend_message('La exportación superó el tiempo máximo ({p0:g} s)', p0=self.timeout))
                            break
                        status_path = job['root'] / 'progress.json'
                        if status_path.exists():
                            stage = json.loads(status_path.read_text(encoding='utf-8'))['stage']
                            with self.lock:
                                if not job['cancelled']:
                                    job['stage'] = stage
                        time.sleep(.1)
                    if not job['cancelled'] and not self.closed and returncode:
                        failure = job['root'] / 'error.txt'
                        details = []
                        metadata = job['root'] / 'error.json'
                        if metadata.exists() and metadata.stat().st_size <= 512 * 1024:
                            try:
                                details = sanitize_diagnostics(json.loads(metadata.read_text(encoding='utf-8')))
                            except (ValueError, OSError):
                                pass  # Preserve the original worker error if metadata is damaged.
                        raise DiagnosticError(failure.read_text(encoding='utf-8') if failure.exists() else backend_message('El motor terminó sin generar el archivo'), diagnostics=details)
                with self.lock:
                    outcome = 'cancelled' if job['cancelled'] or self.closed else 'done'
                    if outcome == 'done':
                        record = job['root'] / 'verification.json'
                        if record.exists(): job['verification'] = json.loads(record.read_text(encoding='utf-8'))
            except Exception as exc:
                with self.lock:
                    outcome = 'cancelled' if job['cancelled'] else 'error'
                    job['error'] = str(exc)[:2000]
                    job['diagnostics'] = error_diagnostics(exc) if outcome == 'error' else []
            finally:
                cleanup_errors = []
                try:
                    self._stop(process)
                except Exception as exc:
                    cleanup_errors.append(str(exc))
                    outcome = 'error'
                try:
                    _clean_job_files(job['root'], keep_result=outcome == 'done')
                except Exception as exc:
                    cleanup_errors.append(str(exc))
                    outcome = 'error'
                if cleanup_errors:
                    # A cleanup failure invalidates publication even if rendering
                    # succeeded. Remove its deliverable too, when the OS permits.
                    try:
                        (job['root'] / 'result').unlink(missing_ok=True)
                    except OSError as result_error:
                        cleanup_errors.append(str(result_error))
                with self.lock:
                    # A cancellation can arrive while the completed worker's
                    # files are being cleaned, after outcome was calculated.
                    # Recheck under the same lock that publishes terminal state
                    # so an accepted cancellation cannot become a downloadable
                    # result. Only the already-rendered result remains here.
                    if outcome == 'done' and (job['cancelled'] or self.closed):
                        outcome = 'cancelled'
                        job['verification'] = None
                        try:
                            _clean_job_files(job['root'])
                        except Exception as exc:
                            cleanup_errors.append(str(exc))
                            outcome = 'error'
                    if cleanup_errors:
                        job['verification'] = None
                        job['diagnostics'] = []
                        detail = '; '.join(cleanup_errors)
                        job['error'] = backend_message(
                            'No se pudo completar la limpieza de la exportación: {detail}',
                            en='Export cleanup could not be completed: {detail}', detail=detail)[:2000]
                    job['updated'] = time.time()
                    job['stage'] = outcome
                reset_language(language_token)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            for job in self.jobs.values():
                job['cancelled'] = True
            self.wake.set()
        self.thread.join(timeout=20)
        if not self.thread.is_alive():
            shutil.rmtree(self.root, ignore_errors=True)


def worker(root):
    import delivery
    import export
    root = Path(root)
    config = json.loads((root / 'job.json').read_text(encoding='utf-8'))
    language_token = set_language(config.get('error_language', 'es'))
    def progress(stage):
        atomic_write(root / 'progress.json', json.dumps({'stage': stage}).encode())
    try:
        if config['kind'] == 'delivery':
            payload = delivery.build(root / 'source', config['formats'], config['revision'], config['label'],
                                     config['captured'], root / 'outputs', progress)
            atomic_write(root / 'result', payload)
            from io import BytesIO
            import zipfile
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                record = json.loads(archive.read('verificacion.json'))
            atomic_write(root / 'verification.json', json.dumps(record, ensure_ascii=False).encode())
        else:
            fmt = config['formats'][0]
            progress('rendering_' + fmt)
            output = export.export(root / 'source' / 'engagement.yaml', fmt, root / ('output.' + fmt))
            progress('checking_' + fmt)
            checks = delivery.inspect_export(output, fmt, config['captured'])
            payload=output.read_bytes()
            atomic_write(root / 'result', payload)
            from version import __version__
            from engine import load_engagement, report_language
            language = report_language(load_engagement(root / 'source' / 'engagement.yaml'))
            record = dict(format='report-gen-export-checks', version=1, tool_version=__version__,
                source_revision=config.get('revision'), warnings=delivery.public_warnings(config['captured'].get('issues',[]), language),
                files={config.get('filename',output.name):dict(bytes=len(payload),sha256=sha256(payload).hexdigest(),checks=checks)})
            atomic_write(root / 'verification.json', json.dumps(record,ensure_ascii=False).encode())
    except Exception as exc:
        atomic_write(root / 'error.txt', str(exc)[:2000].encode('utf-8'))
        atomic_write(root / 'error.json', json.dumps(error_diagnostics(exc), ensure_ascii=False).encode('utf-8'))
        return 1
    finally:
        reset_language(language_token)
    return 0


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--supervisor-gated':
        raise SystemExit(_supervise(json.loads(sys.argv[2])))
    if len(sys.argv) != 3 or sys.argv[1] not in ('--worker', '--worker-gated'):
        raise SystemExit('Use the local report-gen export API')
    if sys.argv[1] == '--worker-gated' and sys.stdin.buffer.read(1) != b'1':
        raise SystemExit('Export worker was not released')
    raise SystemExit(worker(sys.argv[2]))
