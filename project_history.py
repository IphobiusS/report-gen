"""Content-addressed snapshots and bounded, verified, editable project archives."""
from error_messages import message as backend_message
from datetime import datetime, timezone
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import logging
import os
import shutil
import stat
import tempfile
import zipfile
import zlib
import yaml
from storage import atomic_write
from workflows import new_uid, safe_member, normalize
from input_guard import load_yaml, load_yaml_file, load_json
from resources import local_image, referenced_images, project_image_member

MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 20000
STAGES = {'draft', 'delivered', 'retest', 'auto'}
_STAGING = ContextVar('project_transaction_directories', default=())


def _journal_for(stage):
    return stage.with_name('.commit-' + stage.name.lstrip('.') + '.json')


def _recover_commit(journal):
    """Recover one interrupted rename, without guessing or overwriting a state.

    A present stage means activation has not completed. An absent stage and a
    present target mean the new state is installed. Cleanup is retryable.
    """
    if journal.is_symlink(): raise ValueError(backend_message('Registro de recuperación no permitido'))
    with journal.open('rb') as source:
        blob = source.read(4097)
    if len(blob) > 4096: raise ValueError(backend_message('Registro de recuperación demasiado grande'))
    record = load_json(blob)
    if (not isinstance(record, dict) or record.get('format') != 'report-gen-commit-1'
            or not isinstance(record.get('had_target'), bool)):
        raise ValueError(backend_message('Registro de recuperación inválido'))
    paths = []
    for key in ('target', 'previous', 'stage'):
        name = record.get(key)
        if not safe_member(name) or '/' in name:
            raise ValueError(backend_message('Ruta de recuperación inválida'))
        path = journal.parent / name
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError(backend_message('Directorio de recuperación inválido'))
        paths.append(path)
    target, previous, stage = paths
    if (len(set(paths)) != 3 or not previous.name.startswith('.previous-')
            or not stage.name.startswith(('.transaction-', '.restore-'))
            or _journal_for(stage) != journal):
        raise ValueError(backend_message('Identidad de recuperación inválida'))
    if target.exists() and previous.exists() and stage.exists():
        raise ValueError(backend_message('Recuperación ambigua; se conservan las tres copias'))
    if not target.exists() and previous.exists():
        previous.rename(target)
    if not target.exists() and record['had_target']:
        raise ValueError(backend_message('No se encuentra ninguna copia del proyecto; se conserva el registro'))
    # From here the old state is restored, the new state is installed, or an
    # uncommitted creation can be discarded. Never delete the active target.
    try:
        for path in (stage, previous):
            if path.exists(): shutil.rmtree(path)
        journal.unlink()
    except OSError:
        logging.getLogger(__name__).warning('Recuperación completada; queda una copia privada pendiente de limpieza: %s', journal)


def recover_transactions(parent):
    """Called under the editor lock before each request, also after restart."""
    for journal in sorted(Path(parent).glob('.commit-*.json')):
        _recover_commit(journal)


def _activate(stage, directory):
    previous = directory.with_name('.previous-' + new_uid())
    journal = _journal_for(stage)
    # The journal is fsynced by atomic_write before either directory moves.
    atomic_write(journal, dumps(dict(format='report-gen-commit-1',
                 target=directory.name, previous=previous.name, stage=stage.name,
                 had_target=directory.exists())))
    try:
        if directory.exists(): directory.rename(previous)
        stage.rename(directory)
    except Exception:
        _recover_commit(journal)
        raise
    _recover_commit(journal)


@contextmanager
def transaction(directory):
    """Stage a complete state, then activate it with rollback on rename failure.

    Unchanged files can be hard-linked because all writers replace files rather
    than modifying them in place. The editor's process lock serializes readers
    and writers. Cross-process editing remains unsupported.
    """
    directory = Path(directory)
    if directory.is_symlink(): raise ValueError(backend_message('El proyecto contiene enlaces simbólicos'))
    directory = directory.resolve()
    if directory in _STAGING.get():
        yield directory
        return
    directory.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.transaction-', dir=directory.parent))
    token = None
    try:
        if directory.exists():
            if any(path.is_symlink() for path in directory.rglob('*')):
                raise ValueError(backend_message('El proyecto contiene enlaces simbólicos'))
            def copy_file(source, target):
                try: return os.link(source, target)
                except OSError: return shutil.copy2(source, target)
            shutil.copytree(directory, stage, dirs_exist_ok=True, copy_function=copy_file)
        token = _STAGING.set((*_STAGING.get(), stage))
        yield stage
        # Commit has succeeded. A cleanup problem must not be reported as a
        # failed save after the new state has already become visible.
        _activate(stage, directory)
    finally:
        if token is not None: _STAGING.reset(token)
        if stage.exists() and not _journal_for(stage).exists(): shutil.rmtree(stage)


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def digest(blob): return sha256(blob).hexdigest()


