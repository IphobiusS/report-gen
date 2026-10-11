"""Textual presence cannot reuse one physical unit for two distinct units."""
from itertools import combinations, product
import json
import random

from lxml import html
import pytest
from weasyprint import HTML

import export_contract


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('kind', ['table', 'list', 'paragraph'])
def test_real_pdf_cannot_use_a_longer_value_for_a_missing_distinct_value(tmp_path, language, kind):
    values = ['Approved', 'Approved with conditions', 'control alpha', 'alpha beta']

    def markup(items):
        if kind == 'table':
            body = '<table><tr>' + ''.join('<td>' + item + '</td>' for item in items) + '</tr></table>'
        elif kind == 'list':
            body = '<ul>' + ''.join('<li>' + item + '</li>' for item in items) + '</ul>'
        else:
            body = ''.join('<p>' + item + '</p>' for item in items)
        return f'<html lang="{language}"><body>{body}</body></html>'

    original = markup(values)
    expected = export_contract.from_tree(html.document_fromstring(original))
    target = tmp_path / 'complete.pdf'
    HTML(string=original).write_pdf(target)
    checked = export_contract.inspect(target, 'pdf', expected)
    assert checked['verification_scope'] == 'text_presence_only'
    assert checked['finding_association_checked'] is False
    for index in (0, 2):
        changed = list(values)
        changed[index] = 'REPLACED' if index == 0 else 'control alpha beta'
        if index == 2:
            changed.pop(3)  # Two partially overlapping phrases share one physical value.
        target = tmp_path / f'altered-{index}.pdf'
        HTML(string=markup(changed)).write_pdf(target)
        with pytest.raises(ValueError, match='PDF'):
            export_contract.inspect(target, 'pdf', expected)


@pytest.mark.parametrize('units,pages', [
    (['Approved', 'Approved with conditions'], ['Approved with conditions Approved']),
    (['A B', 'B C'], ['A B C A B']),
    (['A A', 'A B'], ['A A A B']),
    (['A B', 'A B', 'B C'], ['A B C A B A B']),
    (['A B C', 'X Y Z'], ['A B X Y footer', 'header C Z']),
    (['A B C', 'C'], ['A B footer', 'C C']),
    (['A B', 'A X'], ['A X A footer', 'header B']),
    (['A B C', 'B'], ['A B footer', 'B C']),
    (['A B C', 'B X'], ['A B X footer', 'header B C']),
])
def test_text_assignment_keeps_alternatives_and_interleaved_page_fragments(units, pages):
    assert export_contract._pdf_present(units, {'pages': pages}, 'tabla', 'table')[0] == len(units)


@pytest.mark.parametrize('units,pages', [
    (['Approved', 'Approved with conditions'], ['Approved with conditions']),
    (['A B', 'B C'], ['A B C']),
    (['A A', 'A A'], ['A A A']),
    (['A B C', 'X C'], ['A B X footer', 'C']),
    (['A B C', 'C'], ['A B footer', 'C']),
])
def test_text_fragments_are_never_shared_between_distinct_values(units, pages):
    with pytest.raises(ValueError, match='PDF'):
        export_contract._pdf_present(units, {'pages': pages}, 'tabla', 'table')


def test_fragment_assignment_matches_exhaustive_small_cases():
    rng = random.Random(322)
    spans = [(start, end) for start in range(6) for end in range(start + 1, 7)]
    candidates = [(span,) for span in spans]
    candidates += [(left, right) for left, right in combinations(spans, 2) if left[1] <= right[0]]
    for _ in range(450):
        options = tuple(tuple(rng.sample(candidates, rng.randint(1, 5)))
                        for _ in range(rng.randint(1, 3)))
        needs = tuple(rng.randint(1, min(3, len(ranges))) for ranges in options)
        feasible = False
        for groups in product(*(combinations(ranges, need) for ranges, need in zip(options, needs))):
            selected = sorted(span for group in groups for candidate in group for span in candidate)
            if all(left[1] <= right[0] for left, right in zip(selected, selected[1:])):
                feasible = True
                break
        assert export_contract._pdf_disjoint_text_ranges(needs, options) is feasible


def test_candidate_materialization_is_bounded_before_text_assignment(monkeypatch):
    monkeypatch.setattr(export_contract, '_PDF_TEXT_MAX_RANGES', 8)
    with pytest.raises(ValueError, match='ambigu') as failure:
        export_contract._pdf_present(['Approved'], {'pages': ['Approved ' * 10000]}, 'tabla', 'table')
    assert 'ausente' not in str(failure.value) and 'Missing' not in str(failure.value)


@pytest.mark.parametrize('limit', ['_PDF_TEXT_MAX_STATES', '_PDF_TEXT_MAX_RANGES'])
def test_text_assignment_work_limits_fail_closed(monkeypatch, limit):
    monkeypatch.setattr(export_contract, limit, 0)
    with pytest.raises(ValueError, match='ambigu'):
        export_contract._pdf_present(['Approved'], {'pages': ['Approved']}, 'tabla', 'table')


@pytest.mark.parametrize('language,fragment', [('es', 'No se pudo completar'),
                                             ('en', 'could not be completed')])
@pytest.mark.parametrize('limit', ['_PDF_TEXT_MAX_STATES', '_PDF_TEXT_MAX_RANGES'])
def test_incomplete_text_verification_preserves_prior_export(tmp_path, monkeypatch, language, fragment, limit):
    import export
    import export_jobs

    markup = '<html><body><table><tr><td>Approved</td></tr></table></body></html>'
    expected = export_contract.from_tree(html.document_fromstring(markup))
    prepared = tmp_path / 'prepared.pdf'
    HTML(string=markup).write_pdf(prepared)
    config = {'kind': 'export', 'formats': ['pdf'], 'error_language': language,
              'captured': {'images': {}, 'image_placements': 0, 'contract': expected}}
    (tmp_path / 'job.json').write_text(json.dumps(config))
    prior = tmp_path / 'result'
    prior.write_bytes(b'previous verified result')

    def render(_source, _format, output):
        output.write_bytes(prepared.read_bytes())
        return output

    monkeypatch.setattr(export, 'export', render)
    monkeypatch.setattr(export_contract, limit, 0)
    assert export_jobs.worker(tmp_path) == 1
    assert prior.read_bytes() == b'previous verified result'
    assert not (tmp_path / 'verification.json').exists()
    error = (tmp_path / 'error.txt').read_text()
    assert fragment in error and 'ambigu' in error
    assert 'ausente' not in error and 'Missing' not in error
