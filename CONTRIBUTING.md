# Contributing

## Workflow

1. Open or pick an issue, and branch from `main`: `feat/<short-name>`,
   `fix/<short-name>` or `docs/<short-name>`.
2. Commit in small steps with [Conventional Commits](https://www.conventionalcommits.org/)
   messages (`feat:`, `fix:`, `test:`, `docs:`, `ci:`, `refactor:`, `chore:`).
3. Open a pull request. CI must be green: lint, tests on every matrix entry,
   the reproducibility check and the build.
4. Merge with a merge commit, so the history shows which branch delivered
   what. Delete the branch afterwards.

## Local checks

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest --cov
hode run configs/synthetic.toml && hode verify results/manifest.json
```

## Rules that protect the science

* **Never commit data.** Reproduce problems on synthetic data (`hode synth`).
* If a change alters results on the synthetic registry, say so in the pull
  request and in `CHANGELOG.md`. The results hash in the manifest will change.
* The analysis core may depend only on `CountSource` and `CountTable`. It must
  never read records directly.
* A new test statistic needs a test against an independent reference, as
  `test_one_way_test_equals_the_g_test` does for the LRT.

## Releasing

Bump `__version__` in `src/hode/__init__.py`, update `CHANGELOG.md`, then
tag the commit: `git tag -a v0.2.0 -m "v0.2.0" && git push --tags`. The release
workflow does the rest.
