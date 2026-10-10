"""Parameter budget and level collapsing.

At ten events per parameter, 1,359 positive cases identify about 136
parameters. One three-way term among ten-level variables adds 9 x 9 x 9 = 729,
so higher orders are reached by spending the budget deliberately, not by
buying compute. These functions make that trade-off explicit and logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import prod

from hode.table import CountTable


def parameter_budget(table: CountTable, events_per_parameter: float = 10.0) -> int:
    """Largest number of parameters the data can identify.

    Uses the rarer of the two outcomes, so the rule also holds for common outcomes.
    """
    if events_per_parameter <= 0:
        raise ValueError("events_per_parameter must be positive")
    events = min(table.events, table.total - table.events)
    return int(events // events_per_parameter)


def term_params(n_levels: tuple[int, ...]) -> int:
    """Parameters introduced by one interaction term over variables with these level counts."""
    return prod(L - 1 for L in n_levels)


@dataclass(frozen=True)
class Collapse:
    """Result of collapsing a table to fit the budget."""

    table: CountTable
    merges: tuple[tuple[str, str, str], ...]  # (variable, merged level a, merged level b)

    @property
    def changed(self) -> bool:
        return bool(self.merges)


def collapse_to_budget(table: CountTable, budget: int) -> Collapse | None:
    """Merge rare levels until the k-way term fits the budget.

    Greedy and deterministic: repeatedly take the variable with the most levels
    (ties broken by position) and merge its two least populated levels. Returns
    ``None`` when even an all-binary term would not fit (budget < 1).
    """
    if budget < 1:
        return None
    merges: list[tuple[str, str, str]] = []
    current = table
    while current.term_params > budget:
        L = current.n_levels
        var = max(range(current.k), key=lambda i: (L[i], -i))
        if L[var] <= 2:  # pragma: no cover - unreachable while budget >= 1
            return None
        sizes = [0] * L[var]
        for row in range(len(current.n)):
            sizes[current.cells[row, var]] += int(current.n[row])
        a, b = sorted(sorted(range(L[var]), key=lambda j: (sizes[j], j))[:2])
        labels = current.levels[var]
        merges.append((current.variables[var], labels[a], labels[b]))
        groups = [[j] for j in range(L[var]) if j not in (a, b)]
        groups.insert(a, [a, b])
        current = current.collapse(var, groups)
    return Collapse(current, tuple(merges))
