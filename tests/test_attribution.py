"""Tests for smoke-AOD attribution."""
import numpy as np
import pandas as pd
import xarray as xr

from firex.attribution import compute_smoke_attribution


def _make_merra2(bc, oc, total, *, has_oc_bb=False, oc_bb=None) -> xr.Dataset:
    times = pd.date_range("2020-01", periods=12, freq="MS")
    n = len(times)
    data = {
        "merra2_aer_BCEXTTAU": ("time", np.full(n, bc)),
        "merra2_aer_OCEXTTAU": ("time", np.full(n, oc)),
        "merra2_aer_TOTEXTTAU": ("time", np.full(n, total)),
    }
    if has_oc_bb:
        data["merra2_aer_OCEXTTAU_bb"] = ("time", np.full(n, oc_bb))
    return xr.Dataset(data, coords={"time": times})


def _make_obs(name: str, value: float) -> xr.Dataset:
    times = pd.date_range("2020-01", periods=12, freq="MS")
    return xr.Dataset({name: ("time", np.full(len(times), value))}, coords={"time": times})


def _make_qfed(oc_value: float) -> xr.Dataset:
    times = pd.date_range("2020-01", periods=12, freq="MS")
    return xr.Dataset({"qfed_oc": ("time", np.full(len(times), oc_value))}, coords={"time": times})


def test_known_split_present_path():
    """When OCEXTTAU_bb is present, OC_bb_share = OC_bb / OC."""
    merra2 = _make_merra2(bc=0.02, oc=0.06, total=0.20, has_oc_bb=True, oc_bb=0.04)
    obs = _make_obs("modis_terra_aod", 0.30)
    qfed = _make_qfed(1e-9)
    out = compute_smoke_attribution(
        merra2=merra2, obs={"modis_terra_aod": obs["modis_terra_aod"]}, qfed=qfed,
    )
    # smoke_fraction = (BC + OC_bb) / TOTAL = (0.02 + 0.04) / 0.20 = 0.30
    np.testing.assert_allclose(out["smoke_fraction"].values, 0.30, atol=1e-6)
    np.testing.assert_allclose(out["smoke_aod_terra"].values, 0.09, atol=1e-6)
    assert out.attrs["oc_split_method"] == "explicit"


def test_fallback_path_triggers():
    """No OCEXTTAU_bb → fallback uses QFED ratio + DJF baseline."""
    merra2 = _make_merra2(bc=0.02, oc=0.06, total=0.20, has_oc_bb=False)
    obs = _make_obs("modis_terra_aod", 0.30)
    qfed = _make_qfed(1e-9)
    out = compute_smoke_attribution(
        merra2=merra2, obs={"modis_terra_aod": obs["modis_terra_aod"]}, qfed=qfed,
    )
    assert out.attrs["oc_split_method"] == "fallback"
    # smoke_fraction must be in [0, 1]
    assert (out["smoke_fraction"].values >= 0).all()
    assert (out["smoke_fraction"].values <= 1).all()


def test_multiple_obs_sources():
    merra2 = _make_merra2(bc=0.02, oc=0.06, total=0.20, has_oc_bb=True, oc_bb=0.04)
    qfed = _make_qfed(1e-9)
    out = compute_smoke_attribution(
        merra2=merra2,
        obs={
            "modis_terra_aod": _make_obs("modis_terra_aod", 0.30)["modis_terra_aod"],
            "modis_aqua_aod": _make_obs("modis_aqua_aod", 0.32)["modis_aqua_aod"],
            "viirs_snpp_aod": _make_obs("viirs_snpp_aod", 0.28)["viirs_snpp_aod"],
            "viirs_noaa20_aod": _make_obs("viirs_noaa20_aod", 0.29)["viirs_noaa20_aod"],
        },
        qfed=qfed,
    )
    for name in ("smoke_aod_terra", "smoke_aod_aqua", "smoke_aod_snpp", "smoke_aod_noaa20"):
        assert name in out
