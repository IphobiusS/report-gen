"""Inline identifiers prefer token boundaries; literal URLs and commands retain flow."""
import os
from pathlib import Path
import shutil
import subprocess

from lxml import html
import pytest

import portable_report
import workflows
from wizard import dump_yaml

URL = ('https://evidence.example.com/reviews/meridian/retention-and-recovery/'
       'approval-boundary/catalogue-check?case=ROUND8-SYNTHETIC&record=CATALOGUE-000001'
       '&view=complete-reference&locale=en#acceptance-criteria')
ASSETS = 'RECON-X 203.0.113.121 | LEDGER-X 198.51.100.121 | CONNECTOR-X 203.0.113.120'


def test_inline_url_classification_preserves_source_and_destinations():
    tree = html.fromstring(f'<main><code>{URL}</code><code>{ASSETS}</code>'
                          f'<pre><code>{URL}</code></pre><a href="{URL}">Evidence register</a></main>')
    before, hrefs = tree.text_content(), tree.xpath('//a/@href')
    portable_report.prepare_text_flow(tree)
    assert tree.text_content() == before
    assert tree.xpath('//a/@href') == hrefs
    assert tree.xpath('//main/code')[0].get('class') == 'report-literal-url'
    assert tree.xpath('//main/code')[1].get('class') is None
    assert tree.xpath('//pre/code')[0].get('class') is None
    assert tree.xpath('//a')[0].get('class') is None


def test_browser_inline_identifiers_wrap_between_tokens_without_losing_text(tmp_path):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    data = {'meta': {'report_title': 'Inline code flow', 'theme': 'ejecutivo', 'lang': 'en'},
            'report': {'sections': [{'key': 'findings'}]}, 'findings': [{
                'id': 'F01', 'mode': 'vuln', 'title': 'Identifier continuity', 'affected': ASSETS,
                'description_md': f'`{URL}`\n\n`' + 'A' * 220 + '`\n\n'
                                  f'```text\ncurl --silent --show-error {URL}\n```\n\n'
                                  f'[{URL}]({URL})\n\n[Evidence register]({URL})'}]}
    workflows.normalize(data)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    result = subprocess.run(['node', str(Path(__file__).with_name('portable_inline_code_0330.cjs')), str(output)],
                            capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
