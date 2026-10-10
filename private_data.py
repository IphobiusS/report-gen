"""Local retention inventory and explicit, transactional cleanup of private copies."""
from error_messages import message as backend_message
from hashlib import sha256
from pathlib import Path
import json
import shutil
import engine
import project_history
from storage import revision

CATEGORIES=('document','images','originals','annexes','unused_annexes','history','legacy_backup','other')
PRUNABLE={'history','unused_annexes','legacy_backup'}


def inventory(directory):
    root=Path(directory)
    if root.is_symlink():raise ValueError(backend_message('Proyecto enlazado / Linked project'))
    data=engine.load_engagement(root/'engagement.yaml')
    active={row.get('member') for row in data.get('attachments',[])}
    groups={key:[] for key in CATEGORIES};stats=[]
    for path in sorted(root.rglob('*')):
        if path.is_symlink():raise ValueError(backend_message('Enlace simbólico en datos privados / Symlink in private data'))
        if not path.is_file():continue
        if len(stats)>=project_history.MAX_FILES:raise ValueError(backend_message('Inventario demasiado grande / Inventory too large'))
        name=path.relative_to(root).as_posix();stat=path.stat()
        stats.append((name,stat.st_size,stat.st_mtime_ns))
        if name=='engagement.yaml':category='document'
        elif name=='engagement.yaml.bak':category='legacy_backup'
        elif name.startswith('img/'):category='images'
        elif name.startswith('originals/'):category='originals'
        elif name.startswith('attachments/'):category='annexes' if name in active else 'unused_annexes'
        elif name.startswith('history/'):category='history'
        else:category='other'
        groups[category].append(dict(name=name,bytes=stat.st_size))
    stamp=sha256(json.dumps(stats,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return dict(project_revision=revision(root/'engagement.yaml'),inventory_revision=stamp,
        root=str(root.resolve()),versions=len(project_history.history(root)),
        categories=[dict(key=key,count=len(rows),bytes=sum(row['bytes'] for row in rows),
                         files=rows[:100],truncated=len(rows)>100,can_prune=key in PRUNABLE)
                    for key,rows in groups.items()],
        external_backups='not_tracked',browser_drafts='browser_only',
        _groups=groups)


def public_inventory(directory):
    result=inventory(directory);result.pop('_groups');return result


def prune(directory,categories,inventory_revision):
    if not isinstance(categories,list) or not categories or any(not isinstance(x,str) or x not in PRUNABLE for x in categories) or len(categories)!=len(set(categories)):
        raise ValueError(backend_message('Elige categorías permitidas / Select permitted categories'))
    before=inventory(directory)
    if before['inventory_revision']!=inventory_revision:raise ValueError(backend_message('El inventario cambió; vuelve a revisarlo / Inventory changed; review again'))
    with project_history.transaction(directory) as stage:
        for category in categories:
            if category=='history':
                if (stage/'history').exists():shutil.rmtree(stage/'history')
            else:
                for row in before['_groups'][category]:
                    path=stage/row['name']
                    # Only paths discovered inside this private staging tree.
                    if path.is_symlink() or not path.resolve().is_relative_to(stage.resolve()):raise ValueError(backend_message('Ruta no permitida / Invalid path'))
                    path.unlink()
        if 'history' in categories:
            project_history.checkpoint(stage,'Estado actual tras limpieza privada','draft',force=True)
    return public_inventory(directory)
