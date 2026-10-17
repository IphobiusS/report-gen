"""Non-blocking cross-process guards for application setup and workspace access.

Locks live in a private user directory, not in projects or distributable sources.
The operating system releases them on process exit; an old lock file is harmless.
"""
from contextlib import contextmanager, ExitStack
from hashlib import sha256
import os
from pathlib import Path
import stat

from error_messages import message
from workspace_paths import _no_links


def _directory():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache')))
    if not base.is_absolute():
        raise ValueError('The report-gen lock directory must be absolute.')
    return base / 'report-gen' / 'locks'


@contextmanager
def exclusive_paths(*paths, lock_directory=None):
    """Reject concurrent use of any canonical path, including another installation.

    Acquire paths in a stable order. The lock is deliberately not reentrant: a
    second server in the same process must also fail instead of sharing data.
    """
    directory = Path(lock_directory) if lock_directory is not None else _directory()
    _no_links(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    names = set()
    for path in paths:
        path = Path(path).expanduser().absolute()
        _no_links(path)
        names.add(os.path.normcase(str(path.resolve())))
    with ExitStack() as stack:
        for name in sorted(names):
            target = directory / (sha256(name.encode('utf-8')).hexdigest() + '.lock')
            _no_links(target)
            fd = os.open(target, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            stream = stack.enter_context(os.fdopen(fd, 'r+b'))
            details = os.fstat(fd)
            if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                raise ValueError('The report-gen lock must be a regular private file.')
            try:
                if os.name == 'nt':
                    import msvcrt
                    if details.st_size == 0:
                        stream.write(b'0'); stream.flush()
                    stream.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    def unlock(stream=stream):
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    def unlock(stream=stream):
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                raise ValueError(message(
                    'Cierra el editor y cualquier instalación en curso antes de continuar. La aplicación o sus datos están en uso.',
                    en='Close the editor and any installation in progress before continuing. The application or its data is in use.',
                    pt='Feche o editor e qualquer instalação em andamento antes de continuar. O aplicativo ou seus dados estão em uso.')) from None
            stack.callback(unlock)
        yield
