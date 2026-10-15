"""Offline scanner documents. Observations never imply a confirmed vulnerability."""
from languages import language_index
from error_messages import message as backend_message
from copy import deepcopy
from hashlib import sha256
import ipaddress
import json
import re

from lxml import etree
from input_guard import ensure_data_tree, load_json
from project_history import now
import workflows

MAX_ROWS = 500
MAX_PORTS = 10000


def _text(obj, key, default='', *, strip=True):
    value = obj.get(key, default)
    if not isinstance(value, str):
        raise ValueError(backend_message('{key}: debe ser texto / expected text', en='{key}: expected text', key=key))
    return value.strip() if strip else value


def _object(obj, key):
    value = obj.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(backend_message('{key}: debe ser un objeto / expected object', en='{key}: expected object', key=key))
    return value


def _strings(value, label):
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ValueError(backend_message('{label}: lista de textos inválida / invalid text list', en='{label}: invalid text list', label=label))
    return value


def nuclei(raw, lang='es'):
    """Accept Nuclei JSONL, including -irr HTTP messages as literal evidence."""
    rows = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        if len(rows) >= MAX_ROWS:
            raise ValueError(backend_message('Máximo 500 resultados por archivo / Maximum 500 results per file', en='Maximum 500 results per file'))
        item = load_json(line)
        if not isinstance(item, dict):
            raise ValueError(backend_message('Línea {line}: se esperaba un objeto Nuclei / expected Nuclei object', en='Line {line}: expected Nuclei object', line=line_number))
        info = _object(item, 'info')
        classification = _object(info, 'classification')
        template_id = _text(item, 'template-id')
        title = _text(info, 'name')
        affected = _text(item, 'matched-at') or _text(item, 'host')
        if not template_id or not title or not affected:
            raise ValueError(backend_message('Línea {line}: faltan template-id, info.name u objetivo / missing template-id, info.name or target', en='Line {line}: missing template-id, info.name or target', line=line_number))
        if 'matcher-status' in item and item['matcher-status'] is not True:
            raise ValueError(backend_message('Línea {line}: no es una coincidencia positiva / not a positive match', en='Line {line}: not a positive match', line=line_number))
        references = _strings(info.get('reference', []), 'reference')
        if any(not re.match(r'^https?://', ref, re.I) for ref in references):
            raise ValueError(backend_message('Referencias Nuclei: solo HTTP(S) / Nuclei references: HTTP(S) only', en='Nuclei references: HTTP(S) only'))
        walkthrough = []
        for key in ('request', 'response'):
            value = _text(item, key, strip=False)
            if value:
                walkthrough.append({'lead': 'Nuclei HTTP ' + {'request': ('solicitud', 'request', 'requisição'), 'response': ('respuesta', 'response', 'resposta')}[key][language_index(lang)], 'command': value})
        extracted = _strings(item.get('extracted-results', []), 'extracted-results')
        if extracted:
            walkthrough.append({'lead': ('Nuclei: resultados extraídos', 'Nuclei: extracted results', 'Nuclei: resultados extraídos')[language_index(lang)], 'command': '\n'.join(extracted)})
        rows.append(dict(title=title, affected=affected, severity=_text(info, 'severity'),
                         description_md=_text(info, 'description'), remediation_md=_text(info, 'remediation'),
                         impact_md='', cvss_vector=_text(classification, 'cvss-metrics'),
                         cwe=', '.join(_strings(classification.get('cwe-id', []), 'cwe-id')),
                         external_id=template_id, confidence='scanner match; technical review required',
                         references=references, walkthrough=walkthrough,
                         origin={'template_id': template_id, 'matcher_name': _text(item, 'matcher-name'),
                                 'scanner_type': _text(item, 'type'), 'matched_at': affected,
                                 'observed_at': _text(item, 'timestamp'), 'source_line': line_number,
                                 'record_sha256': sha256(line.encode()).hexdigest()}))
    if not rows:
        raise ValueError(backend_message('JSONL sin resultados / JSONL contains no results', en='JSONL contains no results'))
    return [], {}, rows


def _xml(raw):
    encoded = raw.encode('utf-8')
    if re.search(br'<!ENTITY\b|<!DOCTYPE[^>\[]*\b(?:SYSTEM|PUBLIC)\b', encoded, re.I):
        raise ValueError(backend_message('No se permiten entidades XML ni DTD externos / XML entities and external DTDs are forbidden', en='XML entities and external DTDs are forbidden'))
    declaration = re.match(br'\s*<\?xml\b[^?]*\bencoding\s*=\s*[\'"]([^\'"]+)', encoded, re.I)
    if declaration and declaration[1].lower() not in (b'utf-8', b'utf8', b'us-ascii', b'ascii'):
        raise ValueError(backend_message('El XML debe declarar UTF-8 / XML must declare UTF-8', en='XML must declare UTF-8'))
    try:
        root = etree.fromstring(encoded, etree.XMLParser(resolve_entities=False, load_dtd=False,
                                                       no_network=True, huge_tree=False))
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ValueError(backend_message('XML de Nmap inválido / Invalid Nmap XML', en='Invalid Nmap XML')) from exc
    if root.tag != 'nmaprun' or root.get('scanner', 'nmap') != 'nmap':
        raise ValueError(backend_message('Se esperaba <nmaprun> / Expected <nmaprun>', en='Expected <nmaprun>'))
    if sum(1 for _ in root.iter()) > 30000:
        raise ValueError(backend_message('El XML contiene demasiados nodos / Too many XML nodes', en='Too many XML nodes'))
    return root


