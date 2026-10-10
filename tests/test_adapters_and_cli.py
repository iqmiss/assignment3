import json

import pandas as pd
import pytest

from hode.adapters import DataFrameSource
from hode.cli import main
from hode.ports import CountSource
from hode.synthetic import SyntheticSource, SyntheticSpec, generate


def test_adapters_implement_the_port(small_source):
    assert isinstance(small_source, CountSource)
    assert isinstance(SyntheticSource(SyntheticSpec(n=500)), CountSource)


def test_fingerprint_ignores_row_and_column_order(small_frame):
    shuffled = small_frame.sample(frac=1, random_state=5)[["y", "c", "a", "b"]]
    assert (
        DataFrameSource(small_frame, "y").fingerprint()
        == DataFrameSource(shuffled, "y").fingerprint()
    )


def test_fingerprint_detects_a_changed_record(small_frame):
    changed = small_frame.copy()
    changed.loc[0, "y"] = 1 - changed.loc[0, "y"]
    assert (
        DataFrameSource(small_frame, "y").fingerprint()
        != DataFrameSource(changed, "y").fingerprint()
    )


def test_missing_values_become_their_own_level(small_frame):
    frame = small_frame.copy()
    frame.loc[:9, "a"] = None
    assert "NA" in DataFrameSource(frame, "y").table(["a"]).levels[0]


def test_bad_inputs_are_rejected(small_frame):
    with pytest.raises(KeyError):
        DataFrameSource(small_frame, "missing")
    with pytest.raises(KeyError):
        DataFrameSource(small_frame, "y", ["a", "nope"])
    with pytest.raises(ValueError):
        DataFrameSource(small_frame.assign(y=2), "y")


def test_synthetic_registry_matches_d1_shape():
    frame = generate()
    assert len(frame) == 21_331
    assert abs(frame["recidivist"].mean() - 0.0637) < 0.005
    assert generate().equals(frame)


def _write_config(tmp_path, data_block):
    cfg = tmp_path / "run.toml"
    cfg.write_text(
        f"{data_block}\n"
        "[search]\norders = [2]\nresamples = 5\n"
        'proxies = ["conviction_group"]\n'
        '[output]\ndir = "out"\n',
        encoding="utf-8",
    )
    return cfg


def test_cli_end_to_end_with_csv_and_verify(tmp_path, capsys):
    data = tmp_path / "registry.csv"
    assert main(["synth", "--n", "3000", "--seed", "11", "--out", str(data)]) == 0
    cfg = _write_config(
        tmp_path, '[data]\nsource = "csv"\npath = "registry.csv"\noutcome = "recidivist"'
    )
    assert main(["run", str(cfg)]) == 0

    manifest_path = tmp_path / "out" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["config"]["data"]["path"] == "registry.csv"
    results = pd.read_csv(tmp_path / "out" / "results.csv")
    # 45 pairs of the 10 fields, 36 pairs once the proxy field is dropped
    assert results.groupby("variant")["variables"].nunique().to_dict() == {
        "all": 45,
        "no-proxy": 36,
    }

    assert main(["verify", str(manifest_path), "--data", str(data)]) == 0
    assert "OK" in capsys.readouterr().out

    frame = pd.read_csv(data)
    frame.loc[0, "recidivist"] = 1 - frame.loc[0, "recidivist"]
    frame.to_csv(data, index=False)
    assert main(["verify", str(manifest_path), "--data", str(data)]) == 1
    assert "fingerprint differs" in capsys.readouterr().err


def test_verify_csv_manifest_requires_the_data_path(tmp_path):
    data = tmp_path / "registry.csv"
    main(["synth", "--n", "2000", "--out", str(data)])
    cfg = _write_config(
        tmp_path, '[data]\nsource = "csv"\npath = "registry.csv"\noutcome = "recidivist"'
    )
    main(["run", str(cfg)])
    with pytest.raises(ValueError):
        main(["verify", str(tmp_path / "out" / "manifest.json")])


def test_cli_synthetic_run_and_tampered_results_hash(tmp_path, capsys):
    cfg = _write_config(tmp_path, '[data]\nsource = "synthetic"\nn = 4000\nseed = 3')
    assert main(["run", str(cfg)]) == 0
    manifest_path = tmp_path / "out" / "manifest.json"
    assert main(["verify", str(manifest_path)]) == 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["results_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert main(["verify", str(manifest_path)]) == 1
    assert "results hash differs" in capsys.readouterr().err


def test_unknown_source_is_rejected(tmp_path):
    cfg = _write_config(tmp_path, '[data]\nsource = "database"')
    with pytest.raises(ValueError):
        main(["run", str(cfg)])