def dumps(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')


def validate_image_blob(name, blob):
    from PIL import Image
    from resources import IMAGE_SUFFIXES
    suffix = Path(name).suffix.lower()
    if suffix not in IMAGE_SUFFIXES: raise ValueError(backend_message('Formato de imagen no permitido: {p0}', p0=name))
    try:
        with Image.open(BytesIO(blob)) as image:
            if image.width * image.height > 25_000_000: raise ValueError(backend_message('Imagen mayor que 25 megapíxeles'))
            allowed = {'PNG': {'.png'}, 'JPEG': {'.jpg', '.jpeg'}, 'GIF': {'.gif'}, 'WEBP': {'.webp'}}
            if suffix not in allowed.get(image.format, set()): raise ValueError(backend_message('El tipo real de la imagen no coincide: {p0}', p0=name))
            image.verify()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError(backend_message('Imagen inválida: {p0}', p0=name)) from exc


def project_files(directory, document='engagement.yaml', *, data=None):
    directory = Path(directory)
    seen = set()
    for name in ('engagement.yaml', 'img', 'originals', 'attachments'):
        root = directory / (document if name == 'engagement.yaml' else name)
        if root.is_symlink(): raise ValueError(backend_message('El proyecto contiene enlaces simbólicos'))
        if root.is_file():
            seen.add(name)
            yield name, root.read_bytes()
        elif root.is_dir():
            for path in sorted(root.rglob('*')):
                if path.is_symlink(): raise ValueError(backend_message('El proyecto contiene enlaces simbólicos'))
                if path.is_file():
                    name = path.relative_to(directory).as_posix()
                    seen.add(name)
                    yield name, path.read_bytes()
    # Legacy CLI projects may keep logos or diagrams outside img/. Preserve
    # every existing referenced resource in versions and portable backups.
    for source in sorted(referenced_images(load_yaml_file(directory / document) if data is None else data)):
        try:
            path = local_image(source, directory)
        except ValueError:
            continue  # A draft may intentionally have a missing/invalid reference.
        name = path.relative_to(directory.resolve()).as_posix()
        if name not in seen:
            seen.add(name)
            yield name, path.read_bytes()


def history(directory):
    from workflows import UID
    root = Path(directory) / 'history' / 'snapshots'
    from incremental_save import require_unlinked
    require_unlinked(root)
    records = []
    for path in root.glob('*.json'):
        if path.is_symlink(): raise ValueError(backend_message('Enlace simbólico en el historial'))
        try: record = load_json(path.read_bytes())
        except (ValueError, UnicodeDecodeError) as exc: raise ValueError(backend_message('Historial inválido')) from exc
        if (not isinstance(record, dict) or not isinstance(record.get('id'), str) or not UID.fullmatch(record['id'])
                or path.stem != record['id'] or not isinstance(record.get('label'), str) or len(record['label']) > 200
                or not isinstance(record.get('stage'), str) or record['stage'] not in STAGES
                or not isinstance(record.get('created'), str) or not isinstance(record.get('files'), dict)):
            raise ValueError(backend_message('Registro de historial inválido'))
        try: datetime.fromisoformat(record['created'])
        except ValueError as exc: raise ValueError(backend_message('Fecha de versión inválida')) from exc
        records.append(record)
    return sorted(records, key=lambda x: x['created'], reverse=True)


def checkpoint(directory, label='Autoguardado', stage='auto', force=False, *, yaml_parts=None, metrics=None, yaml_data=None):
    if stage not in STAGES or not isinstance(label, str) or len(label) > 200: raise ValueError(backend_message('Nombre o etapa de versión inválidos'))
    directory = Path(directory)
    files = {}
    for name, blob in project_files(directory, data=yaml_data):
        key = digest(blob); files[name] = key
        path = directory / 'history' / 'objects' / key
        if name == 'engagement.yaml':
            from incremental_save import store_object
            result = store_object(directory, blob, yaml_parts)
            if metrics is not None:
                for field, value in result.items(): metrics[field] = metrics.get(field, 0) + value
        elif not path.exists(): atomic_write(path, blob)
    previous = history(directory)
    if previous and previous[0]['files'] == files and not force: return previous[0]
    entry = dict(id=new_uid(), created=now(), label=label, stage=stage, files=files)
    atomic_write(directory / 'history' / 'snapshots' / (entry['id'] + '.json'), dumps(entry))
    return entry


def save(directory, data, *, checkpoint_current=True):
    from wizard import dump_yaml
    from validate import require_valid
    require_valid(data)
    normalize(data)
    require_valid(data)
    import incremental_save as incremental
    directory = Path(directory)
    plan = incremental.prepare(directory, data)
    metrics = dict(plan.stats, unchanged=plan.unchanged, transaction=False,
                   object_bytes_written=0, objects_written=0, fragment_bytes_written=0, fragments_written=0)
    # A complete no-op must also preserve the checkpointed resource set. An
    # independently modified image still needs its own recoverable revision.
    if plan.unchanged and directory.resolve() not in _STAGING.get():
        records = history(directory)
        files = {name: digest(blob) for name, blob in project_files(directory, data=plan.existing_data)}
        if records and records[0]['files'] == files:
            # Verify immutable objects before treating an unchanged snapshot as
            # safely recoverable. A cache cannot conceal damaged disk history.
            for name, blob in snapshot_blobs(directory, records[0]):
                pass
            incremental.remember(directory, plan)
            return metrics
    with transaction(directory) as staged:
        metrics['transaction'] = True
        if checkpoint_current and (staged / 'engagement.yaml').exists():
            checkpoint(staged, metrics=metrics, yaml_data=plan.existing_data)
        # Existing private import/restore preparations retain their writer call
        # and failure/rollback contract, including legacy writer instrumentation.
        if not plan.unchanged or directory.resolve() in _STAGING.get():
            with incremental.prepared(data, plan):
                dump_yaml(data, staged / 'engagement.yaml')
        checkpoint(staged, yaml_parts=plan.state.parts if plan.state else None, metrics=metrics,
                   yaml_data=plan.state.data if plan.state else plan.existing_data)
    incremental.remember(directory, plan)
    return metrics


def get_snapshot(directory, sid):
    from workflows import UID
    if not isinstance(sid, str) or not UID.fullmatch(sid): raise ValueError(backend_message('Versión inválida'))
    path = Path(directory) / 'history' / 'snapshots' / (sid + '.json')
    from incremental_save import require_unlinked
    require_unlinked(path)
    if not path.is_file(): raise ValueError(backend_message('Versión inexistente'))
    return load_json(path.read_bytes())


def snapshot_blobs(directory, record):
    files = record.get('files')
    if not isinstance(files, dict) or 'engagement.yaml' not in files: raise ValueError(backend_message('Versión incompleta'))
    for name, key in files.items():
        if not (name == 'engagement.yaml' or project_image_member(name) or safe_member(name, 'originals/') or __import__('attachments').MEMBER.fullmatch(name)):
            raise ValueError(backend_message('Ruta no permitida en la versión'))
        if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key): raise ValueError(backend_message('Hash inválido'))
        path = Path(directory) / 'history' / 'objects' / key
        if not path.is_file() or path.is_symlink(): raise ValueError(backend_message('Falta un archivo de la versión'))
        from incremental_save import read_object
        blob = read_object(directory, key, document=name == 'engagement.yaml')
        if name.startswith('attachments/'):
            __import__('attachments').validate_blob(name,blob)
        elif name != 'engagement.yaml': validate_image_blob(name, blob)
        yield name, blob


