# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-10

First public increment (cycle 2 of the HODE plan).

### Added
- `CountTable` and the `CountSource` port: the analysis core sees count tables only.
- `DataFrameSource` registry adapter with an order-independent data fingerprint.
- Synthetic registry generator that mirrors registry D1 (n = 21,331, 6.37 %),
  with a planted pairwise interaction and a planted three-way interaction.
- Parameter budget (≥ 10 events per parameter) and frequency-based level collapsing.
- Grouped binomial logistic regression (IRLS) and the k-way interaction LRT.
- Benjamini–Hochberg FDR within each order, and hierarchical gating.
- Bootstrap stability on counts, and subgroup profiles with Wilson intervals
  under a minimum-cell disclosure rule.
- `all` / `no-proxy` variants for fields that track administrative status.
- Run manifest and `hode verify`. CLI: `hode synth`, `hode run`, `hode verify`.
- GitHub Actions CI (lint, test matrix, reproducibility check, build) and a
  tag-triggered release workflow.
