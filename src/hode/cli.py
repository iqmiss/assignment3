"""Command-line interface: ``hode synth``, ``hode run``, ``hode verify``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hode import __version__
from hode.manifest import RunConfig, run, verify
from hode.synthetic import SyntheticSpec, generate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hode", description=__doc__)
    parser.add_argument("--version", action="version", version=f"hode {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_synth = sub.add_parser("synth", help="write a synthetic registry to CSV")
    p_synth.add_argument("--n", type=int, default=SyntheticSpec.n)
    p_synth.add_argument("--seed", type=int, default=SyntheticSpec.seed)
    p_synth.add_argument("--out", type=Path, required=True)

    p_run = sub.add_parser("run", help="run a search from a TOML configuration")
    p_run.add_argument("config", type=Path)

    p_verify = sub.add_parser("verify", help="rerun a manifest and compare hashes")
    p_verify.add_argument("manifest", type=Path)
    p_verify.add_argument("--data", type=Path, default=None, help="CSV path for CSV-based runs")

    args = parser.parse_args(argv)

    if args.command == "synth":
        frame = generate(SyntheticSpec(n=args.n, seed=args.seed))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.out, index=False, lineterminator="\n")
        print(f"wrote {len(frame)} rows ({frame['recidivist'].mean():.2%} positive) to {args.out}")
        return 0

    if args.command == "run":
        config = RunConfig.load(args.config)
        frame, manifest = run(config)
        print(
            f"{manifest['n_tests']} tests, {manifest['n_significant']} significant "
            f"at FDR {config.search.fdr}; results in {config.out_dir}"
        )
        shown = frame[frame["significant"]].head(10)
        for _, r in shown.iterrows():
            print(
                f"  [{r.variant}] k={r.order} {r.variables:<50} [{r.representation}] "
                f"q={r.q_value:.2e} stability={r.stability:.2f}"
            )
        return 0

    problems = verify(args.manifest, args.data)
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print("OK: rerun reproduced the data fingerprint and the results hash exactly")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
