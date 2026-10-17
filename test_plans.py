"""Versioned, analyst-authored test cases. Starter plans are not certification catalogs."""
from copy import deepcopy
from itertools import product
import re
import uuid

from error_messages import current_language
from languages import language_index

UID = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
MAX_CASES = 3000
MAX_MATRIX = 300
SPECIALTIES = ('web', 'api', 'ad', 'cloud', 'mobile', 'ai', 'custom')
STATES = {
    'pending': ('Pendiente', 'Pending', 'Pendente'),
    'passed': ('Realizada sin fallo observado', 'Performed; no failure observed', 'Realizada sem falha observada'),
    'failed': ('Fallo observado', 'Failure observed', 'Falha observada'),
    'blocked': ('Bloqueada', 'Blocked', 'Bloqueada'),
    'not_applicable': ('No aplica', 'Not applicable', 'Não se aplica'),
}
TEXT_FIELDS = {'title': 500, 'methodology': 200, 'methodology_version': 80, 'test_id': 120,
               'prerequisites': 16000, 'identity': 1000, 'tenant': 1000, 'operation': 1000,
               'expected': 16000, 'observed': 32000, 'notes': 16000}
REF_FIELDS = {'asset_uids': 'assets', 'finding_uids': 'findings', 'evidence_uids': 'evidence', 'http_evidence_uids': 'http_evidence'}
FIELDS = set(TEXT_FIELDS) | set(REF_FIELDS) | {'uid', 'specialty', 'status'}


def tr(es, en, pt):
    """Select complete authored prose; these triples are not format templates."""
    return (es, en, pt)[language_index(current_language())]


def _error(errors, path, es, en, pt):
    errors.append(('error', path + ': ' + tr(es, en, pt)))


def _pool(data, key):
    rows = data.get(key, [])
    if key == 'http_evidence' and isinstance(rows, list):
        projected = data.get('http_evidence_refs', [])
        if isinstance(projected, list): rows = rows + projected
    return {r.get('uid') for r in rows if isinstance(r, dict) and isinstance(r.get('uid'), str)} if isinstance(rows, list) else set()


def _texts(row, fields, path, errors):
    for key, limit in fields.items():
        value = row.get(key, '')
        if not isinstance(value, str) or len(value) > limit:
            _error(errors, path + '.' + key, 'texto inválido o demasiado largo', 'invalid or oversized text', 'texto inválido ou muito longo')


def _refs(row, key, pool, path, errors):
    value = row.get(key, [])
    if (not isinstance(value, list) or len(value) > 3000
            or any(not isinstance(ref, str) or ref not in pool for ref in value)
            or len(value) != len(set(ref for ref in value if isinstance(ref, str)))):
        _error(errors, path + '.' + key, 'referencias inexistentes o duplicadas', 'missing or duplicate references', 'referências inexistentes ou duplicadas')


def _identity(row, path, occupied, errors):
    uid = row.get('uid')
    if not isinstance(uid, str) or not UID.fullmatch(uid) or uid in occupied:
        _error(errors, path + '.uid', 'identidad permanente inválida o duplicada', 'invalid or duplicate permanent identity', 'identidade permanente inválida ou duplicada')
        return False
    occupied.add(uid)
    return True


def structure_errors(data, occupied=()):
    errors = []
    rows = data.get('test_cases', [])
    if not isinstance(rows, list) or len(rows) > MAX_CASES:
        _error(errors, 'test_cases', 'máximo 3000 casos de prueba', 'maximum 3000 test cases', 'máximo de 3000 casos de teste')
        return errors
    used = set(occupied)
    pools = {key: _pool(data, pool) for key, pool in REF_FIELDS.items()}
    for i, row in enumerate(rows):
        path = f'test_cases[{i}]'
        if not isinstance(row, dict):
            _error(errors, path, 'debe ser un objeto', 'must be an object', 'deve ser um objeto')
            continue
        _identity(row, path, used, errors)
        _texts(row, TEXT_FIELDS, path, errors)
        if not isinstance(row.get('title'), str) or not row['title'].strip():
            _error(errors, path + '.title', 'título obligatorio', 'title required', 'título obrigatório')
        if not isinstance(row.get('status', 'pending'), str) or row.get('status', 'pending') not in STATES:
            _error(errors, path + '.status', 'estado de prueba inválido', 'invalid test status', 'status de teste inválido')
        if not isinstance(row.get('specialty', 'custom'), str) or row.get('specialty', 'custom') not in SPECIALTIES:
            _error(errors, path + '.specialty', 'especialidad inválida', 'invalid specialty', 'especialidade inválida')
        for key, pool in pools.items():
            _refs(row, key, pool, path, errors)
        if row.get('status') in ('passed', 'failed', 'blocked', 'not_applicable') and not str(row.get('observed', '')).strip():
            _error(errors, path + '.observed', 'registra el resultado o la limitación', 'record the result or limitation', 'registre o resultado ou a limitação')
    return errors


