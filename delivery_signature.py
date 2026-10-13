"""Optional local Ed25519 signatures for exact, externally trusted deliveries.

The detached JSON binds the entire ZIP and the exact manifest bytes. The ZIP is
never modified or extracted. No server endpoint accepts or stores private keys.
Cryptography is loaded only when an Ed25519 operation is explicitly requested.
"""
from languages import language_argument, language_index
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import argparse
import base64
import binascii
import json
import os
import re
import stat
import struct
import sys
import tempfile
import unicodedata
import zipfile
import zlib

from error_messages import current_language, language_scope, message as backend_message
from input_guard import load_json, MAX_DOCUMENT_BYTES

ROOT = Path(__file__).resolve().parent
# The existing project/backup archive budgets also apply to detached deliveries.
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 20_000
MAX_DIRECTORY_BYTES = 16 * 1024 * 1024
MAX_SIGNATURE_BYTES = 16 * 1024
MAX_KEY_BYTES = 16 * 1024
CHUNK = 64 * 1024
DOMAIN = b'report-gen-delivery-signature-v1\x00'
FORMAT = 'report-gen-delivery-signature'
HASH = re.compile(r'[a-f0-9]{64}\Z')
VERSION = re.compile(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\Z')
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
            *(f'LPT{i}' for i in range(1, 10))}


def _crypto():
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    except ImportError as exc:
        raise ValueError(backend_message('Instala report-gen[signing] para usar firmas Ed25519',
            en='Install report-gen[signing] to use Ed25519 signatures')) from exc
    return serialization, Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature, UnsupportedAlgorithm


def _path(value):
    path = Path(value).expanduser()
    if '..' in path.parts:
        raise ValueError(backend_message('La ruta de firma no permite ..', en='Signing paths must not contain ..'))
    path = path.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(backend_message('La ruta de firma no permite enlaces simbólicos',
            en='Signing paths must not contain symlinks'))
    return path


def _private_location(path):
    if path.is_relative_to(ROOT) or any((p / 'engagement.yaml').exists() for p in path.parents):
        raise ValueError(backend_message('Guarda la clave privada fuera de report-gen y de los proyectos',
            en='Keep the private key outside report-gen and report projects'))


@contextmanager
def _reader(value, maximum, private=False):
    path = _path(value)
    if private:
        _private_location(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or not 0 < details.st_size <= maximum:
            raise ValueError(backend_message('Archivo de firma vacío, no regular o demasiado grande',
                en='Signing input is empty, not a regular file or too large'))
        if private and (os.name != 'posix' or stat.S_IMODE(details.st_mode) != 0o600 or details.st_nlink != 1):
            raise ValueError(backend_message('La clave privada requiere permisos 0600 y un único enlace en POSIX',
                en='The private key requires mode 0600 and one link on POSIX'))
        with os.fdopen(descriptor, 'rb') as source:
            descriptor = None
            yield source
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read(value, maximum, private=False):
    with _reader(value, maximum, private) as source:
        blob = source.read(maximum + 1)
    if len(blob) > maximum:
        raise ValueError(backend_message('El archivo de firma supera su límite', en='Signing input exceeds its limit'))
    return blob


def _destination(value, inputs=(), private=False):
    path = _path(value)
    if private:
        _private_location(path)
    if path in {_path(item) for item in inputs} or path.exists() or not path.parent.is_dir():
        raise ValueError(backend_message('La salida de firma debe ser nueva y distinta de las entradas',
            en='Signing output must be new and different from all inputs'))
    return path


def _write_new(path, blob, mode):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), mode)
    try:
        if os.name == 'posix':
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'wb') as target:
            descriptor = None
            target.write(blob)
            target.flush()
            os.fsync(target.fileno())
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        path.unlink(missing_ok=True)
        raise


