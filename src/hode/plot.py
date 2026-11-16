"""Heatmaps of the combinations a run found: ``hode plot``.

For every significant pair in a run, draw the outcome rate in each cell of the
two-way table, in the style of the heatmaps of the first study. The figures are
rebuilt from the run's manifest and the same count tables the analysis used,
so they show exactly what was tested. Cells below the run's minimum-cell rule
are left blank: a figure never discloses more than ``results.csv`` may.

matplotlib is an optional dependency (``pip install "hode[plot]"``); the
analysis core does not need it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from hode.manifest import load_manifest
from hode.table import CountTable


def rate_grid(table: CountTable, min_cell: int) -> tuple[np.ndarray, np.ndarray]:
    """Outcome rate and size of every cell of a two-way table, as (L0, L1) arrays.

    The rate is NaN for cells that are unobserved or smaller than ``min_cell``.
    """
    if table.k != 2:
        raise ValueError("a heatmap needs a two-way table")
    n = np.zeros(table.n_levels, dtype=np.int64)
    pos = np.zeros(table.n_levels, dtype=np.int64)
    n[table.cells[:, 0], table.cells[:, 1]] = table.n
    pos[table.cells[:, 0], table.cells[:, 1]] = table.pos
    rate = np.full(table.n_levels, np.nan)
    shown = n >= min_cell
    rate[shown] = pos[shown] / n[shown]
    return rate, n


def _pretty(name: str) -> str:
    return name.replace("_", " ")


def heatmap(table: CountTable, row: pd.Series, min_cell: int, outcome: str):
    """One figure: rate per cell, the highest-risk cell outlined, small cells blank."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    rate, n = rate_grid(table, min_cell)
    average = table.events / table.total
    a, b = table.variables
    rows, cols = table.n_levels

    fig, ax = plt.subplots(figsize=(1.25 * cols + 3.2, 0.62 * rows + 2.2))
    vmax = float(np.nanmax(rate)) if np.isfinite(rate).any() else 1.0
    image = ax.imshow(np.ma.masked_invalid(rate), cmap="Reds", vmin=0, vmax=vmax, aspect="auto")
    for i in range(rows):
        for j in range(cols):
            if np.isnan(rate[i, j]):
                text, colour = f"<{min_cell}", "#888888"
            else:
                text = f"{rate[i, j]:.1%}"
                colour = "white" if rate[i, j] > 0.6 * vmax else "black"
            ax.text(j, i, text, ha="center", va="center", fontsize=9, color=colour)
    if np.isfinite(rate).any():
        i, j = np.unravel_index(np.nanargmax(rate), rate.shape)
        ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, lw=2.5, ec="#14213D"))

    ax.set_xticks(range(cols), table.levels[1], rotation=30, ha="right")
    ax.set_yticks(range(rows), table.levels[0])
    ax.set_xlabel(_pretty(b))
    ax.set_ylabel(_pretty(a))
    ax.set_title(
        f"{_pretty(outcome).capitalize()} rate by {_pretty(a)} and {_pretty(b)}\n"
        f"average {average:.1%} · q = {row.q_value:.1e} · stability {row.stability:.2f}",
        fontsize=11,
    )
    fig.colorbar(image, ax=ax, label="rate", format=lambda x, _: f"{x:.0%}")
    fig.tight_layout()
    return fig


def plot_run(
    manifest_path: str | Path,
    out_dir: str | Path | None = None,
    data_path: str | Path | None = None,
    variant: str = "all",
) -> list[Path]:
    """Draw a heatmap for every significant pair of a run; return the files written."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    manifest_path = Path(manifest_path)
    _, config = load_manifest(manifest_path, data_path)
    results = pd.read_csv(manifest_path.parent / "results.csv")
    chosen = results[
        (results["significant"] == True)  # noqa: E712 (column may hold NaN)
        & (results["order"] == 2)
        & (results["variant"] == variant)
    ].sort_values("q_value")

    out = Path(out_dir) if out_dir is not None else manifest_path.parent / "plots"
    out.mkdir(parents=True, exist_ok=True)
    source = config.source()
    written = []
    for _, row in chosen.iterrows():
        variables = row["variables"].split(" x ")
        fig = heatmap(source.table(variables), row, config.search.min_cell, source.outcome)
        path = out / f"{'__'.join(variables)}.png"
        fig.savefig(path, dpi=150, metadata={"Software": None})
        plt.close(fig)
        written.append(path)
    return written
