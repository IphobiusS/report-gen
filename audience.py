"""Explicit, independently rendered audience projections. No source writes or network."""
from languages import language_index
from error_messages import message as backend_message
from copy import deepcopy
from io import BytesIO
import json
import re
import zipfile

from lxml import html
import engine
import publication
import validate
import workflows

PROFILES = ('technical', 'executive', 'public')
OPTION_KEYS = {'profile', 'finding_uids', 'section_keys', 'title', 'client_alias', 'aliases',
               'approved_content', 'review_confirmed', 'publish_consent', 'provenance_label'}
EXPORT_KEYS = {'formats', 'label', 'acknowledge_warnings'}
PUBLIC_FIELDS = ('title', 'summary', 'impact', 'remediation')
MAX_FINDINGS = 1000
MAX_TEXT = 16000
RISK_FIELDS = ('service', 'objective', 'consequence', 'tolerance', 'source',
               'assumptions', 'priority', 'rationale', 'owner')


def _text(value, label, maximum=MAX_TEXT, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(backend_message('{p0}: texto inválido / invalid text', p0=label))
    from input_guard import ensure_data_tree
    ensure_data_tree(value)
    return value.strip()


def _selection(value, pool, label, explicit=False):
    if value is None and not explicit:
        return list(pool)
    if (not isinstance(value, list) or not value or len(value) > MAX_FINDINGS
            or any(not isinstance(uid, str) or uid not in pool for uid in value)
            or len(set(value)) != len(value)):
        raise ValueError(backend_message('{p0}: selecciona identidades existentes, sin duplicados / select existing identities without duplicates', p0=label))
    return list(value)


def _aliases(options):
    rows = options.get('aliases', [])
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError(backend_message('Máximo 200 sustituciones / Maximum 200 substitutions'))
    publication.validate_config({'redactions': rows})
    if len({row['needle'] for row in rows}) != len(rows):
        raise ValueError(backend_message('Sustituciones duplicadas / Duplicate substitutions'))
    return deepcopy(rows)


def _markdown_text(value, lang='es'):
    """Keep prose, never command/code blocks, embedded images, or link targets."""
    from safe_markup import _parsed
    tree = html.fragment_fromstring(_parsed(str(value or '')), create_parent='div')
    for node in tree.xpath('.//pre|.//code|.//img|.//script|.//style'):
        node.drop_tree()
    text = publication.rendered_text(tree)
    text = re.sub(r'(?i)\b(?:https?|ftp|file)://\S+', ('[detalle técnico omitido]', '[technical detail omitted]', '[detalhe técnico omitido]')[language_index(lang)], text)
    text = re.sub(r'(?<!\w)(?:/(?:home|var|etc|tmp|root|Users|opt|srv|mnt|workspace)/[^\s]*|[A-Za-z]:\\[^\s]*)',
                  ('[ruta omitida]', '[path omitted]', '[caminho omitido]')[language_index(lang)], text)
    return text.strip()


def _plain_md(value):
    """Plain authored content cannot create links, images, anchors, or HTML."""
    # Entity escaping is independent of Markdown punctuation; an author's
    # literal '<img>' remains text, never an export resource or executable node.
    from html import escape
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', escape(str(value), quote=False))


def _meta(source, options, profile):
    original = source.get('meta') or {}
    lang = engine.report_language(source)
    defaults = {'executive': (('Resumen de dirección', 'Executive summary', 'Resumo executivo')[language_index(lang)]),
                'public': (('Caso público', 'Public case study', 'Estudo de caso público')[language_index(lang)])}
    result = {'lang': lang, 'theme': original.get('theme', 'serio'),
              'report_title': _text(options.get('title', defaults[profile]), 'title', 300, True),
              'client': _text(options.get('client_alias', original.get('client', '') if profile == 'executive' else ''),
                              'client_alias', 300, profile == 'public'),
              'version': '1.0', 'branding': {'wordmark': 'report-gen', 'byline': 'report-gen',
                  'confidential_text': ((('EXTRACTO PÚBLICO', 'PUBLIC DERIVATIVE', 'VERSÃO DERIVADA PÚBLICA')[language_index(lang)])) if profile == 'public'
                  else ((('RESUMEN DE DIRECCIÓN', 'EXECUTIVE SUMMARY', 'RESUMO EXECUTIVO')[language_index(lang)]))}}
    # No contacts, private branding, source title, source date, internal layout,
    # document identifiers, author names, custom metadata, or resource paths.
    return result


def _risk_body(risks, finding_uid, lang, redact=lambda value: value):
    labels = dict(zip(RISK_FIELDS, ((('Servicio', 'Objetivo de negocio', 'Consecuencia', 'Tolerancia acordada', 'Fuente del criterio', 'Supuestos', 'Prioridad de intervención', 'Justificación', 'Responsable'), ('Service', 'Business objective', 'Consequence', 'Agreed tolerance', 'Criterion source', 'Assumptions', 'Intervention priority', 'Rationale', 'Owner'), ('Serviço', 'Objetivo de negócio', 'Consequência', 'Tolerância acordada', 'Fonte do critério', 'Premissas', 'Prioridade de intervenção', 'Justificativa', 'Responsável'))[language_index(lang)])))
    rows = [row for row in risks if isinstance(row, dict) and row.get('finding_uid') == finding_uid]
    parts = []
    for row in rows:
        for key in RISK_FIELDS:
            value = row.get(key, '')
            if key == 'tolerance' and not value:
                value = (('No acordado', 'Not agreed', 'Não acordada')[language_index(lang)])
            if key == 'priority' and value == 'unassigned':
                value = (('Sin asignar', 'Unassigned', 'Não atribuída')[language_index(lang)])
            if value:
                parts.append('**' + labels[key] + ':** ' + _plain_md(_markdown_text(redact(str(value)), lang)))
    return '\n\n'.join(parts)


def project(source, options):
    """Pure projection and exact inclusion plan, selected by immutable identities."""
    if not isinstance(options, dict) or set(options) - OPTION_KEYS:
        raise ValueError(backend_message('Opciones de destinatario desconocidas / Unknown audience options'))
    from input_guard import ensure_data_tree
    ensure_data_tree(options)
    ensure_data_tree(source)
    profile = options.get('profile')
    if profile not in PROFILES:
        raise ValueError(backend_message('Destinatario inválido / Invalid audience'))
    if len(source.get('findings') or []) > MAX_FINDINGS:
        raise ValueError(backend_message('Máximo 1000 hallazgos por selección / Maximum 1000 findings per selection'))
    findings = source.get('findings') or []
    pool = {row.get('uid'): row for row in findings}
    if any(not isinstance(uid, str) or not workflows.UID.fullmatch(uid) for uid in pool) or len(pool) != len(findings):
        raise ValueError(backend_message('Abre el proyecto para asignar identidades estables antes de exportar / Open the project to assign stable identities before export'))
    if not pool and options.get('finding_uids') is None and profile != 'public':
        selected = []
    else:
        selected = _selection(options.get('finding_uids'), pool, 'finding_uids', profile == 'public')
    aliases = _aliases(options)
    lang = engine.report_language(source)
    excluded = ['originals', 'capture_inbox', 'private_backup', 'private_history', 'review_comments', 'editorial_reviews']
    selected_rows = [pool[uid] for uid in selected]
    if profile == 'technical':
        data = deepcopy(source)
        data['findings'] = deepcopy(selected_rows)
        linked_groups = {row.get('root_cause_uid') for row in selected_rows}
        if 'root_cause_groups' in data:
            data['root_cause_groups'] = [group for group in data['root_cause_groups'] if group.get('uid') in linked_groups]
        sections = list((source.get('report') or {}).get('sections') or [])
        automatic = workflows.report_sections(source)
        available = {row['key']: row for row in sections + automatic}
        requested = options.get('section_keys')
        if requested is not None:
            keys = _selection(requested, available, 'section_keys')
            kept = [deepcopy(row) for row in sections if row['key'] in keys]
            if not kept:
                # [] triggers the engine's legacy full-report fallback. A
                # deliberately empty authored section prevents that fallback.
                kept = [{'key': 'audience-selection', 'title': (('Selección técnica', 'Technical selection', 'Seleção técnica')[language_index(lang)]),
                         'body': (('Solo los bloques seleccionados.', 'Selected blocks only.', 'Apenas os blocos selecionados.')[language_index(lang)])}]
            data.setdefault('report', {})['sections'] = kept
            config = data['report'].setdefault('workflow', {})
            for key, section_key in [('include_assets', 'rg_assets'), ('include_coverage', 'rg_coverage'),
                                     ('include_retest', 'rg_retest'), ('include_root_causes', 'rg_root_causes')]:
                config[key] = section_key in keys
        else:
            keys = list(available)
        if isinstance(data.get('insights'), dict):
            data['insights'].pop('comments', None)
            data['insights'].pop('reviews', None)
            # Claims and risks of excluded findings never enter a derivative.
            for key in ('claims', 'risks'):
                data['insights'][key] = [row for row in data['insights'].get(key, []) if row.get('finding_uid') in selected]
        config = deepcopy(data.get('publication') or {})
        config['redactions'] = list(config.get('redactions') or []) + aliases
        publication.validate_config(config)
        data['publication'] = config
        included = ['selected_findings_full_content', 'selected_sections', 'enabled_assets_coverage_retest',
                    'cleaned_rendered_images', 'included_attachments', 'report_identity']
        data = publication.project(data)
        plan = dict(included=included, excluded=excluded + ['unselected_findings', 'unselected_sections'],
                    finding_count=len(selected), section_count=len(keys), originals=False,
                    attachments=any(row.get('include') for row in source.get('attachments', [])),
                    finding_uids=selected, section_keys=keys)
        # Annex declarations are removed by publication.project; retain them for
        # the existing safe capture boundary, never invent attachment inclusion.
        if source.get('attachments'):
            data['attachments'] = deepcopy(source['attachments'])
        return data, plan

    if 'section_keys' in options:
        raise ValueError(backend_message('Las secciones son seleccionables en el perfil técnico / Sections are selectable in the technical profile'))
    source_config = source.get('publication') or {}
    publication.validate_config(source_config)
    rules = list(source_config.get('redactions', [])) + aliases
    publication.validate_config({'redactions': rules})

    substitutions = publication.LiteralRedactions(rules)

    def redact(value):
        # Privacy decisions are literal, bounded and precede Markdown escaping.
        return substitutions.text(str(value or ''))

    meta = _meta(source, options, profile)
    for key in ('report_title', 'client'):
        meta[key] = redact(meta[key])
    data = {'meta': meta, 'report': {'sections': []}, 'findings': []}
    excluded += ['commands', 'raw_targets_paths', 'images', 'attachments', 'contacts', 'assets', 'coverage',
                 'retests', 'root_cause_groups', 'raw_evidence', 'unselected_findings', 'source_sections', 'custom_metadata']
    prefix = (('Resumen de dirección', 'Executive summary', 'Resumo executivo')[language_index(lang)])
    if profile == 'public':
        if any(type(options.get(key)) is not bool or options.get(key) is not True
               for key in ('review_confirmed', 'publish_consent')):
            raise ValueError(backend_message('Confirma revisión y autorización de publicación / Confirm review and permission to publish'))
        provenance = options.get('provenance_label')
        if provenance not in ('simulation', 'authorized'):
            raise ValueError(backend_message('Declara simulación o caso autorizado / Declare simulation or an authorized case'))
        if not aliases:
            raise ValueError(backend_message('Indica al menos una sustitución explícita de identidad / Supply at least one explicit identity substitution'))
        rows = options.get('approved_content')
        if not isinstance(rows, list) or len(rows) != len(selected):
            raise ValueError(backend_message('Escribe el contenido público aprobado para cada hallazgo seleccionado / Author approved public content for every selected finding'))
        approved = {}
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {'finding_uid', *PUBLIC_FIELDS}
                    or row.get('finding_uid') not in selected or row['finding_uid'] in approved):
                raise ValueError(backend_message('Contenido público inválido / Invalid public content'))
            approved[row['finding_uid']] = {key: _text(row[key], key, 300 if key == 'title' else MAX_TEXT, required=True) for key in PUBLIC_FIELDS}
        prefix = ((('SIMULACIÓN · CASO FICTICIO · SIN RETEST NUEVO', 'SIMULATION · FICTIONAL CASE · NO NEW RETEST', 'SIMULAÇÃO · CASO FICTÍCIO · SEM NOVO RETESTE')[language_index(lang)])) if provenance == 'simulation' else (
            (('AUTORIZACIÓN DE PUBLICACIÓN DECLARADA POR EL AUTOR', 'PUBLICATION PERMISSION DECLARED BY THE AUTHOR', 'AUTORIZAÇÃO DE PUBLICAÇÃO DECLARADA PELO AUTOR')[language_index(lang)]))
        data['meta']['report_subtitle'] = prefix
        data['meta']['branding']['confidential_text'] = (
            ((('SIMULACIÓN · CASO FICTICIO', 'SIMULATION · FICTIONAL CASE', 'SIMULAÇÃO · CASO FICTÍCIO')[language_index(lang)])) if provenance == 'simulation'
            else ((('PERMISO DECLARADO POR AUTOR', 'PERMISSION DECLARED BY AUTHOR', 'AUTORIZAÇÃO DECLARADA PELO AUTOR')[language_index(lang)])))
        body = ((('Extracto público seleccionado y revisado expresamente. Excluye la evaluación privada y las evidencias originales. La declaración del autor no acredita por sí sola la autorización de un tercero.', 'Explicitly selected and reviewed public derivative. It excludes the private assessment and original evidence. An author declaration is not independent verification of permission.', 'Versão derivada pública explicitamente selecionada e revisada. Exclui a avaliação privada e as evidências originais. Uma declaração do autor não constitui verificação independente da autorização.')[language_index(lang)]))
        for number, uid in enumerate(selected, 1):
            row = approved[uid]
            data['findings'].append({'id': f'F{number:03d}', 'mode': 'vuln', 'title': redact(row['title']),
                'description_md': _plain_md(redact(row['summary'])), 'impact_md': _plain_md(redact(row['impact'])),
                'remediation_md': _plain_md(redact(row['remediation']))})
        included = ['authored_public_title_alias', 'explicitly_approved_public_text', 'declared_publication_basis']
        excluded += ['source_titles', 'source_descriptions', 'source_impacts', 'source_remediations',
                     'technical_scores', 'source_finding_ids_uids', 'all_insights']
    else:
        body = ((('Extracto para decisiones. Severidad técnica y prioridad de negocio son distintas. La tolerancia permanece «No acordado» si no está documentada. No incluye evidencias originales.', 'Decision-oriented derivative. Technical severity and business priority are distinct. Risk tolerance remains “Not agreed” unless documented. No original evidence is included.', 'Versão derivada para decisões. Severidade técnica e prioridade de negócio são distintas. A tolerância ao risco permanece “Não acordada” se não estiver documentada. Nenhuma evidência original é incluída.')[language_index(lang)]))
        risks = (source.get('insights') or {}).get('risks', [])
        for number, (uid, row) in enumerate(zip(selected, selected_rows), 1):
            finding = {'id': f'F{number:03d}', 'mode': 'vuln', 'title': _markdown_text(redact(row.get('title', '')), lang),
                       'description_md': _plain_md(_markdown_text(redact(row.get('description_md') or row.get('summary_md', '')), lang)),
                       'impact_md': _plain_md(_markdown_text(redact(row.get('impact_md', '')), lang)),
                       'remediation_md': _plain_md(_markdown_text(redact(row.get('remediation_md', '')), lang))}
            for key in ('severity', 'cvss', 'cvss_vector', 'cvss_version'):
                if key in row:
                    finding[key] = deepcopy(row[key])
            risk = _risk_body(risks, uid, lang, redact)
            if risk:
                finding['remediation_md'] += '\n\n' + ((('### Decisión de negocio', '### Business decision', '### Decisão de negócio')[language_index(lang)])) + '\n\n' + risk
            data['findings'].append(finding)
        included = ['prose_titles_descriptions_impacts_remediation', 'technical_severity_cvss',
                    'structured_business_decisions', 'selected_client_alias_or_client']
        excluded += ['inline_code', 'code_blocks', 'link_targets', 'source_finding_ids_uids', 'claims']
    data['report']['sections'] = [{'key': 'audience-context', 'title': prefix, 'body': body},
                                  {'key': 'findings'}]
    data = publication.project(data)
    plan = dict(included=included, excluded=excluded, finding_count=len(selected), section_count=2,
                originals=False, attachments=False, finding_uids=selected,
                section_keys=['audience-context', 'findings'])
    return data, plan


