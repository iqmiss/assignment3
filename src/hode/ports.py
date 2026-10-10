"""The CountSource port: the boundary between the data zone and the analysis core.

The core depends only on this protocol. A registry adapter implements it inside
the environment that holds the records; the synthetic adapter implements it
for reviewers and for continuous integration. Neither the core nor the tests
can tell them apart, which is the point.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from hode.table import CountTable


@runtime_checkable
class CountSource(Protocol):
    """Anything that can answer 'give me the counts for these variables'."""

    outcome: str

    def variables(self) -> list[str]:
        """Names of the categorical predictors available for search."""
        ...

    def table(self, variables: Sequence[str]) -> CountTable:
        """Positive and total counts over every observed combination of levels."""
        ...

    def fingerprint(self) -> str:
        """A stable hash identifying the exact data snapshot behind the source."""
        ...
