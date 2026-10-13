"""Portable HTML preserves authored caption line breaks in actual screen layout."""
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image
import pytest

import portable_report
import workflows
from wizard import dump_yaml


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('context', ['sections', 'legacy', 'machine'])
def test_portable_caption_lines_are_visible_not_only_present(tmp_path, language, context):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    Image.new('RGB', (480, 240), '#327391').save(tmp_path / 'figure.png')
    captions = ['', 'TWO-01 first line\nTWO-02 second line',
                '\n'.join(f'CAP-{number:02} explicit caption line' for number in range(60))]
    steps = [{'figure': {'src': 'figure.png', 'caption': caption}} for caption in captions]
    finding = {'id': 'CAP-01', 'mode': 'vuln', 'title': 'Synthetic caption layout',
               'description_md': 'Unverified synthetic record.', 'walkthrough': steps}
    if context == 'machine':
        finding.update(mode='machine', host={'name': 'Synthetic host'},
                       phases=[{'name': 'Capture', 'steps': steps}])
        finding.pop('walkthrough')
    data = {'meta': {'report_title': 'Caption flow', 'lang': language, 'theme': 'corporativo'},
            'report': {'sections': [{'key': 'findings'}]}, 'findings': [finding]}
    workflows.normalize(data)
    if context == 'legacy':
        data.pop('report', None)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    before = (tmp_path / 'engagement.yaml').read_bytes()
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    result = subprocess.run(['node', str(Path(__file__).with_name('portable_multiline_captions_0345.cjs')),
                             str(output)], capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'engagement.yaml').read_bytes() == before