def snapshot_data(directory, sid):
    blobs = dict(snapshot_blobs(directory, get_snapshot(directory, sid)))
    return load_yaml(blobs['engagement.yaml'])


def restore(directory, sid):
    """Validate everything first, then swap the complete directory with rollback."""
    directory = Path(directory)
    record = get_snapshot(directory, sid)
    blobs = dict(snapshot_blobs(directory, record))
    from validate import require_valid
    require_valid(load_yaml(blobs['engagement.yaml']))
    checkpoint(directory, 'Antes de restaurar', 'draft')
    staging = Path(tempfile.mkdtemp(prefix='.restore-', dir=directory.parent))
    try:
        shutil.copytree(directory / 'history', staging / 'history')
        for name, blob in blobs.items(): atomic_write(staging / name, blob)
        atomic_write(staging / 'engagement.yaml.bak', (directory / 'engagement.yaml').read_bytes())
        # Old snapshots without permanent identities migrate as a new state.
        data = load_yaml_file(staging / 'engagement.yaml')
        # The outer activation owns recovery of the public project. Its private
        # preparation must not retain a journal addressed to a temporary name.
        token = _STAGING.set((*_STAGING.get(), staging.resolve()))
        try:
            save(staging, data)
        finally:
            _STAGING.reset(token)
        checkpoint(staging, 'Restaurada: ' + record['label'][:160], 'draft', force=True)
        _activate(staging, directory)
    finally:
        if staging.exists() and not _journal_for(staging).exists(): shutil.rmtree(staging)


