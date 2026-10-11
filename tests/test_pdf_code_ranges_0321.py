"""Wrapped logical code lines cannot reuse another line's physical text."""
from html import escape
from itertools import combinations, product
import json
import random
import time

from lxml import html
import pytest
from weasyprint import HTML

import export_contract


@pytest.mark.parametrize('codes,text', [
    (['TOKENAB', 'TOKEN\nAB'], 'TOKEN\nAB'),
    (['A B', 'A', 'B'], 'A\nB'),
    (['https://bank.example/a', 'https://bank.\nexample/a'], 'https://bank.\nexample/a'),
    (['AB', 'AB', 'A', 'B'], 'AB\nA\nB'),
    (['AB', 'BC'], 'A\nB\nC'),
])
def test_shared_physical_ranges_cannot_supply_missing_code(codes, text):
    with pytest.raises(ValueError, match='código|code'):
        export_contract._pdf_code_multiplicity(codes, text)


@pytest.mark.parametrize('codes,text', [
    (['TOKENAB', 'TOKEN\nAB'], 'TOKEN\nAB\nTOKENAB'),
    (['A B', 'A', 'B'], 'A\nB\nA B'),
    (['AB', 'AB', 'A', 'B'], 'A\nB\nAB\nAB'),
    (['AB', 'BC'], 'A\nB\nC\nAB'),
    (['ABC', 'BC', 'AB'], 'A\nB\nC\nAB\nBC'),
    (['AB', 'BA'], 'A\nB\nA\nB\nA'),
    (['A B', 'AB'], 'A\nB\nAB'),
    (['one', 'two'], 'HEADER\none\nother prose\ntwo\nFOOTER'),
])
def test_complete_code_uses_alternate_placements_without_greedy_rejection(codes, text):
    export_contract._pdf_code_multiplicity(codes, text)


@pytest.mark.parametrize('language', ['en', 'es'])
def test_actual_pdf_missing_block_is_rejected_despite_wrapping_ambiguity(tmp_path, language):
    prefix = (f'<html lang="{language}"><head><style>'
              'pre{font-family:monospace;white-space:pre-wrap}'
              '</style></head><body>')
    original = prefix + '<pre>TOKENAB</pre><pre>TOKEN\nAB</pre></body></html>'
    expected = export_contract.from_tree(html.document_fromstring(original))
    path = tmp_path / 'original.pdf'
    HTML(string=original).write_pdf(path)
    checks = export_contract.inspect(path, 'pdf', expected)
    assert checks['finding_association_checked'] is False
    assert checks['verification_scope'] == 'text_presence_only'
    corrupt = tmp_path / 'missing.pdf'
    HTML(string=prefix + '<pre>TOKEN\nAB</pre></body></html>').write_pdf(corrupt)
    with pytest.raises(ValueError, match='código|code'):
        export_contract.inspect(corrupt, 'pdf', expected)


@pytest.mark.parametrize('code', [
    'https://bank.example/a-b_c/report?id=A%2FB&part=2#evidence',
    r'curl "https://bank.example/a?filter=%5C%2F" --header "X-Ref: A_B"',
    r'Get-Content C:\Synthetic\Evidence\case-001.txt',
    'https://bank.example/informe/año?responsable=José&ámbito=revisión',
    'opaque=' + '0123456789abcdef' * 128,
])
def test_literal_url_characters_survive_physical_wrapping(code):
    wrapped = '\n'.join(code[i:i + 31] for i in range(0, len(code), 31))
    export_contract._pdf_code_multiplicity([code], wrapped)
    checked, count = export_contract._pdf_code_lines(code, wrapped)
    assert checked == 1
    assert count == 1


@pytest.mark.parametrize('replacement', [' ', '\u200b', '\ufeff', '_', '\\', '/'])
def test_inserted_url_characters_are_not_mistaken_for_visual_wraps(replacement):
    source = 'https://bank.example/evidence'
    changed = source[:20] + replacement + source[20:]
    with pytest.raises(ValueError, match='código|code'):
        export_contract._pdf_code_multiplicity([source], changed)


@pytest.mark.parametrize('changed', [
    'https:/bank.example/a?x=1&y=2',
    'https://bank.example/a?x=1y=2',
    'https://bank.example/a?x=1&y=3',
    'https://bank.example/a?x=1&y=2/extra',
])
def test_lost_changed_or_appended_url_punctuation_is_rejected(changed):
    with pytest.raises(ValueError, match='código|code'):
        export_contract._pdf_code_multiplicity(['https://bank.example/a?x=1&y=2'], changed)