def _issues(data, directory, profile):
    language = engine.report_language(data)
    if profile == 'technical':
        issues = workflows.preflight(data, directory, language)
    else:
        issues = [dict(level=level, message=message, path='audience', finding_uid=None,
                       help=backend_message('Review the selected derivative / Revisa el extracto seleccionado', en='Review the selected derivative', pt='Revise a versão derivada selecionada', language=language))
                  for level, message in validate.validate(data, lang=language)]
        issues.append(dict(level='warning', message=((('Este extracto omite deliberadamente reproducción y evidencia original; no es el informe técnico completo.', 'This derivative intentionally omits reproduction and original evidence; it is not a complete technical report.', 'Esta versão derivada omite deliberadamente a reprodução e as evidências originais; não é um relatório técnico completo.')[language_index(language)])),
            path='audience', finding_uid=None, help=backend_message('Conserva el informe técnico completo en privado', en='Keep the complete technical report private', pt='Mantenha o relatório técnico completo em privado', language=language)))
    content = ''
    if not any(row['level'] == 'error' for row in issues):
        tree = publication.render(data, directory)
        content = publication.rendered_text(tree.find('body'))
        if profile != 'technical' and any(
                not re.search(r'(?i)\[(?:redacted|censurado|ocultado)\]$', match[0])
                for _, pattern in publication.PATTERNS for match in pattern.finditer(content)):
            issues.append(dict(level='error', message=backend_message('El extracto contiene posibles secretos; censúralos antes de exportar / The derivative contains potential secrets; redact them before export', en='The derivative contains potential secrets; redact them before export', pt='A versão derivada contém possíveis segredos; oculte-os antes de exportar', language=language),
                               path='audience', finding_uid=None, help=backend_message('Use explicit literal substitutions / Usa sustituciones literales explícitas', en='Use explicit literal substitutions', pt='Use substituições literais explícitas', language=language)))
        from urllib.parse import unquote
        ids = set(tree.xpath('//*[@id]/@id'))
        missing = [ref for ref in tree.xpath('//a[starts-with(@href,"#")]/@href') if ref != '#' and unquote(ref[1:]) not in ids]
        if missing:
            issues.append(dict(level='error', message=backend_message('La selección deja referencias internas sin destino / Selection leaves broken internal references', en='Selection leaves broken internal references', pt='A seleção deixa referências internas sem destino', language=language),
                               path='audience', finding_uid=None, help=backend_message('Include the referenced finding or section / Incluye el hallazgo o la sección referenciada', en='Include the referenced finding or section', pt='Inclua o achado ou a seção referenciada', language=language)))
    return issues, content


