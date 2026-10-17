"""Read-only delivery preparation facts, never a technical certification.

The saved project and its existing review remain authoritative. Nothing here
stores a second copy of editorial decisions or acknowledges warnings.
"""
from languages import language_index
import attachments
import publication
import validate
import re


def docx_url_compatibility(data, directory, lang='es'):
    """Find long *visible* URLs in the outgoing report, never hidden targets.

    This is a content heuristic, not a rendered line-break measurement. It is
    intentionally separate from the blocking review and its completion count.
    """
    import engine
    tree = publication.render(data, directory)
    labels = engine.load_lang(engine.report_language(data))['labels']
    public = publication.project(data)
    findings = {f.get('id'): (index, f) for index, f in enumerate(public.get('findings', []))}
    sections = {s.get('key'): index for index, s in enumerate(public.get('report', {}).get('sections', []))}
    blocks = tree.xpath('//body//*[self::p or self::li or self::td or self::th or self::pre or '
                        'self::h1 or self::h2 or self::h3 or self::h4 or self::figcaption]')
    selected = set(blocks)
    locations = {}
    pattern = re.compile(r'https?://[^\s<>"\']{88,}', re.I)
    for node in blocks:
        # The outermost selected block retains inline formatting boundaries;
        # avoiding descendant blocks counts each visible occurrence once.
        if any(parent in selected for parent in node.iterancestors()):
            continue
        count = sum(len(match[0].rstrip('.,;:!?')) >= 96
                    for match in pattern.finditer(publication.rendered_text(node)))
        if not count:
            continue
        parents = [node, *node.iterancestors()]
        finding = next((p for p in parents if 'finding' in p.get('class', '').split()), None)
        section = next((p for p in parents if p.tag == 'section' and p.get('id')), None)
        if finding is not None and finding.get('id') in findings:
            index, f = findings[finding.get('id')]
            path = f'findings[{index}]'
            field = next((p for p in parents if 'finding-field' in p.get('class', '').split()), None)
            field_label = ''
            if field is not None:
                headings = field.xpath('./h3')
                field_label = headings[0].text_content().strip() if headings else ''
                names = {'description_md': 'desc_root', 'impact_md': 'impact',
                         'remediation_md': 'remediation', 'references': 'references'}
                key = next((key for key, label in names.items() if labels[label] == field_label), None)
                if key:
                    path += '.' + key
            location = dict(path=path, finding_uid=f.get('uid'),
                            label=f.get('id', '') + ' · ' + (f.get('title') or (f.get('host') or {}).get('name') or '')
                                  + (' · ' + field_label if field_label else ''))
        else:
            key = section.get('id') if section is not None else 'cover'
            path = f'report.sections[{sections[key]}]' if key in sections else 'meta'
            heading = section.xpath('./h1|./h2') if section is not None else []
            label = heading[0].text_content().strip() if heading else ('Portada', 'Cover', 'Capa')[language_index(lang)]
            location = dict(path=path, section_key=key, label=label)
        identity = (location.get('finding_uid'), location.get('section_key'), path)
        entry = locations.setdefault(identity, {**location, 'count': 0})
        entry['count'] += count
    rows = list(locations.values())
    return dict(format='docx', status='attention' if rows else 'not_applicable',
                heuristic=True, minimum_characters=96, count=sum(row['count'] for row in rows), locations=rows)


