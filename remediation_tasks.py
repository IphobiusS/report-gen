"""Explicit-field, offline remediation deliveries from one saved project revision."""
from languages import normalize_language, language_index, language_tag
import csv
import io
import unicodedata
import zipfile
from html import escape

import workflows
from error_messages import message


FIELDS = {
    'id': ('ID del hallazgo', 'Finding ID', 'ID do achado'),
    'finding_uid': ('Referencia permanente', 'Permanent reference', 'Referência permanente'),
    'title': ('Título', 'Title', 'Título'),
    'assets': ('Activos afectados', 'Affected assets', 'Ativos afetados'),
    'action': ('Acción de remediación', 'Remediation action', 'Ação de remediação'),
    'owner': ('Responsable', 'Owner', 'Responsável'),
    'due_date': ('Plazo', 'Due date', 'Prazo'),
    'closure_criteria': ('Criterio de cierre', 'Closure criteria', 'Critério de encerramento'),
    'status': ('Estado registrado', 'Recorded status', 'Estado registrado'),
    'group_uid': ('Referencia del grupo', 'Group reference', 'Referência do grupo'),
    'group_name': ('Grupo por causa raíz', 'Root-cause group', 'Grupo de causa raiz'),
    'shared_action': ('Acción común del grupo', 'Shared group action', 'Ação comum do grupo'),
}
REQUIRED = ('id', 'finding_uid')
PRIVATE = frozenset({'title', 'assets', 'action', 'owner', 'closure_criteria', 'group_name', 'shared_action'})


def options(body):
    """No implicit expansion: every authored content field requires selection."""
    fields = body.get('fields')
    if (not isinstance(fields, list) or not fields or len(fields) > len(FIELDS)
            or any(not isinstance(key, str) or key not in FIELDS for key in fields)
            or len(set(fields)) != len(fields) or not set(REQUIRED).issubset(fields)):
        raise ValueError(message('Selecciona campos válidos, incluido el ID y su referencia permanente', en='Select valid fields, including ID and permanent reference'))
    if type(body.get('ack_private', False)) is not bool:
        raise ValueError(message('Confirmación de datos privados inválida', en='Invalid private-data acknowledgement'))
    if PRIVATE.intersection(fields) and body.get('ack_private') is not True:
        raise ValueError(message('Confirma que revisaste los campos que pueden contener datos privados', en='Confirm review of fields that may contain private data'))
    lang = normalize_language(body.get('lang', 'es'), None)
    if lang is None:
        raise ValueError(message('Idioma inválido', en='Invalid language'))
    # A single canonical order keeps preview, CSV and cards consistent.
    return [key for key in FIELDS if key in fields], lang


def rows(data, fields, lang='es'):
    """Keep independent findings and IDs even when they share a cause or action."""
    from root_cause import group_for_finding, resolved_action
    issues = workflows.structure_errors(data)
    if issues:
        raise ValueError('; '.join(text for level, text in issues if level == 'error'))
    assets = {row['uid']: row for row in data.get('assets', []) if row.get('uid')}
    output, seen = [], set()
    for finding in data.get('findings', []):
        uid = finding.get('uid')
        if not isinstance(uid, str) or not workflows.UID.fullmatch(uid) or uid in seen:
            raise ValueError(message('Guarda el proyecto con referencias de hallazgo únicas antes de exportar', en='Save the project with unique finding references before export'))
        seen.add(uid)
        group = group_for_finding(data, finding) or {}
        asset_lines = []
        for ref in finding.get('asset_uids', []):
            asset = assets.get(ref)
            if asset is None:
                raise ValueError(message('Hay un activo vinculado inexistente; corrígelo antes de exportar', en='A linked asset is missing; fix it before export'))
            asset_lines.append(' · '.join(value for value in (asset.get('name', ''), asset.get('target', '')) if value))
        values = {
            'id': finding.get('id', ''), 'finding_uid': uid,
            'title': finding.get('title', ''), 'assets': '\n'.join(asset_lines),
            'action': resolved_action(data, finding), 'owner': finding.get('owner', ''),
            'due_date': finding.get('due_date', ''), 'closure_criteria': finding.get('closure_criteria_md', ''),
            'status': workflows.STATUSES[finding.get('status', 'open')][language_index(lang)],
            'group_uid': group.get('uid', ''), 'group_name': group.get('name', ''),
            'shared_action': group.get('remediation_md', ''),
        }
        if any(not isinstance(value, str) for value in values.values()):
            raise ValueError(message('Los campos de la tarea deben ser texto', en='Task fields must be text'))
        output.append({key: values[key] for key in fields})
    return output


def labels(fields, lang='es'):
    return {key: FIELDS[key][language_index(lang)] for key in fields}


def csv_cell(value):
    """Neutralize spreadsheet formulas including hidden/control prefixes."""
    probe = value
    while probe and (probe[0].isspace() or unicodedata.category(probe[0]) in ('Cc', 'Cf')):
        probe = probe[1:]
    # Tabs/line breaks at the start also trigger spreadsheet interpretation in
    # some import paths. QUOTE_ALL alone does not prevent formula execution.
    if (probe.startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n'))):
        return "'" + value
    return value


def csv_bytes(project_rows, fields, lang='es'):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(labels(fields, lang).values())
    writer.writerows([csv_cell(row[key]) for key in fields] for row in project_rows)
    return b'\xef\xbb\xbf' + stream.getvalue().encode('utf-8')


def card_html(row, fields, lang='es'):
    title = (('Tarea de remediación', 'Remediation task', 'Tarefa de remediação')[language_index(lang)])
    missing = (('Sin registrar', 'Not recorded', 'Sem registro')[language_index(lang)])
    note = ((('Los campos vacíos no se han completado automáticamente. Esta ficha recoge datos registrados; no acredita la corrección. El contenido se muestra como texto.', 'Empty fields have not been filled automatically. This card contains recorded data; it does not prove remediation. Content is displayed as text.', 'Os campos vazios não foram preenchidos automaticamente. Esta ficha contém dados registrados; não comprova remediação. O conteúdo é exibido como texto.')[language_index(lang)]))
    entries = ''.join('<dt>' + escape(label) + '</dt><dd>' + escape(row[key] or missing) + '</dd>'
                      for key, label in labels(fields, lang).items())
    return ('<!doctype html><html lang="' + language_tag(lang) + '"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            '<title>' + title + '</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:54rem;'
            'margin:2rem auto;padding:0 1rem;color:#17212c;background:#fff}dt{font-weight:700;margin-top:1rem}'
            'dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}p{color:#465564}'
            '@media print{body{margin:0}dt{break-after:avoid}dd{orphans:3;widows:3}}</style></head><body>'
            '<main><h1>' + title + '</h1><p>' + note + '</p><dl>' + entries + '</dl></main></body></html>').encode('utf-8')


def cards_zip(project_rows, fields, lang='es'):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for row in project_rows:
            info = zipfile.ZipInfo('task-' + row['finding_uid'] + '.html', date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, card_html(row, fields, lang))
    return output.getvalue()
