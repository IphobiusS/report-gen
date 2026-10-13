"""Read-only retest matrix from the author's recorded project observations.

This projection neither normalizes a legacy document nor changes report output.
Evidence counts describe explicit UID links to registry entries, never file
integrity, sufficiency, technical approval, or completion of a pentest.
"""
from languages import language_index
from error_messages import message as backend_message
from collections import Counter
from datetime import date
import re

import workflows

OUTCOMES = {
    **workflows.RESULTS,
    'not_run': ('Sin observaciones registradas', 'No recorded observations', 'Sem observações registradas'),
    'undated': ('Sin fecha válida para ordenar', 'No valid date for ordering', 'Sem data válida para ordenar'),
    'invalid_result': ('Resultado no reconocido', 'Unrecognized result', 'Resultado não reconhecido'),
}
SEVERITIES = {'critical': ('Crítica', 'Critical', 'Crítica'), 'high': ('Alta', 'High', 'Alta'),
              'medium': ('Media', 'Medium', 'Média'), 'low': ('Baja', 'Low', 'Baixa'),
              'info': ('Informativa', 'Informational', 'Informativa')}


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _text(value):
    return value if isinstance(value, str) else ''


def _valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def summarize(data, lang='es'):
    """Derive saved-document facts without reading resources or writing data.

    Canonical, valid ISO dates rank observations; append order breaks ties as
    in workflows.latest_retest. Undated/invalid-date records remain visible as
    excluded observations. A later unrecognized result cannot reveal an older
    'fixed' record as the latest result. No UID is allocated to legacy records.
    """
    if not isinstance(data, dict):
        raise ValueError(backend_message('El proyecto debe ser un objeto / Project must be an object'))
    for key in ('findings', 'assets', 'evidence', 'coverage'):
        value = data.get(key, [])
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise ValueError(backend_message('{p0}: estructura no reconocida / unrecognized structure', p0=key))
    for finding in data.get('findings', []):
        value = finding.get('retests', [])
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise ValueError(backend_message('retests: estructura no reconocida / unrecognized structure'))
    language_slot = language_index(lang)
    def tr(es, english, portuguese): return (es, english, portuguese)[language_slot]
    def label(labels, key, unknown):
        return labels[key][language_slot] if key in labels else unknown

    findings = _rows(data.get('findings', []))
    assets = _rows(data.get('assets', []))
    evidence = _rows(data.get('evidence', []))
    coverage = _rows(data.get('coverage', []))
    all_rows = findings + assets + evidence + coverage
    all_rows += [row for finding in findings for row in _rows(finding.get('retests', []))]
    identities = Counter(row['uid'] for row in all_rows
                         if isinstance(row.get('uid'), str) and workflows.UID.fullmatch(row['uid']))

    def registry(records):
        index = {}
        for record in records:
            if isinstance(record.get('uid'), str):
                index.setdefault(record['uid'], []).append(record)
        return index
    asset_registry, evidence_registry = registry(assets), registry(evidence)

    def identity(row):
        uid = row.get('uid')
        if uid is None or uid == '': return 'missing'
        if not isinstance(uid, str) or not workflows.UID.fullmatch(uid): return 'invalid'
        return 'duplicate' if identities[uid] != 1 else 'unique'

    def links(refs, pool):
        result = dict(registered=0, missing=0, ambiguous=0, invalid=0, items=[])
        if not isinstance(refs, list):
            result['invalid'] = 1
            return result
        # Count each explicit UID once; a repeated association does not create
        # another asset or another piece of evidence.
        seen = set()
        for uid in refs:
            if not isinstance(uid, str) or not workflows.UID.fullmatch(uid):
                result['invalid'] += 1
                continue
            if uid in seen: continue
            seen.add(uid)
            matches = pool.get(uid, [])
            if not matches:
                result['missing'] += 1
            elif len(matches) != 1 or identities[uid] != 1:
                result['ambiguous'] += 1
            else:
                result['registered'] += 1
                record = matches[0]
                result['items'].append(dict(uid=uid, label=_text(record.get('name') or record.get('title') or record.get('target')) or uid))
        return result

    rows = []
    severity_filters = {}
    status_filters = {}
    result_counts = dict.fromkeys(OUTCOMES, 0)
    for index, finding in enumerate(findings):
        observations = _rows(finding.get('retests', []))
        dated = [(i, record) for i, record in enumerate(observations) if _valid_date(record.get('tested_on'))]
        latest = max(dated, key=lambda pair: (pair[1]['tested_on'], pair[0])) if dated else None
        outcome = latest[1].get('result') if latest else 'undated' if observations else 'not_run'
        if latest and (not isinstance(outcome, str) or outcome not in workflows.RESULTS): outcome = 'invalid_result'
        result_counts[outcome] += 1
        status = _text(finding.get('status')) or 'unrecorded'
        verification = _text(finding.get('verification')) or 'unrecorded'
        severity = _text(finding.get('severity')) or 'unrecorded'
        status_label = label(workflows.STATUSES, status, tr('Sin estado registrado', 'No recorded status', 'Sem estado registrado') if status == 'unrecorded' else tr('Estado no reconocido: ', 'Unrecognized status: ', 'Estado não reconhecido: ') + status)
        verification_label = label(workflows.VERIFICATIONS, verification, tr('Sin verificación registrada', 'No recorded verification', 'Sem verificação registrada') if verification == 'unrecorded' else tr('Verificación no reconocida: ', 'Unrecognized verification: ', 'Verificação não reconhecida: ') + verification)
        severity_label = label(SEVERITIES, severity, tr('Pendiente de valoración', 'Pending assessment', 'Avaliação pendente') if severity == 'unrecorded' else tr('Severidad no reconocida: ', 'Unrecognized severity: ', 'Severidade não reconhecida: ') + severity)
        status_filters[status] = status_label
        severity_filters[severity] = severity_label
        original_evidence = links(finding.get('evidence_uids', []), evidence_registry)
        retest_evidence = links(latest[1].get('evidence_uids', []), evidence_registry) if latest else links([], evidence_registry)
        asset_links = links(finding.get('asset_uids', []), asset_registry)
        excluded_dates = len(observations) - len(dated)
        notices = []
        identity_status = identity(finding)
        if identity_status != 'unique':
            notices.append(dict(key='finding_identity', text=tr('Referencia permanente ausente, inválida o duplicada; no se puede abrir un destino único.', 'Permanent reference is missing, invalid or duplicated; a unique destination cannot be opened.', 'A referência permanente está ausente, inválida ou duplicada; não é possível abrir um destino único.')))
        if excluded_dates:
            notices.append(dict(key='excluded_dates', text=tr(f'{excluded_dates} observaciones sin fecha ISO válida; no intervienen en el último resultado.', f'{excluded_dates} observations without a valid ISO date; excluded from latest-result ordering.', f'{excluded_dates} observações sem data ISO válida; excluídas da ordenação do último resultado.')))
        if status == 'reported_fixed':
            notices.append(dict(key='reported_fix', text=tr('La corrección comunicada es un estado de seguimiento; no demuestra una corrección técnica.', 'A reported fix is a tracking status; it does not demonstrate a technical fix.', 'Uma correção comunicada é um estado de acompanhamento; ela não demonstra uma correção técnica.')))
        if status == 'verified_fixed' and outcome != 'fixed':
            notices.append(dict(key='contradictory_status', text=tr('El estado indica corregido y verificado, pero el último resultado fechado no es «Corregido».', 'Status says verified fixed, but the latest dated result is not “Fixed”.', 'O estado indica corrigido e verificado, mas o último resultado datado não é “Corrigido”.')))
        if outcome == 'fixed' and not retest_evidence['registered']:
            notices.append(dict(key='fixed_without_linked_evidence', text=tr('El resultado registrado es «Corregido» sin evidencia del retest vinculada por UID.', 'The recorded result is “Fixed” without retest evidence linked by UID.', 'O resultado registrado é “Corrigido” sem evidência de reteste vinculada por UID.')))
        broken = sum(group[key] for group in (original_evidence, retest_evidence, asset_links) for key in ('missing', 'ambiguous', 'invalid'))
        if broken:
            notices.append(dict(key='broken_associations', text=tr(f'{broken} asociaciones inexistentes, ambiguas o inválidas; no se cuentan como elementos registrados.', f'{broken} missing, ambiguous or invalid associations; not counted as registered items.', f'{broken} associações ausentes, ambíguas ou inválidas; não contadas como itens registrados.')))
        if outcome == 'invalid_result':
            notices.append(dict(key='invalid_result', text=tr('El último registro fechado tiene un resultado no reconocido; revisa el dato original.', 'The latest dated record has an unrecognized result; review the original data.', 'O último registro datado possui um resultado não reconhecido; revise os dados originais.')))
        latest_record = None
        if latest:
            record_index, record = latest
            latest_record = dict(record_index=record_index, uid=_text(record.get('uid')) or None,
                                 identity_status=identity(record), tested_on=record['tested_on'],
                                 assessor=_text(record.get('assessor')), result=_text(record.get('result')),
                                 evidence=retest_evidence)
        rows.append(dict(key=f'finding:{index}', finding_uid=_text(finding.get('uid')) or None,
                         identity_status=identity_status, display_id=_text(finding.get('id')),
                         title=_text(finding.get('title')), severity=severity, severity_label=severity_label,
                         status=status, status_label=status_label, verification=verification,
                         verification_label=verification_label, outcome=outcome,
                         outcome_label=OUTCOMES[outcome][language_slot], observations=len(observations),
                         excluded_dates=excluded_dates, latest=latest_record,
                         original_evidence=original_evidence, retest_evidence=retest_evidence,
                         assets=asset_links, notices=notices))

    coverage_counts = dict.fromkeys(workflows.COVERAGE, 0)
    coverage_counts.update(unrecorded=0, invalid=0)
    for record in coverage:
        key = record.get('status')
        coverage_counts[key if isinstance(key, str) and key in workflows.COVERAGE else 'unrecorded' if key in (None, '') else 'invalid'] += 1
    return dict(version=1, source='saved_project', technical_validation=False,
                exported_content_unchanged=True, total_findings=len(rows), rows=rows,
                result_counts=result_counts,
                result_labels={key: labels[language_slot] for key, labels in OUTCOMES.items()},
                coverage=dict(registered=len(coverage), counts=coverage_counts,
                              labels={**{key: labels[language_slot] for key, labels in workflows.COVERAGE.items()},
                                      'unrecorded': tr('Sin estado registrado', 'No recorded status', 'Sem estado registrado'),
                                      'invalid': tr('Estado no reconocido', 'Unrecognized status', 'Estado não reconhecido')}),
                filters=dict(statuses=[dict(key=key, label=value) for key, value in status_filters.items()],
                             severities=[dict(key=key, label=value) for key, value in severity_filters.items()],
                             assets=[dict(key=asset['uid'], label=_text(asset.get('name') or asset.get('target')) or asset['uid']) for asset in assets if identity(asset) == 'unique']),
                scope=[tr('El gráfico resume únicamente el último resultado fechado registrado por hallazgo; no certifica la corrección ni el alcance del pentest.', 'The chart summarizes only each finding’s latest dated recorded result; it does not certify remediation or pentest coverage.', 'O gráfico resume apenas o último resultado datado registrado para cada achado; não certifica a remediação nem a cobertura do pentest.'),
                       tr('Estado de seguimiento, verificación técnica y resultado de retest se muestran por separado. Sin observaciones significa que no hay registros; no demuestra que una prueba no se haya ejecutado.', 'Tracking status, technical verification and retest result are shown separately. No observations means there are no records; it does not establish that a test was not performed.', 'O estado de acompanhamento, a verificação técnica e o resultado do reteste são mostrados separadamente. Sem observações significa que não há registros; não demonstra que um teste não foi realizado.'),
                       tr('Las asociaciones cuentan referencias UID únicas a registros existentes. No comprueban archivos, calidad de evidencia ni contenido de capturas o anexos.', 'Associations count unique UID references to existing registry entries. They do not check files, evidence quality, or capture and annex content.', 'As associações contam referências UID únicas a registros existentes. Elas não verificam arquivos, qualidade das evidências nem conteúdo de capturas e anexos.'),
                       tr('Esta vista ejecutiva es de lectura y no se añade a PDF, DOCX o Markdown. Las opciones de inclusión del autor siguen controlando las exportaciones existentes.', 'This executive view is read-only and is not added to PDF, DOCX or Markdown. The author’s inclusion settings still control existing exports.', 'Esta visão executiva é somente leitura e não é adicionada ao PDF, DOCX ou Markdown. As configurações de inclusão do autor continuam controlando as exportações existentes.')])