def checklist(data, directory, issues, lang='es'):
    index = language_index(lang)
    def tr(es, english, portuguese): return (es, english, portuguese)[index]
    errors = sum(item['level'] == 'error' for item in issues)
    warnings = len(issues) - errors
    checks = [dict(key='review', status='blocked' if errors else 'attention' if warnings else 'checked',
                   title=tr('Revisión del informe', 'Report review', 'Revisão do relatório'),
                   detail=tr(f'{errors} errores y {warnings} avisos en la revisión guardada.',
                             f'{errors} errors and {warnings} warnings in the saved review.', f'{errors} erros e {warnings} avisos na revisão salva.'),
                   counts=dict(errors=errors, warnings=warnings))]
    compatibility = None
    structural = validate.structure_issues(data, lang)
    if structural:
        for key, title in [('annexes', tr('Anexos de la entrega', 'Delivery annexes', 'Anexos da entrega')),
                           ('secrets', tr('Posibles secretos', 'Possible secrets', 'Possíveis segredos')),
                           ('associations', tr('Asociaciones de evidencia', 'Evidence associations', 'Associações de evidências'))]:
            checks.append(dict(key=key, status='not_checked', title=title,
                               detail=tr('Corrige la estructura del informe antes de comprobar este punto.',
                                         'Correct the report structure before checking this item.', 'Corrija a estrutura do relatório antes de verificar este item.')))
    else:
        rows = attachments.inventory(data, directory)
        selected = sum(row['status'] == 'included' for row in rows)
        required_pending = sum(row['required'] and row['status'] != 'included' for row in rows)
        selected_missing = sum(row['include'] and row['status'] != 'included' for row in rows)
        excluded = sum(not row['include'] for row in rows)
        pending_review = sum(not row['reviewed'] for row in rows)
        checks.append(dict(key='annexes',
            status='blocked' if required_pending or selected_missing else 'attention' if excluded or pending_review else 'checked',
            title=tr('Anexos de la entrega', 'Delivery annexes', 'Anexos da entrega'),
            detail=tr(f'{selected} incluidos; {excluded} excluidos; {pending_review} sin revisión registrada; {required_pending} obligatorios pendientes. La revisión registrada es una decisión humana; los anexos no se censuran automáticamente.',
                      f'{selected} included; {excluded} excluded; {pending_review} without recorded review; {required_pending} required annexes pending. Recorded review is a human decision; annexes are not automatically redacted.', f'{selected} incluídos; {excluded} excluídos; {pending_review} sem revisão registrada; {required_pending} anexos obrigatórios pendentes. A revisão registrada é uma decisão humana; os anexos não são ocultados automaticamente.'),
            counts=dict(included=selected, excluded=excluded, unreviewed=pending_review,
                        required_pending=required_pending, selected_missing=selected_missing)))
        try:
            inspected = publication.inspect_text(data, directory)
            compatibility = docx_url_compatibility(data, directory, lang)
            alerts = inspected['alerts']
            exceptions = sum(bool(alert['reason'].strip()) for alert in alerts)
            pending = len(alerts) - exceptions
            checks.append(dict(key='secrets', status='attention' if pending else 'checked',
                title=tr('Posibles secretos', 'Possible secrets', 'Possíveis segredos'),
                detail=tr(f'{pending} coincidencias sin excepción y {exceptions} con justificación en el texto que se publicará. Los patrones pueden omitir secretos; las imágenes y el contenido de los anexos necesitan revisión manual.',
                          f'{pending} matches without an exception and {exceptions} with a reason in outgoing text. Patterns can miss secrets; images and annex contents need manual review.', f'{pending} correspondências sem exceção e {exceptions} com justificativa no texto a publicar. Os padrões podem deixar de identificar segredos; imagens e conteúdo dos anexos exigem revisão manual.'),
                counts=dict(unresolved=pending, excepted=exceptions), scope='outgoing_text_patterns'))
        except (ValueError, OSError):
            # Do not return rendered text, secret previews or resource paths in
            # this aggregate. The normal review/inspector provides diagnosis.
            checks.append(dict(key='secrets', status='not_checked', title=tr('Posibles secretos', 'Possible secrets', 'Possíveis segredos'),
                detail=tr('No se pudo inspeccionar la publicación. Revisa los errores y vuelve a abrir el inspector.',
                          'Publication could not be inspected. Review errors and reopen the inspector.', 'Não foi possível inspecionar a publicação. Revise os erros e abra o inspetor novamente.')))
        association_issues = [item for item in issues if
            item.get('path', '').endswith(('.asset_uids', '.evidence_uids', '.asset_uid')) or
            ('.retests[' in item.get('path', '') and item['level'] == 'error') or
            item.get('path', '').startswith('capture_inbox[')]
        broken = sum(item['level'] == 'error' for item in association_issues)
        attention = len(association_issues) - broken
        linked = {uid for finding in data.get('findings', []) for uid in finding.get('evidence_uids', [])}
        linked.update(uid for finding in data.get('findings', []) for row in finding.get('retests', [])
                      for uid in row.get('evidence_uids', []))
        linked.update(uid for finding in data.get('findings', []) for instance in finding.get('instances', [])
                      for uid in instance.get('evidence_uids', []))
        linked.update(uid for finding in data.get('findings', []) for instance in finding.get('instances', [])
                      for row in instance.get('retests', []) for uid in row.get('evidence_uids', []))
        unassociated = sum(row['uid'] not in linked for row in data.get('evidence', []))
        checks.append(dict(key='associations', status='blocked' if broken else 'attention' if attention or unassociated else 'checked',
            title=tr('Asociaciones de evidencia', 'Evidence associations', 'Associações de evidências'),
            detail=tr(f'{broken} errores de referencia; {attention} avisos de asociación; {unassociated} evidencias registradas sin asociación explícita a un hallazgo, instancia o retest. Una referencia válida no demuestra que la evidencia pruebe el hallazgo.',
                      f'{broken} reference errors; {attention} association warnings; {unassociated} registered evidence items without an explicit finding, instance or retest association. A valid reference does not establish that evidence proves the finding.', f'{broken} erros de referência; {attention} avisos de associação; {unassociated} evidências registradas sem associação explícita a um achado, instância ou reteste. Uma referência válida não demonstra que a evidência comprove o achado.'),
            counts=dict(errors=broken, warnings=attention, without_explicit_association=unassociated)))
    checks.append(dict(key='human_review', status='manual', title=tr('Revisión humana', 'Human review', 'Revisão humana'),
        detail=tr('Revisa alcance, hechos, severidad, reproducción y destinatario; abre los archivos generados antes de enviarlos. Esta lista no valida técnicamente el pentest ni autoriza su publicación.',
                  'Review scope, facts, severity, reproduction and recipient; open generated files before sending. This checklist does not technically validate the pentest or authorize publication.', 'Revise o escopo, os fatos, a severidade, a reprodução e o destinatário; abra os arquivos gerados antes de enviá-los. Esta lista não valida tecnicamente o pentest nem autoriza sua publicação.')))
    result = dict(version=1, source='saved_project', technical_validation=False,
                  manual_review_required=True, checks=checks)
    if compatibility and compatibility['count']:
        result['compatibility'] = compatibility
    return result
