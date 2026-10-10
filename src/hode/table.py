"""Contingency tables of an outcome over a combination of categorical variables.

A :class:`CountTable` is the only thing the analysis core ever sees. It holds,
for every observed combination of levels, the number of positive cases and the
number of cases in total. For categorical predictors the logistic likelihood
depends on the data only through these counts (the grouped binomial form), so
nothing statistical is lost by never passing record-level rows to the core.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from math import prod

import numpy as np


@dataclass(frozen=True)
class CountTable:
    """Positive and total counts for each observed cell of a k-way table.

    Attributes:
        variables: names of the k variables, in order.
        levels: for each variable, the level labels; index ``j`` in ``cells``
            refers to ``levels[i][j]``.
        cells: integer array of shape (m, k); one row per observed cell.
        pos: positive (outcome = 1) count in each cell.
        n: total count in each cell; always ``n >= pos`` and ``n > 0``.
    """

    variables: tuple[str, ...]
    levels: tuple[tuple[str, ...], ...]
    cells: np.ndarray
    pos: np.ndarray
    n: np.ndarray

    def __post_init__(self) -> None:
        if self.cells.ndim != 2 or self.cells.shape[1] != len(self.variables):
            raise ValueError("cells must have shape (m, k) with k = len(variables)")
        if not (len(self.pos) == len(self.n) == self.cells.shape[0]):
            raise ValueError("cells, pos and n must have the same length")
        if np.any(self.n <= 0) or np.any(self.pos < 0) or np.any(self.pos > self.n):
            raise ValueError("counts must satisfy 0 <= pos <= n and n > 0")

    @property
    def k(self) -> int:
        return len(self.variables)

    @property
    def n_levels(self) -> tuple[int, ...]:
        return tuple(len(lv) for lv in self.levels)

    @property
    def events(self) -> int:
        return int(self.pos.sum())

    @property
    def total(self) -> int:
        return int(self.n.sum())

    @property
    def term_params(self) -> int:
        """Parameters added by the k-way interaction term: prod(L_i - 1)."""
        return prod(L - 1 for L in self.n_levels)

    def label(self, row: int) -> str:
        """Human-readable label of one cell, e.g. ``region=R2, status=S1``."""
        return ", ".join(
            f"{v}={self.levels[i][self.cells[row, i]]}" for i, v in enumerate(self.variables)
        )

    def collapse(self, var: int, groups: list[list[int]]) -> CountTable:
        """Merge levels of variable ``var``; ``groups`` lists old indices per new level.

        Collapsing works on counts alone, so it is exact: a collapsed table is
        identical to the table that would be counted from collapsed records.
        """
        mapping = np.empty(self.n_levels[var], dtype=np.int64)
        for new, olds in enumerate(groups):
            mapping[olds] = new
        new_labels = tuple("|".join(self.levels[var][j] for j in olds) for olds in groups)
        cells = self.cells.copy()
        cells[:, var] = mapping[cells[:, var]]
        levels = self.levels[:var] + (new_labels,) + self.levels[var + 1 :]
        return aggregate(self.variables, levels, cells, self.pos, self.n)

    def resample(self, rng: np.random.Generator) -> CountTable:
        """One nonparametric bootstrap draw, done on the table instead of the rows.

        Resampling N rows with replacement is a multinomial draw over the 2m
        (cell, outcome) categories, so it never needs the records.
        """
        neg = self.n - self.pos
        probs = np.concatenate([self.pos, neg]) / self.total
        draw = rng.multinomial(self.total, probs)
        m = len(self.n)
        pos, n = draw[:m], draw[:m] + draw[m:]
        keep = n > 0
        return CountTable(self.variables, self.levels, self.cells[keep], pos[keep], n[keep])

    def fingerprint(self) -> str:
        """SHA-256 of the canonical content of the table."""
        h = hashlib.sha256()
        h.update(repr((self.variables, self.levels)).encode())
        for arr in (self.cells, self.pos, self.n):
            h.update(np.ascontiguousarray(arr, dtype=np.int64).tobytes())
        return h.hexdigest()


def aggregate(
    variables: tuple[str, ...],
    levels: tuple[tuple[str, ...], ...],
    cells: np.ndarray,
    pos: np.ndarray,
    n: np.ndarray,
) -> CountTable:
    """Sum duplicate cells and return a table with cells in lexicographic order."""
    uniq, inverse = np.unique(cells, axis=0, return_inverse=True)
    inverse = inverse.ravel()
    pos_sum = np.bincount(inverse, weights=pos, minlength=len(uniq)).astype(np.int64)
    n_sum = np.bincount(inverse, weights=n, minlength=len(uniq)).astype(np.int64)
    keep = n_sum > 0
    return CountTable(variables, levels, uniq[keep].astype(np.int64), pos_sum[keep], n_sum[keep])
