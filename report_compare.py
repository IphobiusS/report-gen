"""Readable, offline comparison of two immutable project versions."""
from base64 import b64encode
from difflib import SequenceMatcher
from hashlib import sha256
from html import escape
from pathlib import Path
import re
import mimetypes
import workflows

FIELDS = {
    'title': ('Título', 'Title'), 'severity': ('Severidad', 'Severity'), 'status': ('Estado', 'Status'),
    'description_md': ('Descripción', 'Description'), 'impact_md': ('Impacto', 'Impact'),
    'remediation_md': ('Remediación', 'Remediation'), 'affected': ('Objetivo', 'Target'),
    'cvss': ('CVSS', 'CVSS'), 'cvss_vector': ('Vector CVSS', 'CVSS vector'),
    'walkthrough': ('Reproducción', 'Reproduction'), 'evidence_uids': ('Evidencias vinculadas', 'Linked evidence'),
    'report_title': ('Título del informe', 'Report title'), 'report': ('Secciones del informe', 'Report sections')}


def _text(value, lang="es"):
    if value is None: return '—'
    if isinstance(value, str): return value
    if isinstance(value, list):
        return '\n\n'.join(_text(item, lang) for item in value) or '—'
    if isinstance(value, dict):
        return '\n\n'.join(FIELDS.get(key, (key.replace('_', ' '), key.replace('_', ' ')))[lang == 'en'] + ': ' + _text(item, lang) for key, item in value.items())
    return str(value)


def diff(before, after, lang="es"):
    """Bound worst-case diff work; full changed text is always preserved."""
    old, new = _text(before, lang), _text(after, lang)
    a, b = re.findall(r'\s+|[^\s]+', old), re.findall(r'\s+|[^\s]+', new)
    if len(a) + len(b) > 6000:
        return '<del>' + escape(old) + '</del>', '<ins>' + escape(new) + '</ins>'
    left, right = [], []
    for op, i, j, k, l in SequenceMatcher(None, a, b, autojunk=True).get_opcodes():
        x, y = escape(''.join(a[i:j])), escape(''.join(b[k:l]))
        if x: left.append(x if op == 'equal' else '<del>' + x + '</del>')
        if y: right.append(y if op == 'equal' else '<ins>' + y + '</ins>')
    return ''.join(left), ''.join(right)


