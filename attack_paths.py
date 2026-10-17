"""Analyst-declared causal DAGs; structure is checked, causality is never inferred."""
from copy import deepcopy
from html import escape
import textwrap
import uuid

from languages import language_index
from test_plans import _error, _identity, _pool, _refs, _texts, tr

MAX_PATHS = 100
MAX_NODES = 40
MAX_EDGES = 100
STATES = {'observed': ('Demostrada por el analista', 'Demonstrated by the analyst', 'Demonstrada pelo analista'),
          'inferred': ('Inferida', 'Inferred', 'Inferida'),
          'blocked': ('Bloqueada', 'Blocked', 'Bloqueada')}
PATH_FIELDS = {'uid', 'title', 'description', 'consequence', 'nodes', 'edges'}
NODE_FIELDS = {'uid', 'title', 'privilege', 'asset_uids', 'finding_uids'}
EDGE_FIELDS = {'uid', 'source_uid', 'target_uid', 'state', 'preconditions', 'observation', 'mitigation', 'evidence_uids', 'http_evidence_uids'}


def topological_nodes(path):
    """Stable order independent of input lists; reject cycles rather than hiding them."""
    nodes = {row['uid']: row for row in path.get('nodes', [])}
    incoming = {uid: 0 for uid in nodes}; outbound = {uid: [] for uid in nodes}
    for edge in path.get('edges', []):
        source, target = edge.get('source_uid'), edge.get('target_uid')
        if source not in nodes or target not in nodes:
            raise ValueError(tr('Transición vinculada a una etapa inexistente', 'Transition links to a missing stage', 'Transição vinculada a uma etapa inexistente'))
        incoming[target] += 1; outbound[source].append(target)
    ready = sorted(uid for uid in nodes if incoming[uid] == 0); result = []
    while ready:
        uid = ready.pop(0); result.append(nodes[uid])
        for target in sorted(outbound[uid]):
            incoming[target] -= 1
            if incoming[target] == 0: ready.append(target); ready.sort()
    if len(result) != len(nodes):
        raise ValueError(tr('La ruta contiene un ciclo; documenta cada transición una vez', 'The path contains a cycle; document each transition once', 'O caminho contém um ciclo; documente cada transição uma vez'))
    return result


