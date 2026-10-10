"""Offline, bounded CSV/Burp/Nuclei/Nmap intake with preview, provenance and deduplication."""
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

MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 500
FIELDS = ('title', 'severity', 'affected', 'description_md', 'impact_md', 'remediation_md',
          'cvss_vector', 'cwe', 'references', 'external_id')
ALIASES = {'title': ('title', 'name', 'titulo', 'título'), 'severity': ('severity', 'severidad', 'risk'),
           'affected': ('affected', 'host', 'url', 'target', 'objetivo'),
           'description_md': ('description_md', 'description', 'descripción', 'descripcion'),
           'impact_md': ('impact_md', 'impact', 'impacto'),
           'remediation_md': ('remediation_md', 'remediation', 'remediación', 'solución'),
           'cvss_vector': ('cvss_vector', 'vector'), 'cwe': ('cwe',),
           'references': ('references', 'referencias'), 'external_id': ('external_id', 'id')}
SEVERITIES = {'critical': 'critical', 'crítica': 'critical', 'critica': 'critical',
              'high': 'high', 'alta': 'high', 'medium': 'medium', 'media': 'medium',
              'low': 'low', 'baja': 'low', 'information': 'info', 'informational': 'info',
              'info': 'info', 'informativa': 'info'}


def fingerprint(finding):
    fields = [str(finding.get(k, '')).strip() for k in ('title', 'affected')]
    return sha256(('\0'.join(fields)).encode()).hexdigest()


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
        raise ValueError(backend_message('XML inválido; selecciona un informe XML de issues de Burp')) from exc
    if root.tag != 'issues':
        raise ValueError(backend_message('Se esperaba un informe Burp con raíz <issues>, no un historial HTTP'))
    if len(list(root.iter())) > 30000:
        raise ValueError(backend_message('El XML contiene demasiados nodos'))
    issues = root.findall('issue')
    if len(issues) > MAX_ROWS:
        raise ValueError(backend_message('Importa como máximo 500 hallazgos por archivo'))
    rows = []
    for issue in issues:
        text = lambda key: issue.findtext(key, default='').strip()
        item = dict(title=text('name'), severity=text('severity'), affected=text('host') + text('path'),
                    description_md='\n\n'.join(filter(None, [_plain(text('issueBackground')), _plain(text('issueDetail'))])),
                    remediation_md='\n\n'.join(filter(None, [_plain(text('remediationBackground')), _plain(text('remediationDetail'))])),
                    impact_md='', external_id=text('serialNumber'), confidence=text('confidence'),
                    references=[], walkthrough=[])
        references = text('references')
        if references:
            tree = html.fragment_fromstring(references, create_parent='div')
            item['references'] = [link for link in tree.xpath('.//a/@href') if link.startswith(('https://', 'http://'))]
        for exchange in issue.findall('requestresponse'):
            for name in ('request', 'response'):
                node = exchange.find(name)
                if node is None or not node.text:
                    continue
                value = node.text
                if node.get('base64') == 'true':
                    try:
                        value = base64.b64decode(re.sub(r'\s+', '', value), validate=True).decode('utf-8', errors='backslashreplace')
                    except ValueError as exc:
                        raise ValueError(backend_message('Mensaje HTTP base64 inválido en Burp XML')) from exc
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
            raise ValueError(backend_message('Cabeceras CSV vacías, duplicadas o más de 64 columnas'))
        if mapping is None:
            mapping = {key: next((head for head in headers if head.casefold() in ALIASES[key]), '') for key in FIELDS}
        if not isinstance(mapping, dict) or set(mapping) - set(FIELDS) or any(
                not isinstance(v, str) or (v and v not in headers) for v in mapping.values()):
            raise ValueError(backend_message('Mapeo de columnas inválido'))
        chosen = [v for v in mapping.values() if v]
        if len(chosen) != len(set(chosen)):
            raise ValueError(backend_message('Cada columna solo puede asignarse a un campo'))
        rows = []
        for line in reader:
            if not line or not any(line):
                continue
            if len(line) != len(headers):
                raise ValueError(backend_message('Fila {p0}: número de columnas incoherente', p0=reader.line_num))
            values = dict(zip(headers, line))
            rows.append({field: values[column] for field, column in mapping.items() if column})
            if len(rows) > MAX_ROWS:
                raise ValueError(backend_message('Importa como máximo 500 hallazgos por archivo'))
        return headers, mapping, rows
    except (csv.Error, StopIteration) as exc:
        raise ValueError(backend_message('CSV inválido o vacío. Usa UTF-8 y columnas delimitadas por coma, punto y coma o tabulador')) from exc


def preview(body, data):
    kind, raw = body.get('format'), body.get('text')
    if not isinstance(kind, str) or kind not in ('csv', 'burp', 'nuclei', 'nmap'):
        raise ValueError(backend_message('Selecciona CSV, Burp XML, Nuclei JSONL o Nmap XML', en='Select CSV, Burp XML, Nuclei JSONL or Nmap XML'))
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
    headers, mapping, rows = (_csv(raw, body.get('mapping')) if kind == 'csv' else
                              scanner_imports.nuclei(raw) if kind == 'nuclei' else _burp(raw))
    seen = {fingerprint(f) for f in data.get('findings', [])}
    seen.update(f['import_source']['fingerprint'] for f in data.get('findings', []) if f.get('import_source'))
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
        if not f['title'].strip(): errors.append('Falta título / Missing title')
        if not f['severity']: errors.append('Severidad desconocida / Unknown severity')
        if f['cvss_vector']:
            try:
                score = cvss.score(f['cvss_vector'])
                f.update(cvss=score['score'], cvss_version=f['cvss_vector'].split('/')[0].split(':')[1])
                if score['severity'] != f['severity']: errors.append('La severidad no coincide con CVSS / Severity differs from CVSS')
            except ValueError:
                errors.append('Vector CVSS inválido / Invalid CVSS vector')
        key = fingerprint(f)
        duplicate = key in seen
        if not errors: seen.add(key)
        f['import_source'] = {'format': kind, 'file_sha256': digest, 'normalized_sha256': normalized_digest, 'hash_scope': 'original_bytes' if 'bytes_base64' in body else 'received_utf8_text', 'fingerprint': key,
                              'external_id': source.get('external_id', ''), 'confidence': source.get('confidence', ''),
                              'reviewed': False, **source.get('origin', {})}
        ensure_data_tree(f)
        result.append(dict(index=index, finding=f, duplicate=duplicate, existing_duplicate=key in project_seen, errors=errors))
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
            raise ValueError(backend_message('La selección contiene filas inválidas o duplicadas; revisa la vista previa'))
        f = row['finding']
        selected_keys.add(f['import_source']['fingerprint'])
        f.update(id=workflows.allocate_finding_id(out), uid=workflows.new_uid())
        f['import_source']['imported_at'] = now()
        out['findings'].append(f)
        count += 1
    return out, count