def _target(value):
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return value.strip().casefold()


def nmap_preview(raw, data, origin):
    root = _xml(raw)
    hosts = root.findall('host')
    if len(hosts) > MAX_ROWS:
        raise ValueError(backend_message('Máximo 500 hosts por archivo / Maximum 500 hosts per file', en='Maximum 500 hosts per file'))
    port_count = 0
    project_seen = {c['import_source']['fingerprint'] for c in data.get('coverage', [])
                    if isinstance(c.get('import_source'), dict) and c['import_source'].get('format') == 'nmap'}
    seen = set(project_seen)
    assets = {_target(a.get('target', '')): a for a in data.get('assets', [])}
    finished = root.find('runstats/finished')
    scan_complete = finished is not None and finished.get('exit') == 'success'
    scaninfo = [{key: scan.get(key, '') for key in ('type', 'protocol', 'numservices', 'services')}
                for scan in root.findall('scaninfo')]
    rows = []
    for index, host in enumerate(hosts):
        addresses = [a.get('addr', '') for a in host.findall('address') if a.get('addrtype') in ('ipv4', 'ipv6')]
        if not addresses:
            raise ValueError(backend_message('Host {index}: dirección IP ausente / missing IP address', en='Host {index}: missing IP address', index=index + 1))
        try:
            addresses = [str(ipaddress.ip_address(a)) for a in addresses]
        except ValueError as exc:
            raise ValueError(backend_message('Host {index}: dirección IP inválida / invalid IP address', en='Host {index}: invalid IP address', index=index + 1)) from exc
        target = addresses[0]
        hostnames = list(dict.fromkeys(n.get('name', '') for n in host.findall('hostnames/hostname') if n.get('name')))
        state_node = host.find('status')
        host_state = state_node.get('state', 'unknown') if state_node is not None else 'unknown'
        services = []
        for port in host.findall('ports/port'):
            port_count += 1
            if port_count > MAX_PORTS:
                raise ValueError(backend_message('Máximo 10000 puertos por archivo / Maximum 10000 ports per file', en='Maximum 10000 ports per file'))
            number, protocol = port.get('portid', ''), port.get('protocol', '')
            if not re.fullmatch(r'[0-9]{1,5}', number) or not 0 <= int(number) <= 65535 or protocol not in ('tcp', 'udp', 'sctp', 'ip'):
                raise ValueError(backend_message('Puerto o protocolo Nmap inválido / Invalid Nmap port or protocol', en='Invalid Nmap port or protocol'))
            if protocol == 'ip' and int(number) > 255:
                raise ValueError(backend_message('Número de protocolo IP inválido / Invalid IP protocol number', en='Invalid IP protocol number'))
            state = port.find('state')
            if state is None or not state.get('state'):
                raise ValueError(backend_message('Puerto sin estado / Port without state', en='Port without state'))
            service = port.find('service')
            values = {key: service.get(key, '') if service is not None else ''
                      for key in ('name', 'product', 'version', 'extrainfo', 'tunnel', 'method', 'conf')}
            services.append(dict(port=int(number), protocol=protocol, state=state.get('state'), **values))
        if len({(s['protocol'], s['port']) for s in services}) != len(services):
            raise ValueError(backend_message('Puerto duplicado en un host / Duplicate port within a host', en='Duplicate port within a host'))
        services.sort(key=lambda s: (s['protocol'], s['port']))
        extra = [{'state': p.get('state', ''), 'count': p.get('count', '')} for p in host.findall('ports/extraports')]
        observation = dict(target=target, addresses=addresses, hostnames=hostnames, state=host_state,
                           services=services, extraports=extra, scan_complete=scan_complete, scaninfo=scaninfo)
        key = sha256(json.dumps(observation, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        source = dict(origin, format='nmap', fingerprint=key, external_id=target, confidence='scanner observation',
                      reviewed=False, scanner_version=root.get('version', ''), observed_at=root.get('startstr', ''),
                      scan_complete=scan_complete, omitted_scripts=len(host.findall('.//script')))
        observation['import_source'] = source
        duplicate = key in seen
        seen.add(key)
        rows.append(dict(index=index, kind='inventory', inventory=observation, duplicate=duplicate,
                         existing_duplicate=key in project_seen, existing_asset=target in assets, errors=[]))
    if not rows:
        raise ValueError(backend_message('XML sin hosts importables / XML contains no importable hosts', en='XML contains no importable hosts'))
    return dict(format='nmap', kind='inventory', sha256=origin['file_sha256'], headers=[], mapping={}, rows=rows,
                counts=dict(rows=len(rows), services=sum(len(r['inventory']['services']) for r in rows),
                            duplicates=sum(r['duplicate'] for r in rows), valid=len(rows)),
                notice=backend_message('Inventario pendiente de revisión. No crea vulnerabilidades. Los scripts NSE no se importan.', en='Inventory awaiting review. Creates no vulnerabilities. NSE scripts are not imported.', pt='Inventário aguardando revisão. Não cria vulnerabilidades. Os scripts NSE não são importados.'))


def nmap_apply(result, data, selected):
    out = deepcopy(data)
    lang = data.get('meta', {}).get('lang', 'es')
    assets = {_target(a.get('target', '')): a for a in out.setdefault('assets', [])}
    selected_keys = set()
    for index in selected:
        row = result['rows'][index]
        item = row['inventory']
        source = deepcopy(item['import_source'])
        key = source['fingerprint']
        if row['existing_duplicate'] or key in selected_keys:
            raise ValueError(backend_message('La selección contiene observaciones duplicadas / Selection contains duplicate observations', en='Selection contains duplicate observations'))
        selected_keys.add(key)
        source['imported_at'] = now()
        target = item['target']
        asset = assets.get(target)
        if asset is None:
            asset = dict(uid=workflows.new_uid(), name=item['hostnames'][0] if item['hostnames'] else target,
                         target=target, kind='host', notes=('Nmap: inventario pendiente de revisión / inventory awaiting review', 'Nmap: inventory awaiting review', 'Nmap: inventário aguardando revisão')[language_index(lang)],
                         import_source=deepcopy(source))
            out['assets'].append(asset)
            assets[target] = asset
        notes = [('Nmap: observaciones importadas; validar alcance y servicios antes de marcar la prueba como realizada.', 'Nmap: imported observations; review scope and services before marking the test performed.', 'Nmap: observações importadas; revise o escopo e os serviços antes de marcar o teste como realizado.')[language_index(lang)],
                 'Host: ' + item['state'], ('Direcciones: ', 'Addresses: ', 'Endereços: ')[language_index(lang)] + ', '.join(item['addresses'])]
        if item['hostnames']:
            notes.append(('Nombres de host: ', 'Hostnames: ', 'Nomes de host: ')[language_index(lang)] + ', '.join(item['hostnames']))
        notes.extend(('Escaneo: ', 'Scan: ', 'Varredura: ')[language_index(lang)] + scan['type'] + ' ' + scan['protocol'] + ' / ' + scan['services'] for scan in item['scaninfo'])
        notes.extend(f"{s['port']}/{s['protocol']} · {s['state']} · " + ' '.join(filter(None, (s['tunnel'], s['name'], s['product'], s['version'], s['extrainfo']))) for s in item['services'])
        notes.extend(('Puertos adicionales: ', 'Extraports: ', 'Portas adicionais: ')[language_index(lang)] + p['state'] + ' (' + p['count'] + ')' for p in item['extraports'])
        if not item['scan_complete']:
            notes.append(('Escaneo sin cierre satisfactorio acreditado; cobertura parcial / Successful completion not recorded; partial coverage', 'Successful completion not recorded; partial coverage', 'Conclusão satisfatória da varredura não registrada; cobertura parcial')[language_index(lang)])
        if source['omitted_scripts']:
            notes.append(backend_message('NSE: {count} scripts omitidos', en='NSE: {count} scripts omitted', pt='NSE: {count} scripts omitidos', language=lang, count=source['omitted_scripts']))
        out.setdefault('coverage', []).append(dict(uid=workflows.new_uid(), asset_uid=asset['uid'],
            test=('Nmap: inventario de servicios / service inventory', 'Nmap: service inventory', 'Nmap: inventário de serviços')[language_index(lang)], status='pending', notes='\n'.join(notes),
            services=deepcopy(item['services']), import_source=source))
    ensure_data_tree(out)
    return out, len(selected)

# SARIF is a bounded, offline intake subset of OASIS SARIF 2.1.0. It does not
# interpret scanner levels as report risk or fetch artifacts/property files.
MAX_SARIF_RUNS = 50
MAX_SARIF_REFERENCES = 10000
MAX_SARIF_LOCATIONS = 100
MAX_SARIF_TEXT = 16384
MAX_SARIF_RECORD_BYTES = 65536
MAX_SARIF_OUTPUT_BYTES = 12 * 1024 * 1024


def _sarif_invalid(field):
    return ValueError(backend_message('SARIF: valor inválido o incoherente en {field}.',
        en='SARIF: invalid or conflicting value at {field}.',
        pt='SARIF: valor inválido ou conflitante em {field}.', field=field))


def _sarif_limit(field, limit):
    return ValueError(backend_message('SARIF: {field} supera el límite de {limit}.',
        en='SARIF: {field} exceeds the limit of {limit}.',
        pt='SARIF: {field} excede o limite de {limit}.', field=field, limit=limit))


def _sarif_object(value, field):
    if not isinstance(value, dict):
        raise _sarif_invalid(field)
    return value


def _sarif_list(value, field, limit):
    if not isinstance(value, list):
        raise _sarif_invalid(field)
    if len(value) > limit:
        raise _sarif_limit(field, limit)
    return value


def _sarif_text(value, field, *, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise _sarif_invalid(field)
    if len(value.encode('utf-8')) > MAX_SARIF_TEXT:
        raise _sarif_limit(field, MAX_SARIF_TEXT)
    return value


def _sarif_index(value, size, field):
    if type(value) is not int or not 0 <= value < size:
        raise _sarif_invalid(field)
    return value


def _sarif_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _sarif_message(message, rule, driver):
    message = _sarif_object(message, 'message')
    for key in ('text', 'markdown', 'id'):
        if key in message:
            _sarif_text(message[key], 'message.' + key)
    template = message
    if not message.get('text') and not message.get('markdown') and message.get('id'):
        strings = _sarif_object(rule.get('messageStrings', {}), 'rule.messageStrings')
        globals_ = _sarif_object(driver.get('globalMessageStrings', {}), 'driver.globalMessageStrings')
        template = _sarif_object(strings.get(message['id'], globals_.get(message['id'])), 'message.id')
    selected = 'text' if template.get('text') else 'markdown'
    value = _sarif_text(template.get(selected), 'message.' + selected, required=True)
    arguments = _sarif_list(message.get('arguments', []), 'message.arguments', 100)
    for argument in arguments:
        _sarif_text(argument, 'message.arguments')
    # Expand incrementally: a small template with repeated large arguments must
    # hit the budget before allocating the full expansion. Literal braces are
    # decoded even without arguments (OASIS SARIF 2.1.0, section 3.11.5).
    pieces, expanded_bytes, cursor = [], 0, 0
    def append(piece):
        nonlocal expanded_bytes
        expanded_bytes += len(piece.encode('utf-8'))
        if expanded_bytes > MAX_SARIF_TEXT:
            raise _sarif_limit('message.expanded', MAX_SARIF_TEXT)
        pieces.append(piece)
    for match in re.finditer(r'\{\{|\}\}|\{[0-9]+\}', value):
        literal = value[cursor:match.start()]
        if '{' in literal or '}' in literal:
            raise _sarif_invalid('message.braces')
        append(literal)
        token = match.group()
        if token in ('{{', '}}'):
            append(token[0])
        else:
            if len(token) > 8 or int(token[1:-1]) >= len(arguments):
                raise _sarif_invalid('message.arguments')
            append(arguments[int(token[1:-1])])
        cursor = match.end()
    if '{' in value[cursor:] or '}' in value[cursor:]:
        raise _sarif_invalid('message.braces')
    append(value[cursor:])
    return ''.join(pieces), selected


def _sarif_rule(result, driver):
    reference = _sarif_object(result.get('rule', {}), 'result.rule')
    # Extensions need their own component/rule namespaces. Reject rather than
    # accidentally resolve their indexes against the driver's rules.
    if 'toolComponent' in reference:
        raise ValueError(backend_message('SARIF: importa reglas del driver; las extensiones toolComponent no son compatibles.',
            en='SARIF: import driver rules; toolComponent extensions are not supported.',
            pt='SARIF: importe regras do driver; extensões toolComponent não são compatíveis.'))
    rules = _sarif_list(driver.get('rules', []), 'driver.rules', MAX_SARIF_REFERENCES)
    identifiers, guids = {}, {}
    for index, candidate in enumerate(rules):
        candidate = _sarif_object(candidate, 'driver.rules')
        identifier = _sarif_text(candidate.get('id'), 'rule.id', required=True)
        identifiers.setdefault(identifier, []).append(index)
        if 'guid' in candidate:
            guid = _sarif_text(candidate['guid'], 'rule.guid', required=True).lower()
            if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', guid):
                raise _sarif_invalid('rule.guid')
            guids.setdefault(guid, []).append(index)
    ids = [result[key] for key in ('ruleId',) if key in result]
    if 'id' in reference:
        ids.append(reference['id'])
    for identifier in ids:
        _sarif_text(identifier, 'ruleId', required=True)
    if len(set(ids)) > 1:
        raise _sarif_invalid('ruleId / rule.id')
    indexes = [result['ruleIndex']] if 'ruleIndex' in result else []
    if 'index' in reference:
        indexes.append(reference['index'])
    for index in indexes:
        if type(index) is not int or index < -1 or index >= len(rules):
            raise _sarif_invalid('ruleIndex')
    if len(set(indexes)) > 1:
        raise _sarif_invalid('ruleIndex / rule.index')
    identifier = ids[0] if ids else ''
    index = indexes[0] if indexes and indexes[0] != -1 else None
    if 'guid' in reference:
        guid = _sarif_text(reference['guid'], 'rule.guid', required=True).lower()
        matches = guids.get(guid, [])
        if len(matches) != 1 or (index is not None and index != matches[0]):
            raise _sarif_invalid('rule.guid / ruleIndex')
        index = matches[0]
    if index is None and identifier:
        matches = identifiers.get(identifier, [])
        if not matches:
            prefixes = [key for key in identifiers if identifier.startswith(key + '/')]
            matches = identifiers[max(prefixes, key=len)] if prefixes else []
        if len(matches) > 1:
            raise _sarif_invalid('ruleId (ambiguous)')
        index = matches[0] if matches else None
    rule = rules[index] if index is not None else {}
    if rule and identifier and identifier != rule['id'] and not identifier.startswith(rule['id'] + '/'):
        raise _sarif_invalid('ruleId / ruleIndex')
    identifier = identifier or rule.get('id', '')
    if not identifier or (reference and not rule):
        raise _sarif_invalid('ruleId')
    # OASIS allows duplicate descriptor IDs when index/GUID disambiguates.
    # Preserve that distinction without making dedup depend on array order.
    descriptor_identity = rule.get('guid', '').lower()
    if not descriptor_identity and rule and len(identifiers[rule['id']]) > 1:
        descriptor_identity = sha256(_sarif_json(rule)).hexdigest()
    return identifier, rule, index, descriptor_identity


def _sarif_locations(result, run):
    """Resolve documentary URIs only; no filesystem or network operation."""
    from urllib.parse import urljoin, urlsplit
    artifacts = _sarif_list(run.get('artifacts', []), 'artifacts', MAX_SARIF_REFERENCES)
    bases = _sarif_object(run.get('originalUriBaseIds', {}), 'originalUriBaseIds')
    if len(bases) > MAX_SARIF_REFERENCES:
        raise _sarif_limit('originalUriBaseIds', MAX_SARIF_REFERENCES)

    def resolve(location, trail=(), base=False):
        location = _sarif_object(location, 'artifactLocation')
        if len(trail) > 32:
            raise _sarif_limit('artifactLocation.depth', 32)
        uri = _sarif_text(location.get('uri', ''), 'artifactLocation.uri')
        base_id = _sarif_text(location.get('uriBaseId', ''), 'artifactLocation.uriBaseId')
        if 'index' in location and (type(location['index']) is not int or location['index'] < -1):
            raise _sarif_invalid('artifactLocation.index')
        if not uri and ('index' not in location or location['index'] == -1) and not base:
            raise _sarif_invalid('artifactLocation.uri / index')
        try:
            parts = urlsplit(uri)
            absolute = bool(parts.scheme)
        except ValueError as exc:
            raise _sarif_invalid('artifactLocation.uri') from exc
        if re.search(r'[\s\\]', uri) or (absolute and base_id):
            raise _sarif_invalid('artifactLocation.uri / uriBaseId')
        if base and uri and (not uri.endswith('/') or parts.query or parts.fragment or (not absolute and not base_id)):
            raise _sarif_invalid('originalUriBaseIds.uri')
        resolved, unresolved = uri, ''
        if base_id:
            token = ('base', base_id)
            if token in trail:
                raise _sarif_invalid('originalUriBaseIds cycle')
            if base_id in bases:
                prefix, unresolved = resolve(bases[base_id], trail + (token,), base=True)
                if prefix and not prefix.endswith('/'):
                    raise _sarif_invalid('originalUriBaseIds.uri')
                resolved = urljoin(prefix, uri) if prefix else uri
                unresolved = unresolved or (base_id if not prefix else '')
            else:
                unresolved = base_id
        if 'index' in location and location['index'] != -1:
            index = _sarif_index(location['index'], len(artifacts), 'artifactLocation.index')
            token = ('artifact', index)
            if token in trail:
                raise _sarif_invalid('artifactLocation.index cycle')
            artifact = _sarif_object(artifacts[index], 'artifacts[index]')
            if 'parentIndex' in artifact and (type(artifact['parentIndex']) is not int or artifact['parentIndex'] != -1):
                raise ValueError(backend_message('SARIF: los artefactos anidados con parentIndex no son compatibles; exporta ubicaciones de archivos de origen.',
                    en='SARIF: nested artifacts with parentIndex are not supported; export source-file locations.',
                    pt='SARIF: artefatos aninhados com parentIndex não são compatíveis; exporte localizações de arquivos de origem.'))
            target = resolve(artifact.get('location'), trail + (token,))
            if uri and (resolved, unresolved) != target:
                raise _sarif_invalid('artifactLocation.uri / index')
            resolved, unresolved = target
        _sarif_text(resolved, 'artifactLocation.resolvedUri')
        return resolved, unresolved

    locations = []
    for location in _sarif_list(result.get('locations', []), 'locations', MAX_SARIF_LOCATIONS):
        location = _sarif_object(location, 'location')
        physical = _sarif_object(location.get('physicalLocation', {}), 'physicalLocation')
        logical = _sarif_list(location.get('logicalLocations', []), 'logicalLocations', MAX_SARIF_LOCATIONS)
        entry = {'original': deepcopy(location)}
        if physical:
            if 'artifactLocation' not in physical:
                raise _sarif_invalid('physicalLocation.artifactLocation')
            uri, unresolved = resolve(physical['artifactLocation'])
            entry.update(uri=uri, unresolved_base_id=unresolved)
            region = _sarif_object(physical.get('region', {}), 'region')
            for key in ('startLine', 'startColumn', 'endLine', 'endColumn', 'charOffset', 'charLength', 'byteOffset', 'byteLength'):
                if key in region and (type(region[key]) is not int or region[key] < (1 if key.endswith(('Line', 'Column')) else 0)):
                    raise _sarif_invalid('region.' + key)
            if 'endLine' in region and region['endLine'] < region.get('startLine', 1):
                raise _sarif_invalid('region.endLine')
            if ('endColumn' in region and region.get('endLine', region.get('startLine')) == region.get('startLine')
                    and region['endColumn'] < region.get('startColumn', 1)):
                raise _sarif_invalid('region.endColumn')
            entry['region'] = {key: region[key] for key in ('startLine', 'startColumn', 'endLine', 'endColumn', 'charOffset', 'charLength', 'byteOffset', 'byteLength') if key in region}
        for item in logical:
            item = _sarif_object(item, 'logicalLocation')
            if 'index' in item:
                raise ValueError(backend_message('SARIF: usa nombres lógicos explícitos; las referencias logicalLocation.index no son compatibles.',
                    en='SARIF: use explicit logical names; logicalLocation.index references are not supported.',
                    pt='SARIF: use nomes lógicos explícitos; referências logicalLocation.index não são compatíveis.'))
            for key in ('fullyQualifiedName', 'name', 'decoratedName', 'kind'):
                if key in item:
                    _sarif_text(item[key], 'logicalLocation.' + key)
            if not (item.get('fullyQualifiedName') or item.get('name') or item.get('decoratedName')):
                raise _sarif_invalid('logicalLocation.name')
        if not physical and not logical:
            raise _sarif_invalid('location')
        entry['logical_locations'] = deepcopy(logical)
        locations.append(entry)
    return locations


def _sarif_repositories(run):
    artifacts = _sarif_list(run.get('artifacts', []), 'artifacts', MAX_SARIF_REFERENCES)
    repositories = []
    for item in _sarif_list(run.get('versionControlProvenance', []), 'versionControlProvenance', 100):
        item = _sarif_object(item, 'versionControlProvenance')
        repository = {key: _sarif_text(item[key], 'versionControlProvenance.' + key)
                      for key in ('repositoryUri', 'revisionId', 'branch', 'revisionTag', 'asOfTimeUtc') if key in item}
        _sarif_text(repository.get('repositoryUri'), 'versionControlProvenance.repositoryUri', required=True)
        if 'mappedTo' in item:
            mapping = _sarif_object(item['mappedTo'], 'versionControlProvenance.mappedTo')
            for key in ('uri', 'uriBaseId'):
                if key in mapping:
                    _sarif_text(mapping[key], 'versionControlProvenance.mappedTo.' + key)
            if 'index' in mapping:
                _sarif_index(mapping['index'], len(artifacts), 'versionControlProvenance.mappedTo.index')
            repository['mappedTo'] = deepcopy(mapping)
        repositories.append(repository)
    return repositories


def sarif_preview(raw, data, origin):
    """Keep scanner observations unverified, with exclusions visible in preview.

    This intentionally accepts self-contained driver results, not arbitrary
    SARIF interchange: external property fragments and extension rule references
    are rejected explicitly. Other unsupported evidence (code flows, fixes,
    attachments) is counted in provenance but never executed or applied.
    """
    if len(raw.encode('utf-8')) > 4 * 1024 * 1024:
        raise _sarif_limit('bytes', 4 * 1024 * 1024)
    document = _sarif_object(load_json(raw), 'document')
    if document.get('version') != '2.1.0':
        raise _sarif_invalid('version (2.1.0)')
    runs = _sarif_list(document.get('runs'), 'runs', MAX_SARIF_RUNS)
    if 'inlineExternalProperties' in document and document['inlineExternalProperties'] != []:
        raise ValueError(backend_message('SARIF: se requiere un archivo autocontenido, sin propiedades externas.',
            en='SARIF: a self-contained file without external properties is required.',
            pt='SARIF: é necessário um arquivo autocontido, sem propriedades externas.'))
    total = 0
    for run in runs:
        run = _sarif_object(run, 'run')
        results = _sarif_list(run.get('results', []), 'results', MAX_ROWS)
        total += len(results)
        if total > MAX_ROWS:
            raise _sarif_limit('results', MAX_ROWS)
        if 'externalPropertyFileReferences' in run and run['externalPropertyFileReferences'] != {}:
            raise ValueError(backend_message('SARIF: se requiere un archivo autocontenido, sin propiedades externas.',
                en='SARIF: a self-contained file without external properties is required.',
                pt='SARIF: é necessário um arquivo autocontido, sem propriedades externas.'))
    project_seen = {finding['import_source']['fingerprint'] for finding in data.get('findings', [])
                    if isinstance(finding.get('import_source'), dict) and finding['import_source'].get('format') == 'sarif'}
    seen = set(project_seen)
    rows, output_bytes = [], 0
    for run_index, run in enumerate(runs):
        driver = _sarif_object(_sarif_object(run.get('tool'), 'tool').get('driver'), 'tool.driver')
        tool = {key: _sarif_text(driver[key], 'tool.driver.' + key) for key in
                ('name', 'version', 'semanticVersion', 'guid', 'informationUri') if key in driver}
        _sarif_text(tool.get('name'), 'tool.driver.name', required=True)
        repositories = _sarif_repositories(run)
        for result_index, result in enumerate(run.get('results', [])):
            result = _sarif_object(result, 'result')
            encoded = _sarif_json(result)
            if len(encoded) > MAX_SARIF_RECORD_BYTES:
                raise _sarif_limit('result.bytes', MAX_SARIF_RECORD_BYTES)
            rule_id, rule, rule_index, descriptor_identity = _sarif_rule(result, driver)
            message, message_format = _sarif_message(result.get('message'), rule, driver)
            locations = _sarif_locations(result, run)
            kind = result.get('kind', 'fail')
            if kind not in ('notApplicable', 'pass', 'fail', 'review', 'open', 'informational'):
                raise _sarif_invalid('result.kind')
            config = _sarif_object(rule.get('defaultConfiguration', {}), 'defaultConfiguration')
            if 'enabled' in config and type(config['enabled']) is not bool:
                raise _sarif_invalid('defaultConfiguration.enabled')
            level = result.get('level', 'none' if kind != 'fail' else config.get('level', 'warning'))
            if level not in ('none', 'note', 'warning', 'error') or (kind != 'fail' and level != 'none'):
                raise _sarif_invalid('result.level')
            # Invocation-level overrides change the meaning of omitted levels.
            # Require producers to materialize those values, rather than guess.
            if 'level' not in result and any(inv.get('ruleConfigurationOverrides') for inv in
                    _sarif_list(run.get('invocations', []), 'invocations', MAX_SARIF_REFERENCES)
                    if isinstance(inv, dict)):
                raise ValueError(backend_message('SARIF: los resultados con ruleConfigurationOverrides deben declarar level.',
                    en='SARIF: results with ruleConfigurationOverrides must declare level.',
                    pt='SARIF: resultados com ruleConfigurationOverrides devem declarar level.'))
            baseline = result.get('baselineState', '')
            if baseline not in ('', 'new', 'unchanged', 'updated', 'absent'):
                raise _sarif_invalid('baselineState')
            suppressions = result.get('suppressions')
            if suppressions is None:
                suppressions = []
            suppressions = _sarif_list(suppressions, 'suppressions', MAX_SARIF_LOCATIONS)
            for suppression in suppressions:
                suppression = _sarif_object(suppression, 'suppression')
                if suppression.get('kind') not in ('inSource', 'external') or suppression.get('status', '') not in ('', 'accepted', 'underReview', 'rejected'):
                    raise _sarif_invalid('suppression.kind / status')
            excluded = baseline == 'absent' or kind != 'fail' or level == 'none' or config.get('enabled') is False or any(s.get('status') != 'rejected' for s in suppressions)
            fingerprints = {}
            for field in ('fingerprints', 'partialFingerprints'):
                values = _sarif_object(result.get(field, {}), field)
                if len(values) > 100:
                    raise _sarif_limit(field, 100)
                fingerprints[field] = {key: _sarif_text(value, field) for key, value in values.items()}
            affected = []
            for location in locations:
                if 'uri' in location:
                    label = (location['unresolved_base_id'] + ': ' if location['unresolved_base_id'] else '') + location['uri']
                    region = location['region']
                    if 'startLine' in region:
                        label += ':' + str(region['startLine'])
                        if 'startColumn' in region:
                            label += ':' + str(region['startColumn'])
                    affected.append(label)
                else:
                    affected.extend(item.get('fullyQualifiedName') or item.get('name') or item.get('decoratedName') for item in location['logical_locations'])
            title = tool['name'] + ' · ' + rule_id
            if 'shortDescription' in rule:
                short, _ = _sarif_message(rule['shortDescription'], {}, driver)
                title += ' · ' + short
            # Identity includes exact context, not just a tool-supplied hash:
            # colliding fingerprints cannot collapse different observations.
            identity = {'tool': {key: tool[key] for key in ('name', 'guid') if key in tool},
                        'rule_id': rule_id, 'rule_descriptor_identity': descriptor_identity, 'message': message,
                        'repositories': sorted([{key: value for key, value in item.items() if key in ('repositoryUri', 'mappedTo')}
                                                for item in repositories], key=lambda value: _sarif_json(value)),
                        'locations': [{key: value for key, value in location.items() if key != 'original'} for location in locations],
                        **fingerprints}
            key = sha256(_sarif_json(identity)).hexdigest()
            source = dict(origin, format='sarif', fingerprint=key, reviewed=False,
                          external_id=rule_id, confidence='scanner observation; technical review required',
                          tool=tool, run_index=run_index, result_index=result_index,
                          version_control_provenance=repositories,
                          rule_id=rule_id, rule_index=rule_index, rule_name=_sarif_text(rule.get('name', ''), 'rule.name'),
                          rule_descriptor_identity=descriptor_identity,
                          rule_reference=deepcopy(result.get('rule', {})),
                          level=level, level_explicit='level' in result, result_kind=kind, baseline_state=baseline,
                          message=deepcopy(result['message']), message_text=message, message_format=message_format,
                          locations=locations, suppressions=deepcopy(suppressions),
                          record_sha256=sha256(encoded).hexdigest(), record_hash_scope='canonical_result_json',
                          omitted_fields=sorted(set(result) - {'ruleId', 'ruleIndex', 'rule', 'message', 'locations', 'level', 'kind', 'baselineState', 'suppressions', 'fingerprints', 'partialFingerprints'}),
                          **fingerprints)
            finding = dict(title=title, affected='\n'.join(affected),
                description_md='\n'.join(workflows.md_text(line) for line in message.splitlines()),
                impact_md='', remediation_md='', cwe='', cvss_vector='', references=[], walkthrough=[],
                mode='vuln', status='open', verification='unverified', severity='info', import_source=source)
            errors = [backend_message('SARIF: resultado excluido por supresión pendiente/aceptada, baseline ausente o estado no activo.',
                en='SARIF: result excluded because of pending/accepted suppression, absent baseline or inactive state.',
                pt='SARIF: resultado excluído por supressão pendente/aceita, baseline ausente ou estado inativo.')] if excluded else []
            row = dict(index=len(rows), finding=finding, duplicate=key in seen,
                       existing_duplicate=key in project_seen, errors=errors, excluded=excluded)
            if not excluded:
                seen.add(key)
            output_bytes += len(_sarif_json(row))
            if output_bytes > MAX_SARIF_OUTPUT_BYTES:
                raise _sarif_limit('preview.bytes', MAX_SARIF_OUTPUT_BYTES)
            rows.append(row)
    if not rows:
        raise ValueError(backend_message('SARIF sin resultados para previsualizar.',
            en='SARIF contains no results to preview.', pt='SARIF sem resultados para pré-visualizar.'))
    response = dict(format='sarif', kind='findings', sha256=origin['file_sha256'], headers=[], mapping={}, rows=rows,
        counts=dict(rows=len(rows), valid=sum(not row['errors'] for row in rows),
                    duplicates=sum(row['duplicate'] for row in rows), excluded=sum(row['excluded'] for row in rows)),
        notice=backend_message('Observaciones SARIF informativas, sin confirmar y pendientes de revisión humana. No se calcula CVSS. Se excluyen los resultados suprimidos, ausentes o inactivos. Las rutas son texto; no se abren archivos ni enlaces.',
            en='Informational SARIF observations, unverified and awaiting human review. No CVSS is calculated. Suppressed, absent or inactive results are excluded. Paths are text; no files or links are opened.',
            pt='Observações SARIF informativas, não verificadas e aguardando revisão humana. O CVSS não é calculado. Resultados suprimidos, ausentes ou inativos são excluídos. Os caminhos são texto; nenhum arquivo ou link é aberto.'))
    ensure_data_tree(response)
    return response