def structure_errors(data, occupied=()):
    errors = []; rows = data.get('attack_paths', [])
    if not isinstance(rows, list) or len(rows) > MAX_PATHS:
        _error(errors, 'attack_paths', 'máximo 100 rutas', 'maximum 100 paths', 'máximo de 100 caminhos'); return errors
    used = set(occupied) | _pool(data, 'test_cases')
    for pi, path in enumerate(rows):
        pp = f'attack_paths[{pi}]'
        if not isinstance(path, dict):
            _error(errors, pp, 'debe ser un objeto', 'must be an object', 'deve ser um objeto'); continue
        _identity(path, pp, used, errors)
        _texts(path, {'title': 500, 'description': 16000, 'consequence': 16000}, pp, errors)
        if not isinstance(path.get('title'), str) or not path['title'].strip():
            _error(errors, pp + '.title', 'título obligatorio', 'title required', 'título obrigatório')
        nodes, edges = path.get('nodes', []), path.get('edges', [])
        if not isinstance(nodes, list) or len(nodes) > MAX_NODES or any(not isinstance(x, dict) for x in nodes):
            _error(errors, pp + '.nodes', 'máximo 40 etapas', 'maximum 40 stages', 'máximo de 40 etapas'); continue
        if not isinstance(edges, list) or len(edges) > MAX_EDGES or any(not isinstance(x, dict) for x in edges):
            _error(errors, pp + '.edges', 'máximo 100 transiciones', 'maximum 100 transitions', 'máximo de 100 transições'); continue
        identities = set(); structural = False
        for ni, node in enumerate(nodes):
            np = pp + f'.nodes[{ni}]'
            valid = _identity(node, np, used, errors)
            if valid: identities.add(node['uid'])
            else: structural = True
            _texts(node, {'title': 500, 'privilege': 4000}, np, errors)
            if not isinstance(node.get('title'), str) or not node['title'].strip():
                _error(errors, np + '.title', 'título obligatorio', 'title required', 'título obrigatório')
            _refs(node, 'asset_uids', _pool(data, 'assets'), np, errors)
            _refs(node, 'finding_uids', _pool(data, 'findings'), np, errors)
        pairs = set()
        for ei, edge in enumerate(edges):
            ep = pp + f'.edges[{ei}]'
            _identity(edge, ep, used, errors)
            _texts(edge, {'preconditions': 16000, 'observation': 16000, 'mitigation': 8000}, ep, errors)
            source, target = edge.get('source_uid'), edge.get('target_uid')
            if not isinstance(source, str) or not isinstance(target, str) or source not in identities or target not in identities:
                structural = True
                _error(errors, ep, 'etapas de origen/destino inexistentes', 'missing source/target stages', 'etapas de origem/destino inexistentes')
            elif source == target or (source, target) in pairs:
                structural = True
                _error(errors, ep, 'transición repetida o hacia sí misma', 'duplicate or self transition', 'transição duplicada ou para si mesma')
            else: pairs.add((source, target))
            if not isinstance(edge.get('state'), str) or edge.get('state') not in STATES:
                _error(errors, ep + '.state', 'estado causal inválido', 'invalid causal state', 'estado causal inválido')
            for key, pool in [('evidence_uids', 'evidence'), ('http_evidence_uids', 'http_evidence')]:
                _refs(edge, key, _pool(data, pool), ep, errors)
            if edge.get('state') == 'observed' and (not str(edge.get('observation', '')).strip() or not (edge.get('evidence_uids') or edge.get('http_evidence_uids'))):
                _error(errors, ep, 'una transición demostrada requiere observación y evidencia vinculada', 'a demonstrated transition requires an observation and linked evidence', 'uma transição demonstrada exige observação e evidência vinculada')
            if edge.get('state') in ('inferred', 'blocked') and not str(edge.get('observation', '')).strip():
                _error(errors, ep + '.observation', 'explica la inferencia o el bloqueo', 'explain the inference or blocker', 'explique a inferência ou o bloqueio')
        if not structural:
            try: topological_nodes(path)
            except ValueError as exc: errors.append(('error', pp + ': ' + str(exc)))
    errors.extend(figure_errors(data))
    return errors


def create(body, uid=None):
    if not isinstance(body, dict) or set(body) - PATH_FIELDS:
        raise ValueError(tr('Campos de ruta inválidos', 'Invalid attack path fields', 'Campos de caminho inválidos'))
    row = deepcopy(body)
    if uid is not None and row.get('uid', uid) != uid:
        raise ValueError(tr('La identidad de la ruta no puede cambiar', 'Path identity cannot change', 'A identidade do caminho não pode mudar'))
    row['uid'] = uid or str(uuid.uuid4())
    for key, fields in [('nodes', NODE_FIELDS), ('edges', EDGE_FIELDS)]:
        if not isinstance(row.get(key, []), list):
            raise ValueError(tr('Etapas y transiciones deben ser listas', 'Stages and transitions must be lists', 'Etapas e transições devem ser listas'))
        row.setdefault(key, [])
        for item in row[key]:
            if not isinstance(item, dict) or set(item) - fields:
                raise ValueError(tr('Campos de etapa o transición inválidos', 'Invalid stage or transition fields', 'Campos de etapa ou transição inválidos'))
            item.setdefault('uid', str(uuid.uuid4()))
    return row


