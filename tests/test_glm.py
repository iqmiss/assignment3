import numpy as np
from scipy.stats import chi2_contingency

from hode.glm import design_matrix, fit_binomial, interaction_test
from hode.table import CountTable


def test_one_way_test_equals_the_g_test(small_source):
    """For k = 1 the likelihood-ratio statistic is the G statistic of the 2 x L table."""
    t = small_source.table(["c"])
    result = interaction_test(t)
    observed = np.vstack([t.pos, t.n - t.pos])
    g, p, dof, _ = chi2_contingency(observed, correction=False, lambda_="log-likelihood")
    assert np.isclose(result.statistic, g)
    assert np.isclose(result.p_value, p)
    assert result.df == dof


def test_grouped_fit_equals_row_level_fit(small_source):
    """Fitting on counts gives the same coefficients as fitting on every record."""
    t = small_source.table(["a", "b"])
    X = design_matrix(t.cells, t.n_levels, 1)
    grouped = fit_binomial(X, t.pos, t.n)

    rows = np.repeat(np.arange(len(t.n)), t.n)
    y = np.concatenate(
        [np.r_[np.ones(p), np.zeros(n - p)] for p, n in zip(t.pos, t.n, strict=True)]
    )
    row_level = fit_binomial(X[rows], y, np.ones(len(y)))

    assert grouped.converged and row_level.converged
    assert np.allclose(grouped.beta, row_level.beta, atol=1e-8)


def test_design_matrix_column_count_matches_the_hierarchy():
    cells = np.array([[i, j, k] for i in range(3) for j in range(2) for k in range(4)])
    # intercept + mains (2+1+3) + pairs (2*1 + 2*3 + 1*3)
    assert design_matrix(cells, (3, 2, 4), 2).shape == (24, 1 + 6 + 11)


def test_no_interaction_gives_a_large_p_value():
    # Odds ratio identical in both strata of b: no a x b interaction at all.
    cells = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    t = CountTable(
        ("a", "b"),
        (("x", "y"), ("p", "q")),
        cells,
        np.array([10, 20, 20, 40]),
        np.array([100, 100, 100, 100]),
    )
    result = interaction_test(t)
    assert result.df == 1
    assert result.p_value > 0.5


def test_strong_interaction_is_detected():
    cells = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    t = CountTable(
        ("a", "b"),
        (("x", "y"), ("p", "q")),
        cells,
        np.array([10, 10, 10, 60]),
        np.array([100, 100, 100, 100]),
    )
    assert interaction_test(t).p_value < 1e-4


def test_zero_event_margin_is_flagged_as_boundary_but_still_tested():
    cells = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    t = CountTable(
        ("a", "b"),
        (("x", "y"), ("p", "q")),
        cells,
        np.array([0, 0, 10, 30]),
        np.array([50, 50, 100, 100]),
    )
    result = interaction_test(t)
    assert result.boundary
    assert result.converged and np.isfinite(result.p_value)


def test_saturated_one_cell_table_has_no_degrees_of_freedom():
    t = CountTable(("a",), (("x",),), np.array([[0]]), np.array([3]), np.array([10]))
    result = interaction_test(t)
    assert result.df == 0 and np.isnan(result.p_value)
