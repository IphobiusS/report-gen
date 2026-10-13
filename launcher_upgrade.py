"""Explicit, offline migration through the existing integral-backup contract.

Never import or execute code from the old installation. Stop both editors before
running: report-gen does not support concurrent processes writing one workspace.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile

from error_messages import language_scope, message
from languages import console_language, language_argument, language_index
import workspace_backup as backup
from workspace_paths import select_workspace


def _no_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        try:
            details = part.lstat()
        except FileNotFoundError:
            continue
        # Windows directory junctions are reparse points, but not necessarily
        # symlinks. The stat fallback also supports Python 3.10/3.11.
        if stat.S_ISLNK(details.st_mode) or getattr(details, 'st_file_attributes', 0) & 0x400:
            raise ValueError(message('No se permiten enlaces simbólicos ni puntos de reanálisis en la migración.',
                en='Symbolic links and reparse points are not allowed during migration.'))
    return path


def _locations(root, external=False):
    base = root if external else root / 'webapp'
    return base / 'projects', base / 'library/findings.json', base / 'library/designs.json'


def _installation(value):
    root = _no_links(Path(value).expanduser())
    if not root.is_dir() or not (root / 'webapp/app.py').is_file() or not (root / 'engine.py').is_file():
        raise ValueError(message('Selecciona la carpeta de instalación que contiene engine.py y webapp/app.py.',
            en='Select the installation directory containing engine.py and webapp/app.py.'))
    for path in _locations(root):
        _no_links(path)
    return root.resolve()


def _pending(root, external=False):
    web = root if external else root / 'webapp'
    paths = [web / '.workspace-restore.json', *web.glob('.workspace-stage-*')]
    projects = web / 'projects'
    if projects.is_dir():
        paths.extend(projects.glob('.commit-*.json'))
    if any(path.exists() or path.is_symlink() for path in paths):
        raise ValueError(message('Hay una recuperación pendiente. Abre y cierra la instalación correspondiente antes de migrar.',
            en='Recovery is pending. Open and close the corresponding installation before migrating.'))


def _empty_destination(root, external=False):
    _pending(root, external)
    projects, findings, designs = _locations(root, external)
    if projects.exists():
        if not projects.is_dir():
            raise ValueError(message('El destino debe tener una carpeta de proyectos vacía.',
                en='The destination must have an empty projects directory.'))
        for path in projects.iterdir():
            if path.name != '.gitkeep' or path.is_symlink() or not path.is_file() or path.stat().st_size:
                raise ValueError(message('La nueva instalación ya contiene proyectos o archivos; usa una instalación vacía.',
                    en='The new installation already contains projects or files; use an empty installation.'))
    # Keep the same personal-library semantics as the validated restore API.
    for path, kind in ((findings, 'findings'), (designs, 'designs')):
        if backup._read_library(path, kind)['templates']:
            raise ValueError(message('La nueva instalación ya contiene plantillas personales; usa una instalación vacía.',
                en='The new installation already contains personal templates; use an empty installation.'))
    library = findings.parent
    if library.exists() and (not library.is_dir() or any(p.name not in {'findings.json', 'designs.json'} for p in library.iterdir())):
        raise ValueError(message('La carpeta de bibliotecas del destino contiene archivos desconocidos; usa una instalación vacía.',
            en='The destination library directory contains unknown files; use an empty installation.'))


def _read_file(path, maximum, destination=None):
    """Reject links and concurrent replacement; never follow a link while reading."""
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
        raise ValueError(message('Los datos deben ser archivos regulares, sin enlaces y dentro del límite integral.',
            en='Data must be regular files without links, within the workspace size limit.'))
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(descriptor, 'rb') as reader:
        opened = os.fstat(reader.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns):
            raise ValueError(message('Los datos cambiaron. Cierra ambos editores y vuelve a intentarlo.',
                en='Data changed. Close both editors and try again.'))
        digest = sha256()
        count = 0
        while chunk := reader.read(min(1024 * 1024, maximum + 1 - count)):
            count += len(chunk)
            if count > maximum:
                raise ValueError(message('Los datos superan el límite integral de 512 MiB.',
                    en='Data exceeds the 512 MiB integral-backup limit.'))
            digest.update(chunk)
            if destination is not None:
                destination.write(chunk)
        after = os.fstat(reader.fileno())
        if (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
            raise ValueError(message('Los datos cambiaron. Cierra ambos editores y vuelve a intentarlo.',
                en='Data changed. Close both editors and try again.'))
    return count, digest.hexdigest()


def _inventory(root):
    _pending(root)
    projects, findings, designs = _locations(root)
    _no_links(projects)
    if projects.exists() and not projects.is_dir():
        raise ValueError(message('La ruta de proyectos no es una carpeta.',
            en='The projects path is not a directory.'))
    paths = [findings, designs]
    directories = [projects] if projects.exists() else []
    seen = 0
    while directories:
        directory = directories.pop()
        for path in directory.iterdir():
            seen += 1
            if seen > backup.MAX_FILES:
                raise ValueError(message('Demasiados archivos para el respaldo integral.',
                    en='Too many files for an integral backup.'))
            _no_links(path)
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                directories.append(path)
            elif stat.S_ISREG(mode):
                if path == projects / '.gitkeep' and path.stat().st_size == 0:
                    continue
                paths.append(path)
            else:
                raise ValueError(message('El origen contiene una entrada especial no permitida.',
                    en='The source contains an unsupported special entry.'))
    result = {}
    total = 0
    for path in sorted(paths):
        _no_links(path)
        if not path.exists():
            continue
        size, digest = _read_file(path, backup.MAX_EXPANDED - total)
        total += size
        result[path.relative_to(root).as_posix()] = (size, digest)
    return result


def _copy_snapshot(source, destination, inventory):
    for name, expected in inventory.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as writer:
            observed = _read_file(source / name, expected[0], writer)
        if observed != expected:
            raise ValueError(message('Los datos cambiaron. Cierra ambos editores y vuelve a intentarlo.',
                en='Data changed. Close both editors and try again.'))


def _write_private(path, blob):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
    with os.fdopen(descriptor, 'wb') as writer:
        writer.write(blob)
        writer.flush()
        os.fsync(writer.fileno())


@contextmanager
def _private_stage(warnings):
    stage = tempfile.TemporaryDirectory(prefix='report-gen-upgrade-')
    completed = False
    try:
        yield Path(stage.name)
        completed = True
    finally:
        try:
            stage.cleanup()
        except OSError:
            # Cleanup must neither hide an existing error nor reverse the
            # reported outcome of an already committed workspace restoration.
            if completed:
                warnings.append(message(
                    'Migración completada; queda una copia temporal privada pendiente de limpieza: {path}',
                    en='Migration completed; a private temporary copy still needs cleanup: {path}',
                    path=stage.name))


def _save_backup(payload, source, target, location):
    base = _no_links(location).resolve()
    if any(base == root or root in base.parents for root in (source, target)):
        raise ValueError(message('El respaldo debe guardarse fuera de ambas instalaciones.',
            en='The backup must be stored outside both installations.'))
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(tempfile.mkdtemp(prefix='upgrade-', dir=base))
    path = directory / 'workspace.zip'
    _write_private(path, payload)
    if path.read_bytes() != payload:
        raise ValueError(message('No se pudo verificar la copia del respaldo.',
            en='The saved backup could not be verified.'))
    return path


@contextmanager
def _without_empty_marker(projects, warnings):
    marker = projects / '.gitkeep'
    existed = marker.exists()
    if existed:
        if marker.is_symlink() or not marker.is_file() or marker.stat().st_size:
            raise ValueError(message('El destino cambió; no se restaura.',
                en='The destination changed; restoration stopped.'))
        marker.unlink()
    completed = False
    try:
        yield
        completed = True
    finally:
        if existed and not marker.exists() and not (projects.parent / '.workspace-restore.json').exists():
            # Restore the harmless packaged placeholder on success and failure.
            # During interrupted activation, preserve the exact journal state:
            # creating a target here could obstruct workspace_backup's rollback.
            try:
                marker.parent.mkdir(parents=True, exist_ok=True)
                with marker.open('xb'):
                    pass
            except OSError:
                # The marker carries no workspace data. Preserve the original
                # restoration error, or report success with this minor warning.
                if completed:
                    warnings.append(message(
                        'Migración completada; no se pudo reponer el archivo vacío .gitkeep. Los proyectos están restaurados.',
                        en='Migration completed; the empty .gitkeep file could not be recreated. Projects are restored.'))


def upgrade(source, destination, *, backup_directory=None, lang='es', workspace=None):
    """Validate a private backup, then restore into empty selected data locations.

    A failed activation retains workspace_backup's journal/recovery contract.
    The saved ZIP survives failure; the original installation is never written.
    """
    with language_scope(lang):
        source, installation = _installation(source), _installation(destination)
        # CLI/launcher passes the selected external root explicitly. An ambient
        # environment must never redirect this low-level migration function.
        selection = select_workspace(installation, workspace, environ={})
        external = selection.external
        target = selection.root if external else installation
        if source == target or source in target.parents or target in source.parents:
            raise ValueError(message('Las instalaciones deben estar en carpetas separadas, sin solaparse.',
                en='Installations must be separate directories without overlap.'))
        _empty_destination(target, external)
        before = _inventory(source)
        base = Path(backup_directory) if backup_directory is not None else Path.home() / 'report-gen-backups'
        warnings = []
        with _private_stage(warnings) as private:
            snapshot = private / 'source'
            snapshot.mkdir()
            _copy_snapshot(source, snapshot, before)
            payload = backup.export_workspace(*_locations(snapshot))
            # A complete throwaway restoration exercises hashes, schemas, nested
            # archives, images and history before touching the destination.
            validation = backup.restore_workspace(payload, *_locations(private / 'validation'))
            if _inventory(source) != before:
                raise ValueError(message('El origen cambió. Cierra ambos editores y repite la migración.',
                    en='The source changed. Close both editors and repeat migration.'))
            _empty_destination(target, external)
            if external:
                base_resolved = _no_links(base).resolve()
                if base_resolved == installation or installation in base_resolved.parents:
                    raise ValueError(message('El respaldo debe guardarse fuera de la instalación.',
                                            en='The backup must be stored outside the installation.'))
            path = _save_backup(payload, source, target, base)
            try:
                if external:
                    select_workspace(installation, target, environ={}, create=True)
                with _without_empty_marker(_locations(target, external)[0], warnings):
                    result = backup.restore_workspace(payload, *_locations(target, external))
            except (OSError, ValueError) as exc:
                raise ValueError(message('No se completó la restauración. Conserva ambas instalaciones y el respaldo: {path}',
                    en='Restoration did not complete. Keep both installations and the backup: {path}', path=str(path))) from exc
            if any(result[key] != validation[key] for key in ('projects', 'findings', 'designs')):
                raise ValueError(message('La verificación final no coincide; conserva ambas instalaciones y el respaldo: {path}',
                    en='Final verification differs; keep both installations and the backup: {path}', path=str(path)))
            warnings[:0] = result.get('warnings', [])
            result['warnings'] = warnings
            result.update(backup=str(path), sha256=sha256(payload).hexdigest(), source_preserved=True)
        try:
            _write_private(path.with_name('result.json'),
                           (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode())
        except OSError:
            # A receipt is informational; it must not turn an already
            # committed restoration into a reported migration failure.
            result['warnings'].append(message(
                'Migración completada; no se pudo guardar result.json. Conserva el respaldo y su SHA-256 indicados.',
                en='Migration completed; result.json could not be saved. Keep the reported backup and SHA-256.'))
        return result


def main(argv=None):
    import argparse
    import sys
    lang = console_language(argv)
    def w(es, en, pt):
        return (es, en, pt)[language_index(lang)]
    parser = argparse.ArgumentParser(description=w('Migración local explícita con respaldo integral.', 'Explicit local migration with an integral backup.', 'Migração local explícita com backup integral.'))
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--workspace', help=w('Destino externo de datos', 'External destination for data', 'Destino externo dos dados'))
    parser.add_argument('--lang', type=language_argument, choices=['es', 'en', 'pt'], default='es')
    args = parser.parse_args(argv)
    try:
        result = upgrade(args.source, args.destination, lang=args.lang, workspace=args.workspace)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
