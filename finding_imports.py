"""Offline, bounded scanner intake with preview, provenance and deduplication."""
from error_messages import message as backend_message
from copy import deepcopy
from hashlib import sha256
from io import StringIO
import base64
import csv
import re
from lxml import etree, html
import cvss
import workflows
import scanner_imports
from input_guard import ensure_data_tree
from project_history import now
from diagnostic_locations import DiagnosticError, diagnostic, location_scope

MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 500
FIELDS = ('title', 'severity', 'affected', 'description_md', 'impact_md', 'remediation_md',
          'cvss_vector', 'cwe', 'references', 'external_id')
ALIASES = {'title': ('title', 'name', 'titulo', 'título'), 'severity': ('severity', 'severidad', 'risk', 'severidade'),
           'affected': ('affected', 'host', 'url', 'target', 'objetivo', 'alvo'),
           'description_md': ('description_md', 'description', 'descripción', 'descripcion', 'descrição', 'descricao'),
           'impact_md': ('impact_md', 'impact', 'impacto'),
           'remediation_md': ('remediation_md', 'remediation', 'remediación', 'solución', 'remediação', 'remediacao', 'solução', 'solucao'),
           'cvss_vector': ('cvss_vector', 'vector'), 'cwe': ('cwe',),
           'references': ('references', 'referencias', 'referências'), 'external_id': ('external_id', 'id')}
SEVERITIES = {'critical': 'critical', 'crítica': 'critical', 'critica': 'critical',
              'high': 'high', 'alta': 'high', 'medium': 'medium', 'media': 'medium', 'média': 'medium',
              'low': 'low', 'baja': 'low', 'baixa': 'low', 'information': 'info', 'informational': 'info',
              'info': 'info', 'informativa': 'info'}


def fingerprint(finding):
    fields = [str(finding.get(k, '')).strip() for k in ('title', 'affected')]
    return sha256(('\0'.join(fields)).encode()).hexdigest()


def source_fingerprint(finding):
    """Scanner identity independent of editable titles and descriptions.

    SARIF keeps its own context-rich identity contract. CSV without source IDs
    retains the legacy content identity; equality alone is never reconciliation.
    """
    source = finding.get('import_source') or {}
    if source.get('source_fingerprint'):
        return source['source_fingerprint']
    kind = source.get('format')
    if kind == 'sarif':
        return source.get('fingerprint', '')
    stable = source.get('external_id', '')
    if kind == 'nuclei':
        context = [source.get('template_id', stable), source.get('matched_at', finding.get('affected', '')), source.get('matcher_name', ''), source.get('scanner_type', '')]
    elif kind == 'zap':
        context = [source.get('alert_ref', stable), finding.get('affected', ''), source.get('method', ''), source.get('parameter', '')]
    elif kind == 'nessus':
        context = [source.get('plugin_id', stable), source.get('host', ''), source.get('port', ''), source.get('protocol', '')]
    elif kind == 'burp' and source.get('issue_type'):
        context = [source['issue_type'], source.get('matched_at', finding.get('affected', ''))]
    elif kind == 'csv' and stable:
        context = [stable, finding.get('affected', '')]
    else:
        return source.get('fingerprint') or fingerprint(finding)
    return sha256(('source-v1\0' + str(kind) + '\0' + '\0'.join(str(part) for part in context)).encode()).hexdigest()


def _plain(markup):
    if not markup:
        return ''
    tree = html.fragment_fromstring(markup, create_parent='div')
    for node in tree.xpath('.//script|.//style|.//iframe'):
        node.drop_tree()
    for node in tree.xpath('.//br|.//p|.//div|.//li|.//tr'):
        node.tail = '\n' + (node.tail or '')
    return '\n'.join(workflows.md_text(line) for line in tree.text_content().strip().splitlines())


