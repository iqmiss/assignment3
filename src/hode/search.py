"""Higher-order determinant search: enumerate, budget, collapse, test, correct, resample.

The search follows the statistical-validation design of the dissertation's
second article:

* a k-way combination is tested only if every (k-1)-way subset of it was
  significant (hierarchical gating), so a triple is never reported on the
  back of pairs that did not hold up on their own;
* Benjamini-Hochberg FDR is applied within each order;
* significant combinations are resampled to measure stability;
* each one is translated into a subgroup profile (size, rate with a 95 %
  Wilson interval, lift) that passes a minimum-cell disclosure rule;
* when proxy fields are declared, every result is produced twice, with and
  without them.
"""

from __future__ import annotations

import zlib
from dataclasses import asdict, dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd

from hode.budget import collapse_to_budget, parameter_budget
from hode.fdr import bh_adjust, bh_threshold
from hode.glm import interaction_test
from hode.ports import CountSource
from hode.table import CountTable

Z95 = 1.959963984540054


@dataclass(frozen=True)
class SearchConfig:
    orders: tuple[int, ...] = (2, 3)
    events_per_parameter: float = 10.0
    fdr: float = 0.05
    collapse: bool = True
    max_term_params: int | None = None
    hierarchical: bool = True
    resamples: int = 200
    stability_seed: int = 7
    min_cell: int = 10
    variables: tuple[str, ...] | None = None
    proxies: tuple[str, ...] = ()


@dataclass
class Result:
    variant: str
    order: int
    variables: str
    representation: str
    levels: str
    term_params: int
    budget: int
    status: str
    statistic: float = float("nan")
    df: int = 0
    p_value: float = float("nan")
    q_value: float = float("nan")
    significant: bool = False
    boundary: bool = False
    stability: float = float("nan")
    top_cell: str = ""
    top_cell_n: int = 0
    top_cell_rate: float = float("nan")
    top_cell_ci_low: float = float("nan")
    top_cell_ci_high: float = float("nan")
    top_cell_lift: float = float("nan")
    merges: str = ""
    _table: CountTable | None = field(default=None, repr=False)
    _combo: tuple[str, ...] = field(default=(), repr=False)


COLUMNS = [f for f in Result.__dataclass_fields__ if not f.startswith("_")]


def run_search(source: CountSource, config: SearchConfig) -> pd.DataFrame:
    """Run the full search and return one row per (variant, combination, representation)."""
    names = list(config.variables) if config.variables else source.variables()
    unknown = [p for p in config.proxies if p not in names]
    if unknown:
        raise ValueError(f"proxy fields not among the variables: {unknown}")
    variants = {"all": names}
    if config.proxies:
        variants["no-proxy"] = [v for v in names if v not in config.proxies]

    results: list[Result] = []
    for variant, vars_ in variants.items():
        results.extend(_search_variant(source, config, variant, vars_))

    frame = pd.DataFrame([{c: getattr(r, c) for c in COLUMNS} for r in results], columns=COLUMNS)
    variant_order = {v: i for i, v in enumerate(variants)}
    frame["_v"] = frame["variant"].map(variant_order)
    frame = frame.sort_values(
        ["_v", "order", "q_value", "p_value", "variables", "representation"],
        na_position="last",
        kind="stable",
    )
    return frame.drop(columns="_v").reset_index(drop=True)


def _search_variant(
    source: CountSource, config: SearchConfig, variant: str, names: list[str]
) -> list[Result]:
    out: list[Result] = []
    significant: dict[int, set[tuple[str, ...]]] = {}
    for k in sorted(config.orders):
        if k < 1 or k > len(names):
            raise ValueError(f"order {k} is outside 1..{len(names)}")
        gate = significant.get(k - 1) if config.hierarchical else None
        family: list[Result] = []
        for combo in combinations(names, k):
            if gate is not None and not all(s in gate for s in combinations(combo, k - 1)):
                out.append(_skipped(variant, combo))
                continue
            rows = _evaluate(source.table(combo), config, variant)
            for r in rows:
                r._combo = combo
            family.extend(r for r in rows if r.status == "tested")
            out.extend(rows)

        p = np.array([r.p_value for r in family])
        for r, q in zip(family, bh_adjust(p), strict=True):
            r.q_value = float(q)
            r.significant = bool(q <= config.fdr)
        threshold = bh_threshold(p, config.fdr)
        for r in family:
            if r.significant and config.resamples > 0:
                r.stability = _stability(r, threshold, config)
        significant[k] = {r._combo for r in family if r.significant}
    return out


