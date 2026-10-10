import numpy as np
import pytest

from hode.adapters import DataFrameSource
from hode.table import CountTable, aggregate


def test_aggregate_sums_duplicate_cells():
    cells = np.array([[0, 1], [0, 1], [1, 0]])
    t = aggregate(
        ("a", "b"), (("x", "y"), ("p", "q")), cells, np.array([1, 0, 1]), np.array([1, 1, 1])
    )
    assert t.cells.tolist() == [[0, 1], [1, 0]]
    assert t.pos.tolist() == [1, 1]
    assert t.n.tolist() == [2, 1]


def test_table_totals_match_the_records(small_frame, small_source):
    t = small_source.table(["a", "c"])
    assert t.total == len(small_frame)
    assert t.events == small_frame["y"].sum()
    assert t.n_levels == (3, 4)
    assert t.term_params == 2 * 3


def test_collapse_on_counts_equals_counting_collapsed_records(small_frame):
    """Collapsing is exact: merging levels in the table == merging them in the data."""
    t = DataFrameSource(small_frame, "y").table(["a", "c"])
    collapsed = t.collapse(1, [[0, 1], [2], [3]])  # c levels t, u, v, w -> t|u, v, w

    merged = small_frame.assign(c=small_frame["c"].replace({"t": "t|u", "u": "t|u"}))
    direct = DataFrameSource(merged, "y").table(["a", "c"])

    assert collapsed.levels == direct.levels
    assert np.array_equal(collapsed.cells, direct.cells)
    assert np.array_equal(collapsed.pos, direct.pos)
    assert np.array_equal(collapsed.n, direct.n)


def test_resample_preserves_sample_size(small_source):
    t = small_source.table(["a", "b"])
    r = t.resample(np.random.default_rng(1))
    assert r.total == t.total
    assert np.all(r.pos <= r.n)


def test_label_names_every_level(small_source):
    t = small_source.table(["a", "b"])
    assert t.label(0) == "a=x, b=p"


def test_fingerprint_changes_with_content(small_source):
    t = small_source.table(["a", "b"])
    other = CountTable(t.variables, t.levels, t.cells, t.pos, t.n + 1)
    assert t.fingerprint() != other.fingerprint()


@pytest.mark.parametrize("pos,n", [([2], [1]), ([-1], [1]), ([0], [0])])
def test_invalid_counts_are_rejected(pos, n):
    with pytest.raises(ValueError):
        CountTable(("a",), (("x",),), np.array([[0]]), np.array(pos), np.array(n))


def test_shape_mismatch_is_rejected():
    with pytest.raises(ValueError):
        CountTable(("a", "b"), (("x",), ("y",)), np.array([[0]]), np.array([0]), np.array([1]))
    with pytest.raises(ValueError):
        CountTable(("a",), (("x",),), np.array([[0]]), np.array([0, 1]), np.array([1]))
