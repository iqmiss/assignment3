import numpy as np
import pytest

from hode.budget import collapse_to_budget, parameter_budget, term_params
from hode.table import CountTable


def _table(events, total, n_levels=(2,)):
    cells = np.zeros((1, len(n_levels)), dtype=np.int64)
    levels = tuple(tuple(f"l{j}" for j in range(L)) for L in n_levels)
    return CountTable(
        tuple(f"v{i}" for i in range(len(n_levels))),
        levels,
        cells,
        np.array([events]),
        np.array([total]),
    )


def test_registry_d1_identifies_about_136_parameters():
    """1,359 positive cases at ten events per parameter: the ceiling from Assignment 1."""
    assert parameter_budget(_table(1359, 21331)) == 135


def test_one_three_way_term_among_ten_level_fields_needs_729_parameters():
    assert term_params((10, 10, 10)) == 729


def test_budget_uses_the_rarer_outcome():
    assert parameter_budget(_table(900, 1000)) == 10


def test_budget_rejects_nonpositive_rule():
    with pytest.raises(ValueError):
        parameter_budget(_table(10, 100), 0)


def test_collapse_fits_the_budget_and_logs_every_merge(d1_source):
    raw = d1_source.table(["region", "age_group", "occupation_group"])
    assert raw.term_params == 7 * 4 * 4
    result = collapse_to_budget(raw, 20)
    assert result is not None and result.changed
    assert result.table.term_params <= 20
    assert result.table.total == raw.total and result.table.events == raw.events
    assert len(result.merges) == sum(raw.n_levels) - sum(result.table.n_levels)


def test_collapse_merges_the_least_populated_levels_first(d1_source):
    raw = d1_source.table(["region", "gender"])
    result = collapse_to_budget(raw, raw.term_params - 1)
    assert result.merges == (("region", "R07", "R08"),)


def test_collapse_is_a_no_op_when_already_within_budget(d1_source):
    raw = d1_source.table(["gender", "complicity_type"])
    result = collapse_to_budget(raw, 100)
    assert not result.changed and result.table is raw


def test_collapse_gives_up_below_one_parameter(d1_source):
    assert collapse_to_budget(d1_source.table(["gender"]), 0) is None
