"""Portable tables keep their content, semantics and readable numeric expressions."""
import os
from pathlib import Path
import shutil
import subprocess

from lxml import html
import pytest

import delivery
import export_contract
import portable_report
import publication
import workflows
from wizard import dump_yaml


@pytest.fixture(params=[('es', 'sections'), ('en', 'sections'), ('es', 'legacy'), ('en', 'legacy')])
def report(tmp_path, request):
    language, layout = request.param
    description = ('Descripción con una tabla comparativa.\n\n'
                   '| ID | Inherente | Actual | Residual | Decisión |\n'
                   '| --- | --- | --- | --- | --- |\n'
                   '| F02 | 4×5=20 | 20 | 4×4=16 | Revisar controles de autorización. |\n'
                   '| F03 | 3×4=12 | 12 | 2×3=6 | Mantener seguimiento del caso. |\n\n'
                   '| Dimensión | Criterio |\n'
                   '| --- | --- |\n'
                   '| Disponibilidad | Recuperación de los servicios durante una interrupción. |\n'
                   '| Fraude | Detección y revisión independiente de operaciones. |\n')
    data = {'meta': {'report_title': 'Portable tables contract', 'theme': 'serio', 'lang': language,
                     'client': 'Entidad sintética', 'assessor': 'Analista sintético'},
            'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Autoaprobación de pagos por el preparador',
                          'severity': 'info', 'cvss': 0, 'description_md': description,
                          'impact_md': 'Información sintética para verificar la distribución de columnas.',
                          'remediation_md': 'Comprobar el contrato de lectura.',
                          'walkthrough': [{'command': "printf 'SIMULACION\\n'"}]}]}
    if layout == 'sections':
        data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    workflows.normalize(data)
    if layout == 'legacy':
        data.pop('report', None)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    original = publication.render(data, tmp_path)
    target = tmp_path / 'report.html'
    target.write_text(portable_report.build(tmp_path), encoding='utf-8')
    return {'path': target, 'root': tmp_path, 'data': data, 'original': original}


def browser_check(report, scenario):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for real-browser checks')
    result = subprocess.run(
        ['node', str(Path(__file__).with_name('portable_tables_0215.cjs')), scenario, str(report['path'])],
        capture_output=True, text=True, timeout=60, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr


def test_field_labels_are_bounded_and_values_stack_without_losing_semantics(report):
    browser_check(report, 'fields')


def test_comparison_expressions_remain_readable_in_keyboard_scroll_regions(report):
    browser_check(report, 'comparison')


def test_streaming_reserves_toolbar_without_exposing_unwired_controls(report):
    browser_check(report, 'streaming')


def test_table_reflow_preserves_source_rows_and_export_semantics(report):
    def inventory(tree):
        return [[[export_contract.normal(cell.text_content()) for cell in row if cell.tag in ('th', 'td')]
                 for row in table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')]
                for table in tree.xpath('//table')]
    tree = html.document_fromstring(report['path'].read_text())
    assert inventory(tree) == inventory(report['original'])
    assert len(tree.xpath('//th')) == len(report['original'].xpath('//th'))
    assert len(tree.xpath('//td')) == len(report['original'].xpath('//td'))
    # The TD/TD cover table is layout, distinct from comparative THEAD tables.
    for table in tree.xpath('//section[contains(concat(" ",normalize-space(@class)," ")," cover ")]//table[not(thead)]'):
        assert not table.xpath('ancestor::div[contains(concat(" ",normalize-space(@class)," ")," report-table-region ")]')
    assert tree.xpath('//*[@id]/@id') == report['original'].xpath('//*[@id]/@id') or (
        # The portable shell adds its established reading controls; report IDs stay exact.
        tree.xpath('//main/div[@class="report-content"]//*[@id]/@id') == report['original'].xpath('//body//*[@id]/@id'))
    captured = delivery.capture(report['root'], report['root'] / 'snapshot')
    checks = delivery.inspect_export(report['path'], 'html', captured)
    assert checks['metadata_values_checked'] >= 1
    assert checks['content_units_checked'] >= 1
    assert checks['structure_units_checked'] >= 1