def generate_keypair(private_key, public_key):
    """Create two new local PEM files. Never overwrite or write into a report."""
    if os.name != 'posix':
        raise ValueError(backend_message('Genera y usa claves privadas en POSIX con permisos 0600',
            en='Generate and use private keys on POSIX with mode 0600'))
    private = _destination(private_key, private=True)
    public = _destination(public_key, inputs=(private,))
    serialization, Private, _, _, _ = _crypto()
    key = Private.generate()
    private_blob = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption())
    public_blob = key.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
    _write_new(private, private_blob, 0o600)
    try:
        _write_new(public, public_blob, 0o644)
    except BaseException:
        private.unlink(missing_ok=True)
        raise
    return {'private_key': str(private), 'public_key': str(public),
            'key_sha256': _fingerprint(key.public_key(), serialization)}


def _fingerprint(key, serialization):
    return sha256(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).hexdigest()


def _key(value, private=False):
    blob = _read(value, MAX_KEY_BYTES, private)
    # cryptography can parse the first PEM block and ignore trailing material.
    # Require one unambiguous external pin/key, retaining ordinary LF/CRLF PEM.
    label = b'PRIVATE KEY' if private else b'PUBLIC KEY'
    pattern = (b'-----BEGIN ' + label + rb'-----\r?\n(?:[A-Za-z0-9+/=]+\r?\n)+'
               + b'-----END ' + label + b'-----')
    if not re.fullmatch(pattern, blob.strip()):
        raise ValueError(backend_message('Se requiere una única clave PEM Ed25519 completa, sin contenido adicional',
            en='One complete Ed25519 PEM key without extra content is required'))
    serialization, Private, Public, _, Unsupported = _crypto()
    try:
        key = (serialization.load_pem_private_key(blob, password=None) if private
               else serialization.load_pem_public_key(blob))
        if not isinstance(key, Private if private else Public):
            raise ValueError
    except (ValueError, TypeError, Unsupported) as exc:
        raise ValueError(backend_message('Se requiere una clave PEM Ed25519 válida',
            en='A valid Ed25519 PEM key is required')) from exc
    return key, serialization, blob


def public_key_fingerprint(public_key):
    """Hash the raw Ed25519 public key read through the strict external pin path."""
    key, serialization, _ = _key(public_key)
    return {'algorithm': 'Ed25519', 'key_sha256': _fingerprint(key, serialization),
            'scope': 'raw_32_byte_public_key'}


def _safe_member(name):
    if (not isinstance(name, str) or not name or len(name.encode('utf-8')) > 1024
            or any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs', 'Zl', 'Zp'} for c in name)
            or re.search(r'[\\:*?"<>|]', name)):
        return False
    return all(part and part not in {'.', '..'} and not part.endswith((' ', '.'))
               and part.split('.')[0].upper() not in RESERVED for part in name.split('/'))