def export_bundle(directory):
    directory = Path(directory)
    files = dict(project_files(directory))
    records = history(directory)
    object_names = {key: name for record in records for name, key in record['files'].items()}
    for path in (directory / 'history').rglob('*'):
        if path.is_symlink(): raise ValueError(backend_message('Enlace simbólico no permitido'))
        if path.is_file():
            name = path.relative_to(directory).as_posix()
            # Version-1 portable backups carry materialized legacy objects;
            # implementation fragments are local storage, not extra inputs.
            if name.startswith('history/fragments/'): continue
            if name.startswith('history/objects/'):
                from incremental_save import read_object
                kind = object_names.get(path.name)
                document = None if kind is None else kind == 'engagement.yaml'
                files[name] = read_object(directory, path.name, document=document)
            else: files[name] = path.read_bytes()
    # A pre-history installation can have its only preceding state in .bak.
    # Turn that recovery copy into an ordinary portable snapshot in memory;
    # exporting must neither migrate nor checkpoint the source installation.
    backup = directory / 'engagement.yaml.bak'
    if backup.is_symlink(): raise ValueError(backend_message('Enlace simbólico no permitido'))
    if backup.is_file():
        from validate import require_valid
        backup_data = None
        from input_guard import MAX_DOCUMENT_BYTES
        with backup.open('rb') as source: backup_blob = source.read(MAX_DOCUMENT_BYTES + 1)
        backup_key = digest(backup_blob)
        current_key = digest(files['engagement.yaml'])
        if backup_key != current_key and not any(r['files'].get('engagement.yaml') == backup_key for r in records):
            try:
                backup_data = load_yaml(backup_blob)
                require_valid(backup_data)
            except ValueError:
                # Modern installations may retain an obsolete, unreadable .bak
                # even though their preceding revisions are already snapshots.
                if not any(r['files'].get('engagement.yaml') != current_key for r in records): raise
            if backup_data is not None:
                previous = dict(project_files(directory, 'engagement.yaml.bak'))
                keys = {name: digest(blob) for name, blob in previous.items()}
                for name, blob in previous.items():
                    if name != 'engagement.yaml': files[name] = blob
                    files['history/objects/' + keys[name]] = blob
                record = dict(id=new_uid(), created=now(), label='Copia de recuperación heredada',
                              stage='draft', files=keys)
                files['history/snapshots/' + record['id'] + '.json'] = dumps(record)
    if sum(map(len, files.values())) > MAX_EXPANDED or len(files) > MAX_FILES: raise ValueError(backend_message('El proyecto excede el límite del respaldo portable (512 MiB / 20000 archivos)'))
    manifest = dict(format='report-gen-project', version=1, created=now(), files={k: digest(v) for k, v in files.items()})
    manifest_blob = dumps(manifest)
    if sum(map(len, files.values())) + len(manifest_blob) > MAX_EXPANDED:
        raise ValueError(backend_message('El respaldo con su manifiesto supera el límite de importación'))
    # Do not issue a successful backup that the importer will reject.
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError(backend_message('El proyecto tiene nombres que solo difieren en mayúsculas'))
    for name, blob in files.items():
        if not safe_member(name): raise ValueError(backend_message('Ruta no portable en el respaldo: {p0}', p0=name))
        if name == 'engagement.yaml':
            from validate import require_valid
            require_valid(load_yaml(blob))
        elif name.startswith(('history/objects/', 'history/snapshots/')): continue
        elif name.startswith('attachments/'): __import__('attachments').validate_blob(name,blob)
        elif project_image_member(name) or name.startswith(('img/', 'originals/')): validate_image_blob(name, blob)
        else: raise ValueError(backend_message('Archivo no permitido en el respaldo: {p0}', p0=name))
    for record in records:
        for name, blob in snapshot_blobs(directory, record):
            if name == 'engagement.yaml':
                from validate import require_valid
                require_valid(load_yaml(blob))
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', manifest_blob)
        for name, blob in files.items(): archive.writestr(name, blob)
    if output.tell() > MAX_ARCHIVE: raise ValueError(backend_message('El ZIP excede 256 MiB'))
    return output.getvalue()