def _burp(raw):
    encoded = raw.encode('utf-8')
    # Burp's ordinary internal ELEMENT/ATTLIST DTD is allowed. Entity declarations
    # and external DTDs are never loaded or expanded, including parameter entities.
    if re.search(br'<!ENTITY\b|<!DOCTYPE[^>\[]*\b(?:SYSTEM|PUBLIC)\b', encoded, re.I):
        raise ValueError(backend_message('No se permiten entidades XML ni DTD externos'))
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(encoded, parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        line, column = getattr(exc, 'position', (None, None))
        raise DiagnosticError(backend_message('XML inválido; selecciona un informe XML de issues de Burp'),
            code='import.xml.invalid', location=dict(line=line, column=column)) from exc
    if root.tag != 'issues':
        raise ValueError(backend_message('Se esperaba un informe Burp con raíz <issues>, no un historial HTTP'))
    if len(list(root.iter())) > 30000:
        raise ValueError(backend_message('El XML contiene demasiados nodos'))
    issues = root.findall('issue')
    if len(issues) > MAX_ROWS:
        raise ValueError(backend_message('Importa como máximo 500 hallazgos por archivo'))
    rows = []
    for issue_index, issue in enumerate(issues):
        with location_scope(record=issue_index + 1, line=issue.sourceline, code='import.burp.issue'):
            text = lambda key: issue.findtext(key, default='').strip()
            item = dict(title=text('name'), severity=text('severity'), affected=text('host') + text('path'),
                        description_md='\n\n'.join(filter(None, [_plain(text('issueBackground')), _plain(text('issueDetail'))])),
                        remediation_md='\n\n'.join(filter(None, [_plain(text('remediationBackground')), _plain(text('remediationDetail'))])),
                        impact_md='', external_id=text('serialNumber'), confidence=text('confidence'),
                        references=[], walkthrough=[], origin=dict(issue_type=text('type'), matched_at=text('host') + text('path')),
                        _source_location=dict(record=issue_index + 1, line=issue.sourceline))
            references = text('references')
            if references:
                tree = html.fragment_fromstring(references, create_parent='div')
                # XPath smart strings retain XML nodes and are not safe-YAML scalars.
                item['references'] = [link for link in tree.xpath('.//a/@href', smart_strings=False)
                                      if link.startswith(('https://', 'http://'))]
            for exchange_index, exchange in enumerate(issue.findall('requestresponse')):
                for name in ('request', 'response'):
                    node = exchange.find(name)
                    if node is None or not node.text:
                        continue
                    value = node.text
                    if node.get('base64') == 'true':
                        try:
                            value = base64.b64decode(re.sub(r'\s+', '', value), validate=True).decode('utf-8', errors='backslashreplace')
                        except ValueError as exc:
                            raise DiagnosticError(backend_message('Mensaje HTTP base64 inválido en Burp XML'),
                                code='import.burp.http_base64', location=dict(record=issue_index + 1,
                                    line=node.sourceline, field=f'requestresponse[{exchange_index}].{name}')) from exc
                    # Binary control bytes remain visible as escapes; never silently discard evidence.
                    value = ''.join(c if c in '\r\n\t' or ord(c) >= 32 else f'\\x{ord(c):02x}' for c in value)
                    item['walkthrough'].append({'lead': 'HTTP ' + name, 'command': value})
            rows.append(item)
    return [], {}, rows


def _csv(raw, mapping):
    try:
        dialect = csv.Sniffer().sniff(raw[:16000], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    try:
        reader = csv.reader(StringIO(raw, newline=''), dialect, strict=True)
        headers = [x.strip() for x in next(reader)]
        if not headers or len(headers) > 64 or any(not x for x in headers) or len(set(headers)) != len(headers):
            raise DiagnosticError(backend_message('Cabeceras CSV vacías, duplicadas o más de 64 columnas'),
                                  code='import.csv.headers', location={'line': 1, 'field': 'headers'})
        if mapping is None:
            mapping = {key: next((head for head in headers if head.casefold() in ALIASES[key]), '') for key in FIELDS}
        if not isinstance(mapping, dict) or set(mapping) - set(FIELDS) or any(
                not isinstance(v, str) or (v and v not in headers) for v in mapping.values()):
            raise ValueError(backend_message('Mapeo de columnas inválido'))
        chosen = [v for v in mapping.values() if v]
        if len(chosen) != len(set(chosen)):
            raise ValueError(backend_message('Cada columna solo puede asignarse a un campo'))
        rows = []
        line_start = reader.line_num + 1
        for line in reader:
            if not line or not any(line):
                line_start = reader.line_num + 1
                continue
            if len(line) != len(headers):
                raise DiagnosticError(backend_message('Fila {p0}: número de columnas incoherente', p0=reader.line_num),
                    code='import.csv.columns', location=dict(record=len(rows) + 1, line=line_start,
                        line_end=reader.line_num))
            values = dict(zip(headers, line))
            rows.append({**{field: values[column] for field, column in mapping.items() if column},
                         '_source_location': dict(record=len(rows) + 1, line=line_start, line_end=reader.line_num)})
            line_start = reader.line_num + 1
            if len(rows) > MAX_ROWS:
                raise ValueError(backend_message('Importa como máximo 500 hallazgos por archivo'))
        return headers, mapping, rows
    except (csv.Error, StopIteration) as exc:
        raise DiagnosticError(backend_message('CSV inválido o vacío. Usa UTF-8 y columnas delimitadas por coma, punto y coma o tabulador'),
            code='import.csv.invalid', location=dict(line=max(1, reader.line_num))) from exc


def preview(body, data):
    with location_scope(operation='import', format=body.get('format'), code='import.invalid'):
        return _preview(body, data)


def _preview(body, data):
    kind, raw = body.get('format'), body.get('text')
    if not isinstance(kind, str) or kind not in ('csv', 'burp', 'nuclei', 'nmap', 'sarif', 'zap', 'nessus'):
        raise ValueError(backend_message('Selecciona CSV, Burp XML, Nuclei JSONL, Nmap XML, SARIF 2.1.0, ZAP JSON/XML o Nessus XML.',
            en='Select CSV, Burp XML, Nuclei JSONL, Nmap XML, SARIF 2.1.0, ZAP JSON/XML or Nessus XML.',
            pt='Selecione CSV, Burp XML, Nuclei JSONL, Nmap XML, SARIF 2.1.0, ZAP JSON/XML ou Nessus XML.'))
    if not isinstance(raw, str) or not raw.strip() or len(raw.encode('utf-8')) > MAX_BYTES:
        raise ValueError(backend_message('El archivo debe contener texto UTF-8 y no superar 4 MiB'))
    original=raw.encode('utf-8')
    if 'bytes_base64' in body:
        encoded=body['bytes_base64']
        if not isinstance(encoded,str) or len(encoded)>MAX_BYTES*4//3+8: raise ValueError(backend_message('Archivo inválido / Invalid file'))
        try: original=base64.b64decode(encoded,validate=True); raw=original.decode('utf-8')
        except (ValueError,UnicodeError) as exc: raise ValueError(backend_message('UTF-8 inválido / Invalid UTF-8')) from exc
        if len(original)>MAX_BYTES: raise ValueError(backend_message('Archivo demasiado grande / File too large'))
    ensure_data_tree({'text': raw})
    raw = raw.lstrip('\ufeff')
    digest = sha256(original).hexdigest()
    normalized_digest=sha256(raw.encode()).hexdigest()
    origin = dict(file_sha256=digest, normalized_sha256=normalized_digest, hash_scope='original_bytes' if 'bytes_base64' in body else 'received_utf8_text')
    if kind == 'nmap':
        return scanner_imports.nmap_preview(raw, data, origin)
    if kind == 'sarif':
        return scanner_imports.sarif_preview(raw, data, origin)
    if kind in ('nuclei', 'zap', 'nessus'):
        headers, mapping, rows = getattr(scanner_imports, kind)(raw, data.get('meta', {}).get('lang', 'es'))
    else:
        headers, mapping, rows = _csv(raw, body.get('mapping')) if kind == 'csv' else _burp(raw)
    seen = {source_fingerprint(f) for f in data.get('findings', [])}
    for f in data.get('findings', []):
        seen.update(source_fingerprint({'import_source': observation.get('source', {}), **observation.get('snapshot', {})}) for observation in f.get('import_observations', []))
    project_seen=set(seen)
    result = []
    for index, source in enumerate(rows):
        f = {k: source.get(k, '') for k in ('title', 'affected', 'description_md', 'impact_md', 'remediation_md', 'cwe', 'cvss_vector')}
        f['mode'], f['status'], f['verification'] = 'vuln', 'open', 'unverified'
        f['severity'] = SEVERITIES.get(str(source.get('severity', '')).strip().casefold(), '')
        f['walkthrough'] = source.get('walkthrough', [])
        refs = source.get('references', [])
        f['references'] = refs if isinstance(refs, list) else [x.strip() for x in refs.splitlines() if x.strip()]
        errors = []
        diagnostics = []
        source_location = dict(operation='import', format=kind,
                               **{'record': index + 1, **source.get('_source_location', {})})
        def invalid(code, field, message):
            errors.append(message)
            location = dict(source_location, field=field)
            if kind == 'nuclei':
                location['field'] = {'title': 'info.name', 'severity': 'info.severity',
                                     'cvss_vector': 'info.classification.cvss-metrics'}.get(field, field)
            if kind == 'csv' and mapping.get(field) in headers:
                location['column'] = headers.index(mapping[field]) + 1
            diagnostics.append(diagnostic(code, message, **location))
        if not f['title'].strip(): invalid('import.title.missing', 'title', backend_message('Falta título / Missing title', en='Missing title', pt='Título ausente'))
        if not f['severity']: invalid('import.severity.unknown', 'severity', backend_message('Severidad desconocida / Unknown severity', en='Unknown severity', pt='Severidade desconhecida'))
        if f['cvss_vector']:
            try:
                score = cvss.score(f['cvss_vector'])
                f.update(cvss=score['score'], cvss_version=f['cvss_vector'].split('/')[0].split(':')[1])
                if score['severity'] != f['severity']: invalid('import.cvss.severity_mismatch', 'cvss_vector', backend_message('La severidad no coincide con CVSS / Severity differs from CVSS', en='Severity differs from CVSS', pt='A severidade não corresponde ao CVSS'))
            except ValueError:
                invalid('import.cvss.invalid', 'cvss_vector', backend_message('Vector CVSS inválido / Invalid CVSS vector', en='Invalid CVSS vector', pt='Vetor CVSS inválido'))
        key = fingerprint(f)
        f['import_source'] = {'format': kind, 'file_sha256': digest, 'normalized_sha256': normalized_digest, 'hash_scope': 'original_bytes' if 'bytes_base64' in body else 'received_utf8_text', 'fingerprint': key,
                              'external_id': source.get('external_id', ''), 'confidence': source.get('confidence', ''),
                              'reviewed': False, **source.get('origin', {})}
        key = source_fingerprint(f)
        f['import_source']['fingerprint'] = key
        f['import_source']['source_fingerprint'] = key
        duplicate = key in seen
        if not errors: seen.add(key)
        ensure_data_tree(f)
        result.append(dict(index=index, finding=f, duplicate=duplicate, existing_duplicate=key in project_seen,
                           errors=errors, diagnostics=diagnostics, source_location=source_location))
    return dict(format=kind, kind='findings', sha256=digest, headers=headers, mapping=mapping, rows=result,
                counts=dict(rows=len(result), valid=sum(not r['errors'] for r in result),
                            duplicates=sum(r['duplicate'] for r in result)))


def apply(body, data):
    result = preview(body, data)
    selected = body.get('selected')
    if (not isinstance(selected, list) or not selected or any(type(i) is not int for i in selected)
            or len(set(selected)) != len(selected) or any(i < 0 or i >= len(result['rows']) for i in selected)):
        raise ValueError(backend_message('Selecciona filas válidas, sin duplicarlas'))
    if result.get('kind') == 'inventory':
        return scanner_imports.nmap_apply(result, data, selected)
    out = deepcopy(data)
    count = 0
    selected_keys=set()
    for index in selected:
        row = result['rows'][index]
        if row['errors'] or row['existing_duplicate'] or row['finding']['import_source']['fingerprint'] in selected_keys:
            message = backend_message('La selección contiene filas inválidas o duplicadas; revisa la vista previa')
            raise DiagnosticError(message, code='import.selection.invalid', location=row.get('source_location', {}),
                                  diagnostics=row.get('diagnostics') or None)
        f = row['finding']
        selected_keys.add(f['import_source']['fingerprint'])
        f.update(id=workflows.allocate_finding_id(out), uid=workflows.new_uid())
        f['import_source']['imported_at'] = now()
        out['findings'].append(f)
        count += 1
    return out, count
