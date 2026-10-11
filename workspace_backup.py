"""Bounded workspace archives and recoverable restoration to an empty installation.

This is a local, single-process operation. It is not a merge or an encrypted archive.
Project archives retain their existing validation, evidence and history contracts.
"""
from error_messages import message as backend_message
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import logging
import re
import shutil
import stat
import tempfile
import zipfile
import zlib

import design_library
import finding_library
import project_history as history
from input_guard import load_json, MAX_DOCUMENT_BYTES
from storage import atomic_write
from workspace_paths import portable_project_slug

MAX_ARCHIVE = history.MAX_ARCHIVE
MAX_EXPANDED = history.MAX_EXPANDED
MAX_FILES = history.MAX_FILES
MAX_PROJECTS = 200
LIBRARIES = ('libraries/findings.json', 'libraries/designs.json')
CLEANUP_WARNING = 'Restauración completada; queda limpieza privada pendiente. Se reintentará al usar la aplicación. / Restoration completed; private cleanup is pending and will be retried.'


def _slug(value):
    return (isinstance(value, str) and 1 <= len(value) <= 80
            and value == value.lower() and not value.startswith('-')
            and all(c.isalnum() or c in '-_' for c in value)
            and portable_project_slug(value) == value)


def _targets(projects, findings, designs):
    paths = [Path(projects), Path(findings), Path(designs)]
    if len(set(p.absolute() for p in paths)) != 3:
        raise ValueError(backend_message('Destinos de respaldo incompatibles'))
    for path in paths:
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError(backend_message('No se permiten enlaces simbólicos en los destinos'))
    if paths[0] in paths[1].parents or paths[0] in paths[2].parents:
        raise ValueError(backend_message('Las bibliotecas deben estar fuera de los proyectos'))
    return paths


def _read_library(path, kind):
    if path.is_symlink():
        raise ValueError(backend_message('Biblioteca enlazada no permitida'))
    if path.exists() and (not path.is_file() or path.stat().st_size > MAX_DOCUMENT_BYTES):
        raise ValueError(backend_message('Biblioteca demasiado grande o no válida'))
    data = finding_library.load(path) if kind == 'findings' else design_library.load_personal(path)
    expected = 'report-gen-library' if kind == 'findings' else 'report-gen-designs'
    if (not isinstance(data, dict) or data.get('format') != expected or type(data.get('version')) is not int
            or data['version'] != 1 or not isinstance(data.get('templates'), list)
            or len(data['templates']) > (500 if kind == 'findings' else 200)):
        raise ValueError(backend_message('Formato de biblioteca inválido'))
    seen = set()
    for entry in data['templates']:
        if not isinstance(entry, dict):
            raise ValueError(backend_message('Plantilla inválida'))
        ident = entry.get('uid' if kind == 'findings' else 'id')
        if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in seen:
            raise ValueError(backend_message('Identidad de plantilla inválida o repetida'))
        seen.add(ident)
        if kind == 'findings':
            from workflows import UID
            if not UID.fullmatch(ident):
                raise ValueError(backend_message('Identificador de hallazgo reutilizable inválido'))
            finding_library.validate_entry(entry)
            versions = entry.get('versions')
            if not isinstance(versions, list) or not 1 <= len(versions) <= 200:
                raise ValueError(backend_message('Historial de plantilla inválido'))
            for version in versions:
                finding_library.validate_entry(version)
        else:
            design_library.text(entry.get('name'), 'Nombre')
    return data


def _project_entries(projects):
    """Exclude only the exact empty regular marker shipped in the package."""
    rows = sorted(projects.iterdir()) if projects.exists() else []
    return [path for path in rows if not (
        path.name == '.gitkeep' and not path.is_symlink()
        and path.is_file() and path.stat().st_size == 0)]


def _empty(paths):
    projects, findings, designs = paths
    if projects.exists() and (not projects.is_dir() or _project_entries(projects)):
        raise ValueError(backend_message('Restaura únicamente en una instalación vacía: ya hay proyectos o archivos'))
    if _read_library(findings, 'findings')['templates'] or _read_library(designs, 'designs')['templates']:
        raise ValueError(backend_message('Restaura únicamente en una instalación vacía: ya hay plantillas personales'))


