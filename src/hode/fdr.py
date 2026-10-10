"""Benjamini-Hochberg false discovery rate control."""

from __future__ import annotations

import numpy as np


def bh_adjust(p_values: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (q-values). NaNs are passed through."""
    p = np.asarray(p_values, dtype=float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    m = int(ok.sum())
    if m == 0:
        return q
    pv = p[ok]
    order = np.argsort(pv, kind="stable")
    ranked = pv[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted = np.empty(m)
    adjusted[order] = np.minimum(ranked, 1.0)
    q[ok] = adjusted
    return q


def bh_threshold(p_values: np.ndarray, alpha: float) -> float:
    """Largest raw p-value declared significant at FDR ``alpha`` (0.0 if none)."""
    p = np.asarray(p_values, dtype=float)
    p = np.sort(p[~np.isnan(p)])
    m = len(p)
    if m == 0:
        return 0.0
    below = p <= alpha * np.arange(1, m + 1) / m
    return float(p[np.nonzero(below)[0].max()]) if below.any() else 0.0
