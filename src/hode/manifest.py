"""Run configuration, run manifest and the reproducibility check.

A manifest records everything needed to repeat a run: the configuration, the
data fingerprint, the code version and a hash of the results. ``verify``
reruns from the manifest and fails if any hash differs.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from hode import __version__
from hode.adapters import DataFrameSource
from hode.ports import CountSource
from hode.search import SearchConfig, config_dict, run_search
from hode.synthetic import SyntheticSource, SyntheticSpec

FLOAT_FORMAT = "%.10g"


@dataclass(frozen=True)
class RunConfig:
    data: dict
    search: SearchConfig
    out_dir: Path

    @classmethod
    def load(cls, path: str | Path) -> RunConfig:
        path = Path(path)
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
        return cls.from_dict(raw, base=path.parent)

    @classmethod
    def from_dict(cls, raw: dict, base: Path = Path(".")) -> RunConfig:
        data = dict(raw.get("data", {"source": "synthetic"}))
        if data.get("source") == "csv":
            data["path"] = str((base / data["path"]).resolve())
        s = dict(raw.get("search", {}))
        s.update({f"{key}": val for key, val in raw.get("stability", {}).items()})
        s = _tuples(s)
        out = raw.get("output", {}).get("dir", "results")
        return cls(data, SearchConfig(**s), (base / out).resolve())

    def to_dict(self) -> dict:
        data = dict(self.data)
        if "path" in data:
            data["path"] = Path(data["path"]).name
        return {"data": data, "search": config_dict(self.search)}

    def source(self) -> CountSource:
        kind = self.data.get("source", "synthetic")
        if kind == "synthetic":
            keys = ("n", "base_rate", "seed")
            spec = {k: self.data[k] for k in keys if k in self.data}
            return SyntheticSource(SyntheticSpec(**spec))
        if kind == "csv":
            return DataFrameSource.from_csv(
                self.data["path"], self.data["outcome"], self.data.get("variables")
            )
        raise ValueError(f"unknown data source {kind!r}")


def _tuples(search: dict) -> dict:
    """TOML and JSON give lists; the frozen config wants tuples."""
    for key in ("orders", "variables", "proxies"):
        if search.get(key) is not None:
            search[key] = tuple(search[key])
    return search


def results_csv(frame: pd.DataFrame) -> str:
    return frame.to_csv(index=False, float_format=FLOAT_FORMAT, lineterminator="\n")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def run(config: RunConfig) -> tuple[pd.DataFrame, dict]:
    """Run a search, write results.csv and manifest.json, return both."""
    source = config.source()
    frame = run_search(source, config.search)
    csv = results_csv(frame)
    cfg = config.to_dict()
    manifest = {
        "hode_version": __version__,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {"numpy": np.__version__, "scipy": scipy.__version__, "pandas": pd.__version__},
        "config": cfg,
        "config_sha256": sha256(json.dumps(cfg, sort_keys=True)),
        "data_fingerprint": source.fingerprint(),
        "results_sha256": sha256(csv),
        "n_tests": int((frame["status"] == "tested").sum()),
        "n_significant": int(frame["significant"].sum()),
    }
    config.out_dir.mkdir(parents=True, exist_ok=True)
    (config.out_dir / "results.csv").write_text(csv, encoding="utf-8", newline="\n")
    (config.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return frame, manifest


def verify(manifest_path: str | Path, data_path: str | Path | None = None) -> list[str]:
    """Rerun the analysis recorded in a manifest; return a list of mismatches (empty = OK)."""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cfg = manifest["config"]
    data = dict(cfg["data"])
    if data.get("source") == "csv":
        if data_path is None:
            raise ValueError("this manifest was produced from a CSV; pass its path with --data")
        data["path"] = str(Path(data_path).resolve())
    search = _tuples(dict(cfg["search"]))
    config = RunConfig(data, SearchConfig(**search), manifest_path.parent)
    source = config.source()
    problems = []
    if source.fingerprint() != manifest["data_fingerprint"]:
        problems.append("data fingerprint differs: the data snapshot is not the same")
    csv = results_csv(run_search(source, config.search))
    if sha256(csv) != manifest["results_sha256"]:
        problems.append("results hash differs: the same inputs gave different results")
    return problems
