"""Portable project model, delivery checks and report projection (no network access)."""
from error_messages import message as backend_message
from datetime import date
from pathlib import Path
import re
import uuid
from urllib.parse import unquote

STATUSES = {'open': ('Abierto', 'Open'), 'in_progress': ('En corrección', 'In progress'),
            'reported_fixed': ('Corrección comunicada', 'Reported fixed'),
            'verified_fixed': ('Corregido y verificado', 'Verified fixed'),
            'accepted': ('Riesgo aceptado', 'Risk accepted'), 'not_verified': ('No verificable', 'Not verifiable')}
VERIFICATIONS = {'unverified': ('Sin verificar', 'Unverified'), 'confirmed': ('Confirmado', 'Confirmed'),
                 'not_reproduced': ('No reproducido', 'Not reproduced'), 'inconclusive': ('Inconcluso', 'Inconclusive')}
RESULTS = {'fixed': ('Corregido', 'Fixed'), 'open': ('Sigue abierto', 'Still open'),
           'partial': ('Corrección parcial', 'Partially fixed'), 'not_verified': ('No verificable', 'Not verifiable')}
COVERAGE = {'pending': ('Pendiente', 'Pending'), 'done': ('Realizada', 'Performed'),
            'blocked': ('Bloqueada', 'Blocked'), 'not_applicable': ('No aplica', 'Not applicable')}
UID = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
MAX_SEQUENCE = 2**53 - 1


def _sequence_number(digits):
    """Read a portable display number without arbitrary-length int conversion."""
    digits = digits.lstrip('0') or '0'
    limit = str(MAX_SEQUENCE)
    if len(digits) > len(limit) or (len(digits) == len(limit) and digits > limit):
        raise ValueError(backend_message('Se agotó el contador de identificadores de hallazgos / Finding identifier counter exhausted'))
    return int(digits)


def _identifier_number(identity):
    # Match the ASCII numeric IDs allocated by both browser and Python. A
    # Unicode/custom identity remains opaque documentary data.
    if isinstance(identity, str) and re.fullmatch(r'F[0-9]+', identity):
        return _sequence_number(identity[1:])
    return 0


def _finding_sequence(data):
    counter = data.get('finding_sequence', 0)
    if type(counter) is not int or not 0 <= counter <= MAX_SEQUENCE:
        raise ValueError(backend_message('Contador de identificadores de hallazgos inválido / Invalid finding identifier counter'))
    return max([counter] + [_identifier_number(f.get('id')) for f in data.get('findings', [])])


def new_uid():
    return str(uuid.uuid4())


def normalize(data):
    """Assign identities once; keep existing IDs, display numbers and legacy fields."""
    # Check before assigning UIDs or schema fields: failure leaves the project
    # unchanged, and a portable source can still be edited at the final number.
    sequence = _finding_sequence(data)
    data['schema_version'] = 2
    for key in ('findings', 'assets', 'evidence', 'coverage'):
        for row in data.setdefault(key, []):
            row.setdefault('uid', new_uid())
    data.setdefault('report', {})
    data['finding_sequence'] = sequence
    return data


def allocate_finding_id(data):
    sequence = max(_finding_sequence(data), max(referenced_finding_numbers(data), default=0))
    if sequence >= MAX_SEQUENCE:
        raise ValueError(backend_message('Se agotó el contador de identificadores de hallazgos / Finding identifier counter exhausted'))
    normalize(data)
    data['finding_sequence'] = sequence + 1
    return 'F' + str(data['finding_sequence'])


def referenced_finding_numbers(data):
    """Reserve removed numeric destinations, including their URL encodings.

    Decode exactly once, as the browser does for a fragment. A percent sign in
    an author's literal identity is not itself an instruction to decode twice.
    """
    for _, value in strings(data):
        for match in re.finditer(r'#F([0-9]+)\b', value):
            yield _sequence_number(match[1])
        for match in re.finditer(r'''#([^\s<>()\[\]{}"'`]+)''', value):
            try:
                identity = unquote(match[1], errors='strict')
            except UnicodeDecodeError:
                continue
            if re.fullmatch(r'F[0-9]+', identity):
                yield _sequence_number(identity[1:])


