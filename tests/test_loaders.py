"""Tests for per-dataset monthly regional-mean loaders."""
import pytest
import xarray as xr

from firex.loaders.ceres_ebaf import load_ceres_ebaf
from firex.loaders.modis_monthly import load_modis_monthly
from firex.loaders.aeronet import load_aeronet
from firex.loaders.merra2_monthly import load_merra2_monthly
from firex.loaders.qfed_monthly import load_qfed_monthly
from firex.loaders.viirs_monthly import load_viirs_monthly
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


def test_viirs_snpp_returns_dataset(fixtures_dir):
    ds = load_viirs_monthly(
        [fixtures_dir / "viirs_snpp_synth.nc"], platform="snpp", mask=_pnw_mask()
    )
    assert "viirs_snpp_aod" in ds.data_vars


def test_viirs_noaa20_returns_dataset(fixtures_dir):
    ds = load_viirs_monthly(
        [fixtures_dir / "viirs_noaa20_synth.nc"], platform="noaa20", mask=_pnw_mask()
    )
    assert "viirs_noaa20_aod" in ds.data_vars


def test_merra2_aer_loads_species(fixtures_dir):
    ds = load_merra2_monthly(
        [fixtures_dir / "merra2_aer_synth.nc"], collection="aer", mask=_pnw_mask()
    )
    assert "merra2_aer_TOTEXTTAU" in ds.data_vars
    assert "merra2_aer_BCEXTTAU" in ds.data_vars
    assert "merra2_aer_OCEXTTAU" in ds.data_vars


def test_merra2_slv_loads_covariates(fixtures_dir):
    ds = load_merra2_monthly(
        [fixtures_dir / "merra2_slv_synth.nc"], collection="slv", mask=_pnw_mask()
    )
    assert "merra2_slv_T2M" in ds.data_vars
    assert "merra2_slv_TQV" in ds.data_vars


def test_merra2_unknown_collection_raises(fixtures_dir):
    with pytest.raises(ValueError, match="Unknown collection"):
        load_merra2_monthly(
            [fixtures_dir / "merra2_aer_synth.nc"], collection="bogus", mask=_pnw_mask()
        )


def test_qfed_loads_monthly_species(fixtures_dir):
    ds = load_qfed_monthly(
        fixtures_dir / "qfed_synth", species=["bc", "oc", "co"], mask=_pnw_mask()
    )
    assert "qfed_bc" in ds.data_vars
    assert "qfed_oc" in ds.data_vars
    assert "qfed_co" in ds.data_vars
    assert ds.dims["time"] == 1  # July 2020 only in fixture


def test_qfed_skips_2016(tmp_path, fixtures_dir):
    """Y2016 is on the deny-list per CLAUDE.md."""
    base = tmp_path / "qfed"
    src_dir = fixtures_dir / "qfed_synth" / "Y2020" / "M07"
    dst_dir = base / "Y2016" / "M07"
    dst_dir.mkdir(parents=True)
    for f in src_dir.iterdir():
        new_name = f.name.replace("20200", "20160")
        (dst_dir / new_name).write_bytes(f.read_bytes())
    ds = load_qfed_monthly(base, species=["bc"], mask=_pnw_mask())
    assert ds.dims["time"] == 0


def test_aeronet_filters_to_pnw_sites(fixtures_dir):
    ds = load_aeronet(
        fixtures_dir / "aeronet_synth.nc", region=REGIONS["pacific-northwest"]
    )
    sites = list(ds["site"].values)
    assert "Trinidad_Head" in sites
    # Bondville (40.05, -88.4) is outside the PNW bbox; should be filtered out.
    assert "Bondville" not in sites
