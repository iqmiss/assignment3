"""Grouped binomial logistic regression and the interaction likelihood-ratio test.

The test for a k-way interaction compares the saturated model (which fits
every observed cell exactly, deviance 0) with the hierarchical model that
contains every term of order k - 1 and below. The deviance of the reduced
model is therefore the likelihood-ratio statistic. For k = 2 this is the
pairwise test of the published study; for k = 1 it equals the G-test.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

import numpy as np
from scipy.special import expit, xlogy
from scipy.stats import chi2

from hode.table import CountTable

ETA_LIMIT = 30.0
BOUNDARY_ETA = 20.0


def design_matrix(cells: np.ndarray, n_levels: tuple[int, ...], max_order: int) -> np.ndarray:
    """Treatment-coded design with every interaction term up to ``max_order``.

    Level 0 of each variable is the reference. Columns for a term over the
    variable subset S are products of the indicator columns of its members.
    """
    m, k = cells.shape
    columns = [np.ones(m)]
    for order in range(1, max_order + 1):
        for subset in combinations(range(k), order):
            ranges = [range(1, n_levels[i]) for i in subset]
            for combo in product(*ranges):
                col = np.ones(m, dtype=bool)
                for i, level in zip(subset, combo, strict=True):
                    col &= cells[:, i] == level
                columns.append(col.astype(float))
    return np.column_stack(columns)


def binomial_deviance(y: np.ndarray, n: np.ndarray, p: np.ndarray) -> float:
    """Deviance of fitted probabilities against the saturated model."""
    mu = n * p
    return float(
        2.0
        * np.sum(
            xlogy(y, y / np.where(mu > 0, mu, 1.0))
            + xlogy(n - y, (n - y) / np.where(n - mu > 0, n - mu, 1.0))
        )
    )


@dataclass(frozen=True)
class Fit:
    beta: np.ndarray
    eta: np.ndarray
    deviance: float
    rank: int
    converged: bool
    iterations: int

    @property
    def boundary(self) -> bool:
        """Some fitted log-odds diverge (a margin with zero events or zero non-events).

        The deviance still converges to its limit, so the likelihood-ratio
        statistic remains valid; the flag tells the reader that nuisance
        coefficients of the reduced model sit on the boundary.
        """
        return bool(np.max(np.abs(self.eta)) > BOUNDARY_ETA)


def fit_binomial(
    X: np.ndarray, y: np.ndarray, n: np.ndarray, max_iter: int = 100, tol: float = 1e-10
) -> Fit:
    """Fit a logistic model to grouped counts by iteratively reweighted least squares.

    Rank-deficient designs (levels absent from the observed cells) are handled
    by the minimum-norm least-squares step; fitted values remain unique.
    """
    y = np.asarray(y, dtype=float)
    n = np.asarray(n, dtype=float)
    p0 = (y.sum() + 0.5) / (n.sum() + 1.0)
    eta = np.full(len(y), np.log(p0 / (1 - p0)))
    beta = np.zeros(X.shape[1])
    dev_old = np.inf
    converged = False
    iterations = 0
    for iterations in range(1, max_iter + 1):  # noqa: B007 - reported in Fit
        p = np.clip(expit(eta), 1e-12, 1 - 1e-12)
        w = n * p * (1 - p)
        z = eta + (y - n * p) / w
        sw = np.sqrt(w)
        beta, *_ = np.linalg.lstsq(X * sw[:, None], z * sw, rcond=None)
        eta = np.clip(X @ beta, -ETA_LIMIT, ETA_LIMIT)
        dev = binomial_deviance(y, n, expit(eta))
        if abs(dev - dev_old) <= tol * (abs(dev) + 0.1):
            converged = True
            break
        dev_old = dev
    rank = int(np.linalg.matrix_rank(X))
    return Fit(beta, eta, dev, rank, converged, iterations)


@dataclass(frozen=True)
class InteractionTest:
    statistic: float
    df: int
    p_value: float
    converged: bool
    boundary: bool


def interaction_test(table: CountTable) -> InteractionTest:
    """Likelihood-ratio test of the highest-order interaction in ``table``."""
    X = design_matrix(table.cells, table.n_levels, table.k - 1)
    fit = fit_binomial(X, table.pos, table.n)
    df = len(table.n) - fit.rank
    stat = max(fit.deviance, 0.0)
    p = float(chi2.sf(stat, df)) if df > 0 else float("nan")
    return InteractionTest(stat, df, p, fit.converged, fit.boundary)
