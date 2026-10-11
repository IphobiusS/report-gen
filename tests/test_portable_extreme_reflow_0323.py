"""The report's nested frames must not consume its readable line width."""
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image
import pytest
import portable_report
import workflows
from wizard import dump_yaml


@pytest.mark.parametrize('lang', ['es', 'en'])
@pytest.mark.parametrize('density', ['comfortable', 'compact'])
@pytest.mark.parametrize('layout', ['sections', 'legacy'])
def test_extreme_reflow_preserves_prose_space_and_font_size(tmp_path, lang, density, layout):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    url = 'https://bank.example.test/' + 'authorization/' * 12 + '?approval=' + 'a' * 80
    data = {'meta': {'report_title': 'Readable assurance report', 'theme': 'corporativo',
                     'lang': lang, 'report_density': density,
                     'client': 'Bank client', 'assessor': 'Report reviewer',
                     'date': '2026-10-11', 'version': '1.0',
                     'branding': {'logo': 'wide.png', 'client_logo': 'tall.png',
                                  'cover_image': 'evidence.png'}},
            'findings': [{'id': 'F01', 'mode': 'vuln', 'severity': 'high',
                          'title': 'Retest closure relies on a mutable path without review',
                          'affected': 'bank.example.test',
                          'description_md': '> QUOTE-ONE retains readable prose.\n>\n'
                                            '> > QUOTE-TWO retains readable prose.\n\n'
                                            '1. LIST-ONE\n    1. LIST-TWO\n        1. LIST-THREE\n\n'
                                            f'[{url}]({url})\n\n```text\ncurl --silent {url}\n'
                                            'case\tpartner\tamount\tcurrency\nF03\tblue\t12.345\tXZ3\n```\n\n'
                                            '| ID | Owner | Decision |\n| --- | --- | --- |\n'
                                            '| F01 | Treasury | TABLE-END |',
                          'walkthrough': [{'lead': 'Evidence review',
                                           'figure': {'src': 'evidence.png',
                                                      'caption': 'Retest closure keeps the complete evidence and original trace.'}}],
                          'remediation_summary': {'short_md': 'Preserve complete review details.'}}]}
    Image.new('RGB', (200, 100), '#165080').save(tmp_path / 'evidence.png')
    Image.new('RGB', (800, 200), '#285870').save(tmp_path / 'wide.png')
    Image.new('RGB', (200, 800), '#357088').save(tmp_path / 'tall.png')
    if layout == 'sections':
        data['report'] = {'sections': [{'key': 'findings'}]}
    workflows.normalize(data)
    if layout == 'legacy':
        data.pop('report', None)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    result = subprocess.run(['node', str(Path(__file__).with_name('portable_extreme_reflow_0323.cjs')), str(output)],
                            capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
