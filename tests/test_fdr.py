import numpy as np
from scipy.stats import false_discovery_control

from hode.fdr import bh_adjust, bh_threshold


def test_bh_matches_scipy():
    p = np.random.default_rng(3).uniform(size=200) ** 3
    assert np.allclose(bh_adjust(p), false_discovery_control(p, method="bh"))


def test_bh_known_values():
    p = np.array([0.01, 0.04, 0.03, 0.005])
    assert np.allclose(bh_adjust(p), [0.02, 0.04, 0.04, 0.02])


def test_nans_are_passed_through_and_not_counted():
    q = bh_adjust(np.array([0.01, np.nan, 0.02]))
    assert np.isnan(q[1])
    assert np.allclose(q[[0, 2]], [0.02, 0.02])


def test_empty_input():
    assert bh_adjust(np.array([])).size == 0
    assert bh_threshold(np.array([]), 0.05) == 0.0


def test_threshold_is_the_largest_rejected_p_value():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.6])
    assert bh_threshold(p, 0.05) == 0.008
    assert bh_threshold(np.array([0.5, 0.9]), 0.05) == 0.0
