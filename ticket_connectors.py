"""Explicit HTTPS ticket exchange. Credentials are transient, technical status is local.

Jira Cloud REST v3 and DefectDojo REST v2 are deliberately small adapters:
link an existing ticket, review selected outgoing fields, and reconcile incoming
owner/date/progress. Neither an external closure nor a scanner result is a retest.
"""
from base64 import b64encode
from copy import deepcopy
from datetime import date
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urlsplit

from error_messages import current_language, message
from languages import language_index
from input_guard import load_json
from workflows import UID, new_uid

PROVIDERS = {'jira', 'defectdojo'}
LOCAL_FIELDS = {'owner', 'due_date', 'reported_remediation'}
PUSH_FIELDS = {'title', 'description_md', 'remediation_md', 'due_date'}
MAX_BYTES = 1024 * 1024


def fail(es, en, pt):
    # These are complete authored messages, not format templates.
    raise ValueError((es, en, pt)[language_index(current_language())])


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(',', ':')).encode()).hexdigest()


def base_url(value):
    if not isinstance(value, str) or len(value) > 500:
        fail('Servidor inválido', 'Invalid server', 'Servidor inválido')
    url = urlsplit(value)
    try:
        port = url.port
    except ValueError:
        port = -1
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or port not in (None, 443)
            or url.path not in ('', '/') or re.search(r'[\s\\\x00-\x1f]', value)):
        fail('Usa el origen HTTPS del servidor, sin ruta ni credenciales',
             'Use the HTTPS server origin without a path or credentials',
             'Use a origem HTTPS do servidor, sem caminho ou credenciais')
    host = url.hostname.encode('idna').decode('ascii').lower()
    if '%' in host:
        fail('Servidor HTTPS público requerido', 'A public HTTPS server is required',
             'É necessário um servidor HTTPS público')
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise ValueError
    except ValueError:
        if ':' in host or '.' not in host or host.endswith(('.localhost', '.local', '.internal')):
            fail('Servidor HTTPS público requerido', 'A public HTTPS server is required',
                 'É necessário um servidor HTTPS público')
        # Numeric private IPs must not fall through as host names.
        if re.fullmatch(r'[0-9.]+', host):
            fail('Dirección no pública', 'Non-public address', 'Endereço não público')
    return 'https://' + ('[' + host + ']' if ':' in host else host)


def validate_link(row, data=None):
    if not isinstance(row, dict) or set(row) - {'uid', 'finding_uid', 'provider', 'base_url', 'external_id',
                                               'baseline', 'remote_state', 'last_exchange'}:
        fail('Vínculo externo inválido', 'Invalid external link', 'Vínculo externo inválido')
    for key in ('uid', 'finding_uid'):
        if not isinstance(row.get(key), str) or not UID.fullmatch(row[key]):
            fail('Identidad externa inválida', 'Invalid external identity', 'Identidade externa inválida')
    if not isinstance(row.get('provider'), str) or row['provider'] not in PROVIDERS or base_url(row.get('base_url')) != row.get('base_url'):
        fail('Proveedor o servidor inválido', 'Invalid provider or server', 'Provedor ou servidor inválido')
    pattern = r'[A-Za-z][A-Za-z0-9_]{0,39}-[1-9][0-9]{0,14}' if row['provider'] == 'jira' else r'[1-9][0-9]{0,14}'
    if not isinstance(row.get('external_id'), str) or not re.fullmatch(pattern, row['external_id']):
        fail('Identificador de ticket inválido', 'Invalid ticket identifier', 'Identificador de ticket inválido')
    for key in ('baseline', 'remote_state'):
        values = row.get(key, {})
        if (not isinstance(values, dict) or set(values) - LOCAL_FIELDS
                or any(not isinstance(v, str) or len(v) > 16000 for v in values.values())):
            fail('Estado externo inválido', 'Invalid external state', 'Estado externo inválido')
        if values.get('due_date'):
            try:
                if date.fromisoformat(values['due_date']).isoformat() != values['due_date']:
                    raise ValueError
            except ValueError:
                fail('Fecha externa inválida', 'Invalid external date', 'Data externa inválida')
    if 'last_exchange' in row and (not isinstance(row['last_exchange'], str) or len(row['last_exchange']) > 50):
        fail('Fecha de intercambio inválida', 'Invalid exchange timestamp', 'Data de intercâmbio inválida')
    if data is not None:
        findings = data.get('findings', [])
        pool = {f.get('uid') for f in findings if isinstance(f, dict) and isinstance(f.get('uid'), str)} if isinstance(findings, list) else set()
        if row['finding_uid'] not in pool:
            fail('El hallazgo vinculado no existe', 'Linked finding does not exist', 'O achado vinculado não existe')
    return row