def _zip_entries(archive, allowed, max_files=MAX_FILES):
    entries = archive.infolist()
    if len(entries) > max_files or sum(e.file_size for e in entries) > MAX_EXPANDED:
        raise ValueError(backend_message('Respaldo demasiado grande'))
    seen = set()
    for entry in entries:
        name = entry.filename
        mode = stat.S_IFMT(entry.external_attr >> 16)
        if (name.casefold() in seen or not allowed(name) or entry.is_dir()
                or entry.flag_bits & 1 or mode not in (0, stat.S_IFREG)):
            raise ValueError(backend_message('Entrada ZIP no permitida: {p0}', p0=name))
        seen.add(name.casefold())
    return entries


def _allowed(name):
    return name == 'manifest.json' or name in LIBRARIES or (
        name.startswith('projects/') and name.endswith('.zip') and _slug(name[9:-4]))


def _budget(files):
    """Count nested, uncompressed payloads as well as their outer containers."""
    size = sum(map(len, files.values()))
    count = len(files)
    for name, blob in files.items():
        if name.startswith('projects/'):
            with zipfile.ZipFile(BytesIO(blob)) as nested:
                rows = nested.infolist()
                size += sum(e.file_size for e in rows)
                count += len(rows)
                if size > MAX_EXPANDED or count > MAX_FILES:
                    raise ValueError(backend_message('Límite integral: 512 MiB expandidos o 20000 archivos'))
    if size > MAX_EXPANDED or count > MAX_FILES:
        raise ValueError(backend_message('Límite integral: 512 MiB expandidos o 20000 archivos'))


def export_workspace(projects, findings, designs):
    paths = _targets(projects, findings, designs)
    recover(*paths)
    history.recover_transactions(paths[0])
    files = {}
    rows = _project_entries(paths[0])
    # Refuse to silently omit a damaged project, a stray file or a symlink.
    if len(rows) > MAX_PROJECTS:
        raise ValueError(backend_message('Límite de 200 proyectos por respaldo integral'))
    if len({directory.name.casefold() for directory in rows}) != len(rows):
        raise ValueError(backend_message('Hay proyectos con nombres equivalentes en mayúsculas o Unicode; cambia uno de los nombres antes de respaldar'))
    for directory in rows:
        if directory.is_symlink() or not directory.is_dir() or not _slug(directory.name):
            raise ValueError(backend_message('Entrada no portable en proyectos: {p0}', p0=directory.name))
        if not (directory / 'engagement.yaml').is_file():
            raise ValueError(backend_message('Proyecto sin engagement.yaml: {p0}', p0=directory.name))
        files['projects/' + directory.name + '.zip'] = history.export_bundle(directory)
        _budget(files)
    for path, kind, name in zip(paths[1:], ('findings', 'designs'), LIBRARIES):
        data = _read_library(path, kind)
        files[name] = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    manifest = {'format': 'report-gen-workspace', 'version': 1, 'created': history.now(),
                'files': {name: sha256(blob).hexdigest() for name, blob in files.items()}}
    files['manifest.json'] = history.dumps(manifest)
    _budget(files)
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, blob in files.items():
            archive.writestr(name, blob)
    if stream.tell() > MAX_ARCHIVE:
        raise ValueError(backend_message('Respaldo integral mayor que 256 MiB'))
    return stream.getvalue()


def _journal(paths):
    return paths[0].parent / '.workspace-restore.json'


def _move(source, target):
    source.rename(target)