def graph_svg(path, lang='es'):
    """Deterministic accessible SVG, escaped text only, no external resources/scripts.

    Single-column stages intentionally avoid undersized branching labels. Distinct
    edge lanes retain the directed relation and analyst-declared state.
    """
    rows = topological_nodes(path)
    index = language_index(lang)
    labels = {row['uid']: n for n, row in enumerate(rows)}
    width, step, top = 1040, 128, 100
    height = max(260, top + len(rows) * step + 90)
    colors = {'observed': '#15803d', 'inferred': '#a16207', 'blocked': '#b91c1c'}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             '<title id="title">' + escape(path.get('title', '')) + '</title>',
             '<desc id="desc">' + escape(('Transiciones declaradas por el analista; el diagrama no prueba causalidad.', 'Analyst-declared transitions; the diagram does not prove causality.', 'Transições declaradas pelo analista; o diagrama não comprova causalidade.')[index]) + '</desc>',
             '<rect width="100%" height="100%" fill="#fff"/>',
             '<text x="28" y="30" font-family="sans-serif" font-size="19" fill="#111827">' + escape(path.get('title', '')[:90]) + '</text>']
    for n, (state, color) in enumerate(colors.items()):
        parts.append(f'<text x="{28+n*335}" y="64" font-family="sans-serif" font-size="13" fill="{color}">' + escape(STATES[state][index]) + '</text>')
    for i, row in enumerate(rows):
        y = top + i * step
        parts.append(f'<rect x="32" y="{y}" width="600" height="94" rx="8" fill="#f8fafc" stroke="#334155"/>')
        title = str(i + 1) + '. ' + row.get('title', '')
        for line, text in enumerate(textwrap.wrap(title, 65)[:2]):
            parts.append(f'<text x="48" y="{y+26+line*19}" font-family="sans-serif" font-size="15" fill="#0f172a">' + escape(text) + '</text>')
        privilege = row.get('privilege', '')
        if privilege:
            parts.append(f'<text x="48" y="{y+77}" font-family="sans-serif" font-size="12" fill="#475569">' + escape(privilege[:85]) + '</text>')
    ordered = sorted(path.get('edges', []), key=lambda e: (labels[e['source_uid']], labels[e['target_uid']], e['uid']))
    # Each edge receives its own lane; 100 edges remain bounded within the canvas.
    for n, edge in enumerate(ordered):
        a, b = labels[edge['source_uid']], labels[edge['target_uid']]
        sy, ty = top + a * step + 58, top + b * step + 30
        lane = 655 + n * (350 / max(1, len(ordered)))
        color = colors.get(edge.get('state'), '#a16207')
        dash = ' stroke-dasharray="6 4"' if edge.get('state') != 'observed' else ''
        parts.append(f'<path d="M 634 {sy} H {lane:.2f} V {ty} H 638" fill="none" stroke="{color}" stroke-width="2"{dash}><title>' + escape(f'{a+1} → {b+1}: ' + STATES.get(edge.get('state'), STATES['inferred'])[index] + ' · ' + edge.get('observation', '')) + '</title></path>')
        parts.append(f'<path d="M 644 {ty-4} L 636 {ty} L 644 {ty+4}" fill="none" stroke="{color}" stroke-width="2"/>')
    parts.append('</svg>')
    return ''.join(parts)