def import_bundle(blob, target):
    """No extractall: allowlisted entries, hashes, total size, duplicates and links."""
    target = Path(target)
    if target.exists(): raise ValueError(backend_message('El destino ya existe'))
    if len(blob) > MAX_ARCHIVE: raise ValueError(backend_message('Respaldo mayor que 256 MiB'))
    staging = Path(tempfile.mkdtemp(prefix='.import-', dir=target.parent))
    try:
        with zipfile.ZipFile(BytesIO(blob)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES + 1 or sum(x.file_size for x in entries) > MAX_EXPANDED: raise ValueError(backend_message('Respaldo demasiado grande'))
            names = set()
            for entry in entries:
                name = entry.filename
                if (not safe_member(name) or name.casefold() in names or entry.flag_bits & 1
                        or stat.S_ISLNK(entry.external_attr >> 16) or entry.is_dir()): raise ValueError(backend_message('Entrada ZIP no permitida'))
                if (name not in ('manifest.json', 'engagement.yaml') and not project_image_member(name)
                        and not name.startswith(('img/', 'originals/', 'attachments/', 'history/objects/', 'history/snapshots/'))):
                    raise ValueError(backend_message('Archivo no permitido en el respaldo'))
                names.add(name.casefold())
            # A ZIP may contain both a file and a descendant of that file.
            # Refuse the ambiguous tree before writing any staging resource,
            # rather than reporting an ordinary invalid upload as a disk error.
            ordered = sorted(names, key=lambda name: name.split('/'))
            if any(child.startswith(parent + '/') for parent, child in zip(ordered, ordered[1:])):
                raise ValueError(backend_message('El respaldo contiene rutas de archivo y directorio incompatibles'))
            if 'manifest.json' not in names: raise ValueError(backend_message('No es un respaldo editable de report-gen'))
            manifest = load_json(archive.read('manifest.json'))
            if (not isinstance(manifest, dict) or manifest.get('format') != 'report-gen-project'
                    or type(manifest.get('version')) is not int or manifest['version'] != 1):
                raise ValueError(backend_message('Formato de respaldo desconocido'))
            hashes = manifest.get('files')
            if not isinstance(hashes, dict) or set(hashes) != {e.filename for e in entries} - {'manifest.json'} or 'engagement.yaml' not in hashes:
                raise ValueError(backend_message('Manifiesto incompleto'))
            for name, expected in hashes.items():
                value = archive.read(name)
                if digest(value) != expected: raise ValueError(backend_message('Integridad del respaldo inválida: {p0}', p0=name))
                if name.startswith('attachments/'):
                    __import__('attachments').validate_blob(name,value)
                elif project_image_member(name) or name.startswith(('img/', 'originals/')):
                    validate_image_blob(name, value)
                atomic_write(staging / name, value)
        from validate import require_valid
        data = load_yaml_file(staging / 'engagement.yaml')
        require_valid(data)
        # Verify every historical object before making the imported project visible.
        for record in history(staging):
            for name, value in snapshot_blobs(staging, record):
                if name == 'engagement.yaml':
                    historical = load_yaml(value)
                    require_valid(historical)
        # The archive already carries its historical states. Normalizing its
        # active YAML is migration, not an additional preceding user revision.
        # This directory is already private. An inner activation could retain
        # a cleanup journal addressed to its temporary name, then recreate that
        # name after publication. Write here and publish the complete state once.
        token = _STAGING.set((*_STAGING.get(), staging.resolve()))
        try:
            save(staging, data, checkpoint_current=False)
        finally:
            _STAGING.reset(token)
        staging.rename(target)
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError, yaml.YAMLError,
            RuntimeError, EOFError, zlib.error) as exc:
        raise ValueError(backend_message('Respaldo inválido')) from exc
    finally:
        if staging.exists(): shutil.rmtree(staging)
