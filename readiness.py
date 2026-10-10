"""Read-only delivery preparation facts, never a technical certification.

The saved project and its existing review remain authoritative. Nothing here
stores a second copy of editorial decisions or acknowledges warnings.
"""
import attachments
import publication
import validate


def checklist(data, directory, issues, lang='es'):
    en = lang == 'en'
    def tr(es, english): return english if en else es
    errors = sum(item['level'] == 'error' for item in issues)
    warnings = len(issues) - errors
    checks = [dict(key='review', status='blocked' if errors else 'attention' if warnings else 'checked',
                   title=tr('Revisión del informe', 'Report review'),
                   detail=tr(f'{errors} errores y {warnings} avisos en la revisión guardada.',
                             f'{errors} errors and {warnings} warnings in the saved review.'),
                   counts=dict(errors=errors, warnings=warnings))]
    structural = validate.structure_issues(data, lang)
    if structural:
        for key, title in [('annexes', tr('Anexos de la entrega', 'Delivery annexes')),
                           ('secrets', tr('Posibles secretos', 'Possible secrets')),
                           ('associations', tr('Asociaciones de evidencia', 'Evidence associations'))]:
            checks.append(dict(key=key, status='not_checked', title=title,
                               detail=tr('Corrige la estructura del informe antes de comprobar este punto.',
                                         'Correct the report structure before checking this item.')))
    else:
        rows = attachments.inventory(data, directory)
        selected = sum(row['status'] == 'included' for row in rows)
        required_pending = sum(row['required'] and row['status'] != 'included' for row in rows)
        selected_missing = sum(row['include'] and row['status'] != 'included' for row in rows)
        excluded = sum(not row['include'] for row in rows)
        pending_review = sum(not row['reviewed'] for row in rows)
        checks.append(dict(key='annexes',
            status='blocked' if required_pending or selected_missing else 'attention' if excluded or pending_review else 'checked',
            title=tr('Anexos de la entrega', 'Delivery annexes'),
            detail=tr(f'{selected} incluidos; {excluded} excluidos; {pending_review} sin revisión registrada; {required_pending} obligatorios pendientes. La revisión registrada es una decisión humana; los anexos no se censuran automáticamente.',
                      f'{selected} included; {excluded} excluded; {pending_review} without recorded review; {required_pending} required annexes pending. Recorded review is a human decision; annexes are not automatically redacted.'),
            counts=dict(included=selected, excluded=excluded, unreviewed=pending_review,
                        required_pending=required_pending, selected_missing=selected_missing)))
        try:
            inspected = publication.inspect_text(data, directory)
            alerts = inspected['alerts']
            exceptions = sum(bool(alert['reason'].strip()) for alert in alerts)
            pending = len(alerts) - exceptions
            checks.append(dict(key='secrets', status='attention' if pending else 'checked',
                title=tr('Posibles secretos', 'Possible secrets'),
                detail=tr(f'{pending} coincidencias sin excepción y {exceptions} con justificación en el texto que se publicará. Los patrones pueden omitir secretos; las imágenes y el contenido de los anexos necesitan revisión manual.',
                          f'{pending} matches without an exception and {exceptions} with a reason in outgoing text. Patterns can miss secrets; images and annex contents need manual review.'),
                counts=dict(unresolved=pending, excepted=exceptions), scope='outgoing_text_patterns'))
        except (ValueError, OSError):
            # Do not return rendered text, secret previews or resource paths in
            # this aggregate. The normal review/inspector provides diagnosis.
            checks.append(dict(key='secrets', status='not_checked', title=tr('Posibles secretos', 'Possible secrets'),
                detail=tr('No se pudo inspeccionar la publicación. Revisa los errores y vuelve a abrir el inspector.',
                          'Publication could not be inspected. Review errors and reopen the inspector.')))
        association_issues = [item for item in issues if
            item.get('path', '').endswith(('.asset_uids', '.evidence_uids', '.asset_uid')) or
            ('.retests[' in item.get('path', '') and item['level'] == 'error') or
            item.get('path', '').startswith('capture_inbox[')]
        broken = sum(item['level'] == 'error' for item in association_issues)
        attention = len(association_issues) - broken
        linked = {uid for finding in data.get('findings', []) for uid in finding.get('evidence_uids', [])}
        linked.update(uid for finding in data.get('findings', []) for row in finding.get('retests', [])
                      for uid in row.get('evidence_uids', []))
        unassociated = sum(row['uid'] not in linked for row in data.get('evidence', []))
        checks.append(dict(key='associations', status='blocked' if broken else 'attention' if attention or unassociated else 'checked',
            title=tr('Asociaciones de evidencia', 'Evidence associations'),
            detail=tr(f'{broken} errores de referencia; {attention} avisos de asociación; {unassociated} evidencias registradas sin asociación explícita a un hallazgo o retest. Una referencia válida no demuestra que la evidencia pruebe el hallazgo.',
                      f'{broken} reference errors; {attention} association warnings; {unassociated} registered evidence items without an explicit finding or retest association. A valid reference does not establish that evidence proves the finding.'),
            counts=dict(errors=broken, warnings=attention, without_explicit_association=unassociated)))
    checks.append(dict(key='human_review', status='manual', title=tr('Revisión humana', 'Human review'),
        detail=tr('Revisa alcance, hechos, severidad, reproducción y destinatario; abre los archivos generados antes de enviarlos. Esta lista no valida técnicamente el pentest ni autoriza su publicación.',
                  'Review scope, facts, severity, reproduction and recipient; open generated files before sending. This checklist does not technically validate the pentest or authorize publication.')))
    return dict(version=1, source='saved_project', technical_validation=False,
                manual_review_required=True, checks=checks)
