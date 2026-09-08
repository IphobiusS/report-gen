"""Content-addressed snapshots and bounded, verified, editable project archives."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import shutil
import stat
import tempfile
import zipfile
import yaml
from storage import atomic_write
from workflows import new_uid, safe_member, normalize

MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 20000
STAGES = {'draft', 'delivered', 'retest', 'auto'}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def digest(blob): return sha256(blob).hexdigest()


def dumps(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')


def validate_image_blob(name, blob):
    from PIL import Image
    from resources import IMAGE_SUFFIXES
    suffix = Path(name).suffix.lower()
    if suffix not in IMAGE_SUFFIXES: raise ValueError('Formato de imagen no permitido: ' + name)
    try:
        with Image.open(BytesIO(blob)) as image:
            if image.width * image.height > 25_000_000: raise ValueError('Imagen mayor que 25 megapíxeles')
            allowed = {'PNG': {'.png'}, 'JPEG': {'.jpg', '.jpeg'}, 'GIF': {'.gif'}, 'WEBP': {'.webp'}}
            if suffix not in allowed.get(image.format, set()): raise ValueError('El tipo real de la imagen no coincide: ' + name)
            image.verify()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError('Imagen inválida: ' + name) from exc


def project_files(directory):
    directory = Path(directory)
    for name in ('engagement.yaml', 'img', 'originals'):
        root = directory / name
        if root.is_symlink(): raise ValueError('El proyecto contiene enlaces simbólicos')
        if root.is_file(): yield name, root.read_bytes()
        elif root.is_dir():
            for path in sorted(root.rglob('*')):
                if path.is_symlink(): raise ValueError('El proyecto contiene enlaces simbólicos')
                if path.is_file(): yield path.relative_to(directory).as_posix(), path.read_bytes()


def history(directory):
    from workflows import UID
    root = Path(directory) / 'history' / 'snapshots'
    records = []
    for path in root.glob('*.json'):
        if path.is_symlink(): raise ValueError('Enlace simbólico en el historial')
        try: record = json.loads(path.read_bytes())
        except (ValueError, UnicodeDecodeError) as exc: raise ValueError('Historial inválido') from exc
        if (not isinstance(record, dict) or not isinstance(record.get('id'), str) or not UID.fullmatch(record['id'])
                or path.stem != record['id'] or not isinstance(record.get('label'), str) or len(record['label']) > 200
                or not isinstance(record.get('stage'), str) or record['stage'] not in STAGES
                or not isinstance(record.get('created'), str) or not isinstance(record.get('files'), dict)):
            raise ValueError('Registro de historial inválido')
        try: datetime.fromisoformat(record['created'])
        except ValueError as exc: raise ValueError('Fecha de versión inválida') from exc
        records.append(record)
    return sorted(records, key=lambda x: x['created'], reverse=True)


def checkpoint(directory, label='Autoguardado', stage='auto', force=False):
    if stage not in STAGES or not isinstance(label, str) or len(label) > 200: raise ValueError('Nombre o etapa de versión inválidos')
    directory = Path(directory)
    files = {}
    for name, blob in project_files(directory):
        key = digest(blob); files[name] = key
        path = directory / 'history' / 'objects' / key
        if not path.exists(): atomic_write(path, blob)
    previous = history(directory)
    if previous and previous[0]['files'] == files and not force: return previous[0]
    entry = dict(id=new_uid(), created=now(), label=label, stage=stage, files=files)
    atomic_write(directory / 'history' / 'snapshots' / (entry['id'] + '.json'), dumps(entry))
    return entry


def save(directory, data):
    from wizard import dump_yaml
    directory = Path(directory)
    if (directory / 'engagement.yaml').exists(): checkpoint(directory)
    normalize(data)
    dump_yaml(data, directory / 'engagement.yaml')
    checkpoint(directory)


def get_snapshot(directory, sid):
    from workflows import UID
    if not isinstance(sid, str) or not UID.fullmatch(sid): raise ValueError('Versión inválida')
    path = Path(directory) / 'history' / 'snapshots' / (sid + '.json')
    if not path.is_file(): raise ValueError('Versión inexistente')
    return json.loads(path.read_bytes())


def snapshot_blobs(directory, record):
    files = record.get('files')
    if not isinstance(files, dict) or 'engagement.yaml' not in files: raise ValueError('Versión incompleta')
    for name, key in files.items():
        if not (name == 'engagement.yaml' or safe_member(name, 'img/') or safe_member(name, 'originals/')):
            raise ValueError('Ruta no permitida en la versión')
        if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key): raise ValueError('Hash inválido')
        path = Path(directory) / 'history' / 'objects' / key
        if not path.is_file() or path.is_symlink(): raise ValueError('Falta un archivo de la versión')
        blob = path.read_bytes()
        if digest(blob) != key: raise ValueError('Archivo de versión alterado')
        if name != 'engagement.yaml': validate_image_blob(name, blob)
        yield name, blob


def snapshot_data(directory, sid):
    blobs = dict(snapshot_blobs(directory, get_snapshot(directory, sid)))
    return yaml.safe_load(blobs['engagement.yaml'])


def restore(directory, sid):
    """Validate everything first, then swap the complete directory with rollback."""
    directory = Path(directory)
    record = get_snapshot(directory, sid)
    blobs = dict(snapshot_blobs(directory, record))
    from validate import require_valid
    require_valid(yaml.safe_load(blobs['engagement.yaml']))
    checkpoint(directory, 'Antes de restaurar', 'draft')
    staging = Path(tempfile.mkdtemp(prefix='.restore-', dir=directory.parent))
    backup = directory.with_name('.previous-' + new_uid())
    try:
        shutil.copytree(directory / 'history', staging / 'history')
        for name, blob in blobs.items(): atomic_write(staging / name, blob)
        atomic_write(staging / 'engagement.yaml.bak', (directory / 'engagement.yaml').read_bytes())
        # Old snapshots without permanent identities migrate as a new state.
        data = yaml.safe_load((staging / 'engagement.yaml').read_bytes())
        save(staging, data)
        checkpoint(staging, 'Restaurada: ' + record['label'][:160], 'draft', force=True)
        directory.rename(backup)
        try: staging.rename(directory)
        except Exception:
            backup.rename(directory); raise
        shutil.rmtree(backup)
    finally:
        if staging.exists(): shutil.rmtree(staging)


def export_bundle(directory):
    directory = Path(directory)
    checkpoint(directory)
    files = dict(project_files(directory))
    for path in (directory / 'history').rglob('*'):
        if path.is_symlink(): raise ValueError('Enlace simbólico no permitido')
        if path.is_file(): files[path.relative_to(directory).as_posix()] = path.read_bytes()
    if sum(map(len, files.values())) > MAX_EXPANDED or len(files) > MAX_FILES: raise ValueError('El proyecto excede el límite del respaldo portable (512 MiB / 20000 archivos)')
    manifest = dict(format='report-gen-project', version=1, created=now(), files={k: digest(v) for k, v in files.items()})
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', dumps(manifest))
        for name, blob in files.items(): archive.writestr(name, blob)
    if output.tell() > MAX_ARCHIVE: raise ValueError('El ZIP excede 256 MiB')
    return output.getvalue()


def import_bundle(blob, target):
    """No extractall: allowlisted entries, hashes, total size, duplicates and links."""
    target = Path(target)
    if target.exists(): raise ValueError('El destino ya existe')
    if len(blob) > MAX_ARCHIVE: raise ValueError('Respaldo mayor que 256 MiB')
    staging = Path(tempfile.mkdtemp(prefix='.import-', dir=target.parent))
    try:
        with zipfile.ZipFile(BytesIO(blob)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES + 1 or sum(x.file_size for x in entries) > MAX_EXPANDED: raise ValueError('Respaldo demasiado grande')
            names = set()
            for entry in entries:
                name = entry.filename
                if (not safe_member(name) or name.casefold() in names or entry.flag_bits & 1
                        or stat.S_ISLNK(entry.external_attr >> 16) or entry.is_dir()): raise ValueError('Entrada ZIP no permitida')
                if name not in ('manifest.json', 'engagement.yaml') and not name.startswith(('img/', 'originals/', 'history/objects/', 'history/snapshots/')):
                    raise ValueError('Archivo no permitido en el respaldo')
                names.add(name.casefold())
            if 'manifest.json' not in names: raise ValueError('No es un respaldo editable de report-gen')
            manifest = json.loads(archive.read('manifest.json'))
            if not isinstance(manifest, dict) or manifest.get('format') != 'report-gen-project' or manifest.get('version') != 1:
                raise ValueError('Formato de respaldo desconocido')
            hashes = manifest.get('files')
            if not isinstance(hashes, dict) or set(hashes) != {e.filename for e in entries} - {'manifest.json'} or 'engagement.yaml' not in hashes:
                raise ValueError('Manifiesto incompleto')
            for name, expected in hashes.items():
                value = archive.read(name)
                if digest(value) != expected: raise ValueError('Integridad del respaldo inválida: ' + name)
                if name.startswith(('img/', 'originals/')): validate_image_blob(name, value)
                atomic_write(staging / name, value)
        from validate import require_valid
        data = yaml.safe_load((staging / 'engagement.yaml').read_bytes())
        try: json.dumps(data, default=str, allow_nan=False)
        except (ValueError, RecursionError) as exc: raise ValueError('YAML recursivo o no finito') from exc
        require_valid(data)
        # Verify every historical object before making the imported project visible.
        for record in history(staging):
            for name, value in snapshot_blobs(staging, record):
                if name == 'engagement.yaml':
                    historical = yaml.safe_load(value)
                    try: json.dumps(historical, default=str, allow_nan=False)
                    except (ValueError, RecursionError) as exc: raise ValueError('YAML histórico recursivo o no finito') from exc
                    require_valid(historical)
        save(staging, data)
        staging.rename(target)
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError('Respaldo inválido') from exc
    finally:
        if staging.exists(): shutil.rmtree(staging)