# Authored starter cases, deliberately small and versioned independently of OWASP,
# MITRE or vendor methodologies. No testing is performed and no coverage is assumed.
_STARTERS = {
    'web': [
        ('RG-WEB-01', ('Autorización del lado del servidor', 'Server-side authorization', 'Autorização no servidor'),
         ('Dos identidades autorizadas con permisos diferentes y datos de prueba.', 'Two authorized identities with different permissions and test data.', 'Duas identidades autorizadas com permissões diferentes e dados de teste.'),
         ('El servidor rechaza el acceso fuera de los permisos de cada identidad.', 'The server rejects access outside each identity’s permissions.', 'O servidor rejeita acesso fora das permissões de cada identidade.')),
        ('RG-WEB-02', ('Invalidación de sesión', 'Session invalidation', 'Invalidação de sessão'),
         ('Sesión de prueba y una petición autenticada reproducible.', 'Test session and a reproducible authenticated request.', 'Sessão de teste e uma requisição autenticada reproduzível.'),
         ('La sesión revocada no permite acceder a recursos protegidos.', 'The revoked session cannot access protected resources.', 'A sessão revogada não permite acesso a recursos protegidos.'))],
    'api': [
        ('RG-API-01', ('Autorización por objeto y organización', 'Object and tenant authorization', 'Autorização por objeto e organização'),
         ('Roles, organizaciones y objetos de prueba autorizados.', 'Authorized test roles, tenants and objects.', 'Papéis, organizações e objetos de teste autorizados.'),
         ('Cada operación respeta el propietario, la organización y el rol.', 'Each operation enforces ownership, tenant boundaries and role permissions.', 'Cada operação respeita o proprietário, a organização e o papel.')),
        ('RG-API-02', ('Propiedades modificables', 'Writable properties', 'Propriedades modificáveis'),
         ('Contrato de la API y objeto desechable de prueba.', 'API contract and a disposable test object.', 'Contrato da API e objeto de teste descartável.'),
         ('Solo se aceptan las propiedades que la identidad puede modificar.', 'Only properties writable by this identity are accepted.', 'Somente propriedades modificáveis por esta identidade são aceitas.'))],
    'ad': [
        ('RG-AD-01', ('Relaciones de privilegio', 'Privilege relationships', 'Relações de privilégio'),
         ('Inventario autorizado de identidades, grupos y permisos.', 'Authorized identity, group and permission inventory.', 'Inventário autorizado de identidades, grupos e permissões.'),
         ('Los permisos efectivos coinciden con las relaciones autorizadas; las rutas se verifican por separado.', 'Effective permissions match authorized relationships; paths are verified separately.', 'As permissões efetivas correspondem às relações autorizadas; os caminhos são verificados separadamente.')),
        ('RG-AD-02', ('Protección del canal de autenticación', 'Authentication channel protection', 'Proteção do canal de autenticação'),
         ('Servicios y métodos de autenticación autorizados para la prueba.', 'Services and authentication methods authorized for testing.', 'Serviços e métodos de autenticação autorizados para teste.'),
         ('Los canales observados aplican las protecciones acordadas para evitar exposición de credenciales.', 'Observed channels enforce the agreed protections against credential exposure.', 'Os canais observados aplicam as proteções acordadas contra exposição de credenciais.'))],
    'cloud': [
        ('RG-CLOUD-01', ('Alcance efectivo de IAM', 'Effective IAM scope', 'Escopo efetivo de IAM'),
         ('Cuenta, región, identidad y recurso de prueba acordados.', 'Agreed account, region, identity and test resource.', 'Conta, região, identidade e recurso de teste acordados.'),
         ('La identidad solo puede realizar acciones y acceder a recursos autorizados.', 'The identity can only perform authorized actions on authorized resources.', 'A identidade só pode realizar ações autorizadas em recursos autorizados.')),
        ('RG-CLOUD-02', ('Exposición de recursos', 'Resource exposure', 'Exposição de recursos'),
         ('Inventario de recursos y política de acceso esperada.', 'Resource inventory and expected access policy.', 'Inventário de recursos e política de acesso esperada.'),
         ('El acceso observado coincide con la política documentada de cada recurso.', 'Observed access matches each resource’s documented policy.', 'O acesso observado corresponde à política documentada de cada recurso.'))],
    'mobile': [
        ('RG-MOBILE-01', ('Almacenamiento local sensible', 'Sensitive local storage', 'Armazenamento local sensível'),
         ('Dispositivo de prueba y versión identificada de la aplicación.', 'Test device and identified application version.', 'Dispositivo de teste e versão identificada do aplicativo.'),
         ('Los datos locales respetan los requisitos acordados de almacenamiento y eliminación.', 'Local data respects the agreed storage and deletion requirements.', 'Os dados locais respeitam os requisitos acordados de armazenamento e exclusão.')),
        ('RG-MOBILE-02', ('Validación de transporte', 'Transport validation', 'Validação de transporte'),
         ('Entorno de prueba de red y flujos autorizados.', 'Test network environment and authorized flows.', 'Ambiente de rede de teste e fluxos autorizados.'),
         ('La aplicación valida los extremos de comunicación conforme a su política.', 'The application validates communication endpoints according to its policy.', 'O aplicativo valida os extremos de comunicação conforme sua política.'))],
    'ai': [
        ('RG-AI-01', ('Separación de instrucciones y contenido', 'Instruction and content separation', 'Separação de instruções e conteúdo'),
         ('Modelo, versión, contexto, herramientas y datos sintéticos documentados.', 'Documented model, version, context, tools and synthetic data.', 'Modelo, versão, contexto, ferramentas e dados sintéticos documentados.'),
         ('El contenido no confiable no autoriza acciones o divulgaciones fuera de la política.', 'Untrusted content does not authorize actions or disclosures outside policy.', 'Conteúdo não confiável não autoriza ações ou divulgações fora da política.')),
        ('RG-AI-02', ('Autorización de herramientas y recuperación', 'Tool and retrieval authorization', 'Autorização de ferramentas e recuperação'),
         ('Identidades de prueba y recursos sintéticos con permisos diferenciados.', 'Test identities and synthetic resources with distinct permissions.', 'Identidades de teste e recursos sintéticos com permissões diferentes.'),
         ('Las herramientas y la recuperación aplican los permisos de la identidad activa.', 'Tools and retrieval enforce the active identity’s permissions.', 'Ferramentas e recuperação aplicam as permissões da identidade ativa.'))],
}