def structure_errors(data):
    rows = data.get('external_tickets', [])
    try:
        if not isinstance(rows, list) or len(rows) > 500:
            fail('Máximo 500 vínculos externos', 'Maximum 500 external links', 'Máximo de 500 vínculos externos')
        identities, destinations = set(), set()
        for row in rows:
            validate_link(row, data)
            target = (row['provider'], row['base_url'], row['external_id'])
            if row['uid'] in identities or target in destinations:
                fail('Vínculo externo duplicado', 'Duplicate external link', 'Vínculo externo duplicado')
            identities.add(row['uid'])
            destinations.add(target)
    except (ValueError, TypeError) as exc:
        return [('error', 'external_tickets: ' + str(exc))]
    return []


def create_link(data, body):
    if not isinstance(body, dict) or set(body) != {'finding_uid', 'provider', 'base_url', 'external_id'}:
        fail('Datos de vínculo inválidos', 'Invalid link fields', 'Campos de vínculo inválidos')
    row = dict(body, uid=new_uid(), baseline={})
    row['base_url'] = base_url(row['base_url'])
    validate_link(row, data)
    candidate = deepcopy(data)
    candidate.setdefault('external_tickets', []).append(row)
    errors = structure_errors(candidate)
    if errors:
        raise ValueError(errors[0][1])
    return candidate, row


def remote_path(link):
    validate_link(link)
    return ('/rest/api/3/issue/' + link['external_id'] if link['provider'] == 'jira'
            else '/api/v2/findings/' + link['external_id'] + '/')


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, port=443, timeout=12, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def remote_request(link, credentials, method='GET', payload=None):
    """No proxies, redirects, private networks, response dumps, or credential writes."""
    validate_link(link)
    if not isinstance(credentials, dict) or set(credentials) - {'username', 'token'}:
        fail('Credenciales inválidas', 'Invalid credentials', 'Credenciais inválidas')
    token = credentials.get('token')
    username = credentials.get('username', '')
    if (not isinstance(token, str) or not 1 <= len(token) <= 4096 or re.search(r'[\s\x00-\x1f]', token)
            or not isinstance(username, str) or len(username) > 300 or re.search(r'[:\r\n]', username)):
        fail('Credenciales inválidas', 'Invalid credentials', 'Credenciais inválidas')
    if link['provider'] == 'jira' and not username:
        fail('Introduce el usuario de Jira', 'Enter the Jira user', 'Informe o usuário do Jira')
    host = urlsplit(link['base_url']).hostname
    connection = None
    try:
        addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            fail('El servidor resolvió a una dirección no pública', 'The server resolved to a non-public address',
                 'O servidor resolveu para um endereço não público')
        connection = _PinnedHTTPS(host, addresses[0])
        authorization = ('Basic ' + b64encode((username + ':' + token).encode()).decode()
                         if link['provider'] == 'jira' else 'Token ' + token)
        encoded = json.dumps(payload, ensure_ascii=True).encode() if payload is not None else None
        if encoded and len(encoded) > MAX_BYTES:
            fail('Contenido externo demasiado grande', 'External payload is too large', 'Conteúdo externo muito grande')
        connection.request(method, remote_path(link), body=encoded,
                           headers={'Authorization': authorization, 'Accept': 'application/json',
                                    'Content-Type': 'application/json', 'User-Agent': 'report-gen-ticket-exchange'})
        response = connection.getresponse()
        raw = response.read(MAX_BYTES + 1)
        if not 200 <= response.status < 300:
            raise ValueError(message('El servidor externo respondió HTTP {p0}', en='The external server returned HTTP {p0}',
                                     pt='O servidor externo retornou HTTP {p0}', p0=response.status))
        if len(raw) > MAX_BYTES:
            fail('Respuesta externa demasiado grande', 'External response is too large', 'Resposta externa muito grande')
        try:
            result = load_json(raw) if raw.strip() else {}
        except ValueError:
            fail('Respuesta externa inválida', 'Invalid external response', 'Resposta externa inválida')
        if not isinstance(result, dict):
            fail('Respuesta externa inválida', 'Invalid external response', 'Resposta externa inválida')
        return result
    except (OSError, http.client.HTTPException, UnicodeError):
        fail('No se pudo completar el intercambio HTTPS; revisa el servidor y las credenciales',
             'Could not complete the HTTPS exchange; check the server and credentials',
             'Não foi possível concluir o intercâmbio HTTPS; verifique o servidor e as credenciais')
    finally:
        if connection:
            connection.close()