def structure_errors(data):
    """Validate workflow fields before they reach filesystem/image/report code."""
    errors = []
    def err(path, msg): errors.append(('error', f'{path}: {msg}'))
    def text(obj, key, path):
        if key in obj and not isinstance(obj[key], str): err(path + '.' + key, backend_message('debe ser texto'))
    def rows(obj, key, path):
        value = obj.get(key, [])
        if not isinstance(value, list) or len(value) > 10000 or any(not isinstance(x, dict) for x in value):
            err(path + '.' + key, backend_message('debe ser una lista de objetos')); return []
        return value
    def refs(obj, key, path):
        value = obj.get(key, [])
        if not isinstance(value, list) or any(not isinstance(x, str) or not UID.fullmatch(x) for x in value):
            err(path + '.' + key, backend_message('referencias inválidas'))
    def ident(row, path, seen):
        if 'uid' in row:
            uid = row['uid']
            if not isinstance(uid, str) or not UID.fullmatch(uid): err(path + '.uid', backend_message('identificador inválido'))
            elif uid in seen: err(path + '.uid', backend_message('identificador duplicado'))
            else: seen.add(uid)
    def dt(row, key, path):
        if row.get(key):
            try:
                value = row[key]
                if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
                    raise ValueError(backend_message('noncanonical date'))
                date.fromisoformat(value)
            except (ValueError, TypeError): err(path + '.' + key, backend_message('usa AAAA-MM-DD'))
    if 'schema_version' in data and (type(data['schema_version']) is not int or data['schema_version'] not in (1, 2)):
        err('schema_version', backend_message('versión de proyecto no soportada'))
    if 'finding_sequence' in data and (type(data['finding_sequence']) is not int or not 0 <= data['finding_sequence'] < 2**53):
        err('finding_sequence', backend_message('contador de identificadores inválido'))
    if 'publication' in data:
        from publication import validate_config
        try: validate_config(data['publication'])
        except ValueError as exc: err('publication',str(exc))
    if 'attachments' in data:
        from attachments import validate_rows
        try: validate_rows(data['attachments'])
        except ValueError as exc: err('attachments',str(exc))
    seen = set()
    for group in ('assets', 'evidence', 'coverage', 'findings'):
        for n, row in enumerate(rows(data, group, 'project')):
            path = f'{group}[{n}]'; ident(row, path, seen)
            fields = {'assets': ('name', 'target', 'kind', 'notes'),
                      'evidence': ('title', 'src', 'original', 'caption'),
                      'coverage': ('test', 'status', 'notes', 'asset_uid'),
                      'findings': ('owner', 'due_date', 'status', 'closure_criteria_md')}[group]
            for key in fields: text(row, key, path)
            if group == 'evidence':
                if not row.get('src'): err(path + '.src', backend_message('ruta de imagen obligatoria'))
                for key, prefix in [('src', 'img/'), ('original', 'originals/')]:
                    if row.get(key) and not safe_member(row[key], prefix): err(path + '.' + key, backend_message('ruta inválida'))
            if group == 'coverage' and (not isinstance(row.get('status', 'pending'), str) or row.get('status', 'pending') not in COVERAGE): err(path, backend_message('estado de cobertura inválido'))
            if group in ('assets', 'coverage') and 'import_source' in row:
                source = row['import_source']
                if not isinstance(source, dict): err(path + '.import_source', backend_message('debe ser un objeto'))
                else:
                    if source.get('format') != 'nmap': err(path, backend_message('origen de importación inválido'))
                    if type(source.get('reviewed')) is not bool: err(path, backend_message('revisión de importación inválida'))
                    for field in ('external_id', 'confidence', 'imported_at', 'scanner_version', 'observed_at'):
                        text(source, field, path + '.import_source')
                    for field in ('file_sha256', 'fingerprint'):
                        if not isinstance(source.get(field), str) or not re.fullmatch(r'[0-9a-f]{64}', source[field]):
                            err(path, backend_message('hash de importación inválido'))
            if group == 'coverage' and 'services' in row:
                for i, service in enumerate(rows(row, 'services', path)):
                    sp = path + f'.services[{i}]'
                    if type(service.get('port')) is not int or not 0 <= service['port'] <= 65535:
                        err(sp, 'puerto inválido / invalid port')
                    if service.get('protocol') not in ('tcp', 'udp', 'sctp', 'ip'):
                        err(sp, 'protocolo inválido / invalid protocol')
                    for field in ('state', 'name', 'product', 'version', 'extrainfo', 'tunnel', 'method', 'conf'):
                        text(service, field, sp)
            if group == 'findings':
                try: _identifier_number(row.get('id'))
                except ValueError: err(path + '.id', backend_message('número de identificador fuera del rango portátil / Identifier number outside the portable range'))
                if 'import_source' in row:
                    source = row['import_source']
                    if not isinstance(source, dict): err(path + '.import_source', backend_message('debe ser un objeto'))
                    else:
                        for field in ('format', 'file_sha256', 'fingerprint', 'external_id', 'confidence', 'imported_at'):
                            text(source, field, path + '.import_source')
                        if source.get('format') not in ('csv', 'burp', 'nuclei'): err(path, backend_message('origen de importación inválido'))
                        if type(source.get('reviewed')) is not bool: err(path, backend_message('revisión de importación inválida'))
                        for field in ('file_sha256', 'fingerprint'):
                            if not isinstance(source.get(field), str) or not re.fullmatch(r'[0-9a-f]{64}', source[field]):
                                err(path, backend_message('hash de importación inválido'))
                if not isinstance(row.get('status', 'open'), str) or row.get('status', 'open') not in STATUSES: err(path, backend_message('estado inválido'))
                if row.get('verification', '') not in ('', 'unverified', 'confirmed', 'not_reproduced', 'inconclusive'):
                    err(path + '.verification', backend_message('verificación técnica inválida'))
                dt(row, 'due_date', path)
                refs(row, 'asset_uids', path); refs(row, 'evidence_uids', path)
                for i, retest in enumerate(rows(row, 'retests', path)):
                    rp = path + f'.retests[{i}]'; ident(retest, rp, seen)
                    for key in ('tested_on', 'assessor', 'notes_md', 'result'): text(retest, key, rp)
                    dt(retest, 'tested_on', rp); refs(retest, 'evidence_uids', rp)
                    if not isinstance(retest.get('result'), str) or retest.get('result') not in RESULTS: err(rp, backend_message('resultado de retest inválido'))
    from root_cause import structure_errors as root_cause_errors
    errors.extend(root_cause_errors(data, seen))
    from capture_inbox import validate_rows
    try: validate_rows(data.get('capture_inbox', []))
    except ValueError as exc: err('capture_inbox', str(exc))
    report = data.get('report', {})
    if isinstance(report, dict) and 'workflow' in report:
        cfg = report['workflow']
        if not isinstance(cfg, dict): err('report.workflow', backend_message('debe ser un objeto'))
        else:
            for key in ('include_assets', 'include_coverage', 'include_retest', 'include_root_causes'):
                if key in cfg and not isinstance(cfg[key], bool): err('report.workflow.' + key, backend_message('debe ser booleano'))
    if 'limitations_md' in data and not isinstance(data['limitations_md'], str): err('limitations_md', backend_message('debe ser texto'))
    return errors