def _directory_preflight(source, size):
    # Bound central-directory parsing before ZipFile constructs any ZipInfo.
    source.seek(max(0, size - 65_557))
    tail = source.read(65_557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError(backend_message('ZIP de entrega inválido', en='Invalid delivery ZIP'))
    fields = struct.unpack('<4s4H2LH', tail[offset:offset + 22])
    _, disk, directory_disk, disk_count, count, directory_size, directory_offset, comment_size = fields
    eocd_offset = size - len(tail) + offset
    if (disk or directory_disk or disk_count != count or not 1 <= count <= MAX_FILES
            or directory_size > MAX_DIRECTORY_BYTES or directory_offset + directory_size != eocd_offset
            or len(tail) - offset != 22 + comment_size):
        raise ValueError(backend_message('ZIP de entrega dividido, ZIP64 o fuera de los límites de metadatos',
            en='Delivery ZIP is split, ZIP64 or exceeds metadata limits'))
    source.seek(0)
    if source.read(4) != b'PK\x03\x04':
        raise ValueError(backend_message('ZIP de entrega con prefijo no permitido',
            en='Delivery ZIP has an unsupported prefix'))
    return count, directory_offset


def _record(value, maximum):
    return (isinstance(value, dict) and set(value) == {'bytes', 'sha256'}
            and type(value.get('bytes')) is int and 0 <= value['bytes'] <= maximum
            and isinstance(value.get('sha256'), str) and bool(HASH.fullmatch(value['sha256'])))


def _manifest(blob, names):
    data = load_json(blob)
    required = {'format', 'version', 'tool_version', 'label', 'created', 'source_revision', 'warnings', 'files'}
    if (not isinstance(data, dict) or not required <= set(data) or set(data) - required - {'design_guidance', 'audience'}
            or data.get('format') != 'report-gen-delivery' or type(data.get('version')) is not int
            or data['version'] != 1 or not isinstance(data.get('tool_version'), str)
            or not VERSION.fullmatch(data['tool_version']) or not isinstance(data.get('files'), dict)
            or not data['files'] or len(data['files']) > MAX_FILES - 2
            or not isinstance(data.get('source_revision'), str) or not HASH.fullmatch(data['source_revision'])
            or not isinstance(data.get('label'), str) or not 1 <= len(data['label']) <= 120
            or not isinstance(data.get('created'), str) or not isinstance(data.get('warnings'), list)):
        raise ValueError(backend_message('Manifiesto de entrega v1 inválido o no soportado',
            en='Invalid or unsupported v1 delivery manifest'))
    if 'design_guidance' in data and not isinstance(data['design_guidance'], dict):
        raise ValueError(backend_message('Metadatos de orientación de entrega inválidos',
            en='Invalid delivery guidance metadata'))
    if 'audience' in data:
        metadata = data['audience']
        if (not isinstance(metadata, dict)
                or set(metadata) != {'profile', 'plan', 'public_permission_declared', 'provenance_label'}
                or metadata.get('profile') not in ('technical', 'executive', 'public')
                or type(metadata.get('public_permission_declared')) is not bool
                or not (metadata.get('provenance_label') is None or isinstance(metadata['provenance_label'], str))
                or not isinstance(metadata.get('plan'), dict)):
            raise ValueError(backend_message('Metadatos de destinatario de entrega inválidos',
                en='Invalid delivery audience metadata'))
        # These are signed documentary decisions, not proof of publication
        # permission. Signing does not grant or validate such permission.
        plan = metadata['plan']
        if (set(plan) != {'included', 'excluded', 'finding_count', 'section_count', 'originals', 'attachments'}
                or any(not isinstance(plan.get(k), list) or any(not isinstance(v, str) for v in plan[k])
                       for k in ('included', 'excluded'))
                or any(type(plan.get(k)) is not int or not 0 <= plan[k] <= MAX_FILES
                       for k in ('finding_count', 'section_count'))
                or any(type(plan.get(k)) is not bool for k in ('originals', 'attachments'))):
            raise ValueError(backend_message('Plan de destinatario de entrega inválido',
                en='Invalid delivery audience plan'))
    extras = names - set(data['files'])
    if (not set(data['files']) <= names
            or extras not in ({'verificacion.json', 'LEEME.txt'}, {'verificacion.json', 'README.txt'})):
        raise ValueError(backend_message('El ZIP no coincide con los archivos del manifiesto y su guía',
            en='ZIP members do not match the manifest files and its guide'))
    for name, record in data['files'].items():
        if (not _safe_member(name) or name in {'verificacion.json', 'LEEME.txt', 'README.txt'}
                or not isinstance(record, dict) or set(record) != {'bytes', 'sha256', 'checks'}
                or not isinstance(record.get('checks'), dict)
                or not _record({k: v for k, v in record.items() if k != 'checks'}, MAX_EXPANDED)):
            raise ValueError(backend_message('Registro de archivo inválido en el manifiesto',
                en='Invalid file record in the manifest'))
    return data


def _member_digest(package, entry, forbidden=()):
    size = 0
    digest = sha256()
    overlap = b''
    width = max((len(needle) for needle in forbidden), default=1) - 1
    with package.open(entry) as source:
        while chunk := source.read(CHUNK):
            size += len(chunk)
            if size > entry.file_size or size > MAX_EXPANDED:
                raise ValueError(backend_message('Entrada ZIP expandida fuera de límites',
                    en='Expanded ZIP member exceeds its limits'))
            if any(needle in overlap + chunk for needle in forbidden):
                raise ValueError(backend_message('La entrega contiene la clave privada de firma',
                    en='The delivery contains the signing private key'))
            overlap = (overlap + chunk)[-width:] if width else b''
            digest.update(chunk)
    if size != entry.file_size:
        raise ValueError(backend_message('Tamaño ZIP incoherente', en='Inconsistent ZIP member size'))
    return {'bytes': size, 'sha256': digest.hexdigest()}


def inspect_delivery(archive, *, forbidden=()):
    """Validate an immutable bounded snapshot without extracting any members."""
    digest = sha256()
    size = 0
    # Archive-only temporary copy, not extracted content. TemporaryFile is private
    # and deleted on close; parsing/hashing share one immutable captured stream.
    with _reader(archive, MAX_ARCHIVE) as original, tempfile.TemporaryFile() as snapshot:
        while chunk := original.read(CHUNK):
            size += len(chunk)
            if size > MAX_ARCHIVE:
                raise ValueError(backend_message('El ZIP excede 256 MiB', en='ZIP exceeds 256 MiB'))
            digest.update(chunk)
            snapshot.write(chunk)
        count, directory_offset = _directory_preflight(snapshot, size)
        snapshot.seek(0)
        try:
            with zipfile.ZipFile(snapshot) as package:
                entries = package.infolist()
                if len(entries) != count or package.start_dir != directory_offset:
                    raise ValueError(backend_message('Directorio ZIP incoherente', en='Inconsistent ZIP directory'))
                if sum(e.file_size for e in entries) > MAX_EXPANDED:
                    raise ValueError(backend_message('La entrega expandida excede 512 MiB',
                        en='Expanded delivery exceeds 512 MiB'))
                seen = set()
                for entry in entries:
                    name = entry.filename
                    mode = stat.S_IFMT(entry.external_attr >> 16)
                    canonical = unicodedata.normalize('NFC', name).casefold()
                    if (not _safe_member(name) or entry.orig_filename != name or canonical in seen
                            or entry.is_dir() or entry.flag_bits & 1 or mode not in (0, stat.S_IFREG)
                            or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                        raise ValueError(backend_message('Entrada ZIP de entrega no permitida',
                            en='Unsupported delivery ZIP member'))
                    seen.add(canonical)
                for name in seen:
                    if any('/'.join(name.split('/')[:i]) in seen for i in range(1, len(name.split('/')))):
                        raise ValueError(backend_message('Colisión entre archivo y directorio ZIP',
                            en='ZIP file/directory collision'))
                names = {e.filename for e in entries}
                if 'verificacion.json' not in names:
                    raise ValueError(backend_message('Falta verificacion.json en la entrega',
                        en='Delivery is missing verificacion.json'))
                entry = package.getinfo('verificacion.json')
                if entry.file_size > MAX_DOCUMENT_BYTES:
                    raise ValueError(backend_message('Manifiesto de entrega demasiado grande',
                        en='Delivery manifest is too large'))
                blob = package.read(entry)
                manifest = _manifest(blob, names)
                for entry in entries:
                    actual = _member_digest(package, entry, forbidden)
                    if entry.filename in manifest['files']:
                        expected = manifest['files'][entry.filename]
                        if actual != {k: expected[k] for k in ('bytes', 'sha256')}:
                            raise ValueError(backend_message('Archivo de entrega alterado respecto al manifiesto',
                                en='Delivery file differs from the manifest'))
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, zlib.error) as exc:
            raise ValueError(backend_message('ZIP de entrega dañado o no soportado',
                en='Delivery ZIP is damaged or unsupported')) from exc
    return {'archive': {'bytes': size, 'sha256': digest.hexdigest()},
            'manifest': {'name': 'verificacion.json', 'bytes': len(blob), 'sha256': sha256(blob).hexdigest()},
            'files_checked': len(manifest['files']), 'tool_version': manifest['tool_version']}


def _signed_bytes(payload):
    # This is a domain-separated application message signed with ordinary
    # Ed25519, not an implementation of Ed25519ctx or Ed25519ph.
    return DOMAIN + json.dumps(payload, ensure_ascii=True, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode('ascii')


def sign_delivery(archive, private_key, signature):
    if os.name != 'posix':
        raise ValueError(backend_message('Genera y usa claves privadas en POSIX con permisos 0600',
            en='Generate and use private keys on POSIX with mode 0600'))
    output = _destination(signature, inputs=(archive, private_key))
    key, serialization, private_blob = _key(private_key, private=True)
    secret = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                               serialization.NoEncryption())
    summary = inspect_delivery(archive, forbidden=(private_blob, secret))
    payload = {k: summary[k] for k in ('archive', 'manifest')}
    payload['key_sha256'] = _fingerprint(key.public_key(), serialization)
    envelope = {'format': FORMAT, 'version': 1, 'algorithm': 'Ed25519', 'payload': payload,
                'signature': base64.b64encode(key.sign(_signed_bytes(payload))).decode('ascii')}
    _write_new(output, (json.dumps(envelope, indent=2, ensure_ascii=True) + '\n').encode('ascii'), 0o644)
    return dict(summary, key_sha256=payload['key_sha256'], signature=str(output))


def verify_delivery(archive, signature, public_key):
    """Trust only the caller-selected external public key, never ZIP metadata."""
    paths = [_path(p) for p in (archive, signature, public_key)]
    if len(set(paths)) != 3 or any(os.path.samefile(paths[i], paths[j]) for i in range(3) for j in range(i)):
        raise ValueError(backend_message('ZIP, firma y clave pública deben ser archivos distintos',
            en='ZIP, signature and public key must be separate files'))
    envelope = load_json(_read(signature, MAX_SIGNATURE_BYTES))
    if (not isinstance(envelope, dict) or set(envelope) != {'format', 'version', 'algorithm', 'payload', 'signature'}
            or envelope.get('format') != FORMAT or type(envelope.get('version')) is not int
            or envelope['version'] != 1 or envelope.get('algorithm') != 'Ed25519'):
        raise ValueError(backend_message('Formato de firma separado inválido o no soportado',
            en='Invalid or unsupported detached signature format'))
    payload = envelope['payload']
    if (not isinstance(payload, dict) or set(payload) != {'archive', 'manifest', 'key_sha256'}
            or not _record(payload.get('archive'), MAX_ARCHIVE)
            or not isinstance(payload.get('manifest'), dict)
            or set(payload['manifest']) != {'name', 'bytes', 'sha256'}
            or payload['manifest']['name'] != 'verificacion.json'
            or not _record({k: v for k, v in payload['manifest'].items() if k != 'name'}, MAX_DOCUMENT_BYTES)
            or not isinstance(payload.get('key_sha256'), str) or not HASH.fullmatch(payload['key_sha256'])):
        raise ValueError(backend_message('Contenido de firma separado inválido', en='Invalid detached signature payload'))
    try:
        signature_blob = base64.b64decode(envelope['signature'], validate=True)
        if len(signature_blob) != 64 or base64.b64encode(signature_blob).decode('ascii') != envelope['signature']:
            raise ValueError
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValueError(backend_message('Firma Ed25519 inválida o truncada',
            en='Invalid or truncated Ed25519 signature')) from exc
    key, serialization, _ = _key(public_key)
    if _fingerprint(key, serialization) != payload['key_sha256']:
        raise ValueError(backend_message('La clave pública externa no corresponde a esta firma',
            en='The external public key does not match this signature'))
    _, _, _, InvalidSignature, _ = _crypto()
    try:
        key.verify(signature_blob, _signed_bytes(payload))
    except InvalidSignature as exc:
        raise ValueError(backend_message('La firma Ed25519 no es válida con la clave pública externa',
            en='Ed25519 signature is invalid for the external public key')) from exc
    summary = inspect_delivery(archive)
    if any(summary[k] != payload[k] for k in ('archive', 'manifest')):
        raise ValueError(backend_message('El ZIP o el manifiesto no coinciden con la firma',
            en='ZIP or manifest does not match the signature'))
    return dict(summary, verified=True, key_sha256=payload['key_sha256'],
                scope='exact_zip_and_manifest_bytes', trusted_key='caller_selected_external_public_key')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument('--lang', type=language_argument, choices=('es', 'en', 'pt'), default='es')
    selected, argv = selector.parse_known_args(argv)
    with language_scope(selected.lang):
        def prose(es, en, pt):
            # Console help/status prose is authored here, not user content.
            return (es, en, pt)[language_index(current_language())]
        parser = argparse.ArgumentParser(description=prose('Firma local opcional de entregas exactas',
            'Optional local signing of exact deliveries', 'Assinatura local opcional de entregas exatas'), parents=[selector])
        commands = parser.add_subparsers(dest='command', required=True)
        generate = commands.add_parser('keygen', help=prose('Genera claves Ed25519 nuevas', 'Generate new Ed25519 keys', 'Gera novas chaves Ed25519'))
        generate.add_argument('--private-key', required=True, help=prose('PEM fuera de app/proyectos, 0600',
                                                                       'PEM outside app/projects, mode 0600', 'PEM fora do aplicativo/projetos, modo 0600'))
        generate.add_argument('--public-key', required=True)
        sign = commands.add_parser('sign', help=prose('Firma un ZIP de entrega existente', 'Sign an existing delivery ZIP', 'Assina um ZIP de entrega existente'))
        sign.add_argument('archive')
        sign.add_argument('--private-key', required=True)
        sign.add_argument('--signature', required=True)
        verify = commands.add_parser('verify', help=prose('Verifica con una clave pública externa fijada',
                                                        'Verify with an externally pinned public key', 'Verifica com uma chave pública externa previamente fixada'))
        verify.add_argument('archive')
        verify.add_argument('--signature', required=True)
        verify.add_argument('--public-key', required=True)
        fingerprint = commands.add_parser('fingerprint', help=prose('Calcula la huella de una clave pública Ed25519',
            'Compute the fingerprint of an Ed25519 public key', 'Calcula a impressão digital de uma chave pública Ed25519'))
        fingerprint.add_argument('--public-key', required=True)
        args = parser.parse_args(argv)
        try:
            if args.command == 'keygen':
                result = generate_keypair(args.private_key, args.public_key)
                message = prose('Claves locales creadas; conserva la privada fuera de entregas y comparte la pública por un canal confiable',
                    'Local keys created; keep the private key outside deliveries and share the public key through a trusted channel', 'Chaves locais criadas; mantenha a chave privada fora das entregas e compartilhe a pública por um canal confiável')
            elif args.command == 'sign':
                result = sign_delivery(args.archive, args.private_key, args.signature)
                message = prose('Firma separada creada para los bytes exactos del ZIP y manifiesto',
                    'Detached signature created for the exact ZIP and manifest bytes', 'Assinatura separada criada para os bytes exatos do ZIP e do manifesto')
            elif args.command == 'fingerprint':
                result = public_key_fingerprint(args.public_key)
                message = prose('Huella SHA-256 de los 32 bytes públicos Ed25519; confirma su origen por un canal confiable',
                    'SHA-256 fingerprint of the 32 Ed25519 public bytes; confirm its origin through a trusted channel', 'Impressão digital SHA-256 dos 32 bytes públicos Ed25519; confirme a origem por um canal confiável')
            else:
                result = verify_delivery(args.archive, args.signature, args.public_key)
                message = prose('Firma verificada con la clave pública externa; no certifica identidad real, hallazgos ni cifrado',
                    'Signature verified with the external public key; it does not certify real identity, findings or encryption', 'Assinatura verificada com a chave pública externa; não certifica identidade real, achados nem criptografia')
            print(json.dumps(dict(result, message=message, language=current_language()), ensure_ascii=False))
            return 0
        except (ValueError, OSError) as exc:
            detail = str(exc) if isinstance(exc, ValueError) else prose('No se pudo acceder al archivo local de firma',
                                                                       'Unable to access the local signing file', 'Não foi possível acessar o arquivo local de assinatura')
            print(json.dumps({'error': detail, 'language': current_language()}, ensure_ascii=False), file=sys.stderr)
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