def test_html_literal_code_still_rejects_inserted_wrap_characters(tmp_path):
    source = 'https://bank.example/a?x=1&y=2'
    tree = html.document_fromstring('<html><body><main><pre>' + escape(source) + '</pre></main></body></html>')
    expected = export_contract.from_tree(tree)
    for replacement in ('\n', ' ', '\u200b', '\ufeff'):
        changed = source[:20] + replacement + source[20:]
        path = tmp_path / 'changed.html'
        path.write_text('<html><body><main><pre>' + escape(changed) + '</pre></main></body></html>')
        with pytest.raises(ValueError, match='literal|Literal'):
            export_contract.inspect(path, 'html', expected)


def test_interval_assignment_matches_exhaustive_small_cases():
    rng = random.Random(321)
    intervals = [(start, stop) for start in range(5) for stop in range(start + 1, 6)]
    for _ in range(350):
        options = tuple(tuple(rng.sample(intervals, rng.randint(1, 5)))
                        for _ in range(rng.randint(1, 3)))
        needs = tuple(rng.randint(1, min(3, len(ranges))) for ranges in options)
        feasible = False
        for groups in product(*(combinations(ranges, need) for ranges, need in zip(options, needs))):
            selected = sorted(span for group in groups for span in group)
            if all(left[1] <= right[0] for left, right in zip(selected, selected[1:])):
                feasible = True
                break
        assert export_contract._pdf_disjoint_code_ranges(needs, options) is feasible


def test_large_repeated_ambiguous_blocks_do_not_require_combinatorial_search():
    count = 1500
    codes = ['TOKENAB', 'TOKEN', 'AB'] * count
    text = ('TOKEN\nAB\nTOKENAB\n') * count
    start = time.monotonic()
    export_contract._pdf_code_multiplicity(codes, text)
    with pytest.raises(ValueError, match='código|code'):
        export_contract._pdf_code_multiplicity(codes, text.removesuffix('TOKENAB\n'))
    assert time.monotonic() - start < 10


def ambiguous_source():
    # Sixteen genuinely different logical lines all match each physical ABCDE
    # block. Only fifteen blocks exist: naive exact search has 15! alternatives.
    codes = [''.join(char + (' ' if bits & (1 << i) else '')
                     for i, char in enumerate('ABCD')) + 'E' for bits in range(16)]
    observed = '\n'.join(['A\nB\nC\nD\nE'] * 15)
    return codes, observed


def test_adversarial_wrap_allocation_has_a_default_work_limit():
    codes, observed = ambiguous_source()
    start = time.monotonic()
    with pytest.raises(ValueError, match='ambiguo|ambiguous') as failure:
        export_contract._pdf_code_multiplicity(codes, observed)
    assert 'ausente' not in str(failure.value)
    assert 'Missing' not in str(failure.value)
    assert time.monotonic() - start < 10


def test_candidate_materialization_is_bounded_before_assignment(monkeypatch):
    def unexpected_assignment(*args):
        pytest.fail('Allocation must not start after the candidate budget is exhausted')

    monkeypatch.setattr(export_contract, '_PDF_CODE_MAX_RANGES', 10)
    monkeypatch.setattr(export_contract, '_pdf_disjoint_code_ranges', unexpected_assignment)
    with pytest.raises(ValueError, match='ambiguo|ambiguous'):
        export_contract._pdf_code_multiplicity(['A'], 'A\n' * 10000)


@pytest.mark.parametrize('limit', ['_PDF_CODE_MAX_STATES', '_PDF_CODE_MAX_RANGES'])
@pytest.mark.parametrize('language,fragment', [('es', 'No se pudo completar'),
                                             ('en', 'could not be completed')])
def test_incomplete_verification_is_controlled_and_preserves_prior_result(
        tmp_path, monkeypatch, limit, language, fragment):
    import export
    import export_jobs
    codes, observed = ambiguous_source()
    prefix = '<html><body>'
    original = prefix + ''.join('<pre>' + code + '</pre>' for code in codes) + '</body></html>'
    expected = export_contract.from_tree(html.document_fromstring(original))
    ambiguous = tmp_path / 'ambiguous.pdf'
    HTML(string=prefix + '<pre>' + observed + '</pre></body></html>').write_pdf(ambiguous)
    config = {'kind': 'export', 'formats': ['pdf'], 'error_language': language,
              'captured': {'images': {}, 'image_placements': 0, 'contract': expected}}
    (tmp_path / 'job.json').write_text(json.dumps(config))
    prior = tmp_path / 'result'
    prior.write_bytes(b'previous verified result')

    def render(_source, _format, output):
        output.write_bytes(ambiguous.read_bytes())
        return output

    monkeypatch.setattr(export, 'export', render)
    monkeypatch.setattr(export_contract, limit, 4)
    assert export_jobs.worker(tmp_path) == 1
    assert prior.read_bytes() == b'previous verified result'
    assert not (tmp_path / 'verification.json').exists()
    error = (tmp_path / 'error.txt').read_text()
    assert fragment in error
    assert 'ambigu' in error
    assert 'ausente' not in error and 'Missing' not in error
