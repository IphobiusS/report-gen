"""Atomic writes and optimistic concurrency for the local editor."""
import hashlib
import os
from pathlib import Path
import tempfile


def revision(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_write(path, blob, backup=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        atomic_write(path.with_suffix(path.suffix + ".bak"), path.read_bytes())
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".write-", delete=False) as f:
            name = f.name
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
