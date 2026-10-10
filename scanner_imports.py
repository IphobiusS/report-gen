"""Offline scanner documents. Observations never imply a confirmed vulnerability."""
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


def nuclei(raw):
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
                walkthrough.append({'lead': 'Nuclei HTTP ' + key, 'command': value})
        extracted = _strings(item.get('extracted-results', []), 'extracted-results')
        if extracted:
            walkthrough.append({'lead': 'Nuclei: extracted results / resultados extraídos', 'command': '\n'.join(extracted)})
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
                notice='Inventario pendiente de revisión. No crea vulnerabilidades. Los scripts NSE no se importan. / '
                       'Inventory awaiting review. Creates no vulnerabilities. NSE scripts are not imported.')


def nmap_apply(result, data, selected):
    out = deepcopy(data)
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
                         target=target, kind='host', notes='Nmap: inventario pendiente de revisión / inventory awaiting review',
                         import_source=deepcopy(source))
            out['assets'].append(asset)
            assets[target] = asset
        notes = ['Nmap: observaciones importadas; validar alcance y servicios antes de marcar la prueba como realizada. / '
                 'Imported observations; review scope and services before marking the test performed.',
                 'Host: ' + item['state'], 'Addresses / Direcciones: ' + ', '.join(item['addresses'])]
        if item['hostnames']:
            notes.append('Hostnames: ' + ', '.join(item['hostnames']))
        notes.extend('Scan: ' + scan['type'] + ' ' + scan['protocol'] + ' / ' + scan['services'] for scan in item['scaninfo'])
        notes.extend(f"{s['port']}/{s['protocol']} · {s['state']} · " + ' '.join(filter(None, (s['tunnel'], s['name'], s['product'], s['version'], s['extrainfo']))) for s in item['services'])
        notes.extend('Extraports: ' + p['state'] + ' (' + p['count'] + ')' for p in item['extraports'])
        if not item['scan_complete']:
            notes.append('Escaneo sin cierre satisfactorio acreditado; cobertura parcial / Successful completion not recorded; partial coverage')
        if source['omitted_scripts']:
            notes.append(f"NSE: {source['omitted_scripts']} scripts omitidos / scripts omitted")
        out.setdefault('coverage', []).append(dict(uid=workflows.new_uid(), asset_uid=asset['uid'],
            test='Nmap: inventario de servicios / service inventory', status='pending', notes='\n'.join(notes),
            services=deepcopy(item['services']), import_source=source))
    ensure_data_tree(out)
    return out, len(selected)