def remote_state(link, raw):
    if not isinstance(raw, dict):
        fail('Respuesta externa inválida', 'Invalid external response', 'Resposta externa inválida')
    if link['provider'] == 'jira':
        fields = raw.get('fields')
        if not isinstance(fields, dict):
            fail('Respuesta externa inválida', 'Invalid external response', 'Resposta externa inválida')
        state = {}
        # Missing fields may reflect permissions or an incomplete response.
        # Only explicit null represents an unassigned owner or an empty date.
        if 'assignee' in fields:
            assignee = fields['assignee']
            if assignee is not None and (not isinstance(assignee, dict) or not isinstance(assignee.get('displayName'), str)):
                fail('Responsable externo inválido', 'Invalid external owner', 'Responsável externo inválido')
            state['owner'] = '' if assignee is None else assignee['displayName']
        if 'duedate' in fields:
            if fields['duedate'] is not None and not isinstance(fields['duedate'], str):
                fail('Fecha externa inválida', 'Invalid external date', 'Data externa inválida')
            state['due_date'] = fields['duedate'] if fields['duedate'] is not None else ''
        if 'status' in fields:
            status = fields['status']
            if not isinstance(status, dict) or not isinstance(status.get('name'), str) or not status['name'].strip():
                fail('Estado externo inválido', 'Invalid external state', 'Estado externo inválido')
            state['reported_remediation'] = 'Jira ' + link['external_id'] + ': ' + status['name']
    else:
        # A reporter is not an assignee. DefectDojo tracking is imported as a
        # communication only; we never guess a local owner from reporter IDs.
        values = {k: raw[k] for k in ('active', 'verified', 'false_p', 'mitigated') if k in raw}
        if (not values or any(type(value) is not bool for key, value in values.items() if key != 'mitigated')
                or 'mitigated' in values and values['mitigated'] is not None and not isinstance(values['mitigated'], str)):
            fail('Estado externo inválido', 'Invalid external state', 'Estado externo inválido')
        progress = 'DefectDojo ' + link['external_id'] + ': ' + json.dumps(values, ensure_ascii=True)
        state = {'reported_remediation': progress}
    if not state:
        fail('La respuesta no contiene campos de seguimiento disponibles',
             'The response contains no available tracking fields',
             'A resposta não contém campos de acompanhamento disponíveis')
    validate_link(dict(link, remote_state=state))
    return state