def recover(projects, findings, designs):
    """Rollback an interrupted activation before any API can observe partial data.

    Rollback itself is idempotent: new targets move back to their stage before
    the previous empty targets are restored. Journal paths are not ZIP inputs.
    """
    journal = Path(projects).parent / '.workspace-restore.json'
    if not journal.exists() and not journal.is_symlink():
        return
    paths = _targets(projects, findings, designs)
    if journal.is_symlink() or journal.stat().st_size > 4096:
        raise ValueError(backend_message('Registro de recuperación inválido'))
    record = load_json(journal.read_bytes())
    if (not isinstance(record, dict) or record.get('format') != 'report-gen-workspace-restore-1'
            or not isinstance(record.get('stage'), str)
            or not re.fullmatch(r'\.workspace-stage-[a-z0-9_]{8}', record['stage'])
            or type(record.get('committed')) is not bool
            or not isinstance(record.get('had'), list) or len(record['had']) != 3
            or any(type(v) is not bool for v in record['had'])):
        raise ValueError(backend_message('Registro de recuperación inválido'))
    stage = journal.parent / record['stage']
    if record['committed']:
        # Installed data is already authoritative. Cleanup can be interrupted
        # after removing any subset of the stage, or before unlinking its journal.
        # Keep the journal until both operations finish so retries are idempotent.
        if stage.is_symlink() or (stage.exists() and not stage.is_dir()):
            raise ValueError(backend_message('Área de recuperación inválida'))
        try:
            if stage.exists(): shutil.rmtree(stage)
            journal.unlink()
        except OSError:
            logging.getLogger(__name__).warning(CLEANUP_WARNING)
            return True
        return False
    if stage.is_symlink() or not stage.is_dir():
        raise ValueError(backend_message('Falta el área de recuperación; se conserva el registro'))
    for tree in (stage, stage/'new', stage/'previous'):
        if tree.is_symlink() or not tree.is_dir():
            raise ValueError(backend_message('Área de recuperación inválida'))
    if not record['committed']:
        for i in reversed(range(3)):
            target, new, previous = paths[i], stage/'new'/str(i), stage/'previous'/str(i)
            if new.is_symlink() or previous.is_symlink():
                raise ValueError(backend_message('Enlace en recuperación no permitido'))
            if not new.exists():
                if not target.exists() or (record['had'][i] and not previous.exists()):
                    raise ValueError(backend_message('Estado ambiguo; se conservan las copias de recuperación'))
                _move(target, new)
            if previous.exists():
                if target.exists():
                    raise ValueError(backend_message('Destino inesperado; se conservan las copias'))
                _move(previous, target)
            if target.exists() != record['had'][i]:
                raise ValueError(backend_message('Recuperación incompleta; se conserva el registro'))
    journal.unlink()
    shutil.rmtree(stage)


def restore_workspace(blob, projects, findings, designs):
    paths = _targets(projects, findings, designs)
    recover(*paths)
    _empty(paths)
    if len(blob) > MAX_ARCHIVE:
        raise ValueError(backend_message('Respaldo integral mayor que 256 MiB'))
    stage = None
    try:
        with zipfile.ZipFile(BytesIO(blob)) as archive:
            entries = _zip_entries(archive, _allowed, MAX_PROJECTS + 3)
            if 'manifest.json' not in archive.namelist():
                raise ValueError(backend_message('Falta el manifiesto del espacio de trabajo'))
            manifest = load_json(archive.read('manifest.json'))
            if (not isinstance(manifest, dict) or manifest.get('format') != 'report-gen-workspace'
                    or type(manifest.get('version')) is not int or manifest['version'] != 1):
                raise ValueError(backend_message('No es un respaldo integral de report-gen'))
            hashes = manifest.get('files')
            names = {entry.filename for entry in entries} - {'manifest.json'}
            if not isinstance(hashes, dict) or set(hashes) != names or not set(LIBRARIES) <= names:
                raise ValueError(backend_message('Manifiesto incompleto'))
            files = {name: archive.read(name) for name in names}
            if any(sha256(value).hexdigest() != hashes[name] for name, value in files.items()):
                raise ValueError(backend_message('Integridad del respaldo inválida'))
            _budget(dict(files, **{'manifest.json': archive.read('manifest.json')}))
        paths[0].parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.workspace-stage-', dir=paths[0].parent))
        (stage/'new'/'0').mkdir(parents=True)
        (stage/'previous').mkdir()
        for name, payload in files.items():
            if name.startswith('projects/'):
                history.import_bundle(payload, stage/'new'/'0'/name[9:-4])
        for index, name, kind in zip((1, 2), LIBRARIES, ('findings', 'designs')):
            atomic_write(stage/'new'/str(index), files[name])
            _read_library(stage/'new'/str(index), kind)
        result = {'projects': sum(name.startswith('projects/') for name in files),
                  'findings': len(_read_library(stage/'new'/'1', 'findings')['templates']),
                  'designs': len(_read_library(stage/'new'/'2', 'designs')['templates'])}
        _empty(paths)
        record = {'format': 'report-gen-workspace-restore-1', 'stage': stage.name,
                  'had': [p.exists() for p in paths], 'committed': False}
        atomic_write(_journal(paths), history.dumps(record))
        for i, path in enumerate(paths):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                _move(path, stage/'previous'/str(i))
            _move(stage/'new'/str(i), path)
        record['committed'] = True
        atomic_write(_journal(paths), history.dumps(record))
        if recover(*paths): result['warnings'] = [CLEANUP_WARNING]
        return result
    except (zipfile.BadZipFile, KeyError, TypeError, RuntimeError, EOFError, zlib.error) as exc:
        raise ValueError(backend_message('Respaldo integral inválido')) from exc
    finally:
        # An activation failure keeps its journal/stage for the next API call.
        if stage and stage.exists() and not _journal(paths).exists():
            shutil.rmtree(stage)
