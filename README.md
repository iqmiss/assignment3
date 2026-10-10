# HODE: higher-order determinant discovery

[![CI](https://github.com/iqmiss/assignment3/actions/workflows/ci.yml/badge.svg)](https://github.com/iqmiss/assignment3/actions/workflows/ci.yml)
[![Release](https://github.com/iqmiss/assignment3/actions/workflows/release.yml/badge.svg)](https://github.com/iqmiss/assignment3/actions/workflows/release.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

HODE finds **combinations of categorical factors** (pairs, triples and more)
that are associated with a binary outcome. It checks that every combination it
reports is **statistically supported**: there must be enough events per
parameter, false discoveries are controlled, and the result must be stable
under resampling. It is the statistical engine of a dissertation on
determinants of recidivism in Kazakhstani administrative data, released here
as a small, tested, reproducible module.

> **Course context.** Applied Software Development Project, Astana IT University,
> Assignment 3 (Software Development and Integration). This module is the
> cycle-2 increment planned in Assignment 1 (costing) and Assignment 2
> (methodology and architecture).

---

## Why

The first study ([1], n = 21,331, 6.37 % recidivists) found that **region is
weak on its own** (Cramér's V = 0.051) **yet takes part in five of the seven
strongest pairwise interactions**. A factor can be negligible alone and
decisive in combination. The obvious next question is what happens with three
or four factors. That study could not answer it, for two reasons:

* **Identifiability.** One three-way term among ten-level fields adds
  9 × 9 × 9 = 729 parameters, while 1,359 positive cases support about 136 at
  ten events per parameter. The data, not the hardware, is the limit.
* **Privacy.** The registry cannot leave its approved environment, so nobody
  else can rerun the analysis.

HODE handles both. It spends a parameter budget explicitly, merging rare
levels when needed and logging every merge. And it never sees a record: the
analysis core works on **count tables** only.

## What it does

```
records ──► [registry adapter] ──► count tables ──► analysis core ──► results.csv
 (secure zone; never leaves)      (CountSource port)                  manifest.json
                                   ▲
            [synthetic adapter] ───┘  (for reviewers and CI)
```

For every combination of *k* variables (k = 2, 3, …), the analysis core:

1. **Budgets.** It computes how many parameters the data can identify
   (≥ 10 events per parameter). An over-budget table is pruned, and a
   collapsed version is built by merging the least populated levels. Levels
   are merged by frequency only, never by outcome.
2. **Gates (hierarchical).** A k-way combination is tested only if every
   (k−1)-way subset of it was significant.
3. **Tests.** It runs a likelihood-ratio test of the k-way interaction against
   the model that has every lower-order term. The fit is a grouped binomial
   logistic regression on the counts, which gives exactly the same estimates
   as a fit on the records (a test checks this).
4. **Corrects.** It applies Benjamini–Hochberg FDR within each order.
5. **Resamples.** It measures bootstrap stability: the share of resamples in
   which the combination stays significant.
6. **Profiles.** It reports the highest-risk subgroup with its size, its rate
   with a 95 % Wilson interval, and its lift. Subgroups with fewer than 10
   cases are never released.
7. **Proxy check.** It optionally reruns everything without the fields that
   track administrative status, to separate life circumstances from
   record-keeping.

## Quick start

```bash
git clone https://github.com/iqmiss/assignment3.git
cd assignment3
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

hode run configs/synthetic.toml        # k = 2, 3 sweep on the synthetic registry
hode verify results/manifest.json      # rerun from the manifest, compare hashes
pytest --cov                           # 53 tests, coverage gate 80 %
```

On your own (de-identified, categorical) data:

```bash
hode synth --out data/example.csv      # see the expected format
```

```toml
# my_run.toml
[data]
source = "csv"
path = "data/my_registry.csv"
outcome = "recidivist"                 # 0/1 column; every other column is a predictor

[search]
orders = [2, 3]
fdr = 0.05
proxies = []                           # fields to drop in the "no-proxy" variant

[output]
dir = "results"
```

## Output

`results.csv` has one row per (variant, combination, representation):

| column | meaning |
|---|---|
| `variant` | `all`, or `no-proxy` when proxy fields are declared |
| `order`, `variables` | k and the combination, e.g. `region x age_group x occupation_group` |
| `representation` | `raw`, or `collapsed` (with the merges listed in `merges`) |
| `term_params`, `budget` | parameters of the k-way term, and the identifiable ceiling |
| `status` | `tested`, `pruned: …`, `skipped: …` (gated out), `excluded: …` |
| `statistic`, `df`, `p_value`, `q_value`, `significant` | LRT and BH-adjusted result |
| `boundary` | some reduced-model margin has zero events (the LRT is still valid; read with care) |
| `stability` | share of bootstrap resamples that stay significant |
| `top_cell`, `top_cell_n`, `top_cell_rate`, `top_cell_ci_low/high`, `top_cell_lift` | subgroup profile, released only if n ≥ `min_cell` |

`manifest.json` records the configuration, the data fingerprint
(order-independent SHA-256), the package versions and the SHA-256 of the
results. `hode verify` reruns the analysis and fails if either hash differs.

## What the synthetic registry shows

The generator mirrors the published registry: n = 21,331, a base rate of
6.37 %, and article 1's grouped field names, including three proxy fields.
It plants a pairwise effect (region × investigation_group) and a life-course
triple (region × occupation_group × age_group: young and unemployed, in two
regions). Every other combination is null.

* **Null data:** no false discoveries in any of the 165 tests, across 5 seeds.
* **n = 21,331:** the pair is found. The triple is **not** recoverable, because
  power runs out before k = 3. This is the risk Assignment 1 put at the top of
  its register.
* **n = 50,000** (the size the client inquiry requires): the triple is
  recovered in most seeds, and it survives removal of the proxy fields.
  `scripts/power_curve.py` measures the detection rate against sample size.

## Technology choices

| Choice | Why | Rejected alternatives |
|---|---|---|
| **Python 3.11+** | The language of the existing pipeline and of the research community. `tomllib` is in the standard library, so configuration needs no dependency. | R (the rest of the pipeline is Python); Julia (too small an ecosystem for reviewers) |
| **NumPy / SciPy** | IRLS on small dense designs, χ² tail probabilities, a well-tested reference for FDR | statsmodels: heavier, and it fits row-level data, which the privacy design forbids in the core |
| **pandas** | Only inside the registry adapter, to read and count records | Polars: faster, but unnecessary at 10⁴–10⁵ rows |
| **pytest + pytest-cov** | Fixtures for synthetic ground truth, and a coverage gate | unittest: more boilerplate |
| **Ruff** | One fast tool for linting and formatting | flake8 + black + isort |
| **GitHub Actions** | Built into the hosting platform, free for public repos, matrix builds | Jenkins (needs a server); GitLab CI (the code lives on GitHub) |
| **TOML config + JSON manifest** | Human-editable input, machine-checkable record | YAML (an extra dependency and ambiguous typing) |

## CI/CD

* **`ci.yml`** runs on every push and pull request. It lints and checks
  formatting, then runs the tests on Python 3.11/3.12/3.13 (Ubuntu) and 3.12
  (Windows) with a coverage gate of 80 %. It then runs a **reproducibility
  job** (`hode run` followed by `hode verify`, with results uploaded as an
  artifact) and builds the wheel and sdist.
* **`release.yml`** runs when a `v*` tag is pushed. It re-runs the tests,
  checks that the tag matches `hode.__version__`, builds the package, records
  a reproducibility manifest, and publishes a GitHub Release with everything
  attached.
* **Dependabot** checks the actions and dependencies monthly.

## Roadmap

These parts of the Assignment 2 architecture are not built yet. They are
tracked as [issues](https://github.com/iqmiss/assignment3/issues):

* content-addressed cache of count tables, so reruns are incremental (FR-07)
* an executor port, so sweeps can run on a secure server in cycle 3
* a planner–validator loop for re-budgeting a rejected combination
* importing candidate combinations from the model-based track for confirmatory testing
* a permutation null as a plug-in test statistic (FR-09)

## Data policy

This repository contains **no data**. That covers real, de-identified and
future datasets alike. It also contains no code from the model-based
(machine-learning) track of the dissertation. `.gitignore` blocks data files,
notebooks and model files. Everything in the tests and CI is synthetic.

## Citing

See [`CITATION.cff`](CITATION.cff). The method extends [1].

[1] *Development and application of a hybrid approach to identify key
determinants of repeat offenses in Kazakhstani administrative data.*
Procedia Computer Science, 2026.

## License

[MIT](LICENSE) © 2026 Aibek Aikumis