def pull_plan(data, link, state):
    validate_link(dict(link, remote_state=state), data)
    finding = next(f for f in data['findings'] if f['uid'] == link['finding_uid'])
    baseline = link.get('baseline', {})
    return [dict(field=k, before=finding.get(k, ''), after=state[k], base=baseline.get(k),
                 conflict=k in baseline and finding.get(k, '') != baseline[k] and finding.get(k, '') != state[k])
            for k in sorted(LOCAL_FIELDS) if k in state and finding.get(k, '') != state[k]]


def apply_pull(data, link_uid, state, accepted):
    if (not isinstance(accepted, list) or not accepted or any(not isinstance(k, str) for k in accepted)
            or len(set(accepted)) != len(accepted) or set(accepted) - LOCAL_FIELDS):
        fail('Selecciona cambios de seguimiento', 'Select tracking changes', 'Selecione alterações de acompanhamento')
    candidate = deepcopy(data)
    link = next((r for r in candidate.get('external_tickets', []) if r['uid'] == link_uid), None)
    if link is None:
        fail('Vínculo inexistente', 'Link not found', 'Vínculo inexistente')
    changes = {r['field']: r for r in pull_plan(candidate, link, state)}
    if set(accepted) - set(changes):
        fail('La selección ya no coincide con la comparación', 'Selection no longer matches the comparison',
             'A seleção não corresponde mais à comparação')
    finding = next(f for f in candidate['findings'] if f['uid'] == link['finding_uid'])
    for key in accepted:
        finding[key] = state[key]
        link.setdefault('baseline', {})[key] = state[key]
    link['remote_state'] = deepcopy(state)
    return candidate


def push_payload(finding, provider, selected):
    if (not isinstance(provider, str) or provider not in PROVIDERS or not isinstance(selected, list) or not selected
            or any(not isinstance(k, str) for k in selected) or len(set(selected)) != len(selected)
            or set(selected) - PUSH_FIELDS):
        fail('Selecciona campos de texto para enviar', 'Select text fields to send', 'Selecione campos de texto para enviar')
    if provider == 'defectdojo' and 'due_date' in selected:
        fail('Esta integración no envía plazos a DefectDojo',
             'This integration does not send deadlines to DefectDojo',
             'Esta integração não envia prazos ao DefectDojo')
    values = {k: finding.get(k, '') for k in selected}
    if any(not isinstance(v, str) or len(v) > 16000 for v in values.values()):
        fail('Texto externo inválido', 'Invalid external text', 'Texto externo inválido')
    if 'title' in values and (not values['title'].strip() or len(values['title']) > 255):
        fail('Título: entre 1 y 255 caracteres', 'Title: 1 to 255 characters', 'Título: de 1 a 255 caracteres')
    if values.get('due_date'):
        try:
            if date.fromisoformat(values['due_date']).isoformat() != values['due_date']:
                raise ValueError
        except ValueError:
            fail('Fecha externa inválida', 'Invalid external date', 'Data externa inválida')
    fields = {}
    if provider == 'jira':
        if 'title' in values:
            fields['summary'] = values['title']
        if 'due_date' in values:
            fields['duedate'] = values['due_date'] or None
        narrative = [values[k] for k in ('description_md', 'remediation_md') if k in values]
        if narrative:
            fields['description'] = {'type': 'doc', 'version': 1, 'content': [
                {'type': 'paragraph', 'content': [{'type': 'text', 'text': value or ' '}]} for value in narrative]}
        return {'fields': fields}
    mapping = {'title': 'title', 'description_md': 'description', 'remediation_md': 'mitigation'}
    return {mapping[k]: value for k, value in values.items()}


def push_changes(link, remote, payload):
    """Exact remote fields replaced by this payload, without unrelated private data."""
    before = remote.get('fields') if link['provider'] == 'jira' else remote
    after = payload.get('fields') if link['provider'] == 'jira' else payload
    if not isinstance(before, dict) or not isinstance(after, dict):
        fail('Respuesta externa inválida para comparar', 'Invalid external response for comparison',
             'Resposta externa inválida para comparação')
    return [dict(field=key, before=deepcopy(before.get(key)), after=deepcopy(value), available=key in before)
            for key, value in after.items()]