def preview(source, directory, options):
    data, plan = project(source, options)
    issues, content = _issues(data, directory, options['profile'])
    return dict(profile=options['profile'], plan=plan, issues=issues,
                allowed_fields=list(PUBLIC_FIELDS) if options['profile'] == 'public' else [],
                content_text=content, data=data,
                available_sections=[{'key': row['key'], 'title': row.get('title', row['key'])}
                                    for row in list((source.get('report') or {}).get('sections') or []) + workflows.report_sections(source)]
                                   if options['profile'] == 'technical' else [])


def capture(source, directory, target, options):
    result = preview(source, directory, options)
    if any(issue['level'] == 'error' for issue in result['issues']):
        raise ValueError('; '.join(issue['message'] for issue in result['issues'] if issue['level'] == 'error'))
    captured = publication.snapshot(directory, target, data=result['data'])
    captured['attachments'] = {}
    if options['profile'] == 'technical':
        import attachments
        captured['attachments'] = attachments.capture(result['data'], directory, target)
    captured['issues'] = result['issues']
    # Stable private UIDs are useful in the local preview, never in the public
    # delivery manifest. Record decisions, field names and counts, not source text.
    captured['audience'] = dict(profile=options['profile'], plan={key: value for key, value in result['plan'].items()
                                                              if key not in ('finding_uids', 'section_keys')},
                                public_permission_declared=options.get('publish_consent') is True,
                                provenance_label=options.get('provenance_label') if options['profile'] == 'public' else None)
    return captured


def build(snapshot, formats, identity, label, captured, output_dir):
    """Use the native four-format verifier, then record the audience decision."""
    import delivery
    payload = delivery.build(snapshot, formats, identity, label, captured, output_dir)
    result = BytesIO()
    with zipfile.ZipFile(BytesIO(payload)) as source, zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as target:
        for member in source.infolist():
            blob = source.read(member.filename)
            if member.filename == 'verificacion.json':
                manifest = json.loads(blob)
                manifest['audience'] = deepcopy(captured['audience'])
                blob = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            target.writestr(member.filename, blob)
    return result.getvalue()
