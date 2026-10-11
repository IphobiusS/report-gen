"""Loaded report fonts must become the rendered font, including a late decode."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

import portable_report
import workflows
from wizard import dump_yaml


def test_loaded_embedded_font_replaces_temporary_fallback(tmp_path):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    data = {
        'meta': {'report_title': 'Independent evidence review', 'theme': 'corporativo',
                 'lang': 'en', 'client': 'Synthetic bank', 'assessor': 'Reviewer'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [{'id': 'F01', 'mode': 'vuln', 'severity': 'high',
                      'title': 'Independent review preserves the complete evidence reference',
                      'description_md': 'A synthetic document used only for font rendering checks.'}],
    }
    workflows.normalize(data)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    result = subprocess.run(
        ['node', str(Path(__file__).with_name('portable_font_stability_0323.cjs')), str(output)],
        capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
