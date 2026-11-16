import numpy as np
import pandas as pd
import pytest

from hode.cli import main
from hode.plot import rate_grid
from hode.table import CountTable


def _two_way():
    # 2 x 3 table; cell (1, 2) is unobserved and cell (0, 1) has only 4 people
    return CountTable(
        variables=("age", "job"),
        levels=(("young", "old"), ("none", "part", "full")),
        cells=np.array([[0, 0], [0, 1], [0, 2], [1, 0], [1, 1]]),
        pos=np.array([6, 2, 1, 3, 0]),
        n=np.array([20, 4, 25, 30, 10]),
    )


def test_rate_grid_places_every_cell_and_hides_small_ones():
    rate, n = rate_grid(_two_way(), min_cell=10)
    assert n.tolist() == [[20, 4, 25], [30, 10, 0]]
    assert rate[0, 0] == pytest.approx(0.30)
    assert rate[0, 2] == pytest.approx(0.04)
    assert rate[1, 0] == pytest.approx(0.10)
    assert rate[1, 1] == 0.0
    assert np.isnan(rate[0, 1])  # below the minimum-cell rule
    assert np.isnan(rate[1, 2])  # never observed


def test_rate_grid_needs_a_two_way_table(small_source):
    with pytest.raises(ValueError):
        rate_grid(small_source.table(["a"]), min_cell=10)


def test_cli_plot_draws_one_heatmap_per_significant_pair(tmp_path, capsys):
    pytest.importorskip("matplotlib")
    cfg = tmp_path / "run.toml"
    cfg.write_text(
        '[data]\nsource = "synthetic"\n'
        '[search]\norders = [2]\nresamples = 5\nproxies = ["registry_group"]\n'
        '[output]\ndir = "out"\n',
        encoding="utf-8",
    )
    assert main(["run", str(cfg)]) == 0
    manifest = tmp_path / "out" / "manifest.json"
    results = pd.read_csv(tmp_path / "out" / "results.csv")
    expected = results[(results["significant"] == True) & (results["variant"] == "all")]  # noqa: E712
    assert len(expected) > 0

    assert main(["plot", str(manifest)]) == 0
    files = sorted((tmp_path / "out" / "plots").glob("*.png"))
    assert len(files) == len(expected)
    assert "age_group__occupation_group.png" in {f.name for f in files}
    for f in files:
        assert f.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert f"{len(expected)} heatmaps written" in capsys.readouterr().out

    assert (
        main(["plot", str(manifest), "--variant", "no-proxy", "--out", str(tmp_path / "np")]) == 0
    )
    assert len(list((tmp_path / "np").glob("*.png"))) > 0


def test_cli_plot_without_matplotlib_explains_how_to_install(tmp_path, monkeypatch, capsys):
    import builtins

    real_import = builtins.__import__

    def no_matplotlib(name, *args, **kwargs):
        if name.startswith("matplotlib"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    cfg = tmp_path / "run.toml"
    cfg.write_text(
        '[data]\nsource = "synthetic"\nn = 3000\n[search]\norders = [2]\nresamples = 2\n'
        '[output]\ndir = "out"\n',
        encoding="utf-8",
    )
    main(["run", str(cfg)])
    monkeypatch.setattr(builtins, "__import__", no_matplotlib)
    assert main(["plot", str(tmp_path / "out" / "manifest.json")]) == 2
    assert "hode[plot]" in capsys.readouterr().err
