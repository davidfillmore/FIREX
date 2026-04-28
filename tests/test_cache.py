"""Tests for atomic-write and freshness helpers."""
import time
from pathlib import Path

import xarray as xr

from firex.cache import atomic_to_netcdf, output_is_fresh


def test_atomic_to_netcdf_writes_file(tmp_path):
    ds = xr.Dataset({"x": ("t", [1.0, 2.0, 3.0])}, coords={"t": [0, 1, 2]})
    out = tmp_path / "out.nc"
    atomic_to_netcdf(ds, out)
    assert out.exists()
    reloaded = xr.open_dataset(out).load()
    assert (reloaded["x"].values == [1.0, 2.0, 3.0]).all()


def test_atomic_to_netcdf_no_tmp_left(tmp_path):
    ds = xr.Dataset({"x": ("t", [1.0])}, coords={"t": [0]})
    out = tmp_path / "out.nc"
    atomic_to_netcdf(ds, out)
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_output_is_fresh_when_newer(tmp_path):
    inp = tmp_path / "in.nc"
    inp.write_text("dummy")
    time.sleep(0.05)
    out = tmp_path / "out.nc"
    out.write_text("dummy")
    assert output_is_fresh(out, [inp]) is True


def test_output_is_stale_when_older(tmp_path):
    out = tmp_path / "out.nc"
    out.write_text("dummy")
    time.sleep(0.05)
    inp = tmp_path / "in.nc"
    inp.write_text("dummy")
    assert output_is_fresh(out, [inp]) is False


def test_output_is_fresh_missing_output_returns_false(tmp_path):
    out = tmp_path / "out.nc"
    inp = tmp_path / "in.nc"
    inp.write_text("dummy")
    assert output_is_fresh(out, [inp]) is False