def report_sections(data):
    from engine import report_language
    from workflows import md_text, table
    if not data.get('report', {}).get('workflow', {}).get('include_attack_paths', True): return []
    paths = data.get('attack_paths', [])
    if not paths: return []
    lang = language_index(report_language(data)); t = lambda es, en, pt: (es, en, pt)[lang]
    findings = {r['uid']: r for r in data.get('findings', []) if r.get('uid')}
    assets = {r['uid']: r for r in data.get('assets', []) if r.get('uid')}
    evidence = {r['uid']: r for r in data.get('evidence', []) if r.get('uid')}
    sections = []
    for path in paths:
        ordered = topological_nodes(path); positions = {row['uid']: str(i+1) for i, row in enumerate(ordered)}
        body = t('Relaciones causales declaradas por el analista. La posición o conexión no demuestra explotación; cada transición conserva su estado y evidencia.',
                 'Analyst-declared causal relationships. Position or connection does not demonstrate exploitation; each transition retains its state and evidence.',
                 'Relações causais declaradas pelo analista. A posição ou conexão não demonstra exploração; cada transição mantém seu status e evidência.')
        figures = sorted([row for row in data.get('attack_path_figures', []) if row.get('path_uid') == path['uid']], key=lambda row: row['part'])
        for figure in figures:
            caption = t('Diagrama de transiciones declaradas', 'Declared transition diagram', 'Diagrama de transições declaradas') + ' · ' + t('parte ', 'part ', 'parte ') + str(figure['part']) + ' / ' + str(figure['parts'])
            body += '\n\n![' + caption + '](' + figure['src'] + ')'
        if path.get('description'): body += '\n\n' + '\n\n'.join(md_text(part) for part in path['description'].replace('\r\n', '\n').split('\n\n'))
        if path.get('consequence'): body += '\n\n**' + t('Consecuencia', 'Consequence', 'Consequência') + '**\n\n' + '\n\n'.join(md_text(part) for part in path['consequence'].replace('\r\n', '\n').split('\n\n'))
        body += '\n\n' + table([t('Etapa', 'Stage', 'Etapa'), t('Condición / privilegio', 'Condition / privilege', 'Condição / privilégio'), t('Activos / hallazgos', 'Assets / findings', 'Ativos / achados')], [
            [positions[row['uid']] + '. ' + row['title'], row.get('privilege', ''), ', '.join(
             [assets[x].get('target') or assets[x].get('name', x) for x in row.get('asset_uids', []) if x in assets]
             + [findings[x].get('id', x) for x in row.get('finding_uids', []) if x in findings])] for row in ordered])
        for edge in sorted(path.get('edges', []), key=lambda e: (int(positions[e['source_uid']]), int(positions[e['target_uid']]), e['uid'])):
            body += '\n\n### ' + t('Transición ', 'Transition ', 'Transição ') + positions[edge['source_uid']] + ' → ' + positions[edge['target_uid']] + ' · ' + STATES[edge['state']][lang]
            for field, title in [('preconditions', t('Condiciones previas', 'Prerequisites', 'Pré-condições')), ('observation', t('Observación / fundamento', 'Observation / rationale', 'Observação / fundamento')), ('mitigation', t('Medida que interrumpe la transición', 'Control interrupting the transition', 'Medida que interrompe a transição'))]:
                if edge.get(field): body += '\n\n**' + title + '**\n\n' + '\n\n'.join(md_text(part) for part in edge[field].replace('\r\n', '\n').split('\n\n'))
            for uid in edge.get('evidence_uids', []):
                item = evidence.get(uid)
                if item and item.get('src'): body += '\n\n![' + md_text(item.get('caption') or item.get('title') or uid) + '](' + item['src'] + ')'
            if edge.get('http_evidence_uids'):
                published = {item.get('uid') for item in data.get('http_evidence_refs', []) if item.get('published')}
                body += '\n\n' + t('Referencias HTTP: ', 'HTTP references: ', 'Referências HTTP: ') + ', '.join(md_text(x) + (' (' + t('contenido reservado', 'content withheld', 'conteúdo reservado') + ')' if x not in published else '') for x in edge['http_evidence_uids'])
        sections.append({'key': 'rg_attack_' + path['uid'].replace('-', ''), 'title': t('Ruta de ataque: ', 'Attack path: ', 'Caminho de ataque: ') + path['title'], 'body': body})
    return sections