def safe_member(name, prefix=''):
    return (isinstance(name, str) and name.startswith(prefix) and not name.startswith('/')
            and not any(c in name for c in ('\\', ':', '\x00'))
            and all(part not in ('', '.', '..') for part in name.split('/')))


def strings(obj, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items(): yield from strings(v, f'{path}.{k}' if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj): yield from strings(v, f'{path}[{i}]')
    elif isinstance(obj, str): yield path, obj


def latest_retest(finding):
    """ISO test date first; append order breaks ties or missing dates."""
    rows=finding.get('retests',[])
    return max(enumerate(rows),key=lambda pair:(pair[1].get('tested_on',''),pair[0]))[1] if rows else {}


def review(data, directory, lang="es"):
    """Actionable warnings; never asserts that a pentest is complete or secure."""
    issues = []
    def add(level, message, path, uid=None):
        issues.append(dict(level=level, message=message, path=path, finding_uid=uid))
    assets = {x.get('uid') for x in data.get('assets', [])}
    evidence = {x.get('uid'): x for x in data.get('evidence', [])}
    for i, f in enumerate(data.get('findings', [])):
        p = f'findings[{i}]'; uid = f.get('uid'); name = f.get('id', f'F{i+1}')
        if f.get('import_source') and not f['import_source'].get('reviewed'):
            add('error', backend_message('{p0}: importación pendiente de revisión / import awaiting review', language=lang, p0=name), p + '.import_source', uid)
        fields = ['title'] + (['description_md', 'impact_md', 'remediation_md'] if f.get('mode') != 'machine' else [])
        for key in fields:
            if not str(f.get(key) or '').strip(): add('warning', backend_message('{p0}: falta {p1}', language=lang, p0=name, p1=key), p + '.' + key, uid)
        content = list(strings(f.get('walkthrough', f.get('phases', []))))
        if not any(value.strip() for _, value in content): add('warning', backend_message('{p0}: faltan pasos de reproducción', language=lang, p0=name), p + '.walkthrough', uid)
        image_present = any((path.endswith('.src') or '![' in value or '<img' in value) for path, value in strings(f))
        if not f.get('evidence_uids') and not f.get('proof') and not f.get('flags') and not image_present: add('warning', backend_message('{p0}: falta evidencia', language=lang, p0=name), p + '.evidence_uids', uid)
        for key, pool in [('asset_uids', assets), ('evidence_uids', evidence)]:
            for ref in f.get(key, []):
                if ref not in pool: add('error', backend_message('{p0}: referencia inexistente en {p1}', language=lang, p0=name, p1=key), p + '.' + key, uid)
        for j, record in enumerate(f.get('retests', [])):
            for ref in record.get('evidence_uids', []):
                if ref not in evidence: add('error', backend_message('{p0}: evidencia de retest inexistente', language=lang, p0=name), p + f'.retests[{j}]', uid)
            if record.get('result') == 'fixed' and not record.get('evidence_uids'):
                add('warning', backend_message('{p0}: retest corregido sin evidencia vinculada', language=lang, p0=name), p + f'.retests[{j}]', uid)
        if f.get('status') == 'verified_fixed' and latest_retest(f).get('result') != 'fixed':
            add('warning', backend_message('{p0}: figura corregido sin un último retest que lo verifique', language=lang, p0=name), p + '.status', uid)
        if f.get('due_date') and f['due_date'] < date.today().isoformat() and f.get('status', 'open') not in ('verified_fixed', 'accepted'):
            add('warning', backend_message('{p0}: fecha de corrección vencida', language=lang, p0=name), p + '.due_date', uid)
    from root_cause import selected_groups
    for group, members in selected_groups(data):
        index = data['root_cause_groups'].index(group)
        for field in ('name', 'cause_md', 'remediation_md'):
            if not group.get(field, '').strip():
                add('warning', backend_message('Grupo de causa raíz: falta {field}', en='Root cause group: missing {field}', language=lang, field=field), f'root_cause_groups[{index}].{field}')
    live={f.get('uid') for f in data.get('findings',[])}
    for i,capture in enumerate(data.get('capture_inbox',[])):
        if capture.get('finding_uid') and capture['finding_uid'] not in live:
            add('warning', backend_message('Captura con vínculo roto: puede volver a incorporarse / Capture has a broken link: it can be linked again', language=lang), f'capture_inbox[{i}]')
    for i, row in enumerate(data.get('coverage', [])):
        if row.get('asset_uid') and row['asset_uid'] not in assets: add('error', backend_message('Cobertura vinculada a un activo inexistente', language=lang), f'coverage[{i}].asset_uid')
        if row.get('status', 'pending') in ('pending', 'blocked'):
            add('warning', backend_message('Prueba pendiente o bloqueada: {p0}', language=lang, p0=row.get('test', '')), f'coverage[{i}].status')
    for path, value in strings(data):
        # Optional reasoning/review is private author material. In particular a
        # comment containing a placeholder must not leak into the client-facing
        # delivery verification warning. Its editorial rules have a separate
        # read-only view; audience projections select presentation text explicitly.
        if path.startswith(('capture_inbox', 'insights')): continue
        match = re.search(r'\b(TODO|TBD|FIXME|pendiente de completar|lorem ipsum)\b|\{\{[^}]+\}\}|<COMPLETAR>', value, re.I)
        uid = None
        fm = re.match(r'findings\[(\d+)\]', path)
        if fm: uid = data['findings'][int(fm[1])].get('uid')
        if match: add('warning', backend_message('Texto pendiente: {p0}', language=lang, p0=match[0]), path, uid)
    from resources import image_references, local_image
    for path, source in image_references(data):
        if path.startswith(('capture_inbox', 'insights')): continue
        uid = None
        fm = re.match(r'findings\[(\d+)\]', path)
        if fm: uid = data['findings'][int(fm[1])].get('uid')
        try: local_image(source, Path(directory))
        except ValueError: add('error', backend_message('Imagen ausente o no permitida: {p0}', language=lang, p0=source), path, uid)
    from attachments import inventory
    for row in inventory(data,directory):
        if row['status'] in ('declared','missing'):
            add('error' if row['include'] or row['required'] else 'warning', backend_message('Anexo declarado ausente: {p0} / Declared annex missing', language=lang, p0=row['name']), 'attachments')
        elif row['status']=='excluded':
            add('error' if row['required'] else 'warning', backend_message('Anexo conservado solo en el proyecto: {p0} / Annex excluded from delivery', language=lang, p0=row['name']), 'attachments')
    if not data.get('findings'): add('warning', backend_message('El proyecto no contiene hallazgos', language=lang), 'findings')
    for issue in issues:
        path=issue['path']
        es='Abre el campo, documenta el dato que falta y contrástalo con la evidencia; después vuelve a revisar.'
        en='Open the field, document the missing information and check it against the evidence; then review again.'
        if path.startswith('findings') and path.endswith('.status'):
            es='El último retest se elige por fecha ISO; si empatan, por orden de registro. Comprueba ese resultado antes de marcar como corregido.'
            en='Latest retest uses the ISO test date, with record order breaking ties. Check that result before marking the finding fixed.'
        elif path.startswith('coverage'):
            es='Documenta si la prueba se realizó, quedó bloqueada o no aplica; explica la limitación sin marcar como realizada una prueba pendiente.'
            en='Document whether the test was performed, blocked or not applicable; explain the limitation without marking a pending test as performed.'
        elif 'capture_inbox' in path:
            es='La captura conserva su original. Abre la bandeja y elige un hallazgo existente para reincorporarla.'
            en='The original capture is retained. Open the inbox and choose an existing finding to link it again.'
        elif 'import_source' in path:
            es='Revisa objetivo, severidad, reproducción y posibles secretos. Confirmar la importación no confirma la vulnerabilidad.'
            en='Review the target, severity, reproduction and possible secrets. Acknowledging the import does not confirm the vulnerability.'
        issue['help']=en if lang=='en' else es
    return issues


def preflight(data, directory, lang="es"):
    """One saved-revision review for the editor and all export captures.

    Validation warnings are advisory, just like workflow warnings; errors stay
    blocking. Keep the actionable workflow metadata when both checks emit the
    same issue. Invalid document structures must not enter workflow traversal.
    """
    import validate
    lang = lang if isinstance(lang, str) and lang in validate.LANGS else "es"
    structure = validate.structure_issues(data, lang)
    issues = [] if structure else review(data, directory, lang)
    validation = structure or validate.validate(data, lang=lang)
    seen = {(issue['level'], issue['message']) for issue in issues}
    for level, message in validation:
        if (level, message) in seen:
            continue
        seen.add((level, message))
        issues.append(dict(level=level, message=message, path='report', finding_uid=None,
                           help=('Review the report data and its evidence. Warnings require a documented decision; errors must be corrected before export.'
                                 if lang == 'en' else
                                 'Revisa los datos del informe y su evidencia. Los avisos requieren una decisión documentada; los errores deben corregirse antes de exportar.')))
    return issues


def english_review(message):
    """Compatibility helper: opaque interpolated text cannot be retranslated.

    review() selects explicit templates before inserting IDs, paths or authored
    text. The historic helper remains callable without corrupting those values.
    """
    return message


def compare(before, after):
    """Compare findings by permanent identity, so reordering is not deletion."""
    result = []
    def walk(a, b, path, uid=None):
        if a == b: return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() | b.keys()): walk(a.get(key), b.get(key), path + '.' + key, uid)
        else: result.append(dict(path=path, finding_uid=uid, before=a, after=b))
    old = {f.get('uid', f.get('id')): f for f in before.get('findings', [])}
    new = {f.get('uid', f.get('id')): f for f in after.get('findings', [])}
    for uid in sorted(old.keys() | new.keys()): walk(old.get(uid), new.get(uid), 'findings.' + str(uid), uid)
    walk({k: v for k, v in before.items() if k != 'findings'}, {k: v for k, v in after.items() if k != 'findings'}, 'project')
    return result


