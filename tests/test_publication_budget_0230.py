"""Literal privacy decisions have pre-allocation UTF-8 expansion budgets."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

import app as api
import publication
import workflows
from wizard import dump_yaml
from _support import auth_client

ROOT = Path(__file__).resolve().parent.parent


class NoAllocationText(str):
    def replace(self, *args, **kwargs):
        raise AssertionError('replace must not run after predicted budget exhaustion')


def guard(rules, limit):
    result = publication.LiteralRedactions(rules)
    result.limit = limit
    return result


def test_growth_is_rejected_before_allocating_replacement_result():
    bounded = guard([{'needle': 'AAAA', 'replacement': 'AAAA' * 1000}], 256)
    with pytest.raises(ValueError, match='expand'):
        bounded.text(NoAllocationText('AAAA' * 4))
    assert bounded.used == 0


def test_each_sequential_intermediate_is_checked_even_if_later_rule_would_shrink():
    bounded = guard([{'needle': 'AAAA', 'replacement': 'BBBB' * 100},
                     {'needle': 'BBBB', 'replacement': ''}], 256)
    with pytest.raises(ValueError, match='expand'):
        bounded.text(NoAllocationText('AAAA'))


def test_small_sequential_growth_is_guarded_before_second_dangerous_rule():
    bounded = guard([{'needle': 'AAAA', 'replacement': 'BBBB' * 4},
                     {'needle': 'BBBB', 'replacement': 'CCCC' * 100}], 64)
    with pytest.raises(ValueError, match='expand'):
        bounded.text('AAAA')
    assert bounded.used == 0


def test_unicode_budget_uses_utf8_bytes_not_character_counts():
    bounded = guard([{'needle': 'AAAA', 'replacement': '🧪' * 4}], 16)
    assert bounded.text('AAAA') == '🧪' * 4
    assert bounded.used == 16
    with pytest.raises(ValueError, match='acumulado'):
        bounded.text('é')
    with pytest.raises(ValueError, match='expand'):
        guard([{'needle': 'AAAA', 'replacement': '🧪' * 4}], 15).text(NoAllocationText('AAAA'))


def test_cumulative_budget_includes_unmodified_protected_text():
    bounded = guard([], 8)
    assert bounded.text('1234', False) == '1234'
    assert bounded.text('5678') == '5678'
    with pytest.raises(ValueError, match='acumulado'):
        bounded.text('9', False)


def test_literal_matching_order_and_source_compatibility_are_preserved():
    source = {'title': 'Alpha_name.example', 'src': 'img/Alpha_name.example.png',
              'uid': 'Alpha_name.example', 'design': {'original': 'Alpha_name.example'},
              'workflow': {'original': 'Alpha_name.example'}, 'original': 'private',
              'insights': {'version': 1, 'comments': [{'body': '{{PRIVATE_COMMENT}}'}]},
              'publication': {'redactions': [{'needle': 'Alpha_name', 'replacement': 'Beta_name'},
                                             {'needle': 'Beta_name.example', 'replacement': 'Reviewed'}]}}
    before = deepcopy(source)
    result = publication.project(source)
    assert result['title'] == 'Reviewed'
    assert result['src'] == source['src'] and result['uid'] == source['uid']
    assert result['design'] == source['design'] and result['workflow'] == source['workflow']
    assert 'original' not in result and 'insights' not in result
    assert source == before


def test_project_counts_keys_and_configuration_passthrough_cumulatively(monkeypatch):
    original_init = publication.LiteralRedactions.__init__
    def tiny(self, rules):
        original_init(self, rules)
        self.limit = 32
    monkeypatch.setattr(publication.LiteralRedactions, '__init__', tiny)
    source = {'design': {'original': 'x' * 16}, 'title': 'y' * 16}
    before = deepcopy(source)
    with pytest.raises(ValueError, match='acumulado'):
        publication.project(source)
    assert source == before


def test_invalid_recursive_or_nonportable_source_is_rejected_before_copy():
    source = {'body': 'valid'}
    source['nested'] = source
    with pytest.raises(ValueError, match='recursiva'):
        publication.project(source)
    with pytest.raises(ValueError, match='control'):
        publication.project({'body': '\x00'})


def document():
    return workflows.normalize({'meta': {'report_title': 'Caso sintético', 'client': 'Banco', 'theme': 'serio', 'lang': 'es'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'Control', 'cvss': 0, 'severity': 'info',
                      'description_md': 'AAAAAAAA', 'impact_md': 'Impacto', 'remediation_md': 'Corrección'}]})


def test_api_preview_and_publication_return_controlled_422_without_source_change(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'case'
    directory.mkdir(parents=True)
    data = document()
    dump_yaml(data, directory/'engagement.yaml')
    original_init = publication.LiteralRedactions.__init__
    def tiny(self, rules):
        original_init(self, rules)
        self.limit = 256
    monkeypatch.setattr(publication.LiteralRedactions, '__init__', tiny)
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    client = auth_client(api.app)
    before = (directory/'engagement.yaml').read_bytes()
    options = {'profile': 'executive', 'aliases': [{'needle': 'AAAA', 'replacement': 'AAAA' * 100}]}
    response = client.post('/api/projects/case/audiences/preview', json=options,
                           headers={'If-Match': '"' + sha256(before).hexdigest() + '"'})
    assert response.status_code == 422 and 'expand' in response.get_json()['error']
    assert (directory/'engagement.yaml').read_bytes() == before
    data['publication'] = {'redactions': options['aliases']}
    dump_yaml(data, directory/'engagement.yaml')
    before = (directory/'engagement.yaml').read_bytes()
    response = client.get('/api/projects/case/publication')
    assert response.status_code == 422 and 'expand' in response.get_json()['error']
    assert (directory/'engagement.yaml').read_bytes() == before


def test_cli_predicts_real_16mib_overflow_from_small_input_without_creating_output(tmp_path):
    source = tmp_path / 'engagement.yaml'
    data = document()
    # 16.8 MB is predicted, never allocated. Source is only ~18 KB.
    data['findings'][0]['description_md'] = 'AAAA' * 4200
    data['publication'] = {'redactions': [{'needle': 'AAAA', 'replacement': 'AAAA' * 1000}]}
    dump_yaml(data, source)
    before = source.read_bytes()
    assert len(before) < 24000
    target = tmp_path / 'report.html'
    result = subprocess.run([sys.executable, str(ROOT/'export.py'), str(source), '--format', 'html', '-o', str(target)],
                            cwd=ROOT, capture_output=True, text=True, timeout=25)
    assert result.returncode != 0
    assert 'Literal substitution would expand text beyond 16 MiB' in result.stderr
    assert not target.exists()
    assert source.read_bytes() == before
