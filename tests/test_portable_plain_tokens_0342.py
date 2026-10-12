"""Bare literal runs fill lines without changing copied text or other exports."""
from html import escape
import os
from pathlib import Path
import shutil
import subprocess

from lxml import html
import pytest

import portable_report
import workflows
from wizard import dump_yaml

URL = 'https://bank.example.test/' + '0123456789abcdef' * 35 + '?case=12&next=%2Fqueue#literal'
TOKEN = 'CASE12_' + '0123456789ABCDEF' * 35


@pytest.mark.parametrize('wrapper', [
    '<p>{}</p>', '<ul><li>{}</li></ul>', '<table><tr><td>{}</td></tr></table>',
    '<blockquote><p>{}</p></blockquote>', '<figure><figcaption>{}</figcaption></figure>',
])
def test_bare_runs_keep_exact_text_and_only_wrap_literals(wrapper):
    tree = html.fromstring('<main>' + wrapper.format('Label ' + escape(URL) + ' prose ' + TOKEN) + '</main>')
    before = tree.text_content()
    portable_report.prepare_text_flow(tree)
    assert tree.text_content() == before
    spans = tree.xpath('.//span[@class="report-literal-token"]')
    assert [node.text for node in spans] == [URL, TOKEN]
    assert spans[0].tail == ' prose '
    once = html.tostring(tree)
    portable_report.prepare_text_flow(tree)
    assert html.tostring(tree) == once


def test_inline_and_tail_nodes_preserve_markup_unicode_and_link_destinations():
    unicode_url = 'https://bank.example.test/cafe\u0301/δ?next=%2Fqueue'
    tree = html.fromstring('<main><p><strong>Label</strong> ' + escape(URL) +
                           ' <em>ordinary words</em> ' + escape(unicode_url) +
                           '</p><p><a href="' + escape(URL, quote=True) + '">Evidence register</a></p></main>')
    before, hrefs = tree.text_content(), tree.xpath('.//a/@href')
    portable_report.prepare_text_flow(tree)
    assert tree.text_content() == before
    assert tree.xpath('.//a/@href') == hrefs
    assert tree.xpath('.//strong')[0].text == 'Label'
    assert tree.xpath('.//em')[0].text == 'ordinary words'
    assert [node.text for node in tree.xpath('.//span')] == [URL, unicode_url]
    assert tree.xpath('.//a')[0].get('class') is None


def test_excluded_nodes_and_non_ascii_words_are_not_rewritten():
    source = ('<html><head><title>' + TOKEN + '</title><style>/* ' + URL + ' */</style></head>'
              '<body><pre>' + TOKEN + '</pre><code>' + TOKEN + '</code>'
              '<script>const value="' + URL + '"</script><textarea>' + TOKEN + '</textarea>'
              '<svg><text>' + TOKEN + '</text></svg><math><mi>' + TOKEN + '</mi></math>'
              '<p>Ordinary English words and palabras españolas cafe\u0301.</p>'
              '<p>' + 'A' * 63 + ' ' + 'B' * 64 + '\u0301 ' + 'é' + 'C' * 64 + '</p></body></html>')
    tree = html.document_fromstring(source)
    before = html.tostring(tree)
    portable_report.prepare_text_flow(tree)
    assert html.tostring(tree) == before


def test_escaped_attack_text_stays_text_and_attributes_are_unchanged():
    attack = '<img/src=x/onerror=alert(1)' + 'X' * 80 + '>'
    tree = html.fromstring('<main><p title="' + escape(TOKEN, quote=True) + '">' +
                           escape(attack) + '</p></main>')
    before = tree.text_content()
    portable_report.prepare_text_flow(tree)
    reparsed = html.fromstring(html.tostring(tree))
    assert reparsed.text_content() == before
    assert not reparsed.xpath('.//img|.//script|.//*[@onerror]')
    assert reparsed.xpath('.//p')[0].get('title') == TOKEN
    assert reparsed.xpath('.//span')[0].text == attack


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_browser_bare_tokens_fill_remaining_line_and_copy_exactly(tmp_path, lang):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    body = (f'P: {URL}\n\nR: {TOKEN}\n\n**I:** {URL} *tail remains.*\n\n'
            f'- L: {URL}\n\n| Value |\n| --- |\n| T: {URL} |\n\n'
            'U: https://bank.example.test/cafe\u0301/δ?next=%2Fqueue\n\n'
            'NORMAL: Ordinary English words and palabras españolas retain normal line boundaries.\n\n'
            f'`{TOKEN}`\n\n```text\n{TOKEN}\n```')
    data = {'meta': {'report_title': 'Bare token flow', 'theme': 'corporativo', 'lang': lang},
            'report': {'sections': [{'key': 'findings'}]}, 'findings': [{
                'id': 'F01', 'mode': 'vuln', 'title': 'Literal prose continuity',
                'description_md': body}]}
    workflows.normalize(data)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    original = (tmp_path / 'engagement.yaml').read_bytes()
    output = tmp_path / 'report.html'
    output.write_text(portable_report.build(tmp_path), encoding='utf-8')
    assert (tmp_path / 'engagement.yaml').read_bytes() == original
    result = subprocess.run(['node', str(Path(__file__).with_name('portable_plain_tokens_0342.cjs')), str(output)],
                            capture_output=True, text=True, timeout=90, env=os.environ.copy())
    if result.returncode == 77:
        pytest.skip(result.stderr.strip())
    assert result.returncode == 0, result.stdout + result.stderr
