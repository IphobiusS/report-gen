"""Nested prose remains readable alongside wide tables at narrow/zoomed widths."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import portable_report
import workflows
import design_library
from design_samples import sample_data
from wizard import dump_yaml


@pytest.mark.parametrize('lang', ['es', 'en'])
@pytest.mark.parametrize('density', ['comfortable', 'compact'])
@pytest.mark.parametrize('profile', ['offsec-oscp', 'htb-cpts'])
def test_nested_quotes_lists_and_wide_table_keep_content_readable(tmp_path, lang, density, profile):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    url = 'https://cobalt.example.test/' + 'segment/' * 16 + 'endpoint?approval=' + 'a' * 120
    body = (f'> QUOTE-ONE [{url}]({url}).\n>\n'
            '> > QUOTE-TWO retains its readable line width.\n\n'
            '1. LIST-ONE\n    1. LIST-TWO\n'
            f'        1. LIST-THREE [{url}]({url}).\n\n'
            '| ID | Owner | URL | Numeric | Status | Notes | Extra | Date |\n'
            '| --- | --- | --- | --- | --- | --- | --- | --- |\n'
            f'| F01 | Treasury | `{url}` | 123456.78 | Pending | Notes | Value | TABLE-END |\n\n'
            f'```text\ncurl --silent {url}\n```\n\n'
            '1234567890. LARGE-COUNTER-ONE retains its complete native number.\n'
            '1234567891. LARGE-COUNTER-TWO retains its complete native number.\n\nNARRATIVE-END')
    data = {'meta': {'report_title': 'Nested flow contract', 'theme': 'corporativo',
                     'lang': lang, 'report_density': density,
                     'branding': {'wordmark': 'LAYOUT LAB',
                                  'confidential_text': 'CONFIDENCIAL' if lang == 'es' else 'CONFIDENTIAL'}},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Nested evidence',
                          'severity': 'high', 'description_md': body}]}
    # Both bundled provider logo families must reflow alongside the certificate
    # name without clipping the mark when the report is narrow or enlarged.
    data['meta']['design'] = sample_data(design_library.profile(profile), 'brand', lang)['meta']['design']
    workflows.normalize(data)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    result = subprocess.run(['node', str(Path(__file__).with_name('portable_nested_flow_0322.cjs')), str(output)],
                            capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