def graph_panels(path, lang='es'):
    """Rasterize three explicit transitions per panel, without external renderers.

    Each directed relation appears exactly once. Shared stage numbers connect
    panels; this does not introduce transitive or implied edges. Full text is
    preserved in the native report following each diagram.
    """
    from io import BytesIO
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont
    if not isinstance(path, dict) or len(path.get('nodes', [])) > MAX_NODES or len(path.get('edges', [])) > MAX_EDGES:
        raise ValueError(tr('Ruta demasiado grande', 'Attack path is too large', 'Caminho muito grande'))
    ordered = topological_nodes(path)
    numbers = {row['uid']: i + 1 for i, row in enumerate(ordered)}
    by_uid = {row['uid']: row for row in ordered}
    edges = sorted(path.get('edges', []), key=lambda e: (numbers[e['source_uid']], numbers[e['target_uid']], e['uid']))
    if not edges: return []
    li = language_index(lang); t = lambda es, en, pt: (es, en, pt)[li]
    colors = {'observed': '#15803d', 'inferred': '#a16207', 'blocked': '#b91c1c'}
    fontfile = str(Path(__file__).parent / 'exporters' / 'fonts' / 'DejaVuSans.ttf')
    font = ImageFont.truetype(fontfile, 24); small = ImageFont.truetype(fontfile, 19)
    heading = ImageFont.truetype(fontfile, 28)
    def lines(text, chosen, width, maximum):
        # Pixel fitting also handles long tokens and wide glyphs.
        words = ' '.join(str(text).split()).split(' '); out = []; line = ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            if chosen.getlength(candidate) <= width: line = candidate; continue
            if line: out.append(line); line = ''
            while word and chosen.getlength(word) > width:
                cut = len(word)
                while cut > 1 and chosen.getlength(word[:cut]) > width: cut -= 1
                out.append(word[:cut]); word = word[cut:]
            line = word
        if line: out.append(line)
        if len(out) > maximum:
            out = out[:maximum]; tail = out[-1]
            while tail and chosen.getlength(tail + ' (...)') > width: tail = tail[:-1]
            out[-1] = tail.rstrip() + ' (...)'
        return out
    panels = []
    chunks = [edges[i:i + 3] for i in range(0, len(edges), 3)]
    for pi, chunk in enumerate(chunks, 1):
        image = Image.new('RGB', (1400, 178 + len(chunk) * 195), 'white'); draw = ImageDraw.Draw(image)
        for index, text in enumerate(lines(path.get('title', ''), heading, 1310, 2)):
            draw.text((40, 22 + index * 33), text, font=heading, fill='#0f172a')
        draw.text((40, 97), t('Parte ', 'Part ', 'Parte ') + str(pi) + ' / ' + str(len(chunks)), font=small, fill='#475569')
        for ei, edge in enumerate(chunk):
            y = 150 + ei * 195; color = colors[edge['state']]
            for side, uid in enumerate((edge['source_uid'], edge['target_uid'])):
                left = 40 + side * 790
                draw.rounded_rectangle((left, y, left + 530, y + 116), radius=12, fill='#f8fafc', outline='#475569', width=2)
                text = str(numbers[uid]) + '. ' + by_uid[uid]['title']
                for line, label in enumerate(lines(text, font, 490, 3)):
                    draw.text((left + 18, y + 13 + line * 30), label, font=font, fill='#0f172a')
            # Broken strokes encode non-observed edges; text carries the state
            # for monochrome output and readers who cannot distinguish color.
            if edge['state'] == 'observed': draw.line((585, y + 55, 813, y + 55), fill=color, width=5)
            else:
                for x in range(585, 805, 20): draw.line((x, y + 55, min(x + 11, 813), y + 55), fill=color, width=4)
            draw.polygon(((813, y + 55), (797, y + 45), (797, y + 65)), fill=color)
            label = STATES[edge['state']][li]
            for line, text in enumerate(lines(label, small, 245, 2)):
                draw.text((700 - small.getlength(text) / 2, y + 82 + line * 22), text, font=small, fill=color)
            evidence_count = len(edge.get('evidence_uids', [])) + len(edge.get('http_evidence_uids', []))
            caption = t('Evidencias vinculadas: ', 'Linked evidence: ', 'Evidências vinculadas: ') + str(evidence_count)
            draw.text((40, y + 130), caption, font=small, fill='#475569')
        footer = t('Relaciones declaradas por el analista. (...) indica texto abreviado; detalles completos a continuación.',
                   'Analyst-declared relationships. (...) marks shortened text; full details follow.',
                   'Relações declaradas pelo analista. (...) indica texto abreviado; os detalhes completos estão a seguir.')
        draw.text((40, image.height - 38), footer, font=small, fill='#475569')
        output = BytesIO(); image.save(output, format='PNG', optimize=False)
        panels.append({'part': pi, 'parts': len(chunks), 'blob': output.getvalue()})
    return panels


