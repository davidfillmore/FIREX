"""Tests for per-dataset monthly regional-mean loaders."""
import pytest
import xarray as xr

from firex.loaders.ceres_ebaf import load_ceres_ebaf
from firex.loaders.modis_monthly import load_modis_monthly
from firex.masks import build_mask
from firex.regions import REGIONS


def _pnw_mask():
    return build_mask(REGIONS["pacific-northwest"], resolution_deg=1.0)


def test_ceres_ebaf_returns_dataset_with_expected_vars(fixtures_dir):
    ds = load_ceres_ebaf(fixtures_dir / "ceres_ebaf_synth.nc", mask=_pnw_mask())
    assert isinstance(ds, xr.Dataset)
    assert ds.dims == {"time": 24}
    expected_vars = {
        "ceres_toa_sw_all", "ceres_toa_sw_clr",
        "ceres_toa_lw_all", "ceres_toa_lw_clr",
        "ceres_toa_net_all", "ceres_toa_net_clr",
        "ceres_sfc_sw_down_all", "ceres_sfc_sw_down_clr",
        "ceres_sfc_lw_down_all", "ceres_sfc_lw_down_clr",
        "ceres_sfc_net_all", "ceres_sfc_net_clr",
        "ceres_cloud_fraction",
    }
    assert expected_vars.issubset(set(ds.data_vars))


def test_ceres_ebaf_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_ceres_ebaf(tmp_path / "nope.nc", mask=_pnw_mask())


def test_ceres_ebaf_missing_variable_raises(fixtures_dir, tmp_path):
    """If a required variable is absent, fail loudly."""
    src = xr.open_dataset(fixtures_dir / "ceres_ebaf_synth.nc")
    src = src.drop_vars(["toa_sw_all_mon"])
    bad = tmp_path / "bad.nc"
    src.to_netcdf(bad)
    with pytest.raises(KeyError, match="toa_sw_all_mon"):
        load_ceres_ebaf(bad, mask=_pnw_mask())


def test_modis_terra_returns_dataset(fixtures_dir):
    ds = load_modis_monthly(
        [fixtures_dir / "modis_terra_synth.nc"], platform="terra", mask=_pnw_mask()
    )
    assert isinstance(ds, xr.Dataset)
    assert "modis_terra_aod" in ds.data_vars
    assert ds.dims == {"time": 24}


def test_modis_aqua_returns_dataset(fixtures_dir):
    ds = load_modis_monthly(
        [fixtures_dir / "modis_aqua_synth.nc"], platform="aqua", mask=_pnw_mask()
    )
    assert "modis_aqua_aod" in ds.data_vars


def test_modis_invalid_platform_raises(fixtures_dir):
    with pytest.raises(ValueError, match="platform must be"):
        load_modis_monthly(
            [fixtures_dir / "modis_terra_synth.nc"], platform="other", mask=_pnw_mask()
        )
