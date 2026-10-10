"""Adapters that implement the CountSource port over record-level data.

``DataFrameSource`` is the registry adapter. It is meant to run inside the
environment that holds the records; only count tables leave it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from hode.table import CountTable, aggregate

MISSING = "NA"


class DataFrameSource:
    """CountSource over a pandas DataFrame of categorical predictors and a 0/1 outcome."""

    def __init__(self, frame: pd.DataFrame, outcome: str, variables: Sequence[str] | None = None):
        if outcome not in frame.columns:
            raise KeyError(f"outcome column {outcome!r} not found")
        y = frame[outcome]
        if not y.isin([0, 1]).all():
            raise ValueError("outcome must be coded 0/1 with no missing values")
        self.outcome = outcome
        names = (
            list(variables) if variables is not None else [c for c in frame.columns if c != outcome]
        )
        missing = [v for v in names if v not in frame.columns]
        if missing:
            raise KeyError(f"variables not found: {missing}")
        self._y = y.to_numpy(dtype=np.int64)
        self._codes: dict[str, np.ndarray] = {}
        self._levels: dict[str, tuple[str, ...]] = {}
        for v in names:
            col = frame[v].astype("string").fillna(MISSING)
            cat = pd.Categorical(col, categories=sorted(col.unique()))
            self._codes[v] = np.asarray(cat.codes, dtype=np.int64)
            self._levels[v] = tuple(str(c) for c in cat.categories)
        self._names = names
        self._fingerprint = _frame_fingerprint(frame[names + [outcome]])

    @classmethod
    def from_csv(cls, path: str | Path, outcome: str, variables: Sequence[str] | None = None):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        frame[outcome] = pd.to_numeric(frame[outcome])
        return cls(frame, outcome, variables)

    def variables(self) -> list[str]:
        return list(self._names)

    def table(self, variables: Sequence[str]) -> CountTable:
        variables = tuple(variables)
        cells = np.column_stack([self._codes[v] for v in variables])
        levels = tuple(self._levels[v] for v in variables)
        ones = np.ones(len(self._y), dtype=np.int64)
        return aggregate(variables, levels, cells, self._y, ones)

    def fingerprint(self) -> str:
        return self._fingerprint


def _frame_fingerprint(frame: pd.DataFrame) -> str:
    """Order-independent SHA-256 of the rows of a frame.

    Each column is encoded against its sorted level labels, the rows are put in
    lexicographic order, and the labels plus the sorted code matrix are hashed.
    Shuffling the rows or the columns leaves the fingerprint unchanged.
    """
    h = hashlib.sha256()
    codes = []
    for col in sorted(frame.columns):
        values = frame[col].astype("string").fillna(MISSING)
        cat = pd.Categorical(values, categories=sorted(values.unique()))
        h.update(repr((col, tuple(cat.categories))).encode())
        codes.append(np.asarray(cat.codes, dtype=np.int64))
    matrix = np.column_stack(codes)
    order = np.lexsort(matrix.T[::-1])
    h.update(np.ascontiguousarray(matrix[order]).tobytes())
    return h.hexdigest()
