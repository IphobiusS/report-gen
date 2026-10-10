"""Portable HTML contract in a real browser (optional Chromium/Playwright runtime).

Set REPORT_GEN_CHROMIUM to a Chromium executable and, when Playwright is not on
Node's module path, REPORT_GEN_PLAYWRIGHT_MODULE to the installed module.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import portable_report
import workflows
from wizard import dump_yaml


@pytest.fixture(params=[('es', 'sections'), ('en', 'sections'), ('es', 'legacy'), ('en', 'legacy')])
def portable_html(tmp_path, request):
    lang, layout = request.param
    source = {
        'meta': {'report_title': 'Portable browser contract', 'lang': lang,
                 'client': 'CLIENT' * 80, 'assessor': 'ASSESSOR' * 80},
        'findings': [
            {'id': 'F01', 'mode': 'vuln', 'title': 'Alpha issue', 'severity': 'high',
             'description_md': 'alpha sentinel\n\n' + 'Z' * 900 + '\n\n| Target | Value |\n| --- | --- |\n| host | ' + 'T' * 700 + ' |',
             'impact_md': 'Business impact', 'remediation_md': 'Correct alpha',
             'walkthrough': [{'command': 'printf ' + 'C' * 900}]},
            {'id': 'F02', 'mode': 'vuln', 'title': 'Beta issue', 'severity': 'low',
             'description_md': 'beta sentinel\n\ncafe\u0301', 'remediation_md': 'Correct beta'},
            {'id': 'F03', 'mode': 'vuln', 'title': 'Gamma issue',
             'description_md': 'gamma sentinel\n\ncafé', 'remediation_md': 'Assess gamma'},
            {'id': 'M01', 'mode': 'machine', 'title': 'Machine delta',
             'host': {'name': 'Machine delta'}, 'walkthrough': [{'command': 'echo delta sentinel'}]},
        ],
    }
    if layout == 'sections':
        source['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    # The legacy fixture deliberately exercises base.html, including its links.
    data = workflows.normalize(source)
    if layout == 'legacy':
        data.pop('report', None)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    target = tmp_path / 'report.html'
    target.write_text(portable_report.build(tmp_path), encoding='utf-8')
    return target


def check_browser(portable_html, scenario):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for real-browser checks')
    result = subprocess.run(
        ['node', str(Path(__file__).with_name('portable_report_browser.cjs')),
         scenario, str(portable_html)],
        capture_output=True, text=True, timeout=60, env=os.environ.copy(),
    )
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr


def test_portable_reflows_without_hiding_content(portable_html):
    check_browser(portable_html, 'layout')


def test_portable_reopening_current_hash_reveals_filtered_finding(portable_html):
    check_browser(portable_html, 'same_hash')


def test_portable_anchors_clear_actual_sticky_toolbar(portable_html):
    check_browser(portable_html, 'anchors')


def test_portable_keyboard_filters_nojs_and_print_contract(portable_html):
    check_browser(portable_html, 'behavior')


def test_portable_search_matches_canonically_equivalent_unicode(portable_html):
    check_browser(portable_html, 'unicode')
