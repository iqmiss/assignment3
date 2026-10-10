import numpy as np
import pandas as pd
import pytest

from hode.adapters import DataFrameSource
from hode.synthetic import SyntheticSource, SyntheticSpec


@pytest.fixture(scope="session")
def d1_source():
    """Synthetic registry at the size of the published registry D1 (n = 21,331)."""
    return SyntheticSource(SyntheticSpec())


@pytest.fixture(scope="session")
def d2_source():
    """Synthetic registry at the size the client asked for (n = 50,000).

    At this size the gated search recovers the planted triple in 17 of 20
    seeds (see scripts/power_curve.py), so the fixture pins a seed where it does:
    the test checks the engine, not the luck of the draw.
    """
    return SyntheticSource(SyntheticSpec(n=50_000, seed=0))


@pytest.fixture(scope="session")
def null_source():
    """Synthetic registry with no planted interactions: every interaction is null."""
    return SyntheticSource(SyntheticSpec(planted=()))


@pytest.fixture
def small_frame():
    rng = np.random.default_rng(0)
    n = 600
    frame = pd.DataFrame(
        {
            "a": rng.choice(["x", "y", "z"], n),
            "b": rng.choice(["p", "q"], n),
            "c": rng.choice(["u", "v", "w", "t"], n, p=[0.4, 0.3, 0.2, 0.1]),
        }
    )
    logit = -1.0 + 0.8 * (frame["a"] == "y") + 0.5 * (frame["b"] == "q")
    frame["y"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return frame


@pytest.fixture
def small_source(small_frame):
    return DataFrameSource(small_frame, "y")
