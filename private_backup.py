"""Version-one confidential workspace envelope; never a client deliverable.

Fixed scrypt parameters cannot be increased by hostile input. AES-GCM authenticates
both the format header and archive before the existing atomic restorer sees it.
No password or decrypted archive is written by this module.
"""
import secrets

from error_messages import message as backend_message
import workspace_backup

MAGIC = b'RGWORKSPACE\x00\x01'
SALT_BYTES = 16
NONCE_BYTES = 12
HEADER_BYTES = len(MAGIC) + SALT_BYTES + NONCE_BYTES
MAX_ENCRYPTED = workspace_backup.MAX_ARCHIVE + HEADER_BYTES + 16


def _crypto():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        from cryptography.exceptions import InvalidTag
    except ImportError:
        raise ValueError(backend_message(
            'Instala la dependencia opcional report-gen[privacy] para usar respaldos cifrados. / Install optional report-gen[privacy] to use encrypted backups.')) from None
    return AESGCM, Scrypt, InvalidTag


def _password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError(backend_message('Contraseña: entre 12 y 256 caracteres. / Password: 12 to 256 characters.'))
    try:
        return password.encode('utf-8')
    except UnicodeError:
        raise ValueError(backend_message('Contraseña no válida. / Invalid password.')) from None


def _key(password, salt, scrypt):
    return scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(_password(password))


def encrypt(payload, password):
    if not isinstance(payload, bytes) or len(payload) > workspace_backup.MAX_ARCHIVE:
        raise ValueError(backend_message('Respaldo integral mayor que 256 MiB. / Workspace backup exceeds 256 MiB.'))
    _password(password)
    aes, scrypt, _ = _crypto()
    salt, nonce = secrets.token_bytes(SALT_BYTES), secrets.token_bytes(NONCE_BYTES)
    header = MAGIC + salt + nonce
    return header + aes(_key(password, salt, scrypt)).encrypt(nonce, payload, header)


def decrypt(blob, password):
    if (not isinstance(blob, bytes) or not HEADER_BYTES + 16 <= len(blob) <= MAX_ENCRYPTED
            or not blob.startswith(MAGIC)):
        raise ValueError(backend_message('Respaldo cifrado no válido o versión no compatible. / Invalid encrypted backup or unsupported version.'))
    aes, scrypt, invalid_tag = _crypto()
    salt = blob[len(MAGIC):len(MAGIC) + SALT_BYTES]
    nonce = blob[len(MAGIC) + SALT_BYTES:HEADER_BYTES]
    try:
        return aes(_key(password, salt, scrypt)).decrypt(nonce, blob[HEADER_BYTES:], blob[:HEADER_BYTES])
    except invalid_tag:
        raise ValueError(backend_message('No se pudo autenticar el respaldo: contraseña incorrecta o archivo alterado. / Backup authentication failed: incorrect password or modified file.')) from None


def export_encrypted(projects, findings, designs, password):
    # Fail before potentially expensive archive construction.
    _password(password)
    _crypto()
    return encrypt(workspace_backup.export_workspace(projects, findings, designs), password)


def restore_encrypted(blob, projects, findings, designs, password):
    return workspace_backup.restore_workspace(decrypt(blob, password), projects, findings, designs)
