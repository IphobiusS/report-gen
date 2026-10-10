"""Read-only project summaries and portable, non-destructive archive metadata."""
from datetime import date, datetime, timezone

from error_messages import message
from input_guard import load_yaml_file
from storage import revision


def validate_metadata(value):
    if not isinstance(value, dict) or set(value) - {'archived', 'delivery_date'}:
        raise ValueError(message('Gestión del proyecto inválida', en='Invalid project management metadata'))
    if 'archived' in value and type(value['archived']) is not bool:
        raise ValueError(message('El estado de archivo debe ser booleano', en='Archive state must be boolean'))
    if 'delivery_date' in value:
        raw = value['delivery_date']
        try:
            if not isinstance(raw, str) or (raw and date.fromisoformat(raw).isoformat() != raw):
                raise ValueError
        except ValueError:
            raise ValueError(message('Fecha de entrega inválida: usa AAAA-MM-DD', en='Invalid delivery date: use YYYY-MM-DD')) from None
    return value


def list_projects(root):
    rows = []
    for directory in sorted(root.iterdir()):
        path = directory / 'engagement.yaml'
        if directory.name.startswith('.') or directory.is_symlink() or not directory.is_dir() or path.is_symlink() or not path.is_file():
            continue
        row = dict(slug=directory.name, title=directory.name, client='', theme='', lang='',
                   available=False, archived=False, delivery_date='', next_due_date='',
                   pending_retests=0, finding_count=0, modified_at='', revision='')
        try:
            document = load_yaml_file(path)
            if not isinstance(document, dict):
                raise ValueError
            meta = document.get('meta') or {}
            if not isinstance(meta, dict):
                raise ValueError
            management = validate_metadata(document.get('project_management', {}))
            findings = document.get('findings', [])
            if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
                raise ValueError
            for key, source in (('title', 'report_title'), ('client', 'client'), ('theme', 'theme'), ('lang', 'lang')):
                if isinstance(meta.get(source), str):
                    row[key] = meta[source]
            deadlines = []
            for finding in findings:
                if finding.get('status') in ('verified_fixed', 'accepted'):
                    continue
                value = finding.get('due_date')
                try:
                    if isinstance(value, str) and value and date.fromisoformat(value).isoformat() == value:
                        deadlines.append(value)
                except ValueError:
                    pass
            delivery = management.get('delivery_date', '')
            row.update(available=True, archived=management.get('archived', False), delivery_date=delivery,
                       next_due_date=min(deadlines + ([delivery] if delivery else []), default=''),
                       pending_retests=sum(item.get('status') == 'reported_fixed' for item in findings),
                       finding_count=len(findings), revision=revision(path),
                       modified_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec='seconds'))
        except (ValueError, OSError, TypeError):
            # Keep the entry recoverable; never leak parser output or silently delete it.
            pass
        rows.append(row)
    return rows