def _skipped(variant: str, combo: tuple[str, ...]) -> Result:
    return Result(
        variant=variant,
        order=len(combo),
        variables=" x ".join(combo),
        representation="-",
        levels="",
        term_params=0,
        budget=0,
        status="skipped: a lower-order subset is not significant",
    )


def _evaluate(raw: CountTable, config: SearchConfig, variant: str) -> list[Result]:
    budget = parameter_budget(raw, config.events_per_parameter)
    out = []
    raw_fits = raw.term_params <= budget
    out.append(
        _test(raw, variant, "raw", budget, config)
        if raw_fits
        else _row(raw, variant, "raw", budget, "pruned: over parameter budget")
    )
    # The collapsed representation is fitted to the identifiability budget and,
    # optionally, to a tighter power cap. Levels are merged by frequency only,
    # never by outcome, so collapsing cannot select for significance.
    target = budget if config.max_term_params is None else min(budget, config.max_term_params)
    if config.collapse and raw.term_params > target:
        collapsed = collapse_to_budget(raw, target)
        if collapsed is None:
            out.append(
                _row(raw, variant, "collapsed", budget, "pruned: budget below one parameter")
            )
        else:
            res = _test(collapsed.table, variant, "collapsed", budget, config)
            res.merges = "; ".join(f"{v}: {a}+{b}" for v, a, b in collapsed.merges)
            out.append(res)
    return out


def _row(table: CountTable, variant: str, representation: str, budget: int, status: str) -> Result:
    return Result(
        variant=variant,
        order=table.k,
        variables=" x ".join(table.variables),
        representation=representation,
        levels="x".join(str(L) for L in table.n_levels),
        term_params=table.term_params,
        budget=budget,
        status=status,
        _table=table,
    )


def _test(
    table: CountTable, variant: str, representation: str, budget: int, config: SearchConfig
) -> Result:
    res = _row(table, variant, representation, budget, "tested")
    t = interaction_test(table)
    res.statistic, res.df, res.boundary = t.statistic, t.df, t.boundary
    if not t.converged:
        res.status = "excluded: fit did not converge"
    elif t.df <= 0:
        res.status = "excluded: no residual degrees of freedom"
    else:
        res.p_value = t.p_value
    _profile(res, table, config.min_cell)
    return res


def wilson_interval(pos: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return float("nan"), float("nan")
    p = pos / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return float(centre - half), float(centre + half)


def _profile(res: Result, table: CountTable, min_cell: int) -> None:
    """Highest-risk subgroup, released only if it passes the minimum-cell disclosure rule."""
    rate = table.events / table.total
    eligible = np.nonzero(table.n >= min_cell)[0]
    if len(eligible) == 0 or rate == 0:
        return
    lift = (table.pos[eligible] / table.n[eligible]) / rate
    best = eligible[int(np.argmax(lift))]
    res.top_cell = table.label(best)
    res.top_cell_n = int(table.n[best])
    res.top_cell_rate = float(table.pos[best] / table.n[best])
    res.top_cell_ci_low, res.top_cell_ci_high = wilson_interval(
        int(table.pos[best]), int(table.n[best])
    )
    res.top_cell_lift = float(lift.max())


def _stability(res: Result, threshold: float, config: SearchConfig) -> float:
    """Share of bootstrap resamples in which the interaction stays below the BH threshold."""
    table = res._table
    assert table is not None
    key = f"{res.variant}/{res.variables}/{res.representation}"
    rng = np.random.default_rng([config.stability_seed, zlib.crc32(key.encode())])
    hits = 0
    for _ in range(config.resamples):
        t = interaction_test(table.resample(rng))
        hits += t.converged and t.df > 0 and t.p_value <= threshold
    return hits / config.resamples


def config_dict(config: SearchConfig) -> dict:
    d = asdict(config)
    d["orders"] = list(config.orders)
    d["variables"] = list(config.variables) if config.variables else None
    d["proxies"] = list(config.proxies)
    return d
