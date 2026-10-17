"""Portable report blocks for the senior assessment workflow.

All four exporters consume the same Markdown projection. Source records remain
unchanged, wide operational rows are split into readable tables and details.
"""
from languages import language_index
from urllib.parse import quote


def instance_sections(data):
    from engine import report_language
    from finding_instances import export_rows
    from workflows import RESULTS, md_text, table
    if not data.get('report', {}).get('workflow', {}).get('include_instances', True):
        return []
    language = report_language(data)
    slot = language_index(language)
    def tr(es, en, pt):
        return (es, en, pt)[slot]
    parts = []
    evidence = {row.get('uid'): row for row in data.get('evidence', [])}

    def append_evidence(identities):
        # Each occurrence/retest owns its proof. Repeating the same image in a
        # later observation retains that historical association in every format.
        for uid in identities:
            row = evidence.get(uid)
            if row and row.get('src'):
                caption = row.get('caption') or row.get('title') or tr('Evidencia', 'Evidence', 'Evidência')
                parts.append('![' + md_text(caption) + '](' + quote(row['src'], safe='/%') + ')')

    for finding in data.get('findings', []):
        if not finding.get('instances'):
            continue
        projection = export_rows(data, finding, language)
        summary = projection['summary']
        parts.append('### ' + md_text(finding.get('id', '') + ' · ' + (finding.get('title') or '')))
        parts.append(md_text(' · '.join(summary['labels'][key] + ': ' + str(value)
                                      for key, value in summary['counts'].items() if value)))
        indices = (0, 1, 3, 4, 5)
        parts.append(table([projection['headers'][i] for i in indices],
                           [[row[i] for i in indices] for row in projection['rows']]))
        for record in projection['rows']:
            parts.append('#### ' + tr('Instancia ', 'Instance ', 'Instância ') + md_text(record[0]))
            for index in (2, 6, 7, 8):
                if record[index]:
                    parts.append('**' + md_text(projection['headers'][index]) + ':** ' + md_text(record[index]))
            instance = finding['instances'][int(record[0]) - 1]
            append_evidence(instance.get('evidence_uids', []))
            for retest in instance.get('retests', []):
                details = ' · '.join(value for value in (retest.get('tested_on', ''),
                                     RESULTS[retest['result']][slot]) if value)
                parts.append('**' + tr('Retest ', 'Retest ', 'Reteste ') + md_text(details) + '**')
                parts.append('**' + tr('Evaluador', 'Assessor', 'Avaliador') + ':** ' + md_text(retest.get('assessor', '')))
                if retest.get('notes_md'):
                    parts.append(retest['notes_md'])
                append_evidence(retest.get('evidence_uids', []))
    return ([{'key': 'rg_instances', 'title': tr('Instancias afectadas y exposición residual',
             'Affected instances and residual exposure', 'Instâncias afetadas e exposição residual'),
              'body': '\n\n'.join(parts)}] if parts else [])


def report_sections(data):
    from test_plans import report_sections as cases
    from attack_paths import report_sections as paths
    return instance_sections(data) + cases(data) + paths(data)
