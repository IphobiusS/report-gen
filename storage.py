"""Atomic writes and optimistic concurrency for the local editor."""
from error_messages import message as backend_message
import hashlib
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager


def require_export_destination(source, output, data):
    """Refuse to replace an input, including filesystem aliases of that input."""
    from resources import referenced_images, relative_image
    source = Path(source).resolve()
    output = Path(output).resolve()
    inputs = {source}
    inputs.update((source.parent / relative_image(src)).resolve()
                  for src in referenced_images(data))
    # Originals and annexes remain project inputs even when they are excluded
    # from this public export. Checking paths does not read or publish them.
    for group in ('evidence', 'capture_inbox'):
        inputs.update((source.parent / row['original']).resolve()
                      for row in data.get(group, [])
                      if isinstance(row.get('original'), str) and row['original'])
    inputs.update((source.parent / row['member']).resolve()
                  for row in data.get('attachments', []) if row.get('member'))
    for entry in inputs:
        if output == entry or (output.exists() and entry.exists() and output.samefile(entry)):
            raise ValueError(backend_message('La salida coincide con una entrada del proyecto; elige otro destino. / Output destination matches a project input; choose another path.'))
    return output


@contextmanager
def atomic_output(path):
    """Keep the previous deliverable intact until a complete export succeeds."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.export-', suffix=path.suffix, delete=False) as f:
        temporary = Path(f.name)
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
