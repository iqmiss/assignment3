"""End-to-end behaviour of the search against synthetic ground truth."""

import numpy as np
import pytest

from hode.search import SearchConfig, run_search, wilson_interval
from hode.synthetic import PROXY_VARIABLES

PAIR = "region x investigation_group"
TRIPLE = "region x age_group x occupation_group"


def _significant(frame, order=None, variant="all"):
    f = frame[(frame["variant"] == variant) & frame["significant"]]
    if order is not None:
        f = f[f["order"] == order]
    return set(f["variables"])


@pytest.fixture(scope="module")
def d2_result(d2_source):
    return run_search(d2_source, SearchConfig(resamples=20, proxies=PROXY_VARIABLES))


def test_planted_pair_and_triple_are_recovered_at_client_scale(d2_result):
    assert PAIR in _significant(d2_result, 2)
    assert _significant(d2_result, 3) == {TRIPLE}


def test_planted_triple_survives_removal_of_proxy_fields(d2_result):
    assert TRIPLE in _significant(d2_result, 3, variant="no-proxy")
    no_proxy = d2_result[d2_result["variant"] == "no-proxy"]["variables"]
    assert not any(p in v for v in no_proxy for p in PROXY_VARIABLES)


def test_significant_results_carry_stability_and_a_profile(d2_result):
    sig = d2_result[d2_result["significant"]]
    assert sig["stability"].between(0, 1).all()
    triple = sig[(sig["variables"] == TRIPLE) & (sig["variant"] == "all")].iloc[0]
    assert triple["top_cell_lift"] > 2
    assert "occupation_group=Unemployed" in triple["top_cell"]
    assert triple["top_cell_ci_low"] < triple["top_cell_rate"] < triple["top_cell_ci_high"]


def test_profiles_respect_the_minimum_cell_rule(d2_result):
    profiled = d2_result[d2_result["top_cell"] != ""]
    assert (profiled["top_cell_n"] >= 10).all()


def test_hierarchical_gating_skips_triples_with_a_non_significant_pair(d2_result):
    rows = d2_result[(d2_result["order"] == 3) & (d2_result["variant"] == "all")]
    sig_pairs = _significant(d2_result, 2)
    for _, r in rows.iterrows():
        a, b, c = r["variables"].split(" x ")
        gated_in = {f"{a} x {b}", f"{a} x {c}", f"{b} x {c}"} <= sig_pairs
        assert gated_in == (not r["status"].startswith("skipped"))


def test_planted_triple_is_not_identifiable_at_registry_d1_size(d1_source):
    """At n = 21,331 power runs out before k = 3: the engine reports no triple."""
    result = run_search(d1_source, SearchConfig(resamples=0))
    assert _significant(result, 3) == set()
    assert PAIR in _significant(result, 2)


def test_no_discoveries_on_null_data(null_source):
    result = run_search(null_source, SearchConfig(orders=(2, 3), hierarchical=False, resamples=0))
    tested = result[result["status"] == "tested"]
    assert len(tested) == 45 + 120
    assert not tested["significant"].any()


def test_over_budget_tables_are_pruned_and_collapsed(d1_source):
    cfg = SearchConfig(
        orders=(3,),
        events_per_parameter=200,
        resamples=0,
        variables=("region", "age_group", "occupation_group"),
    )
    result = run_search(d1_source, cfg)
    by_rep = result.set_index("representation")
    assert sorted(by_rep.index) == ["collapsed", "raw"]
    raw, collapsed = by_rep.loc["raw"], by_rep.loc["collapsed"]
    assert raw["status"] == "pruned: over parameter budget"
    assert collapsed["status"] == "tested"
    assert collapsed["term_params"] <= collapsed["budget"] < raw["term_params"]
    assert collapsed["merges"]


def test_power_cap_adds_a_collapsed_representation(d1_source):
    cfg = SearchConfig(
        orders=(2,), max_term_params=4, resamples=0, variables=("region", "age_group")
    )
    result = run_search(d1_source, cfg)
    assert sorted(result["representation"]) == ["collapsed", "raw"]
    assert (result["status"] == "tested").all()


def test_tiny_budget_prunes_both_representations(small_source):
    cfg = SearchConfig(orders=(2,), events_per_parameter=1e6, resamples=0)
    result = run_search(small_source, cfg)
    assert set(result["status"]) == {
        "pruned: over parameter budget",
        "pruned: budget below one parameter",
    }


def test_search_is_deterministic(d1_source):
    cfg = SearchConfig(orders=(2,), resamples=10)
    a, b = run_search(d1_source, cfg), run_search(d1_source, cfg)
    assert a.equals(b)


def test_invalid_order_and_proxies_are_rejected(small_source):
    with pytest.raises(ValueError):
        run_search(small_source, SearchConfig(orders=(4,)))
    with pytest.raises(ValueError):
        run_search(small_source, SearchConfig(proxies=("nope",)))


def test_wilson_interval_known_value():
    lo, hi = wilson_interval(10, 100)
    assert np.isclose(lo, 0.0552, atol=1e-4) and np.isclose(hi, 0.1744, atol=1e-4)
    assert all(np.isnan(wilson_interval(0, 0)))