def catalog(lang='es'):
    index = language_index(lang)
    return {'name': 'report-gen starter plans', 'version': '1.0', 'official_catalog': False,
            'notice': ('Planes iniciales editables; no representan catálogos oficiales completos ni acreditan cobertura.',
                       'Editable starter plans; these are not complete official catalogs and do not attest coverage.',
                       'Planos iniciais editáveis; não são catálogos oficiais completos nem atestam cobertura.')[index],
            'plans': [{'specialty': specialty, 'cases': [{'test_id': code, 'title': title[index],
                'prerequisites': prerequisites[index], 'expected': expected[index], 'methodology': 'report-gen starter plans',
                'methodology_version': '1.0', 'specialty': specialty, 'status': 'pending'}
                for code, title, prerequisites, expected in rows]} for specialty, rows in _STARTERS.items()]}


def create(body, uid=None):
    if not isinstance(body, dict) or set(body) - FIELDS:
        raise ValueError(tr('Campos de caso de prueba inválidos', 'Invalid test case fields', 'Campos de caso de teste inválidos'))
    row = deepcopy(body)
    if uid is not None and row.get('uid', uid) != uid:
        raise ValueError(tr('La identidad del caso no puede cambiar', 'Test case identity cannot change', 'A identidade do caso não pode mudar'))
    row['uid'] = uid or str(uuid.uuid4())
    row.setdefault('status', 'pending'); row.setdefault('specialty', 'custom')
    for key in REF_FIELDS: row.setdefault(key, [])
    return row


def matrix(body):
    """Return bounded Cartesian cases, without saving or assuming authorization outcomes."""
    if not isinstance(body, dict) or set(body) - {'roles', 'tenants', 'operations', 'base'}:
        raise ValueError(tr('Matriz de pruebas inválida', 'Invalid test matrix', 'Matriz de testes inválida'))
    axes = []
    for key in ('roles', 'tenants', 'operations'):
        values = body.get(key)
        if (not isinstance(values, list) or not 1 <= len(values) <= 30
                or any(not isinstance(x, str) or not x.strip() or len(x) > 300 for x in values)):
            raise ValueError(tr('Cada eje necesita entre 1 y 30 valores de texto', 'Each axis needs 1 to 30 text values', 'Cada eixo precisa de 1 a 30 valores de texto'))
        values = [x.strip() for x in values]
        if len(set(values)) != len(values):
            raise ValueError(tr('La matriz contiene valores duplicados', 'The matrix contains duplicate values', 'A matriz contém valores duplicados'))
        axes.append(values)
    if len(axes[0]) * len(axes[1]) * len(axes[2]) > MAX_MATRIX:
        raise ValueError(tr('Máximo 300 casos por matriz', 'Maximum 300 cases per matrix', 'Máximo de 300 casos por matriz'))
    base = create(body.get('base', {}))
    # Results, evidence and findings are individual observations, never multiplied.
    if base.get('status') != 'pending' or base.get('observed') or base.get('finding_uids') or base.get('evidence_uids') or base.get('http_evidence_uids'):
        raise ValueError(tr('La matriz solo crea pruebas pendientes sin resultados ni evidencias', 'Matrices only create pending tests without results or evidence', 'A matriz só cria testes pendentes sem resultados nem evidências'))
    title = base.get('title', ''); result = []
    if not isinstance(title, str) or not title.strip() or len(title) > 150:
        raise ValueError(tr('Título de matriz obligatorio; máximo 150 caracteres', 'Matrix title required; maximum 150 characters', 'Título da matriz obrigatório; máximo de 150 caracteres'))
    for role, tenant, operation in product(*axes):
        row = create(base)
        row.update(identity=role, tenant=tenant, operation=operation, title=title,
                   test_id=base.get('test_id', ''))
        result.append(row)
    return result