def stage_graphs(source, directory):
    """Return a publication copy with generated PNGs in an isolated target only.

    Caller supplies the temporary published directory, never the author project.
    Existing presentation metadata is replaced using current published text.
    """
    from hashlib import sha256
    from pathlib import Path
    from engine import report_language
    from storage import atomic_write
    data = deepcopy(source); data.pop('attack_path_figures', None)
    issues = structure_errors(data)
    if issues: raise ValueError('; '.join(text for _, text in issues))
    if not data.get('report', {}).get('workflow', {}).get('include_attack_paths', True): return data
    directory = Path(directory).resolve()
    # Fixed generated subpaths, immutable hash names, no source filenames.
    images = directory / 'img'
    if images.is_symlink(): raise ValueError(tr('Destino de gráficos no permitido', 'Graph destination is not allowed', 'Destino de gráficos não permitido'))
    records = []
    for path in data.get('attack_paths', []):
        for panel in graph_panels(path, report_language(data)):
            digest = sha256(panel['blob']).hexdigest()
            name = f"img/rg-attack-{path['uid']}-{panel['part']:03d}-{digest[:16]}.png"
            destination = directory / name
            if destination.is_symlink(): raise ValueError(tr('Destino de gráficos no permitido', 'Graph destination is not allowed', 'Destino de gráficos não permitido'))
            images.mkdir(parents=True, exist_ok=True)
            if destination.exists() and destination.read_bytes() != panel['blob']:
                raise ValueError(tr('Colisión de recurso generado', 'Generated resource collision', 'Colisão de recurso gerado'))
            if not destination.exists(): atomic_write(destination, panel['blob'])
            records.append({'path_uid': path['uid'], 'src': name, 'sha256': digest, 'part': panel['part'], 'parts': panel['parts']})
    if records: data['attack_path_figures'] = records
    return data


def figure_errors(data):
    """Strict portable projection metadata, never a general filesystem locator."""
    import re
    errors = []; figures = data.get('attack_path_figures', [])
    if not isinstance(figures, list) or len(figures) > 3400:
        _error(errors, 'attack_path_figures', 'metadatos de gráficos inválidos', 'invalid graph metadata', 'metadados de gráficos inválidos'); return errors
    paths = {p.get('uid'): p for p in data.get('attack_paths', []) if isinstance(p, dict) and isinstance(p.get('uid'), str)} if isinstance(data.get('attack_paths', []), list) else {}
    seen = set(); parts = {}
    for i, row in enumerate(figures):
        key = f'attack_path_figures[{i}]'
        if not isinstance(row, dict) or set(row) != {'path_uid', 'src', 'sha256', 'part', 'parts'}:
            _error(errors, key, 'metadatos de gráficos inválidos', 'invalid graph metadata', 'metadados de gráficos inválidos'); continue
        uid, digest, part, count = row.get('path_uid'), row.get('sha256'), row.get('part'), row.get('parts')
        if not isinstance(uid, str) or uid not in paths or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or type(part) is not int or type(count) is not int or not 1 <= part <= count <= 34:
            _error(errors, key, 'identidad de gráfico inválida', 'invalid graph identity', 'identidade de gráfico inválida'); continue
        if row.get('src') != f'img/rg-attack-{uid}-{part:03d}-{digest[:16]}.png' or (uid, part) in seen:
            _error(errors, key + '.src', 'ruta de gráfico inválida o duplicada', 'invalid or duplicate graph path', 'caminho de gráfico inválido ou duplicado')
        seen.add((uid, part)); parts.setdefault(uid, []).append(part)
        edges = paths[uid].get('edges', [])
        if not isinstance(edges, list) or count != (len(edges) + 2) // 3:
            _error(errors, key + '.parts', 'cantidad de partes incoherente', 'inconsistent part count', 'quantidade de partes inconsistente')
    for uid, values in parts.items():
        edges = paths[uid].get('edges', [])
        # The core path validator already reports malformed containers. Keep
        # validating imported figure metadata without calling len() on them.
        if isinstance(edges, list) and sorted(values) != list(range(1, (len(edges) + 2) // 3 + 1)):
            _error(errors, 'attack_path_figures', 'faltan partes del gráfico', 'graph parts are missing', 'faltam partes do gráfico')
    return errors
