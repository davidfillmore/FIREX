"""End-to-end smoke test against real ~/Data/... files. Runs all 6 stages
on a 24-month subset and asserts each output NetCDF exists with non-empty time.

Run explicitly:
    pytest tests/test_pipeline_smoke.py -m slow -v
"""
from pathlib import Path

import pytest
import xarray as xr
import yaml


@pytest.mark.slow
def test_pipeline_runs_end_to_end(tmp_path):
    # Copy the real config into a tmp path with a short date window.
    src_cfg = Path("configs/pacific-northwest.yaml")
    cfg = yaml.safe_load(src_cfg.read_text())
    cfg["time"]["start"] = "2020-01"
    cfg["time"]["end"] = "2021-12"
    cfg["output_dir"] = str(tmp_path)
    test_cfg = tmp_path / "config.yaml"
    test_cfg.write_text(yaml.safe_dump(cfg))

    from firex.run_pnw import main

    rc = main(["--config", str(test_cfg), "--force"])
    assert rc == 0

    data_dir = tmp_path / "data"
    # Required outputs (always produced).
    required = [
        "mask.nc", "ceres_ebaf.nc", "modis_terra.nc", "modis_aqua.nc",
        "viirs_snpp.nc", "viirs_noaa20.nc", "merra2_aer.nc", "qfed.nc",
        "aeronet_pnw.nc", "smoke_attribution.nc", "merged.nc",
        "regression_table.csv",
    ]
    # Optional: present only when the corresponding source is staged. Currently
    # MERRA-2 slv is not staged on this machine; orchestrator skips it cleanly.
    optional = ["merra2_slv.nc"]
    for name in required:
        path = data_dir / name
        assert path.exists(), f"missing required output: {path}"
        if path.suffix == ".nc":
            ds = xr.open_dataset(path)
            assert ds.sizes.get("time", 1) > 0, f"empty time axis in {path}"
    for name in optional:
        path = data_dir / name
        if path.exists() and path.suffix == ".nc":
            ds = xr.open_dataset(path)
            assert ds.sizes.get("time", 1) > 0, f"empty time axis in {path}"

    plots_dir = tmp_path / "plots"
    assert any(plots_dir.glob("*.png")), "no plots written"