def render(before, after, old_files, new_files, old_label, new_label, lang='es', internal=False):
    from publication import comparison_projection, clean_image
    if not internal:
        from copy import deepcopy
        from publication import project
        # Apply both valid configurations in their original order. Concatenating
        # two 200-decision configurations creates an invalid 400-decision author
        # setting; deduplication would change non-idempotent literal decisions.
        # Each projection still bounds every intermediate/cumulative text state
        # to 16 MiB and retains the structural/private publication boundary.
        before=project(before)
        before['publication']=deepcopy(after.get('publication',{}))
        before, old_files = comparison_projection(before, old_files)
        after, new_files = comparison_projection(after, new_files)
    else:
        old_files={k:clean_image(v) for k,v in old_files.items() if k.startswith('img/')}
        new_files={k:clean_image(v) for k,v in new_files.items() if k.startswith('img/')}
    en = lang == 'en'
    w = lambda es, english: english if en else es
    old = {f.get('uid', f.get('id')): f for f in before.get('findings', [])}
    new = {f.get('uid', f.get('id')): f for f in after.get('findings', [])}
    added, removed = len(new.keys() - old.keys()), len(old.keys() - new.keys())
    changed = sum(old[k] != new[k] for k in old.keys() & new.keys())
    parts = [f'<header><p>report-gen / {escape(w("Comparación de entregas", "Delivery comparison"))}</p>',
             '<h1>' + escape(after.get('meta', {}).get('report_title', '')) + '</h1>',
             '<p>' + escape(old_label) + ' → ' + escape(new_label) + '</p></header>',
             '<p class="summary">' + escape(w(f'{added} añadidos · {removed} retirados · {changed} modificados',
                                                      f'{added} added · {removed} removed · {changed} modified')) + '</p>',
             '<p>' + escape(w('Retirado significa que ya no está en el informe; no acredita una corrección. Los cambios de estado reflejan lo registrado por el evaluador.',
                               'Removed means no longer in the report; it does not prove remediation. Status changes reflect the assessor’s records.')) + '</p>']
    parts.append('<p><strong>'+escape(w('INTERNA: contiene borradores y datos privados. No entregar al cliente.','INTERNAL: contains drafts and private data. Do not deliver to clients.') if internal else w('Compartible: solo contenido publicado. Las imágenes anteriores se omiten para no recuperar evidencias que después se censuraron. Revisa también el texto histórico antes de compartir.','Shareable: published content only. Earlier images are omitted to avoid restoring evidence later redacted. Review historical text before sharing.'))+'</strong></p>')
    changes = workflows.compare(before, after)
    for change in changes:
        uid, path = change['finding_uid'], change['path']
        finding = new.get(uid) or old.get(uid)
        field = path.split('.')[-1]
        label = (w('Añadido', 'Added') if uid and uid not in old else w('Retirado', 'Removed') if uid and uid not in new else FIELDS.get(field, (field.replace('_', ' '), field.replace('_', ' ')))[en])
        heading = ((finding.get('id', '') + ' / ' + finding.get('title', '') + ' / ') if finding else '') + label
        a, b = change['before'], change['after']
        if field == 'status':
            a, b = (workflows.label(workflows.STATUSES, value, lang) if isinstance(value, str) else value for value in (a, b))
        left, right = diff(a, b, lang)
        parts.append('<section><h2>' + escape(heading) + '</h2><details class="path"><summary>' + w('Referencia técnica', 'Technical reference') + '</summary>' + escape(path) + '</details><div class="pair">'
                     '<div><h3>' + w('Antes', 'Before') + '</h3><pre>' + left + '</pre></div>'
                     '<div><h3>' + w('Después', 'After') + '</h3><pre>' + right + '</pre></div></div></section>')
    images = 0
    # Include processed report resources only, never confidential evidence originals.
    for name in sorted(old_files.keys() | new_files.keys()):
        if name == 'engagement.yaml' or name.startswith('originals/'):
            continue
        a, b = old_files.get(name), new_files.get(name)
        if a == b: continue
        mimetype = mimetypes.guess_type(name)[0]
        if mimetype not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'): continue
        images += 1
        pair = []
        for blob, title in ((a if internal else None, w('Antes (solo interna)', 'Before (internal only)')), (b, w('Después', 'After'))):
            figure = ('<img alt="' + escape(name, quote=True) + '" src="data:' + mimetype + ';base64,' + b64encode(blob).decode() + '">'
                      '<p class="hash">SHA-256 ' + sha256(blob).hexdigest() + '</p>') if blob else '<p>—</p>'
            pair.append('<div><h3>' + title + '</h3>' + figure + '</div>')
        parts.append('<section><h2>' + w('Evidencia / ', 'Evidence / ') + escape(name) + '</h2><div class="pair">' + ''.join(pair) + '</div></section>')
    if not changes and not images:
        parts.append('<p>' + w('No hay diferencias entre estas versiones.', 'There are no differences between these versions.') + '</p>')
    # Same bundled fallback font used by the report exporters; standalone/offline.
    font = b64encode((Path(__file__).parent / 'themes/fonts/Carlito-Regular.ttf').read_bytes()).decode()
    style = '''@font-face{font-family:Report;src:url(data:font/ttf;base64,FONT)}
body{font:11pt/1.55 Calibri,Report,Arial,sans-serif;color:#172435;background:white;margin:0 auto;max-width:1100px;padding:32px}
header{border-bottom:3px solid #284d70;margin-bottom:24px}h1{font-size:24pt}h2{font-size:14pt}h3{font-size:11pt}
section{border-top:1px solid #9ca8b8;margin-top:24px;padding-top:12px}.summary{font-weight:bold}.path,.hash{font-size:8pt;overflow-wrap:anywhere;color:#43536a}
.pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px}.pair>div{min-width:0}
pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}ins{background:#d7f4d6;color:#173d20;text-decoration:underline}del{background:#fbe1dc;color:#672821}
img{display:block;max-width:100%;max-height:650px;object-fit:contain}@media(max-width:650px){body{padding:16px}.pair{grid-template-columns:1fr}}
@page{size:A4;margin:18mm}@media print{body{padding:0;font-size:10pt}h1,h2,h3{break-after:avoid}img{max-height:110mm}.pair{display:block}.pair>div{margin-bottom:14px}*{print-color-adjust:exact}}
'''.replace('FONT', font)
    return '<!doctype html><html lang="' + ('en' if en else 'es') + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' \
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; font-src data:">' \
        '<title>' + w('Comparación de entregas', 'Delivery comparison') + '</title><style>' + style + '</style></head><body>' + ''.join(parts) + '</body></html>'