def label(group, key, lang):
    return group.get(key, (key, key))[lang != 'es']


def md_text(value):
    """Plain user data in generated Markdown tables/headings, never markup."""
    from html import escape
    value = escape(str(value if value is not None else '')).replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', value)


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(md_text(v) for v in headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(md_text(v) for v in row) + ' |' for row in rows])


def report_sections(data):
    from engine import report_language
    lang = report_language(data); es = lang == 'es'
    cfg = data.get('report', {}).get('workflow', {})
    asset_rows = data.get('assets', [])
    # The inventory is a list of records. Legacy rows without permanent IDs
    # must not collapse under the same None dictionary key. Only identified
    # assets participate in the relationship lookup used by coverage rows.
    assets = {a['uid']: a for a in asset_rows if a.get('uid')}
    out = []
    def add(key, title, body): out.append(dict(key=key, title=title, body=body))
    if cfg.get('include_assets', True) and asset_rows:
        add('rg_assets', 'Activos evaluados' if es else 'Assessed assets', table(
            ['Activo', 'Objetivo', 'Tipo', 'Notas'] if es else ['Asset', 'Target', 'Type', 'Notes'],
            [[a.get(k, '') for k in ('name', 'target', 'kind', 'notes')] for a in asset_rows]))
    if cfg.get('include_coverage', True) and (data.get('coverage') or data.get('limitations_md')):
        body = table(['Prueba', 'Activo', 'Estado', 'Observaciones'] if es else ['Test', 'Asset', 'Status', 'Notes'],
                     [[c.get('test'), assets.get(c.get('asset_uid'), {}).get('target', ''), label(COVERAGE, c.get('status', 'pending'), lang), c.get('notes')]
                      for c in data.get('coverage', [])]) if data.get('coverage') else ''
        if data.get('limitations_md'): body += '\n\n### ' + ('Limitaciones' if es else 'Limitations') + '\n\n' + data['limitations_md']
        add('rg_coverage', 'Cobertura y limitaciones' if es else 'Coverage and limitations', body)
    if cfg.get('include_root_causes', False):
        from root_cause import selected_groups
        groups = selected_groups(data)
        if groups:
            blocks = []
            for group, members in groups:
                block = '### ' + md_text(group.get('name') or ('Grupo sin nombre' if es else 'Unnamed group'))
                block += '\n\n' + ('Hallazgos: ' if es else 'Findings: ') + ', '.join(md_text(f.get('id', '')) for f in members)
                block += '\n\n**' + ('Causa raíz' if es else 'Root cause') + '**\n\n' + group.get('cause_md', '')
                block += '\n\n**' + ('Acción común' if es else 'Shared action') + '**\n\n' + group.get('remediation_md', '')
                blocks.append(block)
            add('rg_root_causes', 'Causas raíz y acciones comunes' if es else 'Root causes and shared actions', '\n\n'.join(blocks))
    fs = data.get('findings', [])
    if cfg.get('include_retest', True) and any(f.get('retests') or f.get('owner') or f.get('due_date') or f.get('status', 'open') != 'open' or f.get('verification') for f in fs):
        counts = {key: sum(f.get('status', 'open') == key for f in fs) for key in STATUSES}
        overview = ' · '.join(label(STATUSES, key, lang) + ': ' + str(value) for key, value in counts.items() if value)
        body = md_text(overview) + '\n\n' + table(['Hallazgo', 'Estado', 'Responsable', 'Fecha objetivo', 'Último retest'] if es else ['Finding', 'Status', 'Owner', 'Due date', 'Last retest'],
                     [[f.get('id', '') + ' · ' + (f.get('title') or ''), label(STATUSES, f.get('status', 'open'), lang), f.get('owner'), f.get('due_date'),
                       latest_retest(f).get('tested_on')] for f in fs])
        if any(f.get('verification') for f in fs):
            body += '\n\n### ' + ('Verificación técnica' if es else 'Technical verification') + '\n\n'
            body += table(['Hallazgo', 'Verificación'] if es else ['Finding', 'Verification'],
                          [[f.get('id', ''), label(VERIFICATIONS, f.get('verification'), lang) if f.get('verification') else ('Sin registrar' if es else 'Not recorded')] for f in fs])
        for f in fs:
            for r in f.get('retests', []):
                body += '\n\n### ' + md_text(f.get('id', '') + ' · ' + r.get('tested_on', '') + ' · ' + label(RESULTS, r['result'], lang))
                body += '\n\n' + ('Evaluador: ' if es else 'Assessor: ') + md_text(r.get('assessor', '')) + '\n\n' + r.get('notes_md', '')
                by_uid = {e.get('uid'): e for e in data.get('evidence', [])}
                for uid in r.get('evidence_uids', []):
                    e = by_uid.get(uid)
                    if e: body += '\n\n![' + md_text(e.get('caption') or e.get('title') or 'Evidence') + '](' + e['src'] + ')'
        add('rg_retest', 'Seguimiento de correcciones y retest' if es else 'Remediation tracking and retest', body)
    return out