def report_sections(data):
    from engine import report_language
    from workflows import md_text, table
    if not data.get('report', {}).get('workflow', {}).get('include_test_cases', True): return []
    rows = data.get('test_cases', [])
    if not rows: return []
    lang = language_index(report_language(data))
    t = lambda es, en, pt: (es, en, pt)[lang]
    pools = {k: {x['uid']: x for x in data.get(v, []) if x.get('uid')} for k, v in REF_FIELDS.items()}
    counts = ' · '.join(STATES[key][lang] + ': ' + str(sum(x.get('status', 'pending') == key for x in rows)) for key in STATES)
    body = md_text(counts) + '\n\n' + t('El estado registra la evaluación del analista. Una prueba sin fallo observado no garantiza ausencia de vulnerabilidades.',
        'Status records the analyst’s assessment. A test without an observed failure does not guarantee absence of vulnerabilities.',
        'O status registra a avaliação do analista. Um teste sem falha observada não garante ausência de vulnerabilidades.')
    for n, row in enumerate(rows, 1):
        body += '\n\n### ' + md_text(str(n) + '. ' + row['title'])
        body += '\n\n' + table([t('Campo', 'Field', 'Campo'), t('Valor', 'Value', 'Valor')], [
            [t('Metodología / versión / prueba', 'Methodology / version / test', 'Metodologia / versão / teste'), ' · '.join(row.get(k, '') for k in ('methodology', 'methodology_version', 'test_id'))],
            [t('Estado', 'Status', 'Status'), STATES[row.get('status', 'pending')][lang]],
            [t('Identidad / organización / operación', 'Identity / tenant / operation', 'Identidade / organização / operação'), ' · '.join(row.get(k, '') for k in ('identity', 'tenant', 'operation'))],
            [t('Activos', 'Assets', 'Ativos'), ', '.join(pools['asset_uids'][uid].get('target') or pools['asset_uids'][uid].get('name', uid) for uid in row.get('asset_uids', []) if uid in pools['asset_uids'])],
            [t('Hallazgos', 'Findings', 'Achados'), ', '.join(pools['finding_uids'][uid].get('id', uid) for uid in row.get('finding_uids', []) if uid in pools['finding_uids'])]])
        for field, title in [('prerequisites', t('Condiciones previas', 'Prerequisites', 'Pré-condições')), ('expected', t('Resultado esperado', 'Expected result', 'Resultado esperado')), ('observed', t('Resultado observado / limitación', 'Observed result / limitation', 'Resultado observado / limitação')), ('notes', t('Notas', 'Notes', 'Notas'))]:
            if row.get(field): body += '\n\n#### ' + title + '\n\n' + '\n\n'.join(md_text(part) for part in row[field].replace('\r\n', '\n').split('\n\n'))
        for uid in row.get('evidence_uids', []):
            evidence = pools['evidence_uids'].get(uid)
            if evidence and evidence.get('src'):
                body += '\n\n![' + md_text(evidence.get('caption') or evidence.get('title') or uid) + '](' + evidence['src'] + ')'
        if row.get('http_evidence_uids'):
            published = {item.get('uid') for item in data.get('http_evidence_refs', []) if item.get('published')}
            body += '\n\n' + t('Referencias HTTP: ', 'HTTP references: ', 'Referências HTTP: ') + ', '.join(md_text(x) + (' (' + t('contenido reservado', 'content withheld', 'conteúdo reservado') + ')' if x not in published else '') for x in row['http_evidence_uids'])
    return [{'key': 'rg_test_cases', 'title': t('Plan de pruebas y trazabilidad', 'Test plan and traceability', 'Plano de testes e rastreabilidade'), 'body': body}]
