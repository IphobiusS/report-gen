"""Large-report continuation searches retain a complete disjoint proof."""
import pytest

import export_contract as contract


def observed(raw_pages):
    return {'pages': [contract.normal(page) for page in raw_pages],
            'line_edges': [contract._pdf_line_edges(page) for page in raw_pages]}


def repetitive_report():
    suffix = '· a · b · c · d · e · f · end'
    uri = 'https://bank.example/review ' + suffix
    pages = [uri + '\nA B X\nFOOTER', 'HEADER\nB C\n' + suffix] + [suffix] * 12
    return uri, pages


def test_present_uri_does_not_exhaust_search_for_unrelated_prose():
    uri, pages = repetitive_report()
    actual = observed(pages)
    # This is the actual bounded-search failure seen in a 301-page report:
    # expanding an already complete URI creates unnecessary partial chains.
    with pytest.raises(ValueError, match='ambigu'):
        contract._pdf_uri_page_fragments(uri, actual['pages'], actual['line_edges'], lambda _n: None)
    # The first greedy A-B-C continuation competes with B-X. A shorter prefix
    # on the adjacent pages supplies an exact, globally disjoint alternative.
    assert contract._pdf_present([uri, 'A B C', 'B X'], actual, 'párrafo', 'paragraph') == (3, 1)


@pytest.mark.parametrize('change', ['missing', 'changed', 'reused'])
def test_priority_search_cannot_accept_incomplete_or_reused_text(change):
    uri, pages = repetitive_report()
    units = [uri, 'A B C', 'B X']
    if change == 'missing':
        pages[1] = pages[1].replace('B C', 'B')
    elif change == 'changed':
        pages[1] = pages[1].replace('B C', 'B D')
    else:
        units.append('B C')
    with pytest.raises(ValueError, match='PDF'):
        contract._pdf_present(units, observed(pages), 'párrafo', 'paragraph')


def test_bounded_candidate_pass_does_not_replace_longer_continuations():
    pages = ['A B X footer', 'header B C footer', 'header D']
    assert contract._pdf_present(['A B C D', 'B X'], observed(pages),
                                 'párrafo', 'paragraph')[0] == 2
    assert contract._pdf_text_fragments('A B C D', pages, prefixes=True, page_limit=2) == []
    assert contract._pdf_text_fragments('A B C D', pages, prefixes=True)


def test_direct_matches_remain_eligible_for_alternative_allocation():
    # Both units have a direct occurrence, but those occurrences overlap.
    # A complete proof requires expanding an initially sufficient unit too.
    pages = ['A B C footer', 'header A footer', 'header B']
    assert contract._pdf_present(['A B', 'B C'], observed(pages), 'párrafo', 'paragraph')[0] == 2


def test_authored_hostname_hyphen_can_cross_adjacent_physical_lines():
    unit = 'Inspect d05-r2.aster.example complete.'
    pages = ['Inspect d05-\nFOOTER', 'HEADER\nr2.aster.example complete.']
    assert contract._pdf_present([unit], observed(pages), 'párrafo', 'paragraph') == (1, 1)
    with pytest.raises(ValueError, match='PDF'):
        contract._pdf_present([unit, unit], observed(pages), 'párrafo', 'paragraph')


@pytest.mark.parametrize('change', ['missing-hyphen', 'changed-hyphen', 'case', 'missing-character',
                                  'no-line-end', 'no-line-start', 'middle-page', 'out-of-order',
                                  'non-hyphen-cut'])
def test_literal_hyphen_continuations_preserve_characters_and_boundaries(change):
    unit = 'Inspect d05-r2.aster.example complete.'
    pages = ['Inspect d05-\nFOOTER', 'HEADER\nr2.aster.example complete.']
    if change == 'missing-hyphen':
        pages[0] = pages[0].replace('d05-', 'd05')
    elif change == 'changed-hyphen':
        pages[0] = pages[0].replace('d05-', 'd05_')
    elif change == 'case':
        pages[1] = pages[1].replace('r2', 'R2')
    elif change == 'missing-character':
        pages[1] = pages[1].replace('r2', 'r')
    elif change == 'no-line-end':
        pages[0] = pages[0].replace('d05-', 'd05- UNRELATED')
    elif change == 'no-line-start':
        pages[1] = pages[1].replace('r2.', 'UNRELATED r2.')
    elif change == 'middle-page':
        pages.insert(1, 'NO CONTINUATION')
    elif change == 'out-of-order':
        pages.reverse()
    else:
        pages = ['Inspect d0\nFOOTER', 'HEADER\n5-r2.aster.example complete.']
    with pytest.raises(ValueError, match='PDF'):
        contract._pdf_present([unit], observed(pages), 'párrafo', 'paragraph')