def project_report(source):
    """Pure projection: add asset links/evidence to copies, outside indivisible tables."""
    from publication import project
    from engine import report_language, report_title
    data = project(source)
    # Effective presentation language belongs to this transient projection,
    # not the author's saved metadata or publication decisions.
    data.setdefault('meta', {})['lang'] = report_language(source)
    data['meta']['report_title'] = report_title(data)
    assets = {a.get('uid'): a for a in data.get('assets', [])}
    evidence = {e.get('uid'): e for e in data.get('evidence', [])}
    for c in data.get('coverage', []):
        if c.get('asset_uid') and c['asset_uid'] not in assets:
            raise ValueError(backend_message('Cobertura vinculada a un activo inexistente'))
    for f in data.get('findings', []):
        # Nullable titles are permitted in unfinished source documents. Every
        # exporter receives absent text, without persisting a replacement or
        # inventing a finding title; final review still reports the warning.
        if f.get('title') is None:
            f['title'] = ''
        for key, pool in [('asset_uids', assets), ('evidence_uids', evidence)]:
            if any(ref not in pool for ref in f.get(key, [])):
                raise ValueError(backend_message('{p0}: referencia inexistente en {p1}', p0=str(f.get('id', 'Hallazgo')), p1=key))
        for r in f.get('retests', []):
            if any(ref not in evidence for ref in r.get('evidence_uids', [])):
                raise ValueError(backend_message('{p0}: evidencia de retest inexistente', p0=str(f.get('id', 'Hallazgo'))))
        extra = []
        targets = [assets[x].get('target', '') for x in f.get('asset_uids', []) if x in assets]
        if targets:
            extra.append({'text_md': '**' + ('Activos afectados' if data.get('meta', {}).get('lang') == 'es' else 'Affected assets') + '**\n\n' + '\n'.join('- ' + md_text(x) for x in targets)})
        existing = {value for path, value in strings(f) if path.endswith('.src')}
        for uid in f.get('evidence_uids', []):
            e = evidence.get(uid)
            if e and e['src'] not in existing:
                extra.append({'figure': {'src': e['src'], 'caption': e.get('caption') or e.get('title', '')}})
        if extra:
            if f.get('mode') == 'machine': f.setdefault('phases', []).append({'name': 'Evidencias' if data.get('meta', {}).get('lang') == 'es' else 'Evidence', 'steps': extra})
            else: f.setdefault('walkthrough', []).extend(extra)
    return data
