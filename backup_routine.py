"""Opt-in private backups while the local editor process is running.

The workspace mutation lock protects capture. A real temporary restoration and
read-back validate every new archive before older owned archives can be removed.
Configuration and paths remain local; no passwords or network access are used.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import re
import secrets
import stat
import tempfile
import threading
import time

from error_messages import message
from input_guard import load_json
from storage import atomic_write
from workspace_paths import _no_links
import workspace_backup

INTERVALS = (3600, 86400, 604800)
STATE_NAME = '.report-gen-backup-routine.json'
MAX_STATE = 131072
MAX_RECORDS = 128
NAME = re.compile(r'workspace-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{16}\.zip')
DIGEST = re.compile(r'[a-f0-9]{64}')
FAILURE = 'backup_failed'


def _invalid():
    return ValueError(message('Configuración o carpeta de respaldo no válida. Revisa la ruta y conserva las copias existentes.',
                             en='Invalid backup configuration or directory. Check the path and keep existing copies.'))


def _stamp(value):
    return value is None or (type(value) in (int, float) and math.isfinite(value) and value >= 0)


def _read_regular(path, maximum):
    _no_links(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        details = os.fstat(stream.fileno())
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1 or details.st_size > maximum:
            raise _invalid()
        blob = stream.read(maximum + 1)
        if len(blob) > maximum:
            raise _invalid()
        return blob


class BackupRoutine:
    def __init__(self, projects, findings, designs, installation, mutation_lock, *, clock=time.time):
        self.paths = tuple(Path(p).absolute() for p in (projects, findings, designs))
        self.installation = Path(installation).absolute()
        self.root = self.paths[0].parent
        self.state_path = self.root / STATE_NAME
        self.mutation_lock = mutation_lock
        self.lock = threading.RLock()
        self.clock = clock
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = None
        self.transient_error = None
        self.retry_after = 0

    def _default(self):
        return dict(format='report-gen-backup-routine', version=1, enabled=False,
                    destination='', owner='', interval_seconds=86400, retention=7,
                    records=[], last_success=None, last_verified=None, last_error=None)

    def _load(self):
        if not self.state_path.exists() and not self.state_path.is_symlink():
            _no_links(self.state_path)
            return self._default()
        try:
            state = load_json(_read_regular(self.state_path, MAX_STATE))
            expected = self._default()
            if (not isinstance(state, dict) or set(state) != set(expected)
                    or state['format'] != expected['format'] or type(state['version']) is not int or state['version'] != 1
                    or type(state['enabled']) is not bool or type(state['interval_seconds']) is not int
                    or state['interval_seconds'] not in INTERVALS or type(state['retention']) is not int
                    or not 1 <= state['retention'] <= 90 or not isinstance(state['destination'], str)
                    or len(state['destination']) > 4096 or not isinstance(state['owner'], str)
                    or not re.fullmatch(r'[a-f0-9]{32}', state['owner'])
                    or not isinstance(state['records'], list) or len(state['records']) > MAX_RECORDS
                    or not _stamp(state['last_success']) or not _stamp(state['last_verified'])
                    or state['last_error'] not in (None, FAILURE, 'retention_pending')):
                raise _invalid()
            names = set()
            for row in state['records']:
                if (not isinstance(row, dict) or set(row) != {'name', 'sha256', 'created'}
                        or not isinstance(row['name'], str) or not NAME.fullmatch(row['name'])
                        or row['name'] in names or not isinstance(row['sha256'], str)
                        or not DIGEST.fullmatch(row['sha256']) or row['created'] is None or not _stamp(row['created'])):
                    raise _invalid()
                names.add(row['name'])
            return state
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise _invalid() from None

    def _save(self, state):
        _no_links(self.state_path)
        if self.state_path.exists():
            _read_regular(self.state_path, MAX_STATE)
        blob = (json.dumps(state, ensure_ascii=False, indent=2) + '\n').encode()
        if len(blob) > MAX_STATE:
            raise _invalid()
        atomic_write(self.state_path, blob)

    def _destination(self, value):
        if (not isinstance(value, str) or not value.strip() or len(value) > 4096
                or any(ord(c) < 32 for c in value) or '..' in Path(value).parts):
            raise _invalid()
        destination = Path(value).expanduser()
        if not destination.is_absolute():
            raise _invalid()
        _no_links(destination)
        if not destination.is_dir():
            raise ValueError(message('Crea primero la carpeta de destino y escribe su ruta absoluta.',
                                     en='Create the destination directory first and enter its absolute path.'))
        destination = destination.resolve()
        # A selected parent must not contain source data; no recursive archive
        # directory within the application or workspace is allowed either.
        for source in (self.root, self.installation, *self.paths):
            source = source.resolve()
            if source == destination or source in destination.parents or destination in source.parents:
                raise _invalid()
        return destination

    def _directory(self, state, *, create=False):
        destination = self._destination(state['destination'])
        folder = destination / ('report-gen-backups-' + state['owner'])
        _no_links(folder)
        marker = folder / '.report-gen-owner'
        expected = (state['owner'] + '\n').encode()
        if create and not folder.exists():
            folder.mkdir(mode=0o700)
            descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(expected)
                stream.flush()
                os.fsync(stream.fileno())
        if not folder.is_dir() or _read_regular(marker, 33) != expected:
            raise _invalid()
        return folder

    def configure(self, body):
        with self.lock:
            if (not isinstance(body, dict) or set(body) != {'enabled', 'destination', 'interval_seconds', 'retention', 'ack_unencrypted'}
                    or type(body['enabled']) is not bool or body['ack_unencrypted'] is not True
                    or type(body['interval_seconds']) is not int or body['interval_seconds'] not in INTERVALS
                    or type(body['retention']) is not int or not 1 <= body['retention'] <= 90):
                raise ValueError(message('Revisa destino, frecuencia y retención; confirma que las copias privadas no están cifradas.',
                                         en='Review destination, frequency and retention; acknowledge that private copies are not encrypted.'))
            destination = self._destination(body['destination'])
            state = self._load()
            if state['destination'] != str(destination):
                # Old destinations remain untouched, even after switching back.
                state = self._default()
                state.update(destination=str(destination), owner=secrets.token_hex(16))
            state.update(enabled=body['enabled'], interval_seconds=body['interval_seconds'], retention=body['retention'])
            self._directory(state, create=True)
            self._save(state)
            self.transient_error = None
            self.retry_after = 0
            self.wake_event.set()
            return self.status()

    def disable(self):
        with self.lock:
            state = self._load()
            if state['destination']:
                state['enabled'] = False
                self._save(state)
            self.wake_event.set()
            return self.status()

    def status(self):
        with self.lock:
            state = self._load()
            latest = state['records'][-1] if state['records'] else None
            return dict(enabled=state['enabled'], destination=state['destination'], interval_seconds=state['interval_seconds'],
                        retention=state['retention'], copies=len(state['records']), last_success=state['last_success'],
                        last_verified=state['last_verified'], last_error=self.transient_error or state['last_error'],
                        next_due=(state['last_success'] or 0) + state['interval_seconds'] if state['enabled'] and state['last_success'] else None,
                        latest_name=latest['name'] if latest else None,
                        latest_sha256=latest['sha256'] if latest else None,
                        directory=str(Path(state['destination']) / ('report-gen-backups-' + state['owner'])) if state['destination'] else '',
                        scheduler_running=bool(self.thread and self.thread.is_alive()), encrypted=False, browser_drafts_included=False)

    def _restore_check(self, blob, directory):
        with tempfile.TemporaryDirectory(prefix='.restore-check-', dir=directory) as name:
            root = Path(name)
            result = workspace_backup.restore_workspace(blob, root/'projects', root/'library/findings.json', root/'library/designs.json')
            if result.get('warnings'):
                raise OSError('temporary restore cleanup incomplete')
            return result

    def _archive(self, folder, row):
        blob = _read_regular(folder / row['name'], workspace_backup.MAX_ARCHIVE)
        if sha256(blob).hexdigest() != row['sha256']:
            raise _invalid()
        return blob

    def _retire(self, folder, row):
        # Reject already-modified copies without moving them. Then claim the
        # pathname atomically and revalidate the claimed file, not a pathname
        # that another process could have replaced after the first read.
        self._archive(folder, row)
        quarantine = Path(tempfile.mkdtemp(prefix='.retention-', dir=folder))
        claimed = quarantine / row['name']
        try:
            _no_links(folder)
            os.rename(folder / row['name'], claimed)
            self._archive(quarantine, row)
            claimed.unlink()
        except (OSError, ValueError):
            if claimed.exists() or claimed.is_symlink():
                try:
                    # An exclusive hard-link creation cannot overwrite a new
                    # file at the original name. Preserve the quarantine when
                    # the name is occupied or this filesystem cannot link.
                    os.link(claimed, folder / row['name'], follow_symlinks=False)
                    claimed.unlink()
                except OSError:
                    pass
            raise
        finally:
            try:
                quarantine.rmdir()
            except OSError:
                pass  # Contains a preserved copy; never recursively delete it.

    def _failure(self, state):
        self.transient_error = FAILURE
        self.retry_after = self.clock() + 300
        state['last_error'] = FAILURE
        try:
            self._save(state)
        except (OSError, ValueError):
            pass

    def run(self):
        with self.lock:
            state = self._load()
            if not state['destination']:
                raise ValueError(message('Configura una carpeta antes de crear el respaldo.', en='Configure a directory before creating a backup.'))
            if len(state['records']) >= MAX_RECORDS:
                raise ValueError(message('Hay demasiadas copias pendientes de retención. Conserva los archivos y configura otra carpeta.',
                                         en='Too many copies are pending retention. Keep the files and configure another directory.'))
            try:
                folder = self._directory(state)
                # No partial project, evidence or library mutation is observable.
                with self.mutation_lock:
                    blob = workspace_backup.export_workspace(*self.paths)
                self._restore_check(blob, folder)
                now = self.clock()
                name = 'workspace-' + datetime.fromtimestamp(now, timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(8) + '.zip'
                row = dict(name=name, sha256=sha256(blob).hexdigest(), created=now)
                # No guessed path and no overwrite. An interrupted write remains
                # an unowned .pending file; it can never displace a valid backup.
                descriptor, pending = tempfile.mkstemp(prefix='.pending-', dir=folder)
                try:
                    with os.fdopen(descriptor, 'wb') as stream:
                        stream.write(blob)
                        stream.flush()
                        os.fsync(stream.fileno())
                    _no_links(folder)
                    if sha256(_read_regular(Path(pending), workspace_backup.MAX_ARCHIVE)).hexdigest() != row['sha256']:
                        raise _invalid()
                    target = folder / name
                    if target.exists() or target.is_symlink():
                        raise _invalid()
                    os.rename(pending, target)
                finally:
                    Path(pending).unlink(missing_ok=True)
                state['records'].append(row)
                state.update(last_success=now, last_verified=now, last_error=None)
                # Persist the new verified copy before any old copy is rotated.
                self._save(state)
                retained = []
                pending_rotation = False
                for old in state['records'][:-state['retention']]:
                    try:
                        self._retire(folder, old)
                    except FileNotFoundError:
                        pass
                    except (OSError, ValueError):
                        retained.append(old)
                        pending_rotation = True
                state['records'] = retained + state['records'][-state['retention']:]
                state['last_error'] = 'retention_pending' if pending_rotation else None
                self._save(state)
                self.transient_error = None
                self.retry_after = 0
                return self.status()
            except (OSError, ValueError):
                self._failure(state)
                raise ValueError(message('No se pudo completar el respaldo verificado. Revisa espacio libre, permisos y la carpeta; conserva las copias disponibles.',
                                         en='The verified backup could not be completed. Check free space, permissions and the directory; keep the available copies.')) from None

    def verify_latest(self):
        with self.lock:
            state = self._load()
            if not state['records']:
                raise ValueError(message('Todavía no hay una copia para comprobar.', en='There is no copy to check yet.'))
            try:
                folder = self._directory(state)
                self._restore_check(self._archive(folder, state['records'][-1]), folder)
                state['last_verified'] = self.clock()
                # Checking the newest copy does not resolve older archives that
                # could not be rotated. Keep that pending work visible.
                state['last_error'] = 'retention_pending' if len(state['records']) > state['retention'] else None
                self._save(state)
                self.transient_error = None
                return self.status()
            except (OSError, ValueError):
                self._failure(state)
                raise ValueError(message('No se pudo restaurar temporalmente la última copia. Conserva el archivo y revisa espacio, permisos e integridad.',
                                         en='The latest copy could not be restored temporarily. Keep the file and check space, permissions and integrity.')) from None

    def tick(self):
        with self.lock:
            try:
                state = self._load()
                now = self.clock()
                if state['enabled'] and now >= self.retry_after and (state['last_success'] is None or now - state['last_success'] >= state['interval_seconds']):
                    self.run()
            except (OSError, ValueError):
                # No project text, filesystem path, or exception text is logged.
                self.transient_error = FAILURE
                self.retry_after = self.clock() + 300

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.stop_event.clear()
            def loop():
                while not self.stop_event.is_set():
                    self.tick()
                    self.wake_event.wait(60)
                    self.wake_event.clear()
            self.thread = threading.Thread(target=loop, name='report-gen-private-backups', daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.wake_event.set()
        # Active captures complete safely; the thread never starts a second job.
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
