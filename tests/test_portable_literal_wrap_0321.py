"""Literal URLs fill available lines without altering source or friendly links."""
import os
from pathlib import Path
import shutil
import subprocess

from lxml import html
import pytest

import portable_report
import workflows
from wizard import dump_yaml

URL = ('https://long-audit.example.test/api/v1/treasury/approvals/'
       'abcdefghijklmnopqrs?authorization_mode=pending&transaction_id=0123456789abcdef')


def test_literal_url_detection_keeps_destinations_and_human_labels():
    tree = html.fromstring(f'<main><a href="{URL}">{URL}</a><a href="{URL}">Read the evidence register</a>'
                          f'<ul class="refs"><li>{URL}</li><li>Evidence register, revision 3</li></ul></main>')
    before = tree.text_content()
    hrefs = tree.xpath('//a/@href')
    portable_report.prepare_text_flow(tree)
    assert tree.text_content() == before
    assert tree.xpath('//a/@href') == hrefs
    assert len(tree.xpath('//*[@class="report-literal-url"]')) == 2
    assert tree.xpath('//a')[1].get('class') is None
    assert tree.xpath('//li')[1].get('class') is None


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_browser_literal_wrap_fills_width_and_retains_authored_text(tmp_path, lang):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    data = {'meta': {'report_title': 'Literal wrap contract', 'theme': 'ejecutivo', 'lang': lang},
            'report': {'sections': [{'key': 'findings'}]}, 'findings': [{
                'id': 'F01', 'mode': 'vuln', 'title': 'Literal command layout',
                'description_md': f'[{URL}]({URL})\n\n[Read the evidence register]({URL})\n\n'
                                  f'```text\ncurl --silent --show-error {URL}\n```\n\n'
                                  '```text\n  first line\n\tsecond line\nmañana café café 中文 🙂\n```',
                'references': [URL], 'walkthrough': [{'command': f'curl --silent --show-error {URL}'}],
            }]}
    workflows.normalize(data)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    result = subprocess.run(['node', str(Path(__file__).with_name('portable_literal_wrap_0321.cjs')), str(output)],
                            capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
