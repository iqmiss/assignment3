"""How many records does the planted triple need? Detection rate against sample size.

Runs the gated k = 2, 3 search on synthetic registries of increasing size and
records, for each size, how often the planted three-way interaction is
declared significant and how many other triples are (false discoveries).

    python scripts/power_curve.py --seeds 20 --out results/power_curve.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from hode.search import SearchConfig, run_search
from hode.synthetic import SyntheticSource, SyntheticSpec

TRIPLE = "region x age_group x occupation_group"
SIZES = (21_331, 30_000, 40_000, 50_000, 75_000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--out", type=Path, default=Path("results/power_curve.csv"))
    args = parser.parse_args()

    rows = []
    for n in SIZES:
        for seed in range(args.seeds):
            frame = run_search(
                SyntheticSource(SyntheticSpec(n=n, seed=seed)),
                SearchConfig(orders=(2, 3), resamples=0),
            )
            sig = set(frame[(frame["order"] == 3) & frame["significant"]]["variables"])
            rows.append(
                {
                    "n": n,
                    "seed": seed,
                    "triple_found": TRIPLE in sig,
                    "false_triples": len(sig - {TRIPLE}),
                }
            )
        found = sum(r["triple_found"] for r in rows if r["n"] == n)
        print(f"n={n:>6}: planted triple found in {found}/{args.seeds} seeds", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
