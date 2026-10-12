"""A grid's layout-only sixth cell must not become a blank mobile field."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

import portable_report
from wizard import dump_yaml


def test_odd_cover_metadata_preserves_fields_without_a_stacked_blank(tmp_path):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    data = {
        'meta': {'report_title': 'Independent cover review', 'theme': 'corporativo',
                 'lang': 'en', 'client': 'Synthetic bank', 'email': 'review@example.com',
                 'assessor': 'Example reviewer', 'date': '2026-10-12', 'version': '1.0'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [],
    }
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    result = subprocess.run(
        ['node', str(Path(__file__).with_name('portable_cover_empty_0330.cjs')), str(output)],
        capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
