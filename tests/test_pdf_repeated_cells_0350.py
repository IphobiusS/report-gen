"""Large repeated tables keep strict multiplicity without combinatorial search."""
import pytest

import export_contract as contract


def test_many_overlapping_cell_values_have_a_disjoint_witness():
    count = 1000
    units = ['Approved'] * count + ['Approved with conditions'] * count
    pages = ['Approved Approved with conditions\n' * count
             + 'Approved with conditions\n' * 20]
    assert contract._pdf_present(units, {'pages': pages}, 'tabla', 'table') == (2000, 0)


def test_witness_cannot_supply_short_cells_from_longer_cells_only():
    units = ['Approved'] * 100 + ['Approved with conditions'] * 100
    with pytest.raises(ValueError, match='PDF'):
        contract._pdf_present(units, {'pages': ['Approved with conditions\n' * 100]}, 'tabla', 'table')
