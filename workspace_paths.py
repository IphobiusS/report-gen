"""Explicit local data locations, independent from the installed application.

No automatic move or discovery: without a selection the established webapp/
layout is retained. An external workspace contains projects/, library/ and a
local browser identity; histories and evidence remain inside their project.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import stat
import time

from error_messages import message

ENVIRONMENT_KEY = 'REPORT_GEN_WORKSPACE'
BROWSER_ID_FILE = '.report-gen-browser-id'


def portable_project_slug(slug):
    """Keep a normalized *new* project name usable on supported filesystems.

    Windows device names also apply to directories, including COM/LPT followed
    by a superscript digit. Reserve room for download suffixes and measure UTF-8
    bytes as well as characters: supplementary-plane letters use four bytes.
    Callers resolving an existing project must retain its original identity.
    """
    devices = {'con', 'prn', 'aux', 'nul',
               *(prefix + number for prefix in ('com', 'lpt')
                 for number in (*'123456789', '¹', '²', '³'))}
    if slug.casefold() in devices:
        slug += '-project'
    truncated = False
    while len(slug.encode('utf-8')) > 240:
        slug = slug[:-1]
        truncated = True
    return (slug.rstrip('-') if truncated else slug) or 'engagement'


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    projects: Path
    findings: Path
    designs: Path
    external: bool


def _no_links(path):
    """Check unresolved components, including Windows junctions/reparse points."""
    for entry in (path, *path.parents):
        try:
            details = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(details.st_mode) or getattr(details, 'st_file_attributes', 0) & 0x400:
            raise ValueError(message(
                'El espacio de trabajo no admite enlaces simbólicos ni puntos de reanálisis.',
                en='The workspace does not allow symbolic links or reparse points.'))


def select_workspace(installation, workspace=None, *, environ=None, create=False):
    """Resolve CLI > environment > legacy layout; never migrate existing data.

    Configured roots must not overlap the installation. All configured managed
    paths are checked before creating directories; existing permissions remain
    untouched. Callers should stop other editors before migration or updates.
    """
    installation = Path(installation).resolve()
    environ = os.environ if environ is None else environ
    value = workspace if workspace is not None else environ.get(ENVIRONMENT_KEY)
    external = value is not None
    if external:
        if not str(value).strip() or '\x00' in str(value):
            raise ValueError(message('Indica una carpeta de trabajo válida.', en='Provide a valid workspace directory.'))
        root = Path(value).expanduser().absolute()
        _no_links(root)
        root = root.resolve()
        if root == installation or root in installation.parents or installation in root.parents:
            raise ValueError(message(
                'El espacio de trabajo debe estar fuera de la instalación y no contenerla.',
                en='The workspace must be outside the installation and must not contain it.'))
    else:
        root = installation / 'webapp'
    result = WorkspacePaths(root, root / 'projects', root / 'library/findings.json',
                            root / 'library/designs.json', external)
    if external:
        for directory in (root, result.projects, result.findings.parent):
            _no_links(directory)
            if directory.exists() and not directory.is_dir():
                raise ValueError(message('Una ruta del espacio de trabajo no es una carpeta.',
                                         en='A workspace path is not a directory.'))
        for library in (result.findings, result.designs):
            _no_links(library)
            if library.exists() and (not library.is_file() or library.stat().st_nlink != 1):
                raise ValueError(message('Las bibliotecas deben ser archivos regulares sin enlaces.',
                                         en='Libraries must be regular files without links.'))
    if create:
        if external:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
        result.projects.mkdir(parents=True, exist_ok=True, mode=0o700)
        if external:
            result.findings.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return result


@contextmanager
def workspace_environment(selection):
    """Pass an absolute selection to child processes, restoring embedded callers."""
    previous = os.environ.get(ENVIRONMENT_KEY)
    if selection.external:
        os.environ[ENVIRONMENT_KEY] = str(selection.root)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(ENVIRONMENT_KEY, None)
        else:
            os.environ[ENVIRONMENT_KEY] = previous


def browser_namespace(projects, findings, designs):
    """Stable opaque scope; neither filesystem paths nor this seed leave disk.

    A fresh restore has a fresh identity. Private browser drafts are deliberately
    excluded from project/workspace backups and never adopted by matching slug.
    """
    paths = tuple(Path(value).absolute() for value in (projects, findings, designs))
    for path in paths:
        _no_links(path)
    root = paths[0].parent
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    identity = root / BROWSER_ID_FILE
    _no_links(identity)
    try:
        descriptor = os.open(identity, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(secrets.token_hex(32).encode('ascii') + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
    # An exclusive creator can be between open and fsync in another process.
    # Wait only for an incomplete new seed; never replace a damaged identity.
    seed = b''
    for attempt in range(25):
        descriptor = os.open(identity, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            details = os.fstat(stream.fileno())
            if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                raise ValueError(message('La identidad local del espacio no es un archivo regular sin enlaces.',
                                         en='The local workspace identity must be a regular file without links.'))
            seed = stream.read(66)
        if len(seed) == 65 or len(seed) > 65:
            break
        if attempt < 24:
            time.sleep(0.02)
    if len(seed) != 65 or seed[-1:] != b'\n' or any(byte not in b'0123456789abcdef' for byte in seed[:-1]):
        raise ValueError(message('La identidad local del espacio está dañada. Conserva el archivo y tus borradores; no se ha regenerado.',
                                 en='The local workspace identity is damaged. Keep the file and your drafts; it was not regenerated.'))
    # Including the effective paths separates custom API configurations that
    # share a parent directory, without publishing a path-derived bare hash.
    address = json.dumps([str(path.resolve()) for path in paths], ensure_ascii=False).encode('utf-8')
    return hmac.new(seed[:-1], address, hashlib.sha256).hexdigest()
