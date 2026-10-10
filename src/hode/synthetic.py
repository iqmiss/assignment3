"""Synthetic registry generator with planted, known effects.

The real registry cannot leave its approved environment, so reviewers and CI
run HODE on synthetic data instead. The generator mirrors the published
registry (article 1): its size (n = 21,331), its base rate (6.37 %) and the
names of its grouped fields, including the three fields that track
administrative conviction status (the "proxy" fields). Level labels are
synthetic codes; nothing here describes real people.

Planted structure, known in advance:

* the proxy fields have strong main effects, as in article 1;
* ``region`` is weak on its own ...
* ... but takes part in a planted pairwise interaction
  (region x investigation_group) and a planted three-way interaction
  (region x occupation_group x age_group), the life-course pattern that
  article 2 looks for: unemployment matters in combination with age.

Every other combination is null by construction, so the generator doubles as
a ground truth for whether the search finds what is there and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

from hode.adapters import DataFrameSource

OUTCOME = "recidivist"

# Fields that track prior-offence / registry status (article 1, data_pipeline.py).
PROXY_VARIABLES = ("conviction_group", "crime_context_group", "registry_group")

# name -> (levels, sampling probabilities, main-effect log-odds per level)
VARIABLES: dict[str, tuple[list[str], list[float], list[float]]] = {
    "region": (
        ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"],
        [0.22, 0.18, 0.15, 0.12, 0.11, 0.09, 0.08, 0.05],
        [0.0, 0.05, -0.05, 0.08, -0.04, 0.03, -0.06, 0.02],
    ),
    "age_group": (
        ["18-24", "25-34", "35-44", "45-54", "55+"],
        [0.20, 0.32, 0.25, 0.15, 0.08],
        [0.30, 0.15, 0.0, -0.20, -0.50],
    ),
    "gender": (["F", "M"], [0.18, 0.82], [0.0, 0.30]),
    "occupation_group": (
        ["Worker", "Unemployed", "Student", "Pensioner", "Other"],
        [0.42, 0.38, 0.07, 0.05, 0.08],
        [0.0, 0.25, -0.20, -0.40, 0.05],
    ),
    "investigation_group": (
        ["I1", "I2", "I3", "I4", "I5"],
        [0.40, 0.25, 0.20, 0.10, 0.05],
        [0.0, 0.10, -0.10, 0.20, 0.0],
    ),
    "condition_group": (["N1", "N2", "N3"], [0.70, 0.20, 0.10], [0.0, 0.15, -0.10]),
    "complicity_type": (["Alone", "Group"], [0.78, 0.22], [0.0, 0.10]),
    "conviction_group": (
        ["V1", "V2", "V3", "V4"],
        [0.50, 0.25, 0.15, 0.10],
        [0.0, 1.20, 0.60, -0.50],
    ),
    "crime_context_group": (
        ["C1", "C2", "C3", "C4", "C5"],
        [0.35, 0.25, 0.20, 0.12, 0.08],
        [0.0, 0.50, 0.90, -0.30, 0.20],
    ),
    "registry_group": (["G1", "G2", "G3"], [0.60, 0.25, 0.15], [0.0, 0.50, 1.00]),
}


@dataclass(frozen=True)
class Planted:
    """A planted interaction: extra log-odds where every variable takes one of the given levels."""

    levels: dict[str, tuple[str, ...]]
    log_odds: float


DEFAULT_PLANTED: tuple[Planted, ...] = (
    Planted({"region": ("R05",), "investigation_group": ("I2",)}, 1.0),
    Planted(
        {"region": ("R03", "R04"), "occupation_group": ("Unemployed",), "age_group": ("18-24",)},
        1.6,
    ),
)


@dataclass(frozen=True)
class SyntheticSpec:
    n: int = 21_331
    base_rate: float = 0.0637
    seed: int = 2026
    planted: tuple[Planted, ...] = field(default=DEFAULT_PLANTED)


DEFAULT_SPEC = SyntheticSpec()


def generate(spec: SyntheticSpec = DEFAULT_SPEC) -> pd.DataFrame:
    """Draw a synthetic registry. The same spec always gives the same frame."""
    rng = np.random.default_rng(spec.seed)
    data: dict[str, np.ndarray] = {}
    logit = np.zeros(spec.n)
    for name, (levels, probs, effects) in VARIABLES.items():
        idx = rng.choice(len(levels), size=spec.n, p=probs)
        data[name] = np.asarray(levels, dtype=object)[idx]
        logit += np.asarray(effects)[idx]
    for p in spec.planted:
        mask = np.ones(spec.n, dtype=bool)
        for var, levels in p.levels.items():
            mask &= np.isin(data[var], levels)
        logit += p.log_odds * mask

    # Choose the intercept so that the expected base rate is exactly as specified.
    b0 = brentq(lambda b: expit(b + logit).mean() - spec.base_rate, -20.0, 20.0)
    y = rng.random(spec.n) < expit(b0 + logit)
    frame = pd.DataFrame(data)
    frame[OUTCOME] = y.astype(np.int64)
    return frame


class SyntheticSource(DataFrameSource):
    """CountSource over a freshly generated synthetic registry."""

    def __init__(self, spec: SyntheticSpec = DEFAULT_SPEC):
        self.spec = spec
        super().__init__(generate(spec), OUTCOME)
